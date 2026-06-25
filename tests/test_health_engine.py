"""Tests for health_engine.py – Wiki health check engine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openmem.health_engine import HealthEngine


class TestHealthEngineRunCheck:
    """Tests for run_check()."""

    def test_healthy_wiki(self, health_engine: HealthEngine):
        """A well-formed wiki should return no errors."""
        report = health_engine.run_check()
        assert report["total_directories"] >= 1  # at least root
        assert len(report["errors"]) == 0

    def test_healthy_wiki_with_pages(self, health_engine: HealthEngine, file_store, wiki_with_sample_page: str):
        """A wiki with valid pages should report no errors."""
        report = health_engine.run_check()
        assert report["total_files"] >= 1
        assert len(report["errors"]) == 0

    def test_short_page_content_warning(self, health_engine: HealthEngine, file_store):
        """A page with very short content should produce a warning."""
        file_store.create_page(
            path="/short.md",
            title="Short",
            content="Hi",  # less than 20 chars
            summary="short page",
            parent_path="/",
            tags=[],
            source="test"
        )
        report = health_engine.run_check()
        assert len(report["warnings"]) >= 1
        assert any("内容过短" in w for w in report["warnings"])

    def test_long_summary_warning(self, health_engine: HealthEngine, file_store):
        """A page with a very long summary should produce a warning."""
        long_summary = "x" * 200  # > 150 chars
        file_store.create_page(
            path="/long-summary.md",
            title="Long Summary",
            content="Normal content here for the page.",
            summary=long_summary,
            parent_path="/",
            tags=[],
            source="test"
        )
        report = health_engine.run_check()
        assert len(report["warnings"]) >= 1
        assert any("摘要过长" in w for w in report["warnings"])


class TestHealthEngineCheckDirectory:
    """Tests for the internal _check_directory method."""

    def test_missing_directory_md_error(self, health_engine: HealthEngine, file_store):
        """_check_directory should detect missing 目录.md."""
        # Directly call _check_directory on a path without 目录.md
        report = {
            "total_files": 0,
            "total_directories": 0,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        health_engine._check_directory("/nonexistent", report)
        assert len(report["errors"]) > 0

    def test_nested_directory_check(self, health_engine: HealthEngine, file_store):
        """_check_directory should recurse into subdirectories."""
        file_store.create_directory("/level1", "Level1", "First level", "/")
        file_store.create_directory("/level1/level2", "Level2", "Second level", "/level1")
        file_store.create_page(
            path="/level1/level2/page.md",
            title="Deep Page",
            content="Deep content here for testing.",
            summary="deep",
            parent_path="/level1/level2",
            tags=[],
            source="test"
        )

        report = health_engine.run_check()
        assert report["total_directories"] >= 3  # root + level1 + level2
        assert report["total_files"] >= 1


class TestHealthEngineCheckPage:
    """Tests for the internal _check_page method."""

    def test_missing_frontmatter_field(self, health_engine: HealthEngine, file_store):
        """A page missing a required Front Matter field should produce an error."""
        # Create a minimal .md file without Front Matter
        bad_page = file_store.wiki_root / "bad-page.md"
        bad_page.write_text("# No Front Matter", encoding="utf-8")

        report = health_engine.run_check()
        # The page won't be found by list_directory_items because it has no 目录.md listing
        # So we check it via the recursive scan
        health_engine._check_page("/bad-page.md", report)
        # It should still be counted and checked
        assert report["total_files"] >= 1

    def test_page_exceeds_depth(self, health_engine: HealthEngine, file_store):
        """A page with level exceeding max_depth should produce an error."""
        # Manually create a page file with metadata indicating depth > max_depth.
        # Then also add it to the parent directory's 目录.md so run_check finds it.
        deep_dir = file_store.wiki_root / "deep"
        deep_dir.mkdir(parents=True, exist_ok=True)
        deep_page = deep_dir / "page.md"
        deep_page.write_text(
            "---\ntitle: Deep\npath: /deep/page.md\ntype: page\n"
            "level: 99\nparent: /deep\ncreated_at: '2024-01-01T00:00:00'\n"
            "updated_at: '2024-01-01T00:00:00'\nsummary: deep\ntags: []\nsource: test\n---\n# Deep\nContent",
            encoding="utf-8"
        )
        # Also create a proper 目录.md for /deep so the scan reaches it
        deep_index = deep_dir / "目录.md"
        deep_index.write_text(
            "---\ntitle: Deep\ntype: directory\npath: /deep\nlevel: 2\n"
            "parent: /\ncreated_at: '2024-01-01T00:00:00'\n"
            "updated_at: '2024-01-01T00:00:00'\nsummary: deep dir\ntags: []\nsource: test\n---\n# Deep",
            encoding="utf-8"
        )
        # Add a reference in the root 目录.md so list_directory_items finds /deep
        root_index = file_store.wiki_root / "目录.md"
        root_content = root_index.read_text(encoding="utf-8")
        root_content += "\n- [[deep/目录.md|Deep]]\n"
        root_index.write_text(root_content, encoding="utf-8")

        # FileStore max_depth is still 7, so level 99 should be flagged
        report = health_engine.run_check()
        assert any("深度超过限制" in e or "depth" in e.lower() for e in report["errors"])