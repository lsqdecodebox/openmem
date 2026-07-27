#!/usr/bin/env python
"""
通用 MCP 客户端测试脚本

用法:
  python mcp_client_test.py [config.json]

默认配置路径: ~/.config/opencode/opencode.json

配置格式 (opencode 风格):
{
  "mcp": {
    "服务名": {
      "type": "local",
      "command": ["可执行文件", "参数1", "参数2"],
      "env": {},            // 可选
      "cwd": "..."           // 可选
    }
  }
}

测试项 (针对每个服务):
  1. initialize              - 握手并获取服务器能力
  2. tools/list              - 列出所有工具
  3. tools/call              - 对无必填参数的工具用空参数调用
  4. prompts/list            - 列出所有提示词
  5. prompts/get             - 对无必填参数的 prompt 获取内容
  6. resources/list          - 列出所有资源
  7. resources/read          - 读取每个资源

每个服务独立测试，互不影响。仅支持 type=local (stdio) 的服务。
"""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_CONFIG = Path(__file__).parent / "mcp_servers.json"
OP_TIMEOUT = 60  # 单个服务整体超时(秒)


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "mcp" not in data:
        raise ValueError(f"配置文件中没有 'mcp' 字段: {config_path}")
    return data["mcp"]


def resolve_command(command: str) -> str:
    """Windows 下补全命令扩展名 (npx -> npx.cmd)"""
    if Path(command).suffix or "/" in command or "\\" in command:
        return command
    resolved = shutil.which(command)
    return resolved or command


def tool_has_required_params(input_schema: dict) -> bool:
    return len(input_schema.get("required", [])) > 0


def prompt_has_required_args(prompt) -> bool:
    if not prompt.arguments:
        return False
    return any(arg.required for arg in prompt.arguments)


def extract_text(content_blocks) -> str:
    """从 content blocks 提取文本预览"""
    parts = []
    for block in content_blocks:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(f"<{block.type}>")
    text = " ".join(parts)
    return text[:120] + "..." if len(text) > 120 else text


async def test_server(name: str, server_config: dict) -> dict:
    """测试单个 MCP 服务"""
    r = {
        "name": name,
        "status": "running",
        "initialize": False,
        "server_name": "",
        "protocol_version": "",
        "capabilities": [],
        "tools_listed": 0,
        "tools_called": 0,
        "tools_skipped": 0,
        "prompts_listed": 0,
        "prompts_got": 0,
        "prompts_skipped": 0,
        "resources_listed": 0,
        "resources_read": 0,
        "errors": [],
    }

    if server_config.get("type") != "local":
        r["status"] = "skipped"
        r["errors"].append(f"不支持的 type: {server_config.get('type')}")
        return r

    cmd_list = server_config.get("command")
    if not cmd_list or not isinstance(cmd_list, list) or len(cmd_list) == 0:
        r["status"] = "failed"
        r["errors"].append("command 字段缺失或格式错误")
        return r

    command = resolve_command(cmd_list[0])
    args = cmd_list[1:]
    env = server_config.get("env")
    cwd = server_config.get("cwd")

    merged_env = None
    if env:
        merged_env = dict(os.environ)
        merged_env.update(env)

    try:
        server_params = StdioServerParameters(
            command=command, args=args, env=merged_env, cwd=cwd
        )
    except Exception as e:
        r["status"] = "failed"
        r["errors"].append(f"参数构建失败: {e}")
        return r

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(_run_tests(session, r), timeout=OP_TIMEOUT)
    except asyncio.TimeoutError:
        r["status"] = "timeout"
        r["errors"].append(f"超时 ({OP_TIMEOUT}s)")
    except FileNotFoundError as e:
        r["status"] = "failed"
        r["errors"].append(f"命令不存在: {e}")
    except Exception as e:
        r["status"] = "failed"
        r["errors"].append(f"连接异常: {type(e).__name__}: {e}")

    if r["status"] == "running" and not r["errors"]:
        r["status"] = "passed"
    elif r["status"] == "running":
        r["status"] = "partial"
    return r


