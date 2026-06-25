import logging
import os
from pathlib import Path
from fastmcp import FastMCP
from config import Config
from file_store import FileStore
from llm_client import LLMClient
from write_engine import WriteEngine
from read_engine import ReadEngine
from health_engine import HealthEngine

# 先创建logger但不配置处理器（配置推迟到加载config后）
logger = logging.getLogger(__name__)

# 初始化MCP服务
mcp = FastMCP("Personal Wiki Memory")

# 加载配置
config = Config("openmem.json")

# 配置日志 - 日志文件放在wiki_root目录中
log_dir = config.wiki_root
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / "openmem.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_path), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 初始化组件
file_store = FileStore(config.wiki_root, config.max_depth)
llm_client = LLMClient(config.llm_config)

# 初始化引擎
write_engine = WriteEngine(file_store, llm_client)
read_engine = ReadEngine(file_store, llm_client)
health_engine = HealthEngine(file_store, llm_client)

logger.info("OpenMem MCP服务启动成功")

# 注册MCP工具
@mcp.tool()
def add_memory(content: str, suggested_path: str = None, tags: list[str] = None) -> str:
    """
    Add a new memory and automatically classify it to the best Wiki location.

    Uses LLM-powered analysis to understand the content and determine the optimal path
    under the Wiki root. Creates intermediate directories and a directory summary page
    when needed.

    Modes:
    - When suggested_path is provided: place the memory under that path as a hint
    - When suggested_path is None: auto-classify based on content semantics

    Use when:
    - You have new information, knowledge, or notes to persist
    - You want the system to automatically organize content into the Wiki structure
    - You want to capture conversation insights or personal learnings

    Args:
        content: The memory content to add (Markdown formatted text)
        suggested_path: Optional suggested path, e.g. "/00-Personal/Learning"
        tags: Optional list of tags for categorization

    Returns:
        Path of the newly created or updated page
    """
    try:
        return write_engine.add_memory(content, suggested_path, tags)
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        return f"错误: {str(e)}"

@mcp.tool()
def update_memory(path: str, content: str, mode: str = "merge") -> bool:
    """
    Update an existing Wiki page at the specified path.

    Supports three update modes for flexible content management:
    - merge: intelligently merge new content with existing content (LLM-assisted)
    - append: append new content to the end of the existing page
    - overwrite: completely replace the existing page content

    Use when:
    - You want to update or revise an existing memory or note
    - You need to add supplementary information to a page
    - You want to correct or replace outdated content

    Requires: Complete page path obtained from search_memories or get_directory

    Args:
        path: Full page path, e.g. "/00-Personal/Learning/Python-notes.md"
        content: The new content to write
        mode: Update mode: merge(intelligent merge)/append(append)/overwrite(overwrite)

    Returns:
        Whether the update was successful
    """
    try:
        return write_engine.update_memory(path, content, mode)
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        return False

@mcp.tool()
def search_memories(query: str, max_depth: int = 7, max_results: int = 3) -> str:
    """
    Search memories by progressively exploring the Wiki from the root directory.

    Uses a depth-first, LLM-guided search strategy:
    - Starts at the root directory and reads directory summaries
    - Follows the most relevant branches based on the query
    - Returns structured results with matched content and explanations

    Progressive loading levels:
    - Level 1: directory overviews and summaries
    - Level 2: individual page content inspection
    - Level 3: cross-page synthesis and answer generation

    Use when:
    - You want to find relevant memories or notes by topic or keyword
    - You need to recall information previously stored in the Wiki
    - You want a synthesized answer drawn from multiple pages
    - You don't know the exact page path and need to discover it

    Args:
        query: The search query describing what to find
        max_depth: Maximum directory depth to search, default 7
        max_results: Maximum number of results to return, default 3

    Returns:
        Structured search results with matched content and answers
    """
    try:
        return read_engine.search(query, max_depth, max_results)
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        return f"错误: {str(e)}"

