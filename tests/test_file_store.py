"""Tests for file_store.py – file system operations for the Wiki."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from openmem.file_store import FileStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_md_files(store: FileStore, rel_dir: str = "") -> int:
    """Count .md files (excluding directory.md) under a relative path."""
    target = store.wiki_root / rel_dir
    return sum(1 for f in target.rglob("*.md") if f.name != "目录.md" and ".tmp" not in f.suffix)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileStoreInit:
    """Tests for FileStore initialization."""

    def test_ensure_root_creates_directory(self, tmp_path: Path):
        """Root directory and 目录.md should be created on init."""
        root = tmp_path / "new_wiki"
        store = FileStore(root, max_depth=7)
        assert root.exists()
        assert (root / "目录.md").exists()

    def test_ensure_root_skips_existing(self, tmp_path: Path):
        """If root already exists with 目录.md, init should not error."""
        root = tmp_path / "existing_wiki"
        root.mkdir(parents=True, exist_ok=True)
        index = root / "目录.md"
        index.write_text("# Existing", encoding="utf-8")

        before = list(root.iterdir())
        FileStore(root, max_depth=7)
        after = list(root.iterdir())
        assert before == after


class TestFileStoreReadWrite:
    """Tests for reading and writing pages."""

    def test_read_page_exists(self, file_store: FileStore, wiki_with_sample_page: str):
        """read_page should return a Post for an existing page."""
        post = file_store.read_page(wiki_with_sample_page)
        assert post is not None
        assert post.metadata["title"] == "测试页面"

    def test_read_page_not_found(self, file_store: FileStore):
        """read_page should return None for a non-existent page."""
        assert file_store.read_page("/nonexistent.md") is None

    def test_read_directory_root(self, file_store: FileStore):
        """read_directory('/') should return the root 目录.md."""
        post = file_store.read_directory("/")
        assert post is not None
        assert post.metadata["title"] == "我的个人知识库"

    def test_read_directory_nonexistent(self, file_store: FileStore):
        """read_directory should return None for a missing directory."""
        post = file_store.read_directory("/no-such-dir")
        assert post is None


class TestFileStoreCreate:
    """Tests for creating pages and directories."""

    def test_create_page(self, file_store: FileStore):
        """create_page should create a new .md file."""
        ok = file_store.create_page(
            path="/my-page.md",
            title="My Page",
            content="# Hello",
            summary="A test page",
            parent_path="/",
            tags=["test"]
        )
        assert ok is True
        assert (file_store.wiki_root / "my-page.md").exists()

    def test_create_page_existing_path(self, file_store: FileStore, wiki_with_sample_page: str):
        """create_page should return False when page already exists."""
        ok = file_store.create_page(
            path=wiki_with_sample_page,
            title="Duplicate",
            content="dup",
            summary="dup",
            parent_path="/"
        )
        assert ok is False

    def test_create_page_exceeds_depth(self, file_store: FileStore):
        """create_page should return False when depth > max_depth."""
        deep_path = "/a/b/c/d/e/f/g/h/i/j/page.md"  # level 12
        ok = file_store.create_page(
            path=deep_path,
            title="Deep",
            content="too deep",
            summary="too deep",
            parent_path="/a/b/c/d/e/f/g/h/i/j"
        )
        assert ok is False

    def test_create_directory(self, file_store: FileStore):
        """create_directory should create a directory with 目录.md."""
        ok = file_store.create_directory(
            path="/new-dir",
            title="New Directory",
            summary="A new directory",
            parent_path="/"
        )
        assert ok is True
        assert (file_store.wiki_root / "new-dir").is_dir()
        assert (file_store.wiki_root / "new-dir" / "目录.md").exists()

    def test_create_directory_existing(self, file_store: FileStore, wiki_with_sample_directory: str):
        """create_directory should return False when directory already exists."""
        ok = file_store.create_directory(
            path=wiki_with_sample_directory,
            title="Duplicate",
            summary="dup",
            parent_path="/"
        )
        assert ok is False

    def test_create_directory_exceeds_depth(self, file_store: FileStore):
        """create_directory should return False when depth > max_depth."""
        file_store.max_depth = 2
        ok = file_store.create_directory(
            path="/a/b/c/d",
            title="Too Deep",
            summary="too deep",
            parent_path="/a/b/c"
        )
        assert ok is False

    def test_create_page_updates_parent_index(self, file_store: FileStore):
        """Creating a page should add a link to the parent directory.md."""
        file_store.create_page(
            path="/indexed-page.md",
            title="Indexed",
            content="# Indexed",
            summary="indexed",
            parent_path="/"
        )
        parent = file_store.read_directory("/")
        assert "Indexed" in parent.content


class TestFileStoreUpdate:
    """Tests for updating pages."""

    def test_update_page_content(self, file_store: FileStore, wiki_with_sample_page: str):
        """update_page should change the content of an existing page."""
        ok = file_store.update_page(wiki_with_sample_page, "新内容")
        assert ok is True
        post = file_store.read_page(wiki_with_sample_page)
        assert post.content.strip() == "新内容"

    def test_update_page_nonexistent(self, file_store: FileStore):
        """update_page should return False for non-existent page."""
        ok = file_store.update_page("/ghost.md", "content")
        assert ok is False

    def test_update_page_updates_timestamp(self, file_store: FileStore, wiki_with_sample_page: str):
        """update_page should refresh the updated_at timestamp."""
        post_before = file_store.read_page(wiki_with_sample_page)
        old_ts = post_before.metadata["updated_at"]
        file_store.update_page(wiki_with_sample_page, "updated content")
        post_after = file_store.read_page(wiki_with_sample_page)
        assert post_after.metadata["updated_at"] >= old_ts


class TestFileStoreList:
    """Tests for listing directory contents."""

    def test_list_root_empty_before_add(self, file_store: FileStore):
        """list_directory_items('/') should return an empty list initially."""
        items = file_store.list_directory_items("/")
        assert items == []

    def test_list_root_after_add(self, file_store: FileStore, wiki_with_sample_page: str):
        """After adding a page, list_directory_items should include it."""
        items = file_store.list_directory_items("/")
        assert len(items) == 1
        assert items[0]["title"] == "测试页面"
        assert items[0]["type"] == "page"

    def test_list_directory_with_subdir(self, file_store: FileStore, wiki_with_sample_directory: str):
        """A directory should appear in the parent listing."""
        items = file_store.list_directory_items("/")
        dir_items = [i for i in items if i["type"] == "directory"]
        assert any(d["title"] == "测试目录" for d in dir_items)

    def test_list_nonexistent_directory(self, file_store: FileStore):
        """list_directory_items should return [] for non-existent dirs."""
        assert file_store.list_directory_items("/no-such") == []


class TestFileStoreExport:
    """Tests for wiki export."""

    def test_export_wiki_creates_zip(self, file_store: FileStore, tmp_path: Path):
        """export_wiki should produce a .zip file."""
        output = tmp_path / "export.zip"
        result = file_store.export_wiki(str(output))
        assert os.path.exists(result)
        assert result.endswith(".zip")

    def test_export_wiki_contains_files(self, file_store: FileStore, wiki_with_sample_page: str, tmp_path: Path):
        """Exported zip should contain the created page."""
        output = tmp_path / "wiki_backup.zip"
        result = file_store.export_wiki(str(output))

        import zipfile
        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            # The wiki root dir name should be in the archive
            assert any("test-page.md" in n for n in names)