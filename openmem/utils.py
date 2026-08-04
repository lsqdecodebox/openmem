import re
import logging
from pathlib import Path
from dataclasses import dataclass

import frontmatter

logger = logging.getLogger(__name__)

SUMMARY_FILENAME = "summary.md"


@dataclass
class PathValidation:
    valid: bool
    depth: int
    message: str


def validate_path_depth(path: str, max_depth: int = 7) -> PathValidation:
    if path == "/" or path == "":
        return PathValidation(valid=True, depth=0, message="根目录")

    parts = path.strip("/").split("/")
    depth = len(parts)

    if depth > max_depth:
        return PathValidation(
            valid=False,
            depth=depth,
            message=f"路径深度{depth}超过最大限制{max_depth}",
        )

    return PathValidation(valid=True, depth=depth, message="校验通过")


def sanitize_path(path: str) -> str:
    if not path:
        return path

    path = path.replace("\\", "/")
    path = re.sub(r"/+", "/", path)

    parts = path.split("/")
    safe_parts = []
    for part in parts:
        if part == ".." or part == ".":
            continue
        if part.strip():
            safe_parts.append(part.strip())

    result = "/".join(safe_parts)
    if path.startswith("/"):
        result = "/" + result

    return result


def compute_level(path: str) -> int:
    if path == "/" or path == "":
        return 1
    parts = path.strip("/").split("/")
    return len(parts)


def parse_frontmatter(file_path: Path) -> frontmatter.Post:
    with open(file_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    return post


def build_frontmatter(
    title: str, type_: str, level: int, summary: str, tags: list[str]
) -> dict:
    return {
        "title": title,
        "type": type_,
        "level": level,
        "summary": summary,
        "tags": tags,
    }


def count_content_chars(content: str) -> int:
    plain = _strip_markdown(content)
    return len(plain.strip())


def _strip_markdown(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^[#]+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"---+", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def validate_frontmatter(metadata: dict) -> tuple[bool, list[str]]:
    required_fields = ["title", "type", "level", "summary", "tags"]
    missing = []

    for field in required_fields:
        if field not in metadata or metadata[field] is None:
            missing.append(field)

    is_valid = len(missing) == 0
    return (is_valid, missing)


def is_core_page(file_path: Path, wiki_root: Path) -> bool:
    if file_path.suffix != ".md":
        return False
    return file_path.parent == wiki_root


def is_directory_summary(entry: Path) -> bool:
    """判断文件是否为目录的 summary.md"""
    return entry.is_file() and entry.name == SUMMARY_FILENAME


def build_compressed_filenames(filenames: list[str]) -> tuple[int, str]:
    """
    输入被压缩的文件名列表，返回 (count, filenames_str)
    filenames_str 为文件名按序拼接、整体截断 50 字
    """
    names = "；".join(filenames)
    if len(names) > 50:
        names = names[:50]
    return len(filenames), names