@mcp.tool()
def get_page(path: str) -> str:
    """
    Retrieve the full content of a specific Wiki page by its path.

    Returns the complete page including Front Matter metadata and Markdown body content.
    Use this after discovering a page path via search_memories or get_directory.

    Use when:
    - You have a specific page path from search_memories or get_directory
    - You need to inspect a page's full content in detail
    - You want to read the metadata (tags, date, title) stored in Front Matter

    Requires: Complete page path (e.g., obtained from search_memories or get_directory)

    Args:
        path: Full page path, e.g. "/00-Personal/Learning/Python-notes.md"

    Returns:
        Full page content including Front Matter metadata
    """
    try:
        post = file_store.read_page(path)
        if post:
            return f"---\n{post.metadata}\n---\n{post.content}"
        else:
            return f"页面不存在: {path}"
    except Exception as e:
        logger.error(f"获取页面失败: {e}")
        return f"错误: {str(e)}"

@mcp.tool()
def get_directory(path: str = "/") -> str:
    """
    Browse the Wiki filesystem structure for a specific directory path.

    Returns a structured listing of all entries (files and subdirectories) under the
    given directory, including each item's title, summary, and full path.

    Views:
    - Default view: list immediate children with title, type, summary, and path
    - Root path "/": shows all top-level category directories

    Use when:
    - You need to discover available directories and pages before reading
    - You want to browse the Wiki structure to understand its organization
    - You need to find what pages exist under a specific category
    - You want to navigate to subdirectories or find new content areas

    Args:
        path: Directory path, defaults to root "/"

    Returns:
        Directory structure with item type, title, summary, and path for each entry
    """
    try:
        items = file_store.list_directory_items(path)
        if not items:
            return f"目录为空或不存在: {path}"
        
        result = f"# 目录: {path}\n\n"
        for item in items:
            result += f"- [{item['type']}] {item['title']}: {item['summary']}\n  路径: {item['path']}\n"
        
        return result
    except Exception as e:
        logger.error(f"获取目录失败: {e}")
        return f"错误: {str(e)}"

@mcp.tool()
def create_directory(path: str, title: str, summary: str) -> bool:
    """
    Create a new directory and its corresponding directory summary page.

    Creates both the physical directory on disk and a directory.md page with title,
    summary, and Front Matter metadata. The directory becomes browseable via
    get_directory immediately.

    Use when:
    - You need to create a new category or topic area in the Wiki
    - You want to organize memories into a new subdirectory structure
    - You need a dedicated space for a new project or subject

    Args:
        path: Full path for the new directory, e.g. "/00-Personal/Learning/Programming"
        title: Display title for the directory
        summary: Brief description of the directory's content and purpose

    Returns:
        Whether the directory was created successfully
    """
    try:
        return write_engine.create_directory(path, title, summary)
    except Exception as e:
        logger.error(f"创建目录失败: {e}")
        return False

@mcp.tool()
def run_health_check() -> dict:
    """
    Run a comprehensive health check on the entire Wiki.

    Scans all pages and directories to verify structural integrity and content quality.
    Checks performed:
    - Missing or orphaned directory.md files
    - Broken internal links between pages
    - Pages with missing or malformed Front Matter metadata
    - Empty directories or pages
    - Naming consistency and depth violations

    Use when:
    - You want to verify the Wiki is in good shape
    - You suspect structural issues after many add/update operations
    - You want a periodic maintenance report
    - You need to identify pages that need attention or repair

    Returns:
        Health check report with findings, warnings, and recommendations
    """
    try:
        return health_engine.run_check()
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {"error": str(e)}

@mcp.tool()
def export_wiki(output_path: str = "wiki_export.zip") -> str:
    """
    Export the entire Wiki as a ZIP archive for backup or migration.

    Packages all pages, directories, and metadata into a single compressed file.
    The exported archive preserves the full directory structure and can be used for:
    - Backup and restore
    - Migrating the Wiki to another location or machine
    - Sharing the Wiki content with others

    Use when:
    - You want to create a backup of the entire Wiki
    - You need to migrate or transfer the Wiki to another system
    - You want to share the complete Wiki content as a single file

    Args:
        output_path: Output file path, defaults to "wiki_export.zip"

    Returns:
        Full path to the exported ZIP file
    """
    try:
        return file_store.export_wiki(output_path)
    except Exception as e:
        logger.error(f"导出Wiki失败: {e}")
        return f"错误: {str(e)}"

if __name__ == "__main__":
    mcp.run()