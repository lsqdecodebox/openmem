import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

import frontmatter

from openmem.initializer import ensure_core_prompts
from openmem.store import WikiStore


def _extract_text(result) -> str:
    return result.data


def _build_test_mcp(wiki_root: Path) -> FastMCP:
    ensure_core_prompts(wiki_root)
    store = WikiStore(wiki_root, max_depth=7, snapshot_cfg={"enabled": False})

    mcp = FastMCP("Personal Wiki Memory")

    @mcp.tool()
    def get_directory(path: str = "/") -> str:
        """获取指定目录的层级文件列表"""
        return store.get_directory(path)

    @mcp.tool()
    def read_memory(path: str) -> str:
        """读取指定路径的完整Wiki页面内容"""
        return store.read_memory(path)

    @mcp.tool()
    def write_memory(
        content: str, path: str | None = None, tags: list[str] | None = None, summary: str | None = None
    ) -> str:
        """写入记忆（覆盖写入，缺目录自动创建，更新前自动快照）"""
        return store.write_memory(content=content, path=path, tags=tags, summary=summary)

    @mcp.tool()
    def write_asset(
        source: str,
        path: str,
        filename: str,
        type: str = "files",
        overwrite: bool = False,
    ) -> str:
        """写入图片、文件、视频等二进制资料到记忆中"""
        return store.write_asset(source=source, path=path, filename=filename, type=type, overwrite=overwrite)

    @mcp.tool()
    def read_asset(path: str) -> str:
        """读取记忆中已有的图片、文件、视频等资产的本地路径"""
        return store.read_asset(path=path)

    @mcp.prompt(name="core_principles", description="记忆系统核心提示词，供LLM调度决策")
    def core_principles_prompt() -> str:
        """获取所有核心提示词"""
        return store.get_core_principles()

    return mcp


@pytest.fixture
def mcp_server(tmp_path: Path) -> FastMCP:
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()
    return _build_test_mcp(wiki_root)


@pytest.fixture
def wiki_root(tmp_path: Path) -> Path:
    return tmp_path / "wiki"


