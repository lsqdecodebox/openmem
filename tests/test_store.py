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
            {"title": "项目A", "type": "page", "level": 2, "summary": "原始", "tags": ["旧标签"]},
        )

        store_with_snapshot = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": True}
        )
        result = store_with_snapshot.write_memory(
            content="新内容",
            path="/01-工作/项目A",
            tags=["新标签"],
            summary="新摘要",
        )

        post = parse_frontmatter(self.wiki_root / "01-工作" / "项目A.md")
        assert post.content.strip() == "新内容"
        assert "原始内容" not in post.content
        assert post.metadata["tags"] == ["新标签"]
        assert post.metadata["summary"] == "新摘要"

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

    def test_write_memory_with_summary(self):
        result = self.store.write_memory(
            content="带摘要的内容",
            path="/01-工作/带摘要",
            summary="自定义摘要",
        )

        file_path = self.wiki_root / "01-工作" / "带摘要.md"
        assert file_path.exists()
        post = parse_frontmatter(file_path)
        assert post.metadata["summary"] == "自定义摘要"

    def test_write_memory_summary_auto_generated(self):
        result = self.store.write_memory(
            content="无摘要内容",
            path="/01-工作/无摘要",
        )

        file_path = self.wiki_root / "01-工作" / "无摘要.md"
        assert file_path.exists()
        post = parse_frontmatter(file_path)
        assert post.metadata["summary"] != ""

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

    def test_get_directory_excludes_asset_dirs(self):
        for t in ("images", "files", "videos"):
            d = self.wiki_root / t
            d.mkdir(parents=True, exist_ok=True)
            (d / "asset.bin").write_bytes(b"x")

        result = json.loads(self.store.get_directory("/"))
        names = [c["name"] for c in result["children"]]
        assert "images" not in names
        assert "files" not in names
        assert "videos" not in names

    def test_read_memory_rejects_asset_path(self):
        for p in ("images/a/png", "files/a/bin", "videos/a/mp4"):
            r = self.store.read_memory(p)
            assert "error" in r and "资产目录" in r

    def test_write_memory_rejects_asset_path(self):
        for p in ("/images/a/png", "/files/a/bin", "/videos/a/mp4"):
            r = self.store.write_memory(content="x", path=p)
            assert "error" in r and "资产目录" in r

        for t in ("images", "files", "videos"):
            assert not (self.wiki_root / t).exists()


