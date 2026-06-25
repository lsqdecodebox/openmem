"""Tests for llm_client.py – OpenAI-compatible LLM client."""

from unittest.mock import MagicMock, patch

import pytest

from openmem.llm_client import LLMClient


@pytest.fixture
def llm_config():
    return {
        "base_url": "https://api.openai.com/v1",
        "api_key": "test-key",
        "small_model": "gpt-4o-mini",
        "large_model": "gpt-4o",
        "timeout": 5
    }


@pytest.fixture
def client(llm_config: dict) -> LLMClient:
    return LLMClient(llm_config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_init_stores_config(self, llm_config: dict):
        """LLMClient should store config values."""
        client = LLMClient(llm_config)
        assert client.base_url == "https://api.openai.com/v1"
        assert client.small_model == "gpt-4o-mini"
        assert client.large_model == "gpt-4o"

    def test_init_creates_openai_client(self, llm_config: dict):
        """LLMClient should instantiate an OpenAI client."""
        client = LLMClient(llm_config)
        assert client.client is not None

    def test_init_with_defaults(self):
        """LLMClient should apply defaults for missing config keys."""
        with patch("openmem.llm_client.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = MagicMock()
            client = LLMClient({})
            assert client.base_url == "https://api.openai.com/v1"
            assert client.small_model == "gpt-4o-mini"
            assert client.timeout == 30


class TestLLMClientChatCompletion:
    """Tests for chat_completion()."""

    def test_chat_completion_success(self, client: LLMClient):
        """chat_completion should return the response content."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello world"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        result = client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            use_large_model=False
        )
        assert result == "Hello world"

    def test_chat_completion_uses_large_model(self, client: LLMClient):
        """When use_large_model=True, the large model should be used."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            use_large_model=True
        )
        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"

    def test_chat_completion_uses_small_model(self, client: LLMClient):
        """When use_large_model=False, the small model should be used."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            use_large_model=False
        )
        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_chat_completion_raises_on_error(self, client: LLMClient):
        """chat_completion should raise when the API call fails."""
        client.client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
        with pytest.raises(Exception, match="API error"):
            client.chat_completion([{"role": "user", "content": "Hi"}])


class TestLLMClientGenerateSummary:
    """Tests for generate_summary()."""

    def test_generate_summary_calls_chat(self, client: LLMClient):
        """generate_summary should delegate to chat_completion."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "摘要内容"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        result = client.generate_summary("这是一段很长的内容需要总结。")
        assert result == "摘要内容"

    def test_generate_summary_uses_small_model(self, client: LLMClient):
        """generate_summary should use the small model."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "summary"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        client.generate_summary("some content")
        call_kwargs = client.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == client.small_model


class TestLLMClientSelectBestMatch:
    """Tests for select_best_match()."""

    def test_select_best_match_returns_paths(self, client: LLMClient):
        """select_best_match should return selected paths."""
        candidates = [
            {"title": "Python", "summary": "Python programming", "path": "/python"},
            {"title": "Java", "summary": "Java programming", "path": "/java"},
        ]
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "1,2"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        result = client.select_best_match("programming languages", candidates, top_k=2)
        assert result == ["/python", "/java"]

    def test_select_best_match_empty_candidates(self, client: LLMClient):
        """select_best_match should return empty list for empty candidates without calling LLM."""
        # Mock the underlying OpenAI chat.completions.create so it's never called
        # when candidates is empty (the early return should prevent API calls).
        original_create = client.client.chat.completions.create
        client.client.chat.completions.create = MagicMock(side_effect=Exception("Should not be called"))

        result = client.select_best_match("query", [], top_k=2)
        assert result == []
        client.client.chat.completions.create.assert_not_called()

    def test_select_best_match_invalid_indices(self, client: LLMClient):
        """select_best_match should handle non-numeric LLM output gracefully."""
        candidates = [
            {"title": "Python", "summary": "Python", "path": "/python"},
        ]
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "invalid"
        client.client.chat.completions.create = MagicMock(return_value=mock_response)

        result = client.select_best_match("query", candidates, top_k=1)
        assert result == []