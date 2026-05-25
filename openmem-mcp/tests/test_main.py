"""Tests for main.py – MCP tool registration and top-level error handling."""

from unittest.mock import MagicMock, patch

import pytest

# We import the module-level objects after patching dependencies
from main import (
    mcp, config, file_store, llm_client,
    write_engine, read_engine, health_engine,
    add_memory, update_memory, search_memories,
    get_page, get_directory, create_directory,
    run_health_check, export_wiki
)


# ---------------------------------------------------------------------------
# Fixture: ensure MCP server is registered with expected tools
# ---------------------------------------------------------------------------

class TestMCPToolRegistration:
    """Tests that MCP tools are properly registered."""

    def test_mcp_tools_registered(self):
        """The MCP server should have all 8 tools registered."""
        import asyncio
        loop = asyncio.new_event_loop()

        tool_list = loop.run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tool_list}
        expected = {
            "add_memory",
            "update_memory",
            "search_memories",
            "get_page",
            "get_directory",
            "create_directory",
            "run_health_check",
            "export_wiki",
        }
        assert tool_names == expected


# ---------------------------------------------------------------------------
# Individual tool tests
# ---------------------------------------------------------------------------

class TestAddMemoryTool:
    """Tests for the add_memory MCP tool."""

    def test_add_memory_success(self):
        """add_memory should return the path on success."""
        with patch.object(write_engine, "add_memory", return_value="/test/memory.md") as mock:
            result = add_memory(content="# Hello", suggested_path="/test", tags=["tag1"])
            assert result == "/test/memory.md"
            mock.assert_called_once_with("# Hello", "/test", ["tag1"])

    def test_add_memory_error(self):
        """add_memory should return error message on exception."""
        with patch.object(write_engine, "add_memory", side_effect=Exception("写失败")):
            result = add_memory(content="test")
            assert "错误" in result


class TestUpdateMemoryTool:
    """Tests for the update_memory MCP tool."""

    def test_update_memory_success(self):
        """update_memory should return True on success."""
        with patch.object(write_engine, "update_memory", return_value=True) as mock:
            result = update_memory(path="/test.md", content="new", mode="overwrite")
            assert result is True
            mock.assert_called_once_with("/test.md", "new", "overwrite")

    def test_update_memory_failure(self):
        """update_memory should return False on exception."""
        with patch.object(write_engine, "update_memory", side_effect=Exception("更新失败")):
            result = update_memory(path="/test.md", content="new")
            assert result is False


class TestSearchMemoriesTool:
    """Tests for the search_memories MCP tool."""

    def test_search_memories_success(self):
        """search_memories should return the search result string."""
        with patch.object(read_engine, "search", return_value="搜索结果") as mock:
            result = search_memories(query="test", max_depth=5, max_results=2)
            assert result == "搜索结果"
            mock.assert_called_once_with("test", 5, 2)

    def test_search_memories_error(self):
        """search_memories should return error message on exception."""
        with patch.object(read_engine, "search", side_effect=Exception("搜索失败")):
            result = search_memories(query="test")
            assert "错误" in result


class TestGetPageTool:
    """Tests for the get_page MCP tool."""

    def test_get_page_found(self):
        """get_page should return formatted page content when found."""
        mock_post = MagicMock()
        mock_post.metadata = {"title": "Test", "path": "/test.md"}
        mock_post.content = "Page content"
        with patch.object(file_store, "read_page", return_value=mock_post):
            result = get_page(path="/test.md")
            # Metadata is rendered as Python dict repr between --- delimiters
            assert "'title': 'Test'" in result or "title: Test" in result
            assert "Page content" in result

    def test_get_page_not_found(self):
        """get_page should return 'page not found' when missing."""
        with patch.object(file_store, "read_page", return_value=None):
            result = get_page(path="/ghost.md")
            assert "不存在" in result

    def test_get_page_error(self):
        """get_page should return error message on exception."""
        with patch.object(file_store, "read_page", side_effect=Exception("读失败")):
            result = get_page(path="/test.md")
            assert "错误" in result


class TestGetDirectoryTool:
    """Tests for the get_directory MCP tool."""

    def test_get_directory_with_items(self):
        """get_directory should return a formatted listing."""
        items = [
            {"type": "page", "title": "Page1", "summary": "Summary1", "path": "/page1.md"},
            {"type": "directory", "title": "Dir1", "summary": "Dir summary", "path": "/dir1"},
        ]
        with patch.object(file_store, "list_directory_items", return_value=items):
            result = get_directory(path="/")
            assert "Page1" in result
            assert "Dir1" in result
            assert "目录" in result

    def test_get_directory_empty(self):
        """get_directory should return 'empty' message for empty dir."""
        with patch.object(file_store, "list_directory_items", return_value=[]):
            result = get_directory(path="/empty")
            assert "空" in result

    def test_get_directory_error(self):
        """get_directory should return error message on exception."""
        with patch.object(file_store, "list_directory_items", side_effect=Exception("读目录失败")):
            result = get_directory(path="/")
            assert "错误" in result


class TestCreateDirectoryTool:
    """Tests for the create_directory MCP tool."""

    def test_create_directory_success(self):
        """create_directory should return True on success."""
        with patch.object(write_engine, "create_directory", return_value=True) as mock:
            result = create_directory(path="/new", title="New", summary="A new dir")
            assert result is True
            mock.assert_called_once_with("/new", "New", "A new dir")

    def test_create_directory_failure(self):
        """create_directory should return False on exception."""
        with patch.object(write_engine, "create_directory", side_effect=Exception("创建失败")):
            result = create_directory(path="/new", title="New", summary="desc")
            assert result is False


class TestRunHealthCheckTool:
    """Tests for the run_health_check MCP tool."""

    def test_run_health_check_success(self):
        """run_health_check should return the health report dict."""
        report = {"total_files": 0, "total_directories": 1, "errors": [], "warnings": [], "suggestions": []}
        with patch.object(health_engine, "run_check", return_value=report):
            result = run_health_check()
            assert result == report

    def test_run_health_check_error(self):
        """run_health_check should return error dict on exception."""
        with patch.object(health_engine, "run_check", side_effect=Exception("检查失败")):
            result = run_health_check()
            assert "error" in result


class TestExportWikiTool:
    """Tests for the export_wiki MCP tool."""

    def test_export_wiki_success(self):
        """export_wiki should return the output path."""
        with patch.object(file_store, "export_wiki", return_value="/tmp/wiki.zip") as mock:
            result = export_wiki(output_path="my_backup.zip")
            assert result == "/tmp/wiki.zip"
            mock.assert_called_once_with("my_backup.zip")

    def test_export_wiki_default_path(self):
        """export_wiki should use default path when not specified."""
        with patch.object(file_store, "export_wiki", return_value="/tmp/wiki_export.zip") as mock:
            result = export_wiki()
            assert result == "/tmp/wiki_export.zip"
            mock.assert_called_once_with("wiki_export.zip")

    def test_export_wiki_error(self):
        """export_wiki should return error message on exception."""
        with patch.object(file_store, "export_wiki", side_effect=Exception("导出失败")):
            result = export_wiki()
            assert "错误" in result