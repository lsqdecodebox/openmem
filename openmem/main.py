import logging
import shutil
from pathlib import Path
from fastmcp import FastMCP
from openmem.config import Config
from openmem.file_store import FileStore
from openmem.llm_client import LLMClient
from openmem.write_engine import WriteEngine
from openmem.read_engine import ReadEngine
from openmem.health_engine import HealthEngine

logger = logging.getLogger(__name__)
mcp = FastMCP("Personal Wiki Memory")

config = None
file_store = None
llm_client = None
write_engine = None
read_engine = None
health_engine = None


def run():
    global config, file_store, llm_client, write_engine, read_engine, health_engine

    user_config_dir = Path.home() / ".config" / "openmem"
    user_config = user_config_dir / "openmem.json"

    if not user_config.exists():
        example_config = Path(__file__).parent / "openmem.json.example"
        if example_config.exists():
            user_config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(example_config, user_config)
            print(f"已复制配置文件模板到: {user_config}")
            print("请编辑该文件，填入您的 LLM API 密钥后再运行。")
            return
        else:
            print(f"未找到配置文件 {user_config}，也未找到示例文件 {example_config}")
            return

    config = Config(str(user_config))
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

    file_store = FileStore(config.wiki_root, config.max_depth)
    llm_client = LLMClient(config.llm_config)

    write_engine = WriteEngine(file_store, llm_client)
    read_engine = ReadEngine(file_store, llm_client)
    health_engine = HealthEngine(file_store, llm_client)

    logger.info("OpenMem MCP服务启动成功")

    register_tools()
    mcp.run()


def register_tools():
    @mcp.tool()
    def add_memory(content: str, suggested_path: str = None, tags: list[str] = None) -> str:
        try:
            return write_engine.add_memory(content, suggested_path, tags)
        except Exception as e:
            logger.error(f"添加记忆失败: {e}")
            return f"错误: {str(e)}"

    @mcp.tool()
    def update_memory(path: str, content: str, mode: str = "merge") -> bool:
        try:
            return write_engine.update_memory(path, content, mode)
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    @mcp.tool()
    def search_memories(query: str, max_depth: int = 7, max_results: int = 3) -> str:
        try:
            return read_engine.search(query, max_depth, max_results)
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return f"错误: {str(e)}"

    @mcp.tool()
    def get_page(path: str) -> str:
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
        try:
            return write_engine.create_directory(path, title, summary)
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return False

    @mcp.tool()
    def run_health_check() -> dict:
        try:
            return health_engine.run_check()
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {"error": str(e)}

    @mcp.tool()
    def export_wiki(output_path: str = "wiki_export.zip") -> str:
        try:
            return file_store.export_wiki(output_path)
        except Exception as e:
            logger.error(f"导出Wiki失败: {e}")
            return f"错误: {str(e)}"

    globals().update(locals())


if __name__ == "__main__":
    run()
