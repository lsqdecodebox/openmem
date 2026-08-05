"""认证服务测试：grant 端点逻辑、幂等发证、端点契约、端到端权限。

测试分层：
1. GrantRequest schema（extra=allow、applicantCode 必填）
2. validate_applicant（no-op 钩子）
3. grant_user_key（首次签发、幂等、永不为 admin、key 格式）
4. format_grant_response（响应格式）
5. UserStore.find_by_applicant / add_user（存取层）
6. /auth/grant 端点（独立 FastMCP + Starlette TestClient，200/422/400/403/500/幂等）
7. 端到端：grant 签发的 key → ApiKeyAuth.verify_token → role=user
"""

import json
import time
from pathlib import Path

import pytest
from fastmcp import FastMCP
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient

from openmem.auth import ApiKeyAuth, Role, UserStore
from openmem.auth_service import (
    GrantRequest,
    format_grant_response,
    grant_user_key,
    validate_applicant,
)


# ----------------------------- fixtures -----------------------------

@pytest.fixture
def users_file(tmp_path: Path) -> Path:
    """空 users.json（含一个 admin，无 applicantCode）"""
    f = tmp_path / "users.json"
    data = {
        "users": [
            {
                "api_key": "om_admin_existing",
                "username": "admin",
                "role": "admin",
                "status": "active",
                "created_at": "2026-08-05T10:00:00",
            }
        ]
    }
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


@pytest.fixture
def store(users_file: Path) -> UserStore:
    return UserStore(users_file)


# ----------------------------- GrantRequest schema -----------------------------

class TestGrantRequest:
    def test_minimal_valid(self):
        req = GrantRequest(applicantCode="APP-001")
        assert req.applicantCode == "APP-001"
        assert req.username is None
        assert req.note is None

    def test_full_valid(self):
        req = GrantRequest(
            applicantCode="APP-001",
            username="claude-desktop",
            note="内部系统发放",
        )
        assert req.username == "claude-desktop"
        assert req.note == "内部系统发放"

    def test_extra_allow透传联调字段(self):
        """extra=allow：联调期追加字段不报错、可访问"""
        req = GrantRequest(
            applicantCode="APP-001",
            timestamp="2026-08-05T10:00:00",
            signature="abc123",
            source="internal-portal",
        )
        assert req.applicantCode == "APP-001"
        # 多余字段存入 __pydantic_extra__
        assert req.__pydantic_extra__["signature"] == "abc123"
        assert req.__pydantic_extra__["source"] == "internal-portal"

    def test_applicantCode必填(self):
        with pytest.raises(ValidationError):
            GrantRequest()

    def test_applicantCode空字符串允许(self):
        """空字符串通过 schema，由 grant_user_key 校验拒绝"""
        req = GrantRequest(applicantCode="")
        assert req.applicantCode == ""


# ----------------------------- validate_applicant -----------------------------

class TestValidateApplicant:
    def test_noop透传不抛异常(self):
        """当前为 no-op，任何输入都返回 None"""
        req = GrantRequest(applicantCode="anything")
        assert validate_applicant(req) is None

    def test_noop带额外字段也不抛异常(self):
        req = GrantRequest(applicantCode="x", signature="y", timestamp="t")
        assert validate_applicant(req) is None


# ----------------------------- grant_user_key -----------------------------

class TestGrantUserKey:
    def test_首次签发(self, store: UserStore):
        req = GrantRequest(applicantCode="APP-001", username="client-a")
        user, is_new = grant_user_key(store, req)
        assert is_new is True
        assert user["role"] == Role.USER
        assert user["status"] == "active"
        assert user["applicantCode"] == "APP-001"
        assert user["username"] == "client-a"
        assert "created_at" in user

    def test_首次签发key格式(self, store: UserStore):
        req = GrantRequest(applicantCode="APP-001")
        user, _ = grant_user_key(store, req)
        key = user["api_key"]
        assert key.startswith("om_")
        assert len(key) == 35  # om_ (3) + 32 hex
        assert "admin" not in key
        assert "user" not in key

    def test_幂等返回同一个key(self, store: UserStore):
        req = GrantRequest(applicantCode="APP-001", username="client-a")
        user1, is_new1 = grant_user_key(store, req)
        user2, is_new2 = grant_user_key(store, req)
        assert is_new1 is True
        assert is_new2 is False
        assert user1["api_key"] == user2["api_key"]

    def test_幂等不同applicantCode签发不同key(self, store: UserStore):
        req1 = GrantRequest(applicantCode="APP-001")
        req2 = GrantRequest(applicantCode="APP-002")
        user1, _ = grant_user_key(store, req1)
        user2, _ = grant_user_key(store, req2)
        assert user1["api_key"] != user2["api_key"]

    def test_永不为admin(self, store: UserStore):
        """无论输入什么，签发的角色永远是 user"""
        req = GrantRequest(applicantCode="APP-001", username="someone")
        user, _ = grant_user_key(store, req)
        assert user["role"] == Role.USER
        assert user["role"] != Role.ADMIN

    def test_默认username回退(self, store: UserStore):
        """username 为空时回退为 applicant-<code>"""
        req = GrantRequest(applicantCode="APP-001")
        user, _ = grant_user_key(store, req)
        assert user["username"] == "applicant-APP-001"

    def test_空applicantCode拒绝(self, store: UserStore):
        req = GrantRequest(applicantCode="")
        with pytest.raises(ValueError):
            grant_user_key(store, req)

    def test_note可选写入(self, store: UserStore):
        req = GrantRequest(applicantCode="APP-001", note="测试备注")
        user, _ = grant_user_key(store, req)
        assert user["note"] == "测试备注"


