"""tools/list 角色可见性测试。

验证 ``RoleFilteredMCP.list_tools`` 按角色过滤工具：
- admin / stdio 默认：返回全部 5 个工具
- user：隐藏 ``write_memory`` / ``write_asset``，仅返回 3 个读工具
- tools/call 阶段的 ``require_admin`` 守卫保留作为纵深防御

依赖 fastmcp，未安装时自动跳过。
"""

import json

import pytest

fastmcp = pytest.importorskip("fastmcp")

from openmem.auth import ADMIN_TOOL_NAMES, PERMISSIONS, Role, require_admin
from openmem.main import RoleFilteredMCP


# ----------------------------- fixtures -----------------------------

@pytest.fixture
def mcp_instance(monkeypatch):
    """构造一个注册了全部 5 个工具的 RoleFilteredMCP 实例。

    用最简单的 dummy 工具替代真实 store 调用，避免初始化 wiki/配置等副作用。
    默认 monkeypatch get_current_role=admin，单测可覆盖为 user。
    """
    monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.ADMIN)
    mcp = RoleFilteredMCP("test-visibility")

    @mcp.tool()
    def get_directory(path: str = "/") -> str:
        return "dir"

    @mcp.tool()
    def read_memory(path: str) -> str:
        return "mem"

    @mcp.tool()
    def read_asset(path: str) -> str:
        return "asset"

    @mcp.tool()
    def write_memory(content: str, path: str | None = None) -> str:
        return "wmem"

    @mcp.tool()
    def write_asset(source: str, path: str, filename: str) -> str:
        return "wasset"

    return mcp


ALL_TOOL_NAMES = {"get_directory", "read_memory", "read_asset", "write_memory", "write_asset"}
READ_TOOL_NAMES = {"get_directory", "read_memory", "read_asset"}


# ----------------------------- list_tools 可见性 -----------------------------

class TestListToolsVisibility:
    @pytest.mark.asyncio
    async def test_admin看到全部工具(self, mcp_instance, monkeypatch):
        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.ADMIN)
        tools = await mcp_instance.list_tools()
        names = {t.name for t in tools}
        assert names == ALL_TOOL_NAMES

    @pytest.mark.asyncio
    async def test_user隐藏写工具(self, mcp_instance, monkeypatch):
        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.USER)
        tools = await mcp_instance.list_tools()
        names = {t.name for t in tools}
        assert names == READ_TOOL_NAMES
        assert "write_memory" not in names
        assert "write_asset" not in names

    @pytest.mark.asyncio
    async def test_user保留读工具(self, mcp_instance, monkeypatch):
        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.USER)
        tools = await mcp_instance.list_tools()
        names = {t.name for t in tools}
        assert {"get_directory", "read_memory", "read_asset"}.issubset(names)

    @pytest.mark.asyncio
    async def test_admin与user工具数差异恰好为admin专属(self, mcp_instance, monkeypatch):
        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.ADMIN)
        admin_tools = {t.name for t in await mcp_instance.list_tools()}

        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.USER)
        user_tools = {t.name for t in await mcp_instance.list_tools()}

        assert admin_tools - user_tools == ADMIN_TOOL_NAMES
        assert ADMIN_TOOL_NAMES == {"write_memory", "write_asset"}

    @pytest.mark.asyncio
    async def test_角色切换后listing动态变化(self, mcp_instance, monkeypatch):
        """同一实例，先 admin 后 user，listing 应分别反映"""
        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.ADMIN)
        assert len(await mcp_instance.list_tools()) == 5

        monkeypatch.setattr("openmem.main.get_current_role", lambda: Role.USER)
        assert len(await mcp_instance.list_tools()) == 3


# ----------------------------- 纵深防御：require_admin 守卫 -----------------------------

class TestRequireAdminGuard:
    """验证 listing 过滤被绕过时，call 阶段守卫仍生效。"""

    def test_user调write_memory被拒(self, monkeypatch):
        monkeypatch.setattr("openmem.auth.get_current_role", lambda: Role.USER)
        result = require_admin("write_memory")
        assert result is not None
        data = json.loads(result)
        assert data["status"] == "forbidden"
        assert "write_memory" in data["message"]

    def test_user调write_asset被拒(self, monkeypatch):
        monkeypatch.setattr("openmem.auth.get_current_role", lambda: Role.USER)
        result = require_admin("write_asset")
        assert result is not None
        assert "forbidden" in result

    def test_admin调write_memory放行(self, monkeypatch):
        monkeypatch.setattr("openmem.auth.get_current_role", lambda: Role.ADMIN)
        assert require_admin("write_memory") is None

    def test_权限矩阵与admin工具集一致(self):
        """ADMIN_TOOL_NAMES 应等于 PERMISSIONS 中 admin 独占的工具"""
        expected = {
            name for name, roles in PERMISSIONS.items()
            if Role.ADMIN in roles and Role.USER not in roles
        }
        assert ADMIN_TOOL_NAMES == expected