class TestDirectorySummaryAndCompression:
    def setup_method(self):
        import tempfile

        self.wiki_root = Path(tempfile.mkdtemp())
        self.store = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False}
        )

    def test_get_directory_no_title_field(self):
        _create_md(
            self.wiki_root / "00-个人" / "学习.md",
            "# 学习",
            {"title": "学习", "type": "page", "level": 2, "summary": "学习记录", "tags": []},
        )
        result = json.loads(self.store.get_directory("/00-个人"))
        for c in result["children"]:
            assert "title" not in c

    def test_summary_md_promoted_to_dir_meta(self):
        _create_md(
            self.wiki_root / "00-个人" / "summary.md",
            "",
            {
                "title": "summary",
                "type": "directory_summary",
                "level": 1,
                "summary": "个人信息总览",
                "tags": ["个人"],
            },
        )
        _create_md(
            self.wiki_root / "00-个人" / "健康.md",
            "# 健康",
            {"title": "健康", "type": "page", "level": 2, "summary": "健康", "tags": []},
        )
        result = json.loads(self.store.get_directory("/"))
        dir_node = next(c for c in result["children"] if c["name"] == "00-个人")
        assert dir_node["summary"] == "个人信息总览"
        assert dir_node["tags"] == ["个人"]
        names = [c["name"] for c in dir_node["children"]]
        assert "summary.md" not in names
        assert "健康.md" in names

    def test_write_memory_summary_path(self):
        result = self.store.write_memory(
            content="应被忽略的正文",
            path="/00-个人/summary",
            summary="个人信息总览",
            tags=["个人"],
        )
        assert json.loads(result)["status"] == "ok"

        file_path = self.wiki_root / "00-个人" / "summary.md"
        assert file_path.exists()
        post = parse_frontmatter(file_path)
        assert post.metadata["type"] == "directory_summary"
        assert post.metadata["summary"] == "个人信息总览"
        assert post.content.strip() == ""

    def test_read_memory_can_read_summary(self):
        _create_md(
            self.wiki_root / "00-个人" / "summary.md",
            "",
            {
                "title": "summary",
                "type": "directory_summary",
                "level": 1,
                "summary": "个人信息总览",
                "tags": ["个人"],
            },
        )
        content = self.store.read_memory("/00-个人/summary")
        assert "个人信息总览" in content
        assert "directory_summary" in content

    def test_compression_triggered_when_over_limit(self):
        for i in range(5):
            _create_md(
                self.wiki_root / "00-个人" / f"文件{i}.md",
                f"# 文件{i}",
                {"title": f"文件{i}", "type": "page", "level": 2, "summary": f"摘要{i}", "tags": []},
            )
        store = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False}, max_chars=200
        )
        result = json.loads(store.get_directory("/00-个人"))
        assert "_compressed_filecount" in result
        assert result["_compressed_filecount"] == 5
        assert "_compressed_filenames" in result
        assert len(result["children"]) == 0 or all(
            c["type"] == "directory" for c in result["children"]
        )

    def test_compression_excludes_summary_md(self):
        _create_md(
            self.wiki_root / "00-个人" / "summary.md",
            "",
            {
                "title": "summary",
                "type": "directory_summary",
                "level": 1,
                "summary": "总览",
                "tags": [],
            },
        )
        for i in range(5):
            _create_md(
                self.wiki_root / "00-个人" / f"文件{i}.md",
                f"# 文件{i}",
                {"title": f"文件{i}", "type": "page", "level": 2, "summary": f"摘要{i}", "tags": []},
            )
        store = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False}, max_chars=200
        )
        result = json.loads(store.get_directory("/"))
        dir_node = next(c for c in result["children"] if c["name"] == "00-个人")
        assert dir_node["summary"] == "总览"
        assert dir_node["_compressed_filecount"] == 5
        assert "summary.md" not in dir_node["_compressed_filenames"]

    def test_compression_bottom_up(self):
        for i in range(3):
            _create_md(
                self.wiki_root / "00-个人" / "学习" / f"文件{i}.md",
                f"# 文件{i}",
                {"title": f"文件{i}", "type": "page", "level": 3, "summary": f"摘要{i}", "tags": []},
            )
            _create_md(
                self.wiki_root / "01-工作" / f"文件{i}.md",
                f"# 工作{i}",
                {"title": f"工作{i}", "type": "page", "level": 2, "summary": f"工作摘要{i}", "tags": []},
            )
        store = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False}, max_chars=300
        )
        result = json.loads(store.get_directory("/"))

        deep_dir = next(c for c in result["children"] if c["name"] == "00-个人")
        deep_sub = next(c for c in deep_dir["children"] if c["name"] == "学习")
        assert "_compressed_filecount" in deep_sub
        assert deep_sub["_compressed_filecount"] == 3

    def test_compressed_filenames_truncated_50(self):
        for i in range(20):
            _create_md(
                self.wiki_root / "00-个人" / f"超长文件名编号{i}.md",
                f"# 文件{i}",
                {"title": f"文件{i}", "type": "page", "level": 2, "summary": f"摘要{i}", "tags": []},
            )
        store = WikiStore(
            self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False}, max_chars=100
        )
        result = json.loads(store.get_directory("/00-个人"))
        assert len(result["_compressed_filenames"]) <= 50