async def _run_tests(session: ClientSession, r: dict):
    # 1. initialize
    print(f"  [1/7] initialize ...", end=" ", flush=True)
    try:
        init = await session.initialize()
        r["initialize"] = True
        r["server_name"] = init.serverInfo.name if init.serverInfo else ""
        r["protocol_version"] = str(init.protocolVersion)
        caps = init.capabilities
        cap_list = []
        if getattr(caps, "tools", None):
            cap_list.append("tools")
        if getattr(caps, "prompts", None):
            cap_list.append("prompts")
        if getattr(caps, "resources", None):
            cap_list.append("resources")
        if getattr(caps, "logging", None):
            cap_list.append("logging")
        if getattr(caps, "roots", None):
            cap_list.append("roots")
        r["capabilities"] = cap_list
        print(f"OK  server='{r['server_name']}' caps=[{','.join(cap_list)}]")
    except Exception as e:
        r["errors"].append(f"initialize 失败: {e}")
        print(f"FAIL  {e}")
        return

    # 2. tools/list
    print(f"  [2/7] tools/list ...", end=" ", flush=True)
    try:
        tools = (await session.list_tools()).tools
        r["tools_listed"] = len(tools)
        print(f"OK  {len(tools)} tools")
        for t in tools:
            required = t.inputSchema.get("required", [])
            mark = "*" if required else " "
            print(f"        {mark} {t.name}({', '.join(t.inputSchema.get('properties', {}).keys())})")
    except Exception as e:
        r["errors"].append(f"tools/list 失败: {e}")
        print(f"FAIL  {e}")

    # 3. tools/call (仅无必填参数的工具)
    print(f"  [3/7] tools/call ...", end=" ", flush=True)
    try:
        tools = (await session.list_tools()).tools
        called, skipped = 0, 0
        for t in tools:
            if tool_has_required_params(t.inputSchema):
                skipped += 1
                continue
            try:
                result = await session.call_tool(t.name, arguments={})
                called += 1
                status = "error" if result.isError else "ok"
                preview = extract_text(result.content) if result.content else ""
                print(f"\n        -> {t.name}: {status}  {preview}")
            except Exception as e:
                r["errors"].append(f"call_tool {t.name} 异常: {e}")
                print(f"\n        -> {t.name}: EXC  {e}")
        r["tools_called"] = called
        r["tools_skipped"] = skipped
        if called == 0 and skipped > 0:
            print(f"SKIP  ({skipped} tools have required params)")
        else:
            print(f"        called={called}, skipped={skipped}")
    except Exception as e:
        r["errors"].append(f"tools/call 阶段失败: {e}")
        print(f"FAIL  {e}")

    # 4. prompts/list
    print(f"  [4/7] prompts/list ...", end=" ", flush=True)
    try:
        prompts = (await session.list_prompts()).prompts
        r["prompts_listed"] = len(prompts)
        print(f"OK  {len(prompts)} prompts")
        for p in prompts:
            arg_names = [a.name for a in p.arguments] if p.arguments else []
            print(f"        - {p.name}({', '.join(arg_names)})")
    except Exception as e:
        r["errors"].append(f"prompts/list 失败: {e}")
        print(f"FAIL  {e}")

    # 5. prompts/get (仅无必填参数的 prompt)
    print(f"  [5/7] prompts/get ...", end=" ", flush=True)
    try:
        prompts = (await session.list_prompts()).prompts
        got, skipped = 0, 0
        for p in prompts:
            if prompt_has_required_args(p):
                skipped += 1
                continue
            try:
                result = await session.get_prompt(p.name)
                got += 1
                msg_count = len(result.messages) if result.messages else 0
                total_len = 0
                for msg in result.messages or []:
                    if hasattr(msg.content, "text"):
                        total_len += len(msg.content.text)
                print(f"\n        -> {p.name}: {msg_count} msgs, {total_len} chars")
            except Exception as e:
                r["errors"].append(f"get_prompt {p.name} 异常: {e}")
                print(f"\n        -> {p.name}: EXC  {e}")
        r["prompts_got"] = got
        r["prompts_skipped"] = skipped
        if got == 0 and skipped > 0:
            print(f"SKIP  ({skipped} prompts have required args)")
        else:
            print(f"        got={got}, skipped={skipped}")
    except Exception as e:
        r["errors"].append(f"prompts/get 阶段失败: {e}")
        print(f"FAIL  {e}")

    # 6. resources/list
    print(f"  [6/7] resources/list ...", end=" ", flush=True)
    try:
        resources = (await session.list_resources()).resources
        r["resources_listed"] = len(resources)
        print(f"OK  {len(resources)} resources")
        for res in resources:
            print(f"        - {res.uri}  ({res.mimeType or 'unknown'})")
    except Exception as e:
        r["errors"].append(f"resources/list 失败: {e}")
        print(f"FAIL  {e}")

    # 7. resources/read
    print(f"  [7/7] resources/read ...", end=" ", flush=True)
    try:
        resources = (await session.list_resources()).resources
        read_count = 0
        for res in resources:
            try:
                result = await session.read_resource(res.uri)
                read_count += 1
                preview = ""
                if result.contents:
                    first = result.contents[0]
                    if hasattr(first, "text"):
                        preview = first.text[:80] + "..." if len(first.text) > 80 else first.text
                print(f"\n        -> {res.uri}: {len(result.contents)} blocks  {preview}")
            except Exception as e:
                r["errors"].append(f"read_resource {res.uri} 异常: {e}")
                print(f"\n        -> {res.uri}: EXC  {e}")
        r["resources_read"] = read_count
        if read_count == 0 and len(resources) == 0:
            print("SKIP  (no resources)")
        else:
            print(f"        read={read_count}")
    except Exception as e:
        r["errors"].append(f"resources/read 阶段失败: {e}")
        print(f"FAIL  {e}")


def print_summary(results: list[dict]):
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Service':<20} {'Status':<10} {'Init':<6} {'Tools':<12} {'Prompts':<12} {'Resources':<14}")
    print("-" * 70)
    for r in results:
        tools_str = f"{r['tools_listed']}/{r['tools_called']}"
        prompts_str = f"{r['prompts_listed']}/{r['prompts_got']}"
        res_str = f"{r['resources_listed']}/{r['resources_read']}"
        init_str = "OK" if r["initialize"] else "FAIL"
        print(
            f"{r['name']:<20} {r['status']:<10} {init_str:<6} "
            f"{tools_str:<12} {prompts_str:<12} {res_str:<14}"
        )
        for err in r["errors"]:
            print(f"  ! {err}")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    print(f"Total: {total} | Passed: {passed} | Partial: {partial} | Failed: {failed} | Skipped: {skipped} | Timeout: {timeout}")


async def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG

    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        print(f"用法: python {Path(__file__).name} [config.json]")
        sys.exit(1)

    print(f"配置文件: {config_path}\n")
    servers = load_config(config_path)

    if not servers:
        print("配置中没有 MCP 服务")
        sys.exit(1)

    print(f"发现 {len(servers)} 个服务: {', '.join(servers.keys())}\n")

    results = []
    for name, cfg in servers.items():
        print("#" * 70)
        print(f"# {name}")
        print(f"# command: {cfg.get('command')}")
        print("#" * 70)
        r = await test_server(name, cfg)
        results.append(r)
        print()

    print_summary(results)

    if any(r["status"] in ("failed", "timeout") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