# ----------------------------- format_grant_response -----------------------------

class TestFormatGrantResponse:
    def test_响应格式(self):
        user = {
            "api_key": "om_abc",
            "role": "user",
            "username": "x",
            "status": "active",
            "applicantCode": "APP-1",
            "created_at": "2026-01-01T00:00:00",
        }
        resp = format_grant_response(user, is_new=True)
        assert resp["api_key"] == "om_abc"
        assert resp["role"] == "user"
        assert resp["is_new"] is True
        assert resp["applicantCode"] == "APP-1"

    def test_响应is_newFalse(self):
        user = {"api_key": "om_abc", "role": "user"}
        resp = format_grant_response(user, is_new=False)
        assert resp["is_new"] is False


# ----------------------------- UserStore.find_by_applicant / add_user -----------------------------

class TestUserStoreApplicant:
    def test_find_by_applicant未命中(self, store: UserStore):
        assert store.find_by_applicant("nonexistent") is None

    def test_find_by_applicant空字符串(self, store: UserStore):
        assert store.find_by_applicant("") is None

    def test_find_by_applicant命中(self, store: UserStore):
        store.add_user({
            "api_key": "om_user_1",
            "username": "c1",
            "role": "user",
            "status": "active",
            "applicantCode": "APP-001",
        })
        user = store.find_by_applicant("APP-001")
        assert user is not None
        assert user["api_key"] == "om_user_1"

    def test_add_user写入后find_by_key命中(self, store: UserStore):
        store.add_user({
            "api_key": "om_new_key",
            "username": "new",
            "role": "user",
            "status": "active",
            "applicantCode": "APP-X",
        })
        # 同进程内立即可见（缓存已失效）
        assert store.find_by_key("om_new_key") is not None

    def test_add_user不覆盖已有用户(self, store: UserStore):
        """追加行为：原 admin 仍在"""
        store.add_user({
            "api_key": "om_new",
            "username": "new",
            "role": "user",
            "status": "active",
            "applicantCode": "APP-X",
        })
        assert store.find_by_key("om_admin_existing") is not None
        assert store.find_by_key("om_new") is not None

    def test_add_user缺api_key抛异常(self, store: UserStore):
        with pytest.raises(ValueError):
            store.add_user({"username": "x", "role": "user"})

    def test_add_user缓存失效可热更新(self, store: UserStore, users_file: Path):
        """写入后不重建 store，直接查询可见"""
        store.add_user({
            "api_key": "om_hot",
            "username": "hot",
            "role": "user",
            "status": "active",
            "applicantCode": "APP-HOT",
        })
        # 不重建 store，直接查
        assert store.find_by_applicant("APP-HOT") is not None
        assert store.find_by_key("om_hot") is not None

    def test_add_user持久化到文件(self, store: UserStore, users_file: Path):
        store.add_user({
            "api_key": "om_persist",
            "username": "p",
            "role": "user",
            "status": "active",
            "applicantCode": "APP-P",
        })
        # 重新读文件确认落盘
        data = json.loads(users_file.read_text(encoding="utf-8"))
        codes = [u.get("applicantCode") for u in data["users"]]
        assert "APP-P" in codes

    def test_find_by_applicant不校验status(self, store: UserStore):
        """与 find_by_key 不同：disabled 用户也能被 applicantCode 查到（幂等语义）"""
        store.add_user({
            "api_key": "om_disabled_app",
            "username": "d",
            "role": "user",
            "status": "disabled",
            "applicantCode": "APP-DIS",
        })
        user = store.find_by_applicant("APP-DIS")
        assert user is not None
        assert user["status"] == "disabled"


# ----------------------------- /auth/grant 端点 -----------------------------
# 用独立 FastMCP 实例 + 临时 UserStore，避免污染全局 main.mcp

