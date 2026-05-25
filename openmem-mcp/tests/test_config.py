"""Tests for config.py – configuration loading and properties."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from config import Config


class TestConfigInitialization:
    """Tests for Config loading and initialization."""

    def test_load_config_success(self, config_file: Path):
        """Config should load from a valid JSON file."""
        cfg = Config(str(config_file))
        assert cfg._config["wiki_root"] == "./test_wiki"
        assert cfg._config["max_depth"] == 7

    def test_load_config_file_not_found(self):
        """Config should raise FileNotFoundError when file is missing."""
        with pytest.raises(FileNotFoundError):
            Config("nonexistent_config.json")

    def test_load_config_invalid_json(self, tmp_path: Path):
        """Config should raise JSONDecodeError for malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json}", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            Config(str(bad_file))


class TestConfigProperties:
    """Tests for Config property accessors."""

    @pytest.fixture
    def cfg(self, config_file: Path) -> Config:
        return Config(str(config_file))

    def test_wiki_root(self, cfg: Config):
        """wiki_root should be an absolute Path."""
        root = cfg.wiki_root
        assert isinstance(root, Path)
        assert root.is_absolute()

    def test_llm_config(self, cfg: Config):
        """llm_config should return the llm dict."""
        llm = cfg.llm_config
        assert llm["base_url"] == "https://api.openai.com/v1"
        assert llm["api_key"] == "test-key"

    def test_max_depth(self, cfg: Config):
        """max_depth should return the configured depth."""
        assert cfg.max_depth == 7

    def test_default_tags(self, cfg: Config):
        """default_tags should return an empty list when unset."""
        assert cfg.default_tags == []

    def test_logging_level(self, cfg: Config):
        """logging_level should return the configured level."""
        assert cfg.logging_level == "ERROR"


class TestConfigSave:
    """Tests for Config.save()."""

    def test_save_updates_file(self, config_file: Path):
        """save() should persist changes back to disk."""
        cfg = Config(str(config_file))
        cfg._config["max_depth"] = 10
        cfg.save()

        # Reload and verify
        cfg2 = Config(str(config_file))
        assert cfg2.max_depth == 10