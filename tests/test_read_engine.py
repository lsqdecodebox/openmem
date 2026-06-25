"""Tests for read_engine.py – progressive search engine."""

from unittest.mock import MagicMock, patch

import pytest

from openmem.read_engine import ReadEngine


class TestReadEngineSearch:
    """Tests for search()."""

    def test_search_no_results(self, read_engine: ReadEngine):
        """search on an empty wiki should return 'no results' message."""
        result = read_engine.search("something")
        assert "没有找到相关的记忆" in result

    def test_search_with_results(self, read_engine: ReadEngine, file_store, wiki_with_sample_page: str):
        """search should return content when matching pages exist."""
        # Mock select_best_match to return our page path
        read_engine.llm_client.select_best_match.return_value = [wiki_with_sample_page]
        read_engine.llm_client.chat_completion.return_value = "这是根据搜索结果生成的回答。"

        result = read_engine.search("测试", max_depth=7, max_results=3)
        assert "这是根据搜索结果生成的回答" in result

    def test_search_respects_max_results(self, read_engine: ReadEngine, file_store):
        """search should limit results to max_results."""
        # Create multiple pages
        for i in range(5):
            file_store.create_page(
                path=f"/page-{i}.md",
                title=f"Page {i}",
                content=f"Content {i}",
                summary=f"Summary {i}",
                parent_path="/",
                tags=[],
                source="test"
            )

        read_engine.llm_client.select_best_match.return_value = [
            "/page-0.md", "/page-1.md", "/page-2.md", "/page-3.md", "/page-4.md"
        ]
        read_engine.llm_client.chat_completion.return_value = "回答。"

        # max_results=2 should only pass 2 results to the answer generator
        read_engine.search("query", max_depth=7, max_results=2)
        call_args = read_engine.llm_client.chat_completion.call_args
        messages = call_args[0][0]  # first positional arg is messages
        context_msg = [m for m in messages if m["role"] == "user"][0]
        # The context should only contain 2 sources
        assert context_msg["content"].count("来源:") == 2

    def test_search_handles_llm_error(self, read_engine: ReadEngine, file_store, wiki_with_sample_page: str):
        """search should not crash when LLM select_best_match raises."""
        # Patch list_directory_items to return items so select_best_match is called,
        # then make select_best_match raise an exception.
        with patch.object(read_engine.file_store, "list_directory_items") as mock_list:
            mock_list.return_value = [
                {"title": "Test", "path": wiki_with_sample_page, "summary": "summary", "type": "page"}
            ]
            read_engine.llm_client.select_best_match.side_effect = Exception("LLM error")
            result = read_engine.search("query")
            # Should fall through gracefully to "no results"
            assert "没有找到相关的记忆" in result

    def test_search_with_results(self, read_engine: ReadEngine, file_store, wiki_with_sample_page: str):
        """search should return content when matching pages exist."""
        # Mock select_best_match to return our page path
        read_engine.llm_client.select_best_match.return_value = [wiki_with_sample_page]
        read_engine.llm_client.chat_completion.return_value = "这是根据搜索结果生成的回答。"

        result = read_engine.search("测试", max_depth=7, max_results=3)
        assert "这是根据搜索结果生成的回答" in result

    def test_search_respects_max_results(self, read_engine: ReadEngine, file_store):
        """search should limit results to max_results."""
        # Create multiple pages
        for i in range(5):
            file_store.create_page(
                path=f"/page-{i}.md",
                title=f"Page {i}",
                content=f"Content {i}",
                summary=f"Summary {i}",
                parent_path="/",
                tags=[],
                source="test"
            )

        read_engine.llm_client.select_best_match.return_value = [
            "/page-0.md", "/page-1.md", "/page-2.md", "/page-3.md", "/page-4.md"
        ]
        read_engine.llm_client.chat_completion.return_value = "回答。"

        # max_results=2 should only pass 2 results to the answer generator
        read_engine.search("query", max_depth=7, max_results=2)
        call_args = read_engine.llm_client.chat_completion.call_args
        messages = call_args[0][0]
        context_msg = [m for m in messages if m["role"] == "user"][0]
        # The context should only contain 2 sources
        assert context_msg["content"].count("来源:") == 2

    def test_search_handles_llm_error(self, read_engine: ReadEngine, file_store, wiki_with_sample_page: str):
        """search should not crash when LLM select_best_match raises."""
        read_engine.llm_client.select_best_match.side_effect = Exception("LLM error")
        result = read_engine.search("query")
        # Should fall through to "no results"
        assert "没有找到相关的记忆" in result


class TestReadEngineRecursiveSearch:
    """Tests for the recursive search internals."""

    def test_recursive_search_enters_directories(self, read_engine: ReadEngine, file_store):
        """_search_recursive should enter subdirectories when LLM selects them."""
        # Create a directory with a page inside
        file_store.create_directory("/sub", "Sub", "Sub dir", "/")
        file_store.create_page("/sub/page.md", "Sub Page", "Sub content", "sub", "/sub")

        # select_best_match receives items from list_directory_items which uses
        # os.path.join (OS-native separators). Return paths that match the exact
        # item["path"] values so the item lookup succeeds.
        def select_mock(query, items, top_k=2):
            for item in items:
                normalized = item["path"].replace("\\", "/")
                if normalized == "/sub":
                    return [item["path"]]  # return actual OS-native path
                if normalized == "/sub/page.md":
                    return [item["path"]]
            return []

        read_engine.llm_client.select_best_match.side_effect = select_mock
        read_engine.llm_client.chat_completion.return_value = "answer text"

        result = read_engine.search("find sub page")
        assert "answer" in result

    def test_recursive_search_respects_max_depth(self, read_engine: ReadEngine):
        """_search_recursive should stop at max_depth."""
        results = []
        read_engine._search_recursive("query", "/", results, max_depth=0, current_level=1)
        assert len(results) == 0


class TestReadEngineGenerateAnswer:
    """Tests for _generate_answer()."""

    def test_generate_answer_with_results(self, read_engine: ReadEngine):
        """_generate_answer should return a formatted answer."""
        read_engine.llm_client.chat_completion.return_value = "这是回答。"

        results = [
            {"path": "/test.md", "title": "Test", "content": "Content", "summary": "Summary"}
        ]
        answer = read_engine._generate_answer("question", results)
        assert answer == "这是回答。"

    def test_generate_answer_no_results(self, read_engine: ReadEngine):
        """_generate_answer should return 'no results' for empty list."""
        answer = read_engine._generate_answer("question", [])
        assert "没有找到相关的记忆" in answer