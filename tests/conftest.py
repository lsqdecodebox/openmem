"""Shared test fixtures for OpenMem MCP tests."""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, patch

import pytest

from openmem.config import Config
from openmem.file_store import FileStore
from openmem.llm_client import LLMClient
from openmem.write_engine import WriteEngine
from openmem.read_engine import ReadEngine
from openmem.health_engine import HealthEngine


# ---------------------------------------------------------------------------
# Helper: create a minimal config JSON on disk
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def minimal_config_dict() -> Dict[str, Any]:
    return {
        "wiki_root": "./test_wiki",
        "max_depth": 7,
        "default_tags": [],
        "llm": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "small_model": "gpt-4o-mini",
            "large_model": "gpt-4o",
            "timeout": 5
        },
        "logging": {
            "level": "ERROR"
        }
    }


@pytest.fixture
def config_file(tmp_path: Path, minimal_config_dict: Dict[str, Any]) -> Path:
    """Create a temporary openmem.json config file."""
    cfg_path = tmp_path / "openmem.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(minimal_config_dict, f, indent=2, ensure_ascii=False)
    return cfg_path


@pytest.fixture
def config(config_file: Path) -> Config:
    """Return a Config instance backed by the temporary config file."""
    return Config(str(config_file))


# ---------------------------------------------------------------------------
# Fixtures for components that require a real (temporary) wiki root
# ---------------------------------------------------------------------------

@pytest.fixture
def wiki_root(tmp_path: Path) -> Path:
    """A temporary directory used as the wiki root."""
    root = tmp_path / "test_wiki"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def file_store(wiki_root: Path) -> FileStore:
    """FileStore backed by a temporary wiki root."""
    return FileStore(wiki_root, max_depth=7)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """A fully mocked LLMClient (no real API calls)."""
    client = MagicMock(spec=LLMClient)
    client.chat_completion.return_value = "测试标题"
    client.generate_summary.return_value = "这是一个测试摘要。"
    client.select_best_match.return_value = []
    return client


@pytest.fixture
def write_engine(file_store: FileStore, mock_llm_client: MagicMock) -> WriteEngine:
    """WriteEngine with mocked LLM client."""
    return WriteEngine(file_store, mock_llm_client)


@pytest.fixture
def read_engine(file_store: FileStore, mock_llm_client: MagicMock) -> ReadEngine:
    """ReadEngine with mocked LLM client."""
    return ReadEngine(file_store, mock_llm_client)


@pytest.fixture
def health_engine(file_store: FileStore, mock_llm_client: MagicMock) -> HealthEngine:
    """HealthEngine with mocked LLM client."""
    return HealthEngine(file_store, mock_llm_client)


# ---------------------------------------------------------------------------
# Helper to create a page fixture in the wiki
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_page_path() -> str:
    return "/test-page.md"


@pytest.fixture
def wiki_with_sample_page(file_store: FileStore, sample_page_path: str) -> str:
    """Create a sample page in the wiki and return its path."""
    file_store.create_page(
        path=sample_page_path,
        title="测试页面",
        content="# 测试页面\n\n这是测试内容。",
        summary="测试摘要",
        parent_path="/",
        tags=["test"],
        source="test"
    )
    return sample_page_path


@pytest.fixture
def wiki_with_sample_directory(file_store: FileStore) -> str:
    """Create a sample directory in the wiki and return its path."""
    file_store.create_directory(
        path="/测试目录",
        title="测试目录",
        summary="测试目录摘要",
        parent_path="/"
    )
    return "/测试目录"