class TestWriteAsset:
    def setup_method(self):
        import tempfile

        self.wiki_root = Path(tempfile.mkdtemp())
        self.store = WikiStore(self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False})

    def test_write_asset_from_file(self):
        import tempfile

        raw_data = b"hello world binary data"

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(raw_data)
            temp_path = f.name

        try:
            result = self.store.write_asset(
                source=temp_path,
                path="01-工作/项目A",
                filename="test.bin",
                type="files",
            )

            parsed = json.loads(result)
            assert parsed["status"] == "ok"
            assert parsed["type"] == "files"
            assert parsed["filename"] == "test.bin"
            assert parsed["size"] == len(raw_data)

            saved_path = self.wiki_root / "files" / "01-工作" / "项目A" / "test.bin"
            assert saved_path.exists()
            assert saved_path.read_bytes() == raw_data
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_write_asset_images(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png content")
            temp_path = f.name

        try:
            result = self.store.write_asset(
                source=temp_path,
                path="01-工作/项目A",
                filename="diagram.png",
                type="images",
            )

            parsed = json.loads(result)
            assert parsed["status"] == "ok"
            assert parsed["type"] == "images"
            assert parsed["filename"] == "diagram.png"

            saved_path = self.wiki_root / "images" / "01-工作" / "项目A" / "diagram.png"
            assert saved_path.exists()
            assert saved_path.read_bytes() == b"fake png content"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_write_asset_overwrite_false(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"v1")
            temp_path = f.name

        try:
            self.store.write_asset(
                source=temp_path,
                path="01-工作",
                filename="data.bin",
                type="files",
            )

            result = self.store.write_asset(
                source=temp_path,
                path="01-工作",
                filename="data.bin",
                type="files",
                overwrite=False,
            )

            parsed = json.loads(result)
            assert parsed["status"] == "file_exists"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_write_asset_overwrite_true(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"v1")
            temp_path_v1 = f.name

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"v2_new")
            temp_path_v2 = f.name

        try:
            self.store.write_asset(
                source=temp_path_v1,
                path="01-工作",
                filename="data.bin",
                type="files",
            )

            result = self.store.write_asset(
                source=temp_path_v2,
                path="01-工作",
                filename="data.bin",
                type="files",
                overwrite=True,
            )

            parsed = json.loads(result)
            assert parsed["status"] == "ok"
            assert parsed["size"] == len(b"v2_new")

            saved_path = self.wiki_root / "files" / "01-工作" / "data.bin"
            assert saved_path.read_bytes() == b"v2_new"
        finally:
            Path(temp_path_v1).unlink(missing_ok=True)
            Path(temp_path_v2).unlink(missing_ok=True)

    def test_write_asset_invalid_type(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"data")
            temp_path = f.name

        try:
            result = self.store.write_asset(
                source=temp_path,
                path="01-工作",
                filename="data.bin",
                type="invalid",
            )

            parsed = json.loads(result)
            assert parsed["status"] == "error"
            assert "不支持的文件类型" in parsed["message"]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_write_asset_empty_filename(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"data")
            temp_path = f.name

        try:
            result = self.store.write_asset(
                source=temp_path,
                path="01-工作",
                filename="",
                type="files",
            )

            parsed = json.loads(result)
            assert parsed["status"] == "error"
            assert "filename" in parsed["message"]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_write_asset_source_not_exist(self):
        result = self.store.write_asset(
            source="/nonexistent/file.png",
            path="01-工作",
            filename="file.png",
            type="images",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "文件不存在" in parsed["message"]

    def test_write_asset_source_not_file(self):
        result = self.store.write_asset(
            source=str(self.wiki_root),
            path="01-工作",
            filename="file.bin",
            type="files",
        )

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "路径不是文件" in parsed["message"]

    def test_write_asset_videos(self):
        import tempfile

        raw_data = b"video bytes"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(raw_data)
            temp_path = f.name

        try:
            result = self.store.write_asset(
                source=temp_path,
                path="02-学习",
                filename="video.mp4",
                type="videos",
            )

            parsed = json.loads(result)
            assert parsed["status"] == "ok"
            assert parsed["type"] == "videos"

            saved_path = self.wiki_root / "videos" / "02-学习" / "video.mp4"
            assert saved_path.exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestReadAsset:
    def setup_method(self):
        import tempfile

        self.wiki_root = Path(tempfile.mkdtemp())
        self.store = WikiStore(self.wiki_root, max_depth=7, snapshot_cfg={"enabled": False})

    def test_read_asset_existing(self):
        asset_path = self.wiki_root / "files" / "01-工作" / "data.bin"
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"hello asset")

        result = self.store.read_asset("files/01-工作/data.bin")

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["relative_path"] == "files/01-工作/data.bin"
        assert parsed["absolute_path"] == str(asset_path.resolve())
        assert parsed["size"] == len(b"hello asset")

    def test_read_asset_not_exist(self):
        result = self.store.read_asset("images/nonexistent/file.png")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "不存在" in parsed["message"]

    def test_read_asset_not_file(self):
        dir_path = self.wiki_root / "images" / "subdir"
        dir_path.mkdir(parents=True, exist_ok=True)

        result = self.store.read_asset("images/subdir")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "不是文件" in parsed["message"]

    def test_read_asset_empty_path(self):
        result = self.store.read_asset("")

        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "path" in parsed["message"]

    def test_read_asset_path_traversal(self):
        result = self.store.read_asset("../../../etc/passwd")

        parsed = json.loads(result)
        assert parsed["status"] == "error"

    def test_read_asset_videos(self):
        asset_path = self.wiki_root / "videos" / "02-学习" / "video.mp4"
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"video content")

        result = self.store.read_asset("videos/02-学习/video.mp4")

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["relative_path"] == "videos/02-学习/video.mp4"
