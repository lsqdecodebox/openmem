import json
from pathlib import Path

import frontmatter

from openmem.store import WikiStore


def _create_md(path: Path, content: str, metadata: dict | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content)
    if metadata:
        post.metadata = metadata
    with open(path, "w", encoding="utf-8") as f:
        frontmatter.dump(post, f)


class TestMCPAPI:
    def setup_method(self):
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
        self.store = WikiStore(self.wiki_root, snapshot_cfg={"enabled": False})

    def test_get_directory_returns_json(self):
        result = self.store.get_directory("/")

        parsed = json.loads(result)
        assert parsed["type"] == "directory"
        assert "children" in parsed

    def test_read_memory_returns_content(self):
        _create_md(
            self.wiki_root / "测试页面.md",
            "测试正文",
            {"title": "测试页面", "type": "page", "level": 1, "summary": "测试", "tags": []},
        )

        result = self.store.read_memory("/测试页面")

        assert "---" in result
        assert "title:" in result

    def test_write_memory_returns_path(self):
        result = self.store.write_memory(content="测试内容", path="/测试页面")

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["path"] == "/测试页面"

    def test_core_principles_prompt(self):
        result = self.store.get_core_principles()

        assert len(result) > 0
        assert "记忆管理规则" in result
