import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastmcp import FastMCP

from openmem.initializer import initialize, DEFAULT_CONFIG
from openmem.store import WikiStore

mcp = FastMCP("Personal Wiki Memory")

CONFIG_PATH = Path.home() / ".config" / "openmem" / "openmem.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG


def setup_logging(config: dict):
    log_cfg = config.get("logging", DEFAULT_CONFIG["logging"])
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = log_cfg.get(
        "format",
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_cfg.get("file_enabled", False):
        log_path = Path(log_cfg.get("file_path", "./logs/openmem.log")).expanduser()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=log_cfg.get("max_file_size_mb", 10) * 1024 * 1024,
                backupCount=log_cfg.get("backup_count", 5),
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter(fmt))
            handlers.append(file_handler)
        except (PermissionError, OSError) as e:
            print(
                f"[openmem] 警告：无法创建日志目录 {log_path.parent}（{e}），"
                "将仅使用控制台日志输出",
                file=sys.stderr,
            )

    logging.basicConfig(level=level, format=fmt, handlers=handlers)

    for _noisy in ("mcp.server.lowlevel.server", "mcp.server.streamable_http_manager"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)


config = load_config()
setup_logging(config)

logger = logging.getLogger(__name__)
wiki_root = Path(config.get("wiki_root", "./wiki")).expanduser()
initialize(CONFIG_PATH, wiki_root)

store = WikiStore(
    wiki_root=wiki_root,
    max_depth=config.get("max_depth", 7),
    snapshot_cfg=config.get("snapshot"),
)


@mcp.tool()
def get_directory(path: str = "/") -> str:
    """获取记忆中指定目录的层级文件列表，即记忆概要

    Args:
        path: 目录路径，默认根目录

    Returns:
        目录结构和子条目列表（含每个条目的title、summary、type、level）
    """
    return store.get_directory(path)


@mcp.tool()
def read_memory(path: str) -> str:
    """读取指定路径的完整Wiki页面内容，即读取记忆

    Args:
        path: 页面完整路径，如"/00-个人/学习/Python学习笔记"

    Returns:
        页面完整内容，包括Front Matter
    """
    return store.read_memory(path)


@mcp.tool()
def write_memory(
    content: str, path: str | None = None, tags: list[str] | None = None, summary: str | None = None
) -> str:
    """覆盖写入指定路径的完整Wiki页面内容，即写入记忆

    Args:
        content: 要写入的记忆内容
        path: 目标路径，如"/00-个人/学习/Python学习笔记"。为空时返回need_path提示
        tags: 可选的标签列表
        summary: 可选的页面摘要，为空时自动生成

    Returns:
        最终页面路径
    """
    return store.write_memory(content=content, path=path, tags=tags, summary=summary)


@mcp.tool()
def write_asset(
    source: str,
    path: str,
    filename: str,
    type: str = "files",
    overwrite: bool = False,
) -> str:
    """写入图片、文件、视频等二进制资料到记忆中, 以下样例 最终路径为"files/01-工作/项目A/diagram.png"

    Args:
        source: 本地文件路径，工具会读取该文件内容并写入记忆中
        path: 存储子路径，如"01-工作/项目A"
        filename: 文件名，如"diagram.png"
        type: 资产类型，可选: images, files, videos, 默认files
        overwrite: 是否覆盖已有文件，默认False

    Returns:
        写入结果，包含状态、路径、文件名、类型、大小
    """
    return store.write_asset(source=source, path=path, filename=filename, type=type, overwrite=overwrite)


@mcp.tool()
def read_asset(path: str) -> str:
    """读取记忆中已有的图片、文件、视频等资产的本地路径

    Args:
        path: 资产相对路径，如"images/01-工作/项目A/diagram.png"

    Returns:
        资产信息，包含绝对路径、相对路径、文件大小
    """
    return store.read_asset(path=path)


@mcp.prompt(name="core_principles", description="记忆系统核心提示词，供LLM调度决策")
def core_principles_prompt() -> str:
    """获取所有核心提示词（一级目录下所有.md文件的内容合集），供客户端LLM用于调度决策

    Returns:
        所有核心提示词的完整内容，按文件名排列拼接
    """
    return store.get_core_principles()


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="openmem", description="Personal Wiki Memory MCP Server")
    parser.add_argument("--remote", action="store_true", help="以 streamable-http 远程模式启动（默认 stdio 本地模式）")
    parser.add_argument("--host", help="远程模式绑定主机地址（覆盖 config.remote.host）")
    parser.add_argument("--port", type=int, help="远程模式监听端口（覆盖 config.remote.port）")
    parser.add_argument("--path", help="远程模式 HTTP 端点路径（覆盖 config.remote.path）")
    args = parser.parse_args()

    if args.remote:
        remote_cfg = config.get("remote", {})
        mcp.run(
            transport="streamable-http",
            host=args.host or remote_cfg.get("host", "127.0.0.1"),
            port=args.port or remote_cfg.get("port", 6000),
            path=args.path or remote_cfg.get("path", "/mcp"),
            log_level="warning",
            uvicorn_config={
                "access_log": False,
                "use_colors": False,
            },
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
