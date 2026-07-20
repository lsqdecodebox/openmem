import json
from pathlib import Path

from openmem.initializer import (
    ensure_config,
    ensure_wiki_root,
    ensure_core_prompts,
    initialize,
    DEFAULT_CONFIG,
    CORE_PROMPTS,
)
from openmem.utils import parse_frontmatter


def test_ensure_config_creates_default(tmp_path: Path):
    config_path = tmp_path / "openmem.json"

    result = ensure_config(config_path)

    assert config_path.exists()
    with open(config_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == DEFAULT_CONFIG
    assert result == config_path


def test_ensure_config_skips_existing(tmp_path: Path):
    config_path = tmp_path / "openmem.json"
    custom = {"wiki_root": "./custom"}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(custom, f)

    ensure_config(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["wiki_root"] == "./custom"


def test_ensure_wiki_root_creates_directory(tmp_path: Path):
    wiki_root = tmp_path / "new-wiki"

    ensure_wiki_root(wiki_root)

    assert wiki_root.exists()
    assert wiki_root.is_dir()


def test_ensure_core_prompts_creates_files(tmp_path: Path):
    wiki_root = tmp_path

    ensure_core_prompts(wiki_root)

    for filename in CORE_PROMPTS:
        file_path = wiki_root / filename
        assert file_path.exists()
        post = parse_frontmatter(file_path)
        assert post.metadata["type"] == "corepage"
        assert post.metadata["level"] == 1


def test_ensure_core_prompts_skips_existing(tmp_path: Path):
    wiki_root = tmp_path
    (wiki_root / "记忆管理规则.md").write_text("custom content", encoding="utf-8")

    ensure_core_prompts(wiki_root)

    content = (wiki_root / "记忆管理规则.md").read_text(encoding="utf-8")
    assert "custom content" in content


def test_initialize_full_flow(tmp_path: Path):
    config_path = tmp_path / "openmem.json"
    wiki_root = tmp_path / "wiki"

    initialize(config_path, wiki_root)

    assert config_path.exists()
    assert wiki_root.exists()
    for filename in CORE_PROMPTS:
        assert (wiki_root / filename).exists()