def build_test_app(user_store: UserStore, grant_enabled: bool):
    """构造与 main.py /auth/grant handler 逻辑一致的测试 app。

    复用 auth_service 纯函数，handler 为薄层（解析→校验→签发→响应）。
    """
    import logging
    logger = logging.getLogger("test_grant")

    mcp = FastMCP("test")

    @mcp.custom_route("/auth/grant", methods=["POST"])
    async def auth_grant(request: Request) -> Response:
        if not grant_enabled:
            return JSONResponse(
                {"status": "error", "message": "grant 服务已被禁用"},
                status_code=403,
            )

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "message": "请求体必须是合法 JSON"},
                status_code=400,
            )

        try:
            req = GrantRequest.model_validate(body)
        except ValidationError as e:
            return JSONResponse(
                {"status": "error", "message": "请求体校验失败", "detail": e.errors()},
                status_code=422,
            )

        err = validate_applicant(req)
        if err is not None:
            return JSONResponse(
                {"status": "error", "message": err},
                status_code=401,
            )

        try:
            user, is_new = grant_user_key(user_store, req)
        except ValueError as e:
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=400,
            )
        except OSError as e:
            logger.error(f"grant 写入 users.json 失败: {e}")
            return JSONResponse(
                {"status": "error", "message": "服务端写入用户失败"},
                status_code=500,
            )

        return JSONResponse(format_grant_response(user, is_new), status_code=200)

    return mcp.http_app(path="/mcp")


class TestGrantEndpoint:
    def test_成功签发(self, store: UserStore):
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp = client.post("/auth/grant", json={"applicantCode": "APP-001", "username": "c1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["api_key"].startswith("om_")
        assert body["role"] == "user"
        assert body["is_new"] is True
        assert body["applicantCode"] == "APP-001"

    def test_幂等返回同一个key(self, store: UserStore):
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp1 = client.post("/auth/grant", json={"applicantCode": "APP-001"})
        resp2 = client.post("/auth/grant", json={"applicantCode": "APP-001"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["api_key"] == resp2.json()["api_key"]
        assert resp1.json()["is_new"] is True
        assert resp2.json()["is_new"] is False

    def test_缺applicantCode返回422(self, store: UserStore):
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp = client.post("/auth/grant", json={"username": "c1"})
        assert resp.status_code == 422

    def test_非JSON返回400(self, store: UserStore):
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp = client.post("/auth/grant", content="not json", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 400

    def test_grant禁用返回403(self, store: UserStore):
        app = build_test_app(store, grant_enabled=False)
        client = TestClient(app)
        resp = client.post("/auth/grant", json={"applicantCode": "APP-001"})
        assert resp.status_code == 403

    def test_联调额外字段透传不报错(self, store: UserStore):
        """模拟联调期请求体带 timestamp/signature 等额外字段"""
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp = client.post("/auth/grant", json={
            "applicantCode": "APP-001",
            "username": "c1",
            "timestamp": "2026-08-05T10:00:00",
            "signature": "abc123",
            "source": "internal-portal",
        })
        assert resp.status_code == 200
        assert resp.json()["is_new"] is True

    def test_空applicantCode返回400(self, store: UserStore):
        app = build_test_app(store, grant_enabled=True)
        client = TestClient(app)
        resp = client.post("/auth/grant", json={"applicantCode": ""})
        assert resp.status_code == 400

    def test_有authProvider时端点仍可无key访问(self, store: UserStore):
        """关键验证：即使 mcp 挂了 ApiKeyAuth，custom_route 也不被 TokenVerifier 拦截。

        这是"鸡生蛋"问题的核心：grant 端点必须在无 key 时可访问，
        否则用户无法获取第一个 key。
        """
        auth = ApiKeyAuth(store)
        mcp = FastMCP("test-with-auth", auth=auth)

        @mcp.custom_route("/auth/grant", methods=["POST"])
        async def grant(request: Request) -> Response:
            return JSONResponse({"ok": True}, status_code=200)

        client = TestClient(mcp.http_app(path="/mcp"))
        # 不带 Authorization 头，应 200 而非 401
        resp = client.post("/auth/grant", json={"applicantCode": "APP-001"})
        assert resp.status_code == 200


# ----------------------------- 端到端：grant key → ApiKeyAuth -----------------------------

class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_grant签发的key可被ApiKeyAuth验证且角色为user(self, store: UserStore):
        """grant 签发 → 写入 users.json → ApiKeyAuth.verify_token 通过 → role=user"""
        req = GrantRequest(applicantCode="APP-001", username="e2e-client")
        user, _ = grant_user_key(store, req)
        api_key = user["api_key"]

        auth = ApiKeyAuth(store)
        token = await auth.verify_token(api_key)
        assert token is not None
        assert token.client_id == "e2e-client"
        assert token.claims["role"] == Role.USER

    @pytest.mark.asyncio
    async def test_grant签发的key无写权限(self, store: UserStore):
        """端到端验证权限矩阵：user 角色 write_memory 应被拒"""
        from openmem.auth import require_admin, PERMISSIONS
        req = GrantRequest(applicantCode="APP-001")
        user, _ = grant_user_key(store, req)

        auth = ApiKeyAuth(store)
        token = await auth.verify_token(user["api_key"])
        assert token.claims["role"] == Role.USER

        # user 角色不在 write_memory 允许集合
        assert Role.USER not in PERMISSIONS["write_memory"]
        assert Role.USER in PERMISSIONS["read_memory"]
