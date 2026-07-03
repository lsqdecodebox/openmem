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

代码结构概览：
  1. run_standalone_tests()  — 独立模式入口：创建临时目录 + 子进程执行
  2. run_standalone_worker() — 独立模式工作进程：mock Config 后直接调用 main 中的函数
  3. run_client_tests()      — 客户端模式：通过 MCP 协议远程调用
  4. main()                  — 命令行参数解析，调度上述三种模式
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
    独立模式的主控函数。
    流程：
      1. 创建临时目录（tempfile.mkdtemp），作为隔离的 wiki 根目录
      2. 读取项目根目录的 openmem.json，将其 wiki_root 改为临时目录
      3. 将修改后的配置写入临时目录下的 openmem.json
      4. 设置环境变量 OPENMEM_CONFIG 指向临时配置
      5. 以 --standalone-worker 参数启动自身子进程（subprocess.run）
         - 子进程会执行 run_standalone_worker() 中的实际测试逻辑
         - 子进程的 stdout/stderr 直接输出到终端（capture_output=False）
      6. 子进程结束后，清理临时目录
      7. 根据子进程返回码判断测试是否全部通过

    这样做的目的是：完全隔离测试环境，不影响用户已有的 wiki 数据。
    """
    tmp_dir = tempfile.mkdtemp(prefix="openmem_test_")
    worker_script = os.path.join(SCRIPT_DIR, "test_mcp_integration.py")

    # 读取项目根目录的 openmem.json 配置
    config_path = os.path.join(PROJECT_DIR, "openmem.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 将 wiki_root 改为临时目录
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
    独立模式的实际测试函数，在隔离的子进程中执行。
    流程：
      1. 从环境变量 OPENMEM_CONFIG 读取临时配置文件路径
      2. 读取临时配置文件，获取临时 wiki_root 路径
      3. 将项目目录加入 sys.path，以便导入 main 模块
      4. 使用 unittest.mock 模拟 main.Config：
         - 将 wiki_root 指向临时目录
         - 从临时配置中读取 max_depth / default_tags / llm_config
      5. 导入 main 模块中的 mcp 对象和所有 tool 函数
      6. 创建一个新的事件循环，依次执行 10 项测试：
         测试1:  工具注册检查 — 调用 mcp.list_tools() 验证 8 个工具已注册
         测试2:  add_memory — 添加一条测试记忆，记录返回的页面路径
         测试3:  get_page — 读取刚才添加的页面，验证内容包含"测试记忆"
         测试4:  get_directory — 读取根目录 "/"
         测试5:  update_memory(append) — 追加内容
         测试6:  update_memory(overwrite) — 覆盖内容 + 验证覆盖结果
         测试7:  search_memories — 搜索关键词"测试"
         测试8:  create_directory — 创建目录 /测试目录 + 验证目录存在
         测试9:  run_health_check — 健康检查，验证返回 dict
         测试10: export_wiki — 导出为 zip 文件，验证文件存在
      7. 全部通过返回 0，否则返回 1

    注意：由于 main 模块在导入时会自动初始化 MCP 服务和 wiki 对象，
          而 wiki 对象依赖于 Config，所以必须在 import main 之前 mock Config。
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
            # 调用 mcp.list_tools() 获取已注册的工具列表
            # 验证是否包含预期的 8 个工具：add_memory, update_memory, ...
            # 同时报告是否存在多余的工具（非预期工具）
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
            # 调用 add_memory 添加一条 markdown 格式的记忆
            # 成功时返回页面路径（字符串），失败时返回包含"错误"的字符串
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
                # 使用上一步返回的路径读取页面，验证内容包含"测试记忆"
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
                # 读取根目录，验证返回非空（不含"错误"）
                print_header("测试4: get_directory")
                result = get_directory(path="/")
                if "错误" in result:
                    print_result(False, f"get_directory 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "get_directory 成功，根目录非空")

                # ---- 5. update_memory (append) ----
                # 以追加模式（append）更新页面内容
                # 成功时返回 True，失败时返回包含"错误"的字符串
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
                # 以覆盖模式（overwrite）更新页面内容
                # 然后用 get_page 验证内容已被覆盖
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
                # 搜索关键词"测试"，最多返回 3 条结果
                print_header("测试7: search_memories")
                result = search_memories(query="测试", max_results=3)
                if "错误" in result:
                    print_result(False, f"search_memories 失败: {result}")
                    all_passed = False
                else:
                    print_result(True, "search_memories 成功")

            # ---- 8. create_directory ----
            # 创建目录 /测试目录，并验证根目录中能看到它
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
            # 健康检查，验证返回值为 dict 类型
            # 打印 errors 和 warnings 的数量
            print_header("测试9: run_health_check")
            result = run_health_check()
            if not isinstance(result, dict):
                print_result(False, f"run_health_check 应返回 dict: {result}")
                all_passed = False
            else:
                print_result(True, f"run_health_check 成功: errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}")

            # ---- 10. export_wiki ----
            # 导出 wiki 为 zip 文件，验证导出文件存在
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
    """
    客户端模式测试函数。
    流程：
      1. 使用 mcp 库的 ClientSession + stdio_client
      2. 以子进程方式启动 main.py 作为 MCP 服务端
      3. 通过 MCP 协议（session.call_tool）依次调用各工具
      4. 测试项（共 9 项，比独立模式少 update_memory overwrite 验证）：
         测试1: 工具注册检查 — 验证工具数量 >= 8
         测试2: add_memory — 添加记忆
         测试3: get_page — 读取页面
         测试4: get_directory — 读取目录
         测试5: update_memory(append) — 追加更新
         测试6: search_memories — 搜索
         测试7: create_directory — 创建目录
         测试8: run_health_check — 健康检查
         测试9: export_wiki — 导出 wiki

    注意：此模式直接操作真实的 wiki 数据（使用 openmem.json 中的配置），
          会实际修改 wiki 文件，因此适合在测试环境而非生产环境运行。
    server_url 参数当前未使用，保留供未来扩展（如连接远程 MCP 服务）。
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        import asyncio
    except ImportError:
        print("客户端模式需要安装 mcp 库：pip install mcp")
        return False

    async def test():
        # 配置 MCP 服务端参数：通过子进程运行 main.py
        server_params = StdioServerParameters(
            command=PYTHON,
            args=["main.py"]
        )

        # 建立 stdio 通道并创建客户端 session
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
    """
    命令行入口：
      --standalone / -s     : 独立模式（推荐），使用临时目录隔离测试
      --standalone-worker   : 内部参数，被 --standalone 调用的子进程使用
      --client / -c         : 客户端模式，通过 MCP 协议连接本地的 main.py 服务
      无参数时默认走客户端模式
    """
    parser = argparse.ArgumentParser(description="OpenMem MCP 集成测试")
    parser.add_argument(
        "--standalone", "-s",
        action="store_true",
        help="独立模式：自动使用临时 wiki 目录并运行全部测试"
    )
    parser.add_argument(
        "--standalone-worker",
        action="store_true",
        help=argparse.SUPPRESS  # 不显示在帮助中，仅供内部使用
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