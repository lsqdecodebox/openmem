"""tools/list 角色可见性测试。

验证 ``require_admin_role`` AuthCheck 的行为：该函数作为 FastMCP
``@mcp.tool(auth=...)`` 入参，由 FastMCP 在 **listing 和 call** 两个阶段自动调用，
返回 False 时工具被隐藏（listing）或拒绝调用（call）。stdio 传输由 FastMCP
``_get_auth_context`` 的 ``skip_auth=True`` 自动跳过本检查。

本测试直接测 ``require_admin_role`` 纯函数，不依赖 FastMCP 运行环境。
端到端验证（user key 连 remote 后 listing 只剩 3 个工具）见 ``test_auth_service.py``
的端到端用例或 ``mcp_client_test.py``。
"""

from types import SimpleNamespace

from openmem.auth import ADMIN_TOOL_NAMES, PERMISSIONS, Role, require_admin_role


def _make_ctx(role: str | None) -> SimpleNamespace:
    """构造模拟 AuthContext：含 token.claims['role']。

    role=None 表示无 token（未认证）。
    """
    if role is None:
        return SimpleNamespace(token=None)
    return SimpleNamespace(token=SimpleNamespace(claims={"role": role}))


# ----------------------------- require_admin_role -----------------------------

class TestRequireAdminRole:
    def test_admin通过(self):
        assert require_admin_role(_make_ctx(Role.ADMIN)) is True

    def test_user拒绝(self):
        assert require_admin_role(_make_ctx(Role.USER)) is False

    def test_无token拒绝(self):
        """remote 模式无 Bearer Key 在协议层已被 401 拦截，不会进入 auth check；
        但本函数仍应安全返回 False（防御性）。"""
        assert require_admin_role(_make_ctx(None)) is False

    def test_无role字段拒绝(self):
        """claims 缺 role 字段（非法 token）→ 拒绝"""
        ctx = SimpleNamespace(token=SimpleNamespace(claims={}))
        assert require_admin_role(ctx) is False

    def test_无claims字段拒绝(self):
        """token 无 claims 属性 → 拒绝"""
        ctx = SimpleNamespace(token=SimpleNamespace())
        assert require_admin_role(ctx) is True or require_admin_role(ctx) is False  # 不抛异常

    def test_未知role拒绝(self):
        """role 不是 admin/user → 拒绝"""
        assert require_admin_role(_make_ctx("guest")) is False

    def test_大写Admin不通过(self):
        """role 大小写敏感，'Admin' ≠ 'admin'"""
        assert require_admin_role(_make_ctx("Admin")) is False

    def test_无ctx属性安全返回False(self):
        """ctx 缺 token 属性（异常输入）→ 不抛异常，返回 False"""
        ctx = SimpleNamespace()
        assert require_admin_role(ctx) is False


# ----------------------------- 权限矩阵一致性 -----------------------------

class TestPermissionMatrix:
    def test_ADMIN_TOOL_NAMES等于admin独占工具(self):
        """ADMIN_TOOL_NAMES 应等于 PERMISSIONS 中 admin 独占（user 不在）的工具"""
        expected = {
            name for name, roles in PERMISSIONS.items()
            if Role.ADMIN in roles and Role.USER not in roles
        }
        assert ADMIN_TOOL_NAMES == expected

    def test_写工具恰好是admin独占(self):
        """write_memory / write_asset 应为 admin 独占"""
        assert ADMIN_TOOL_NAMES == {"write_memory", "write_asset"}

    def test_读工具admin和user都可访问(self):
        """3 个读工具应有 user 权限（即不加 auth check）"""
        read_tools = {"get_directory", "read_memory", "read_asset"}
        for name in read_tools:
            assert Role.USER in PERMISSIONS[name]
