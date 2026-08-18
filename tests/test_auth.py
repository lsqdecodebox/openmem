import json
import os
import time
from pathlib import Path

import pytest

from openmem.auth import (
    ApiKeyAuth,
    UserStore,
    Role,
    PERMISSIONS,
    get_current_role,
    require_admin_role,
)
from openmem.initializer import ensure_users_file


# ---------- fixtures ----------

@pytest.fixture
def users_file(tmp_path: Path) -> Path:
    """创建含 admin + user 两个用户的 users.json"""
    f = tmp_path / "users.json"
    data = {
        "users": [
            {
                "api_key": "om_admin_test123",
                "username": "admin",
                "role": "admin",
                "status": "active",
                "created_at": "2026-08-05T10:00:00",
                "note": "test admin",
            },
            {
                "api_key": "om_user_test456",
                "username": "claude-desktop",
                "role": "user",
                "status": "active",
                "created_at": "2026-08-05T10:00:00",
                "note": "test user",
            },
            {
                "api_key": "om_disabled_test789",
                "username": "disabled-user",
                "role": "user",
                "status": "disabled",
                "created_at": "2026-08-05T10:00:00",
                "note": "disabled",
            },
        ]
    }
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


@pytest.fixture
def store(users_file: Path) -> UserStore:
    return UserStore(users_file)


@pytest.fixture
def auth(store: UserStore) -> ApiKeyAuth:
    return ApiKeyAuth(store)


# ---------- ApiKeyAuth.verify_token ----------

class TestApiKeyAuthVerifyToken:
    @pytest.mark.asyncio
    async def test_verify_token_valid_admin(self, auth: ApiKeyAuth):
        token = await auth.verify_token("om_admin_test123")
        assert token is not None
        assert token.client_id == "admin"
        assert token.claims["role"] == "admin"

    @pytest.mark.asyncio
    async def test_verify_token_valid_user(self, auth: ApiKeyAuth):
        token = await auth.verify_token("om_user_test456")
        assert token is not None
        assert token.client_id == "claude-desktop"
        assert token.claims["role"] == "user"

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth: ApiKeyAuth):
        token = await auth.verify_token("nonexistent_key")
        assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_disabled_user(self, auth: ApiKeyAuth):
        token = await auth.verify_token("om_disabled_test789")
        assert token is None


# ---------- UserStore ----------

class TestUserStore:
    def test_find_by_key_admin(self, store: UserStore):
        user = store.find_by_key("om_admin_test123")
        assert user is not None
        assert user["role"] == "admin"

    def test_find_by_key_not_found(self, store: UserStore):
        assert store.find_by_key("nope") is None

    def test_find_by_key_empty(self, store: UserStore):
        assert store.find_by_key("") is None

    def test_hot_reload(self, users_file: Path, store: UserStore):
        # 初始加载
        assert store.find_by_key("om_admin_test123") is not None
        assert store.find_by_key("om_new_key") is None

        # 修改 users.json（需确保 mtime 变化）
        data = json.loads(users_file.read_text(encoding="utf-8"))
        data["users"].append({
            "api_key": "om_new_key",
            "username": "new",
            "role": "user",
            "status": "active",
        })
        time.sleep(0.05)  # 确保 mtime 变化（某些文件系统精度低）
        users_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 不重建 store，直接查询 → 应感知到新用户
        assert store.find_by_key("om_new_key") is not None

    def test_missing_file(self, tmp_path: Path):
        store = UserStore(tmp_path / "nonexistent.json")
        assert store.find_by_key("any") is None


# ---------- get_current_role / require_admin_role ----------

from types import SimpleNamespace


def _make_auth_ctx(role: str | None):
    """构造模拟 AuthContext：含 token.claims['role']。role=None 表示无 token。"""
    if role is None:
        return SimpleNamespace(token=None)
    return SimpleNamespace(token=SimpleNamespace(claims={"role": role}))


class TestRoleChecks:
    def test_get_current_role_stdio(self):
        """无 HTTP 上下文时（stdio 模式），默认 admin"""
        role = get_current_role()
        assert role == Role.ADMIN

    def test_require_admin_role_allows_admin(self):
        """admin 角色 → 放行"""
        assert require_admin_role(_make_auth_ctx(Role.ADMIN)) is True

    def test_require_admin_role_blocks_user(self):
        """user 角色 → 拒绝"""
        assert require_admin_role(_make_auth_ctx(Role.USER)) is False

    def test_require_admin_role_blocks_no_token(self):
        """无 token（未认证）→ 拒绝"""
        assert require_admin_role(_make_auth_ctx(None)) is False

    def test_permissions_matrix(self):
        """验证权限矩阵完整性"""
        assert PERMISSIONS["write_memory"] == {Role.ADMIN}
        assert PERMISSIONS["write_asset"] == {Role.ADMIN}
        assert PERMISSIONS["read_memory"] == {Role.ADMIN, Role.USER}
        assert PERMISSIONS["get_directory"] == {Role.ADMIN, Role.USER}
        assert PERMISSIONS["read_asset"] == {Role.ADMIN, Role.USER}


# ---------- ensure_users_file (首次引导) ----------

class TestEnsureUsersFile:
    def test_creates_admin(self, tmp_path: Path, monkeypatch):
        """users.json 不存在 → 创建含 1 个 admin"""
        monkeypatch.delenv("OPENMEM_ADMIN_API_KEY", raising=False)
        users_file = tmp_path / "users.json"
        ensure_users_file(users_file)

        assert users_file.exists()
        data = json.loads(users_file.read_text(encoding="utf-8"))
        assert len(data["users"]) == 1
        assert data["users"][0]["role"] == "admin"
        assert data["users"][0]["status"] == "active"
        assert data["users"][0]["api_key"].startswith("om_")

    def test_idempotent(self, tmp_path: Path):
        """users.json 已存在 → 不覆盖"""
        users_file = tmp_path / "users.json"
        existing = {"users": [{"api_key": "existing_key", "username": "x", "role": "admin", "status": "active"}]}
        users_file.write_text(json.dumps(existing), encoding="utf-8")

        ensure_users_file(users_file)

        data = json.loads(users_file.read_text(encoding="utf-8"))
        assert data["users"][0]["api_key"] == "existing_key"

    def test_admin_from_env(self, tmp_path: Path, monkeypatch):
        """环境变量 OPENMEM_ADMIN_API_KEY → 用该值"""
        monkeypatch.setenv("OPENMEM_ADMIN_API_KEY", "om_from_env_123")
        users_file = tmp_path / "users.json"
        ensure_users_file(users_file)

        data = json.loads(users_file.read_text(encoding="utf-8"))
        assert data["users"][0]["api_key"] == "om_from_env_123"

    def test_generated_key_format(self, tmp_path: Path, monkeypatch):
        """无环境变量 → 生成 om_ 前缀 + 32 hex（不泄露角色信息）"""
        monkeypatch.delenv("OPENMEM_ADMIN_API_KEY", raising=False)
        users_file = tmp_path / "users.json"
        ensure_users_file(users_file)

        data = json.loads(users_file.read_text(encoding="utf-8"))
        key = data["users"][0]["api_key"]
        assert key.startswith("om_")
        # om_ (3) + 32 hex = 35
        assert len(key) == 35
        assert "admin" not in key
        assert "user" not in key
