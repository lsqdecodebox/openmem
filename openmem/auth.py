"""API Key 认证与权限校验。

设计要点：
- ``ApiKeyAuth`` 继承 FastMCP ``TokenVerifier``，仅在 HTTP 传输层生效（stdio 免疫）。
- ``UserStore`` 通过 mtime 缓存实现 users.json 热更新，无需重启。
- ``require_admin_role`` 作为 FastMCP ``AuthCheck``，通过 ``@mcp.tool(auth=...)``
  同时作用于 listing（隐藏工具）与 call（拒绝调用）两个阶段；stdio 由 FastMCP
  ``_get_auth_context`` 的 ``skip_auth=True`` 自动跳过。
"""

import json
import logging
import os
from pathlib import Path

from fastmcp.server.auth import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class Role:
    ADMIN = "admin"
    USER = "user"


PERMISSIONS: dict[str, set[str]] = {
    "get_directory": {Role.ADMIN, Role.USER},
    "read_memory": {Role.ADMIN, Role.USER},
    "read_asset": {Role.ADMIN, Role.USER},
    "write_memory": {Role.ADMIN},
    "write_asset": {Role.ADMIN},
}

ADMIN_TOOL_NAMES = {
    name for name, roles in PERMISSIONS.items() if Role.ADMIN in roles and Role.USER not in roles
}


class UserStore:
    """users.json 读写，mtime 变化才重读，支持热更新。"""

    def __init__(self, users_file: Path):
        self.users_file = users_file
        self._cached_mtime: float | None = None
        self._cached_users: dict[str, dict] = {}

    def _load(self) -> dict[str, dict]:
        """返回 {api_key: user_dict}，mtime 未变则返回缓存。"""
        if not self.users_file.exists():
            self._cached_mtime = None
            self._cached_users = {}
            return self._cached_users

        try:
            mtime = self.users_file.stat().st_mtime
        except OSError:
            return self._cached_users

        if mtime == self._cached_mtime:
            return self._cached_users

        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"读取 users.json 失败: {e}，使用上次缓存")
            return self._cached_users

        users_list = data.get("users", []) if isinstance(data, dict) else []
        self._cached_users = {
            u["api_key"]: u for u in users_list if isinstance(u, dict) and "api_key" in u
        }
        self._cached_mtime = mtime
        logger.debug(f"users.json 已重载，共 {len(self._cached_users)} 个用户")
        return self._cached_users

    def find_by_key(self, api_key: str) -> dict | None:
        """按 api_key 查找用户，未找到或 status 非 active 返回 None。"""
        if not api_key:
            return None
        users = self._load()
        user = users.get(api_key)
        if not user:
            return None
        if user.get("status", "active") != "active":
            return None
        return user

    def find_by_applicant(self, applicant_code: str) -> dict | None:
        """按 applicantCode 查找用户（幂等发证用），未找到返回 None。

        与 find_by_key 不同：不校验 status，因为幂等命中应返回已签发的 key，
        即使该用户后续被禁用，调用方也应知道"该 applicantCode 已发过证"。
        """
        if not applicant_code:
            return None
        users = self._load()
        for user in users.values():
            if user.get("applicantCode") == applicant_code:
                return user
        return None

    def add_user(self, user: dict) -> dict:
        """追加一个用户到 users.json 并失效 mtime 缓存。

        - 不做唯一性校验（调用方负责保证 api_key / applicantCode 唯一）
        - 原子写入失败时抛 OSError，缓存保持旧值
        - 写入后立即失效 _cached_mtime，下次查询强制重读
        """
        if not isinstance(user, dict) or "api_key" not in user:
            raise ValueError("add_user 需要 dict 且至少包含 api_key 字段")

        # 读取当前完整 users 列表（不依赖缓存，确保追加不丢数据）
        current_list: list[dict] = []
        if self.users_file.exists():
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    current_list = data.get("users", []) or []
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"add_user 读取 users.json 失败: {e}")
                # 不追加到不可靠的旧数据上，但仍尝试写入单条记录

        current_list.append(user)
        payload = {"users": current_list}

        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # 失效缓存，下次查询强制重读
        self._cached_mtime = None
        logger.info(f"已追加用户到 users.json: username={user.get('username')}, "
                    f"role={user.get('role')}, applicantCode={user.get('applicantCode')}")
        return user


class ApiKeyAuth(TokenVerifier):
    """FastMCP TokenVerifier：Bearer Key → users.json 查询 → AccessToken。

    仅在 streamable-http 传输层生效；verify_token 返回 None 时由
    RequireAuthMiddleware 直接返回 401，请求不会进入工具层。
    """

    def __init__(self, user_store: UserStore):
        super().__init__()
        self.user_store = user_store

    async def verify_token(self, token: str) -> AccessToken | None:
        user = self.user_store.find_by_key(token)
        if not user:
            logger.debug(f"API Key 认证失败: {token[:12]}...")
            return None

        role = user.get("role", Role.USER)
        username = user.get("username", "unknown")

        logger.debug(f"API Key 认证通过: username={username}, role={role}")
        return AccessToken(
            token=token,
            client_id=username,
            scopes=[],
            claims={"role": role, "username": username},
        )


def get_current_role() -> str:
    """获取当前请求角色。

    - stdio 模式：无 HTTP 上下文，get_access_token() 返回 None → 默认 admin（信任本机）
    - remote 模式：从 AccessToken.claims["role"] 读取；claims 缺失时降级为 user
    """
    try:
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
    except Exception:
        token = None

    if token is None:
        return Role.ADMIN

    role = token.claims.get("role") if token.claims else None
    return role if role in (Role.ADMIN, Role.USER) else Role.USER


def require_admin_role(ctx) -> bool:
    """FastMCP AuthCheck：仅 admin 角色可访问。

    作为 ``@mcp.tool(auth=...)`` 的入参，由 FastMCP 在 **listing 和 call** 两个阶段
    自动调用：
    - listing 阶段（``list_tools``）：返回 False 时工具被静默跳过 → user 看不到
    - call 阶段（``_get_tool``）：返回 False 时返回 None → 协议层报"工具不存在"

    stdio 传输由 FastMCP ``_get_auth_context`` 的 ``skip_auth=True`` 自动跳过本检查，
    即 stdio 默认全权放行（信任本机）。

    Args:
        ctx: ``fastmcp.utilities.authorization.AuthContext``，``ctx.token`` 为
            ``AccessToken | None``，``claims["role"]`` 由 ``ApiKeyAuth.verify_token``
            注入。

    Returns:
        True=允许访问；False=拒绝。
    """
    token = getattr(ctx, "token", None)
    if token is None:
        return False
    claims = getattr(token, "claims", None) or {}
    return claims.get("role") == Role.ADMIN