@pytest.mark.asyncio
async def test_client_list_tools(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        tools = await client.list_tools()

    tool_names = [t.name for t in tools]
    assert "get_directory" in tool_names
    assert "read_memory" in tool_names
    assert "write_memory" in tool_names
    assert "write_asset" in tool_names
    assert "read_asset" in tool_names


@pytest.mark.asyncio
async def test_client_list_prompts(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        prompts = await client.list_prompts()

    prompt_names = [p.name for p in prompts]
    assert "core_principles" in prompt_names


@pytest.mark.asyncio
async def test_client_call_get_directory(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_directory", {"path": "/"})

    result_text = _extract_text(result)
    parsed = json.loads(result_text)
    assert parsed["type"] == "directory"
    assert "children" in parsed


@pytest.mark.asyncio
async def test_client_call_write_then_read(mcp_server: FastMCP, wiki_root: Path):
    async with Client(mcp_server) as client:
        write_result = await client.call_tool(
            "write_memory",
            {"content": "Python学习笔记", "path": "/02-学习/Python", "tags": ["学习"]},
        )
        read_result = await client.call_tool(
            "read_memory", {"path": "/02-学习/Python"}
        )

    write_text = _extract_text(write_result)
    write_parsed = json.loads(write_text)
    assert write_parsed["status"] == "ok"

    read_text = _extract_text(read_result)
    assert "Python学习笔记" in read_text


@pytest.mark.asyncio
async def test_client_call_write_no_path(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "write_memory", {"content": "some content"}
        )

    result_text = _extract_text(result)
    parsed = json.loads(result_text)
    assert parsed["status"] == "need_path"


@pytest.mark.asyncio
async def test_client_call_write_depth_exceeded(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "write_memory",
            {"content": "test", "path": "/a/b/c/d/e/f/g/h"},
        )

    result_text = _extract_text(result)
    assert "error" in result_text or "超过" in result_text


@pytest.mark.asyncio
async def test_client_get_prompt_core_principles(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        result = await client.get_prompt("core_principles")

    messages_text = ""
    for msg in result.messages:
        if hasattr(msg.content, "text"):
            messages_text += msg.content.text

    assert "记忆管理规则" in messages_text


@pytest.mark.asyncio
async def test_client_full_workflow(mcp_server: FastMCP, wiki_root: Path):
    async with Client(mcp_server) as client:
        dir_result = await client.call_tool("get_directory", {"path": "/"})
        dir_text = _extract_text(dir_result)
        dir_parsed = json.loads(dir_text)
        assert dir_parsed["type"] == "directory"

        write_result = await client.call_tool(
            "write_memory",
            {"content": "项目进度记录", "path": "/01-工作/项目A", "tags": ["工作"]},
        )
        write_text = _extract_text(write_result)
        write_parsed = json.loads(write_text)
        assert write_parsed["status"] == "ok"

        read_result = await client.call_tool(
            "read_memory", {"path": "/01-工作/项目A"}
        )
        read_text = _extract_text(read_result)
        assert "项目进度记录" in read_text

        dir_after = await client.call_tool("get_directory", {"path": "/01-工作"})
        dir_after_text = _extract_text(dir_after)
        dir_after_parsed = json.loads(dir_after_text)
        child_names = [c["name"] for c in dir_after_parsed["children"]]
        assert "项目A.md" in child_names

        update_result = await client.call_tool(
            "write_memory",
            {"content": "本周新增进展", "path": "/01-工作/项目A"},
        )
        update_text = _extract_text(update_result)
        update_parsed = json.loads(update_text)
        assert update_parsed["status"] == "ok"

        read_updated = await client.call_tool(
            "read_memory", {"path": "/01-工作/项目A"}
        )
        read_updated_text = _extract_text(read_updated)
        assert "本周新增进展" in read_updated_text

        principles = await client.get_prompt("core_principles")
        principles_text = ""
        for msg in principles.messages:
            if hasattr(msg.content, "text"):
                principles_text += msg.content.text
        assert len(principles_text) > 0


@pytest.mark.asyncio
async def test_client_write_asset(mcp_server: FastMCP, wiki_root: Path):
    import tempfile

    raw_data = b"test binary data"

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(raw_data)
        temp_path = f.name

    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作/项目A",
                    "filename": "test.bin",
                    "type": "files",
                },
            )

        result_text = _extract_text(result)
        parsed = json.loads(result_text)
        assert parsed["status"] == "ok"
        assert parsed["type"] == "files"
        assert parsed["filename"] == "test.bin"
        assert parsed["size"] == len(raw_data)

        saved_path = wiki_root / "files" / "01-工作" / "项目A" / "test.bin"
        assert saved_path.exists()
        assert saved_path.read_bytes() == raw_data
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_client_write_asset_images(mcp_server: FastMCP, wiki_root: Path):
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake png content")
        temp_path = f.name

    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作/项目A",
                    "filename": "diagram.png",
                    "type": "images",
                },
            )

        result_text = _extract_text(result)
        parsed = json.loads(result_text)
        assert parsed["status"] == "ok"
        assert parsed["type"] == "images"

        saved_path = wiki_root / "images" / "01-工作" / "项目A" / "diagram.png"
        assert saved_path.exists()
        assert saved_path.read_bytes() == b"fake png content"
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_client_write_asset_file_exists(mcp_server: FastMCP, wiki_root: Path):
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(b"data")
        temp_path = f.name

    try:
        async with Client(mcp_server) as client:
            await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作",
                    "filename": "test.bin",
                    "type": "files",
                },
            )
            result = await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作",
                    "filename": "test.bin",
                    "type": "files",
                    "overwrite": False,
                },
            )

        result_text = _extract_text(result)
        parsed = json.loads(result_text)
        assert parsed["status"] == "file_exists"
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_client_write_asset_invalid_type(mcp_server: FastMCP, wiki_root: Path):
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(b"data")
        temp_path = f.name

    try:
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作",
                    "filename": "test.bin",
                    "type": "invalid",
                },
            )

        result_text = _extract_text(result)
        parsed = json.loads(result_text)
        assert parsed["status"] == "error"
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_client_read_asset(mcp_server: FastMCP, wiki_root: Path):
    import tempfile

    raw_data = b"test binary data"

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(raw_data)
        temp_path = f.name

    try:
        async with Client(mcp_server) as client:
            await client.call_tool(
                "write_asset",
                {
                    "source": temp_path,
                    "path": "01-工作",
                    "filename": "readme.bin",
                    "type": "files",
                },
            )

            result = await client.call_tool(
                "read_asset",
                {"path": "files/01-工作/readme.bin"},
            )

        result_text = _extract_text(result)
        parsed = json.loads(result_text)
        assert parsed["status"] == "ok"
        assert parsed["size"] == len(raw_data)
        assert parsed["relative_path"] == "files/01-工作/readme.bin"
        assert "files" in parsed["absolute_path"]
        assert "readme.bin" in parsed["absolute_path"]
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_client_read_asset_not_exist(mcp_server: FastMCP):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "read_asset",
            {"path": "images/nonexistent/file.png"},
        )

    result_text = _extract_text(result)
    parsed = json.loads(result_text)
    assert parsed["status"] == "error"
    assert "不存在" in parsed["message"]


@pytest.mark.asyncio
async def test_client_write_asset_source_not_exist(mcp_server: FastMCP, wiki_root: Path):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "write_asset",
            {
                "source": "/nonexistent/file.png",
                "path": "01-工作",
                "filename": "file.png",
                "type": "images",
            },
        )

    result_text = _extract_text(result)
    parsed = json.loads(result_text)
    assert parsed["status"] == "error"
