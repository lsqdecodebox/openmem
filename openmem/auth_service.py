"""认证服务：grant 端点逻辑。

设计要点：
- ``GrantRequest`` 用 Pydantic v2，``extra="allow"`` 透传联调期多余字段，不报错不丢失。
- ``validate_applicant`` 为 no-op 钩子：当前不校验 applicantCode（内部系统可信），
  联调期改凭证规则只动这一个函数，端点主体不变。
- ``grant_user_key`` 幂等：同 applicantCode 二次调用返回同一个 key，不签新 key。
- 永远签发 ``user`` 角色，永不签发 admin。
"""

import logging
import secrets
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from openmem.auth import Role, UserStore

logger = logging.getLogger(__name__)


class GrantRequest(BaseModel):
    """/auth/grant 请求体。

    extra="allow"：联调期请求体可追加任意字段（如 timestamp/signature/source），
    Pydantic 会将其存入 ``__pydantic_extra__``，不报错、不丢失，供
    ``validate_applicant`` 或日志使用。
    """

    model_config = ConfigDict(extra="allow")

    applicantCode: str = Field(..., description="发证凭证，由内部系统发送，当前不校验合法性")
    username: str | None = Field(default=None, description="可选，users.json 标识")
    note: str | None = Field(default=None, description="可选备注")


def validate_applicant(req: GrantRequest) -> str | None:
    """校验发证凭证。

    当前为 no-op（内部系统可信，不校验 applicantCode）。
    联调期若需引入凭证规则（如签名校验、白名单、时间戳防重放），
    只修改本函数：

    - 返回 None：校验通过
    - 返回 str：校验失败，str 作为错误信息返回给调用方
    """
    _ = req  # 当前不读取任何字段，预留联调扩展
    return None


def _generate_user_key() -> str:
    """生成 om_ 前缀 + 32 hex 的 user 级 key，不含角色信息。"""
    return f"om_{secrets.token_hex(16)}"


def grant_user_key(user_store: UserStore, req: GrantRequest) -> tuple[dict, bool]:
    """签发（或幂等返回）一个 user 级 API Key。

    Args:
        user_store: users.json 存取层
        req: 已通过 Pydantic 解析的请求体

    Returns:
        (user_dict, is_new)
        - user_dict: 写入/命中的用户记录
        - is_new: True=本次新签发；False=幂等命中已存在

    Raises:
        ValueError: applicantCode 为空
    """
    if not req.applicantCode:
        raise ValueError("applicantCode 不能为空")

    # 幂等查找：同 applicantCode 已发过证 → 返回同一个 key
    existing = user_store.find_by_applicant(req.applicantCode)
    if existing is not None:
        logger.info(f"幂等命中 applicantCode={req.applicantCode}，返回已存在 key")
        return existing, False

    # 首次签发
    api_key = _generate_user_key()
    now = datetime.now().isoformat(timespec="seconds")
    user = {
        "api_key": api_key,
        "username": req.username or f"applicant-{req.applicantCode}",
        "role": Role.USER,  # 永远 user，永不 admin
        "status": "active",
        "created_at": now,
        "applicantCode": req.applicantCode,
    }
    if req.note:
        user["note"] = req.note

    user_store.add_user(user)
    logger.info(f"新签发 user key: applicantCode={req.applicantCode}, username={user['username']}")
    return user, True


def format_grant_response(user: dict, is_new: bool) -> dict:
    """格式化 /auth/grant 200 响应体。"""
    return {
        "api_key": user["api_key"],
        "role": user.get("role", Role.USER),
        "username": user.get("username"),
        "status": user.get("status", "active"),
        "applicantCode": user.get("applicantCode"),
        "created_at": user.get("created_at"),
        "is_new": is_new,
    }
