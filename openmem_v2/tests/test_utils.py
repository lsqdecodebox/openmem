from pathlib import Path

from openmem.utils import (
    validate_path_depth,
    sanitize_path,
    compute_level,
    merge_content,
    count_content_chars,
    validate_frontmatter,
    is_core_page,
)


def test_validate_path_depth_valid():
    result = validate_path_depth("/a/b/c", max_depth=7)
    assert result.valid is True
    assert result.depth == 3


def test_validate_path_depth_exceeded():
    result = validate_path_depth("/a/b/c/d/e/f/g/h", max_depth=7)
    assert result.valid is False
    assert result.depth == 8


def test_validate_path_depth_root():
    result = validate_path_depth("/", max_depth=7)
    assert result.valid is True
    assert result.depth == 0


def test_sanitize_path_removes_traversal():
    result = sanitize_path("/a/../b/./c")
    assert result == "/a/b/c"


def test_sanitize_path_normalizes_slashes():
    result = sanitize_path("//a///b//")
    assert result == "/a/b"


def test_sanitize_path_empty():
    result = sanitize_path("")
    assert result == ""


def test_compute_level():
    assert compute_level("/") == 1
    assert compute_level("/a") == 1
    assert compute_level("/a/b") == 2
    assert compute_level("/a/b/c") == 3


def test_merge_content_append():
    result = merge_content("原始内容", "新增内容")
    assert "原始内容" in result
    assert "新增内容" in result
    assert "---" in result


def test_merge_content_duplicate():
    result = merge_content("原始内容", "原始内容")
    assert result.count("原始内容") == 1


def test_merge_content_empty_new():
    result = merge_content("原始内容", "")
    assert result == "原始内容"


def test_merge_content_empty_existing():
    result = merge_content("", "新内容")
    assert result == "新内容"


def test_count_content_chars():
    content = "# 标题\n\n这是正文内容"
    count = count_content_chars(content)
    assert count > 0


def test_validate_frontmatter_complete():
    metadata = {
        "title": "test",
        "type": "page",
        "level": 1,
        "summary": "s",
        "tags": [],
    }
    is_valid, missing = validate_frontmatter(metadata)
    assert is_valid is True
    assert len(missing) == 0


def test_validate_frontmatter_incomplete():
    metadata = {"title": "test"}
    is_valid, missing = validate_frontmatter(metadata)
    assert is_valid is False
    assert "type" in missing
    assert "level" in missing


def test_is_core_page():
    wiki_root = Path("/wiki")
    core_file = wiki_root / "记忆管理规则.md"
    sub_file = wiki_root / "00-个人" / "健康.md"

    assert is_core_page(core_file, wiki_root) is True
    assert is_core_page(sub_file, wiki_root) is False
