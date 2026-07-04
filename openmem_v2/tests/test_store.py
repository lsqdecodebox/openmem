import json
from datetime import datetime, timedelta
from pathlib import Path

import frontmatter

from openmem.store import WikiStore
from openmem.utils import parse_frontmatter


def _create_md(path: Path, content: str, metadata: dict | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content)
    if metadata:
        post.metadata = metadata
    with open(path, "w", encoding="utf-8") as f:
        frontmatter.dump(post, f)


class TestWikiStore:
    def setup_method(self, tmp_path_factory=None):
        import tempfile

        self.wiki_root = Path(tempfile.mkdtemp())
        _create_md(
            self.wiki_root / "记忆管理规则.md",
            "# 记忆管理规则\n\n内容",
            {"title": "记忆管理规则", "type": "corepage", "level": 1, "summary": "测试", "tags": ["核心"]},
        )
        _create_md(
            self.wiki_root / "用户偏好习惯.md",
            "# 用户偏好习惯\n\n内容",
            {"title": "用户偏好习惯", "type": "corepage", "level": 1, "summary": "测试", "tags": ["核心"]},
        )
        self.store = WikiStore(self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False})

    def test_get_directory_root(self):
        result_json = self.store.get_directory("/")
        result = json.loads(result_json)

        assert result["type"] == "directory"
        names = [c["name"] for c in result["children"]]
        assert "记忆管理规则.md" in names

    def test_get_directory_subdirectory(self):
        _create_md(
            self.wiki_root / "00-个人" / "健康.md",
            "# 健康",
            {"title": "健康", "type": "page", "level": 2, "summary": "健康", "tags": []},
        )

        result_json = self.store.get_directory("/00-个人")
        result = json.loads(result_json)

        names = [c["name"] for c in result["children"]]
        assert "健康.md" in names

    def test_get_directory_nonexistent(self):
        result = self.store.get_directory("/不存在")
        assert "error" in result or "不存在" in result

    def test_read_memory_existing(self):
        _create_md(
            self.wiki_root / "00-个人" / "测试.md",
            "Hello World",
            {"title": "测试", "type": "page", "level": 2, "summary": "测试", "tags": []},
        )

        content = self.store.read_memory("/00-个人/测试")
        assert "Hello World" in content

    def test_read_memory_nonexistent(self):
        result = self.store.read_memory("/不存在的路径")
        assert "error" in result or "不存在" in result

    def test_write_memory_create_new(self):
        result = self.store.write_memory(
            content="新内容",
            path="/01-工作/项目B",
            tags=["工作"],
        )

        file_path = self.wiki_root / "01-工作" / "项目B.md"
        assert file_path.exists()
        post = parse_frontmatter(file_path)
        assert post.metadata["type"] == "page"
        assert "工作" in post.metadata["tags"]

    def test_write_memory_update_existing(self):
        _create_md(
            self.wiki_root / "01-工作" / "项目A.md",
            "原始内容",
            {"title": "项目A", "type": "page", "level": 2, "summary": "原始", "tags": []},
        )

        store_with_snapshot = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": True}
        )
        result = store_with_snapshot.write_memory(
            content="新增内容",
            path="/01-工作/项目A",
        )

        post = parse_frontmatter(self.wiki_root / "01-工作" / "项目A.md")
        assert "原始内容" in post.content
        assert "新增内容" in post.content

        snapshots_dir = self.wiki_root / ".snapshots"
        if snapshots_dir.exists():
            snapshots = list(snapshots_dir.rglob("*.md"))
            assert len(snapshots) >= 1

    def test_write_memory_depth_exceeded(self):
        deep_path = "/a/b/c/d/e/f/g/h"

        result = self.store.write_memory(content="test", path=deep_path)

        assert "error" in result or "超过" in result

    def test_write_memory_no_path(self):
        result = self.store.write_memory(content="test", path=None)

        result_dict = json.loads(result)
        assert result_dict["status"] == "need_path"

    def test_get_core_principles(self):
        result = self.store.get_core_principles()

        assert "记忆管理规则" in result
        assert "用户偏好习惯" in result

    def test_snapshot_created_before_update(self):
        _create_md(
            self.wiki_root / "测试.md",
            "v1",
            {"title": "测试", "type": "page", "level": 1, "summary": "v1", "tags": []},
        )

        store_with_snapshot = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": True}
        )
        store_with_snapshot.write_memory(content="v2", path="/测试")

        snapshot_dir = self.wiki_root / ".snapshots" / "测试"
        assert snapshot_dir.exists()
        snapshots = list(snapshot_dir.glob("*.md"))
        assert len(snapshots) == 1
        assert "v1" in snapshots[0].read_text(encoding="utf-8")

    def test_snapshot_cleanup(self):
        snapshot_dir = self.wiki_root / ".snapshots" / "测试"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        old_time = datetime.now() - timedelta(days=30)
        old_snapshot = snapshot_dir / "2020-01-01T00-00-00.md"
        old_snapshot.write_text("old", encoding="utf-8")

        import os

        mod_time = old_time.timestamp()
        os.utime(old_snapshot, (mod_time, mod_time))

        store_with_cleanup = WikiStore(
            self.wiki_root,
            max_depth=7,
            snapshot_cfg={"enabled": False, "retention_days": 7},
        )
        store_with_cleanup._cleanup_snapshots()

        assert not old_snapshot.exists()
