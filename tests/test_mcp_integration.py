#!/usr/bin/env python3
"""
OpenMem MCP 集成测试脚本

用法（独立模式，自动使用临时 wiki 目录，不依赖外部 MCP 服务）：
    python tests/test_mcp_integration.py --standalone

用法（客户端模式，需要 MCP 服务已启动）：
    python tests/test_mcp_integration.py

本脚本会测试所有 8 个 MCP tool 是否正常响应：
  - add_memory      添加记忆
  - update_memory   更新记忆
  - search_memories  搜索记忆
  - get_page        获取页面
  - get_directory   获取目录
  - create_directory 创建目录
  - run_health_check 健康检查
  - export_wiki     导出 Wiki
"""

import argparse
import json
import os
import sys
import tempfile
import shutil
import subprocess

PYTHON = sys.executable
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def print_header(title):
    print()
    print("=" * 55)
    print(f" {title}")
    print("=" * 55)


def print_result(ok: bool, msg: str):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {msg}")


# ============================================================================
# 模式1：子进程模式 —— 在临时目录中启动 MCP 服务并调用所有 tools
# ============================================================================

def run_standalone_tests():
    """
    在子进程中运行集成测试。
    使用临时 wiki 目录和临时配置文件，完全隔离，不影响已有数据。
    使用 --standalone-worker 标志调用自身执行实际测试逻辑。
    """
    tmp_dir = tempfile.mkdtemp(prefix="openmem_test_")
    worker_script = os.path.join(SCRIPT_DIR, "test_mcp_integration.py")

    # 创建临时配置文件
    config_path = os.path.join(PROJECT_DIR, "openmem.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["wiki_root"] = tmp_dir
    test_config_path = os.path.join(tmp_dir, "openmem.json")
    with open(test_config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 在临时目录中启动子进程
    env = os.environ.copy()
    env["OPENMEM_CONFIG"] = test_config_path

    print_header("OpenMem MCP 集成测试（子进程模式）")
    print(f"  临时 wiki 目录: {tmp_dir}")
    print(f"  临时配置文件: {test_config_path}")

    result = subprocess.run(
        [PYTHON, worker_script, "--standalone-worker"],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=False,
        text=True,
    )

    # 清理临时目录
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return result.returncode == 0


# ============================================================================
# 模式2：独立工作进程 —— 被 run_standalone_tests 调用
# ============================================================================

def run_standalone_worker():
    """
    在隔离环境中执行实际的集成测试逻辑。
    由 run_standalone_tests 通过子进程启动。
    通过 OPENMEM_CONFIG 环境变量获取临时配置文件路径。
    """
    test_config_path = os.environ.get("OPENMEM_CONFIG")
    if not test_config_path:
        print("错误: 缺少 OPENMEM_CONFIG 环境变量")
        sys.exit(1)

    with open(test_config_path, "r", encoding="utf-8") as f:
        test_config = json.load(f)

    tmp_dir = test_config["wiki_root"]

    # 修改 sys.path 确保能导入 main
    sys.path.insert(0, PROJECT_DIR)

    # 模拟 main.Config —— 先 mock 再 import main
    import unittest.mock as mock
    with mock.patch("main.Config") as MockConfig:
        mock_config_instance = mock.MagicMock()
        mock_config_instance.wiki_root = tmp_dir
        mock_config_instance.max_depth = test_config.get("max_depth", 7)
        mock_config_instance.default_tags = test_config.get("default_tags", [])
        mock_config_instance.llm_config = test_config.get("llm", {})
        MockConfig.return_value = mock_config_instance

        from main import (
            mcp, add_memory, update_memory, search_memories,
            get_page, get_directory, create_directory,
            run_health_check, export_wiki
        )
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        all_passed = True

        try:
            # ---- 1. 工具注册检查 ----
            print_header("测试1: 工具注册检查")
            tool_list = loop.run_until_complete(mcp.list_tools())
            tool_names = {t.name for t in tool_list}
            expected = {
                "add_memory", "update_memory", "search_memories",
                "get_page", "get_directory", "create_directory",
                "run_health_check", "export_wiki"
            }
            missing = expected - tool_names
            extra = tool_names - expected
            if missing:
                print_result(False, f"缺少工具: {missing}")
                all_passed = False
            else:
                extra_msg = f", 额外: {extra}" if extra else ""
                print_result(True, f"已注册 {len(tool_names)} 个工具{extra_msg}")

            # ---- 2. add_memory ----
            print_header("测试2: add_memory")
            result = add_memory(
                content="# 测试记忆\n\n这是一条集成测试记忆。",
                suggested_path="/测试/集成测试",
                tags=["测试", "集成测试"]
            )
            if "错误" in result:
                print_result(False, f"add_memory 失败: {result}")
                all_passed = False
            else:
                test_page_path = result
                print_result(True, f"add_memory 成功: {test_page_path}")

                # ---- 3. get_page ----
                print_header("测试3: get_page")
                result = get_page(path=test_page_path)
                if "错误" in result:
                    print_result(False, f"get_page 失败: {result}")
                    all_passed = False
                elif "测试记忆" not in result:
                    print_result(False, "get_page 返回内容不包含'测试记忆'")
                    all_passed = False
                else:
                    print_result(True, "get_page 成功，内容包含'测试记忆'")

                # ---- 4. get_directory ----
                print_header("测试4: get_directory")
                result = get_directory(path="/")
                if "错误" in result:
                    print_result(False, f"get_directory 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "get_directory 成功，根目录非空")

                # ---- 5. update_memory (append) ----
                print_header("测试5: update_memory (append)")
                result = update_memory(
                    path=test_page_path,
                    content="\n\n## 追加的内容\n\n这是追加的测试内容。",
                    mode="append"
                )
                if result is not True:
                    print_result(False, f"update_memory (append) 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "update_memory (append) 成功")

                # ---- 6. update_memory (overwrite) ----
                print_header("测试6: update_memory (overwrite)")
                result = update_memory(
                    path=test_page_path,
                    content="# 覆盖后的标题\n\n内容已被完全覆盖。",
                    mode="overwrite"
                )
                if result is not True:
                    print_result(False, f"update_memory (overwrite) 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "update_memory (overwrite) 成功")

                # 验证覆盖后的内容
                page_content = get_page(path=test_page_path)
                if "覆盖后的标题" not in page_content:
                    print_result(False, "验证覆盖内容失败")
                    all_passed = False
                else:
                    print_result(True, "验证覆盖内容成功")

                # ---- 7. search_memories ----
                print_header("测试7: search_memories")
                result = search_memories(query="测试", max_results=3)
                if "错误" in result:
                    print_result(False, f"search_memories 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "search_memories 成功")

            # ---- 8. create_directory ----
            print_header("测试8: create_directory")
            result = create_directory(
                path="/测试目录",
                title="测试目录",
                summary="用于集成测试的目录"
            )
            if result is not True:
                print_result(False, f"create_directory 失败: {result}")
                all_passed = False
            else:
                print_result(True, "create_directory 成功")

            # 验证目录已创建
            dir_content = get_directory(path="/")
            if "测试目录" not in dir_content:
                print_result(False, "验证目录创建失败")
                all_passed = False
            else:
                print_result(True, "验证目录创建成功")

            # ---- 9. run_health_check ----
            print_header("测试9: run_health_check")
            result = run_health_check()
            if not isinstance(result, dict):
                print_result(False, f"run_health_check 应返回 dict: {result}")
                all_passed = False
            else:
                print_result(True, f"run_health_check 成功: errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}")

            # ---- 10. export_wiki ----
            print_header("测试10: export_wiki")
            export_path = os.path.join(tmp_dir, "wiki_export.zip")
            result = export_wiki(output_path=export_path)
            if "错误" in result:
                print_result(False, f"export_wiki 失败: {result}")
                all_passed = False
            elif not os.path.exists(export_path):
                print_result(False, f"导出文件不存在: {export_path}")
                all_passed = False
            else:
                print_result(True, f"export_wiki 成功: {result}")
                os.remove(export_path)

        except Exception as e:
            print(f"\n  [FAIL] 未预期异常: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        finally:
            loop.close()

    print()
    print("=" * 55)
    if all_passed:
        print(" [DONE] 所有 10 项集成测试全部通过！")
    else:
        print(" [FAIL] 存在失败的测试项，请检查以上日志。")
    print("=" * 55)

    sys.exit(0 if all_passed else 1)


# ============================================================================
# 模式3：客户端模式 —— 通过 MCP 协议调用远程 MCP 服务
# ============================================================================

def run_client_tests(server_url: str = None):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        import asyncio
    except ImportError:
        print("客户端模式需要安装 mcp 库：pip install mcp")
        return False

    async def test():
        server_params = StdioServerParameters(
            command=PYTHON,
            args=["main.py"]
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 列出所有 tools
                tools = await session.list_tools()
                print_header("测试1: 工具注册检查")
                assert len(tools.tools) >= 8, f"期望至少8个tool，实际{len(tools.tools)}"
                print_result(True, f"已注册 {len(tools.tools)} 个工具")

                # 测试 add_memory
                print_header("测试2: add_memory")
                result = await session.call_tool("add_memory", {
                    "content": "# 测试记忆\n\n这是一条测试记忆，用于验证MCP调用是否正常。",
                    "suggested_path": "/测试",
                    "tags": ["测试", "集成测试"]
                })
                assert result.content and len(result.content) > 0
                path = result.content[0].text.strip()
                print_result(True, f"add_memory 成功: {path}")

                # 测试 get_page
                print_header("测试3: get_page")
                result = await session.call_tool("get_page", {"path": path})
                assert result.content and len(result.content) > 0
                print_result(True, f"get_page 成功")

                # 测试 get_directory
                print_header("测试4: get_directory")
                result = await session.call_tool("get_directory", {"path": "/"})
                assert result.content and len(result.content) > 0
                print_result(True, "get_directory 成功")

                # 测试 update_memory (append)
                print_header("测试5: update_memory (append)")
                result = await session.call_tool("update_memory", {
                    "path": path,
                    "content": "\n\n## 追加内容\n\n这是追加的测试内容。",
                    "mode": "append"
                })
                assert result.content and result.content[0].text == "true"
                print_result(True, "update_memory (append) 成功")

                # 测试 search_memories
                print_header("测试6: search_memories")
                result = await session.call_tool("search_memories", {
                    "query": "测试记忆",
                    "max_results": 3
                })
                assert result.content and len(result.content) > 0
                print_result(True, "search_memories 成功")

                # 测试 create_directory
                print_header("测试7: create_directory")
                result = await session.call_tool("create_directory", {
                    "path": "/测试目录",
                    "title": "测试目录",
                    "summary": "用于集成测试的目录"
                })
                assert result.content and result.content[0].text == "true"
                print_result(True, "create_directory 成功")

                # 测试 run_health_check
                print_header("测试8: run_health_check")
                result = await session.call_tool("run_health_check", {})
                assert result.content and len(result.content) > 0
                print_result(True, "run_health_check 成功")

                # 测试 export_wiki
                print_header("测试9: export_wiki")
                export_path = os.path.join(tempfile.gettempdir(), f"wiki_test_export_{int(__import__('time').time())}.zip")
                result = await session.call_tool("export_wiki", {"output_path": export_path})
                assert result.content and len(result.content) > 0
                print_result(True, f"export_wiki 成功")
                if os.path.exists(export_path):
                    os.remove(export_path)

                print()
                print("=" * 55)
                print(" [DONE] 所有 MCP 集成测试通过！")
                print("=" * 55)
                return True

    try:
        return asyncio.run(test())
    except Exception as e:
        print(f"  [FAIL] 集成测试失败: {e}")
        return False


# ============================================================================
# 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="OpenMem MCP 集成测试")
    parser.add_argument(
        "--standalone", "-s",
        action="store_true",
        help="独立模式：自动使用临时 wiki 目录并运行全部测试"
    )
    parser.add_argument(
        "--standalone-worker",
        action="store_true",
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--client", "-c",
        action="store_true",
        help="客户端模式：通过 MCP 协议调用已启动的 MCP 服务"
    )
    args = parser.parse_args()

    if args.standalone_worker:
        run_standalone_worker()
    elif args.standalone:
        success = run_standalone_tests()
    else:
        success = run_client_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()