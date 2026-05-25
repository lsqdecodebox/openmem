"""Tests for write_engine.py – writing and updating memory."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from write_engine import WriteEngine


class TestWriteEngineAddMemory:
    """Tests for add_memory()."""

    def test_add_memory_with_suggested_path(self, write_engine: WriteEngine, file_store):
        """add_memory with suggested_path should create a page at that path."""
        path = write_engine.add_memory(
            content="# Hello\n\nThis is a test memory.",
            suggested_path="/测试目录"
        )
        assert path.startswith("/测试目录/")
        assert path.endswith(".md")

    def test_add_memory_with_suggested_page_path(self, write_engine: WriteEngine, file_store):
        """add_memory with a full .md path should create that page."""
        path = write_engine.add_memory(
            content="# Specific Page\n\nContent here.",
            suggested_path="/my-specific-page.md"
        )
        assert path == "/my-specific-page.md"
        post = file_store.read_page(path)
        assert post is not None

    def test_add_memory_no_suggested_path(self, write_engine: WriteEngine, file_store):
        """add_memory without suggested_path should still create a page under root."""
        path = write_engine.add_memory(
            content="# Auto Classified\n\nSome content."
        )
        assert path.startswith("/")
        assert path.endswith(".md")

    def test_add_memory_with_tags(self, write_engine: WriteEngine, file_store):
        """add_memory should pass tags through to the created page."""
        path = write_engine.add_memory(
            content="# Tagged Memory",
            tags=["tag1", "tag2"]
        )
        post = file_store.read_page(path)
        assert post is not None
        assert "tag1" in post.metadata.get("tags", [])
        assert "tag2" in post.metadata.get("tags", [])

    def test_add_memory_empty_content(self, write_engine: WriteEngine):
        """add_memory should still create a page even with empty content."""
        path = write_engine.add_memory(content="")
        assert path.endswith(".md")


class TestWriteEngineUpdateMemory:
    """Tests for update_memory()."""

    def test_update_memory_append_mode(self, write_engine: WriteEngine, file_store, wiki_with_sample_page: str):
        """update_memory in append mode should add content to the end."""
        write_engine.update_memory(wiki_with_sample_page, "\n\n追加内容", mode="append")
        post = file_store.read_page(wiki_with_sample_page)
        assert "追加内容" in post.content

    def test_update_memory_overwrite_mode(self, write_engine: WriteEngine, file_store, wiki_with_sample_page: str):
        """update_memory in overwrite mode should replace content entirely."""
        write_engine.update_memory(wiki_with_sample_page, "全新内容", mode="overwrite")
        post = file_store.read_page(wiki_with_sample_page)
        assert post.content.strip() == "全新内容"

    def test_update_memory_merge_mode(self, write_engine: WriteEngine, file_store, wiki_with_sample_page: str):
        """update_memory in merge mode should call LLM for smart merge."""
        write_engine.llm_client.chat_completion.return_value = "合并后的内容"
        write_engine.update_memory(wiki_with_sample_page, "新内容", mode="merge")
        post = file_store.read_page(wiki_with_sample_page)
        assert post.content.strip() == "合并后的内容"
        # Verify LLM was called with merge prompt
        call_args = write_engine.llm_client.chat_completion.call_args
        assert call_args is not None
        messages = call_args[0][0]  # first positional arg is messages
        assert any("智能合并" in m["content"] for m in messages)

    def test_update_memory_nonexistent_page(self, write_engine: WriteEngine):
        """update_memory on a non-existent page should return False."""
        result = write_engine.update_memory("/ghost.md", "content", mode="append")
        assert result is False


class TestWriteEngineCreateDirectory:
    """Tests for create_directory()."""

    def test_create_directory_success(self, write_engine: WriteEngine, file_store):
        """create_directory should create a directory with 目录.md."""
        ok = write_engine.create_directory(
            path="/测试目录-2",
            title="测试目录2",
            summary="第二个测试目录"
        )
        assert ok is True
        assert (file_store.wiki_root / "测试目录-2").is_dir()
        assert (file_store.wiki_root / "测试目录-2" / "目录.md").exists()

    def test_create_directory_nested(self, write_engine: WriteEngine, file_store):
        """create_directory should support nested paths."""
        ok = write_engine.create_directory(
            path="/父目录/子目录",
            title="子目录",
            summary="嵌套目录"
        )
        assert ok is True
        assert (file_store.wiki_root / "父目录" / "子目录").is_dir()

    def test_create_directory_existing(self, write_engine: WriteEngine, wiki_with_sample_directory: str):
        """create_directory should return False for an existing directory."""
        ok = write_engine.create_directory(
            path=wiki_with_sample_directory,
            title="重复",
            summary="重复"
        )
        assert ok is False


class TestWriteEngineInternalMethods:
    """Tests for internal helper methods."""

    def test_generate_title_calls_llm(self, write_engine: WriteEngine):
        """_generate_title should call chat_completion."""
        write_engine._generate_title("Some content here")
        write_engine.llm_client.chat_completion.assert_called_once()

    def test_create_new_page_creates_file(self, write_engine: WriteEngine, file_store):
        """_create_new_page should create a .md file in the given parent."""
        path = write_engine._create_new_page("New page content", "/")
        assert path.startswith("/")
        assert path.endswith(".md")
        assert file_store.read_page(path) is not None