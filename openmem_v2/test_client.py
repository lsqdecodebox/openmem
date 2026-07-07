# test_client.py
import asyncio
import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openmem.main"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to openmem MCP Server!\n")

            # ---------- Test Tools ----------
            print("=== 1. Test Tools ===")
            tools = await session.list_tools()
            print(f"Found {len(tools.tools)} tools:")
            for tool in tools.tools:
                params = list(tool.inputSchema.get("properties", {}).keys())
                print(f"  - {tool.name}({', '.join(params)})")

            # get_directory
            print("\n--- get_directory ---")
            dir_result = await session.call_tool("get_directory", arguments={"path": "/"})
            dir_text = dir_result.content[0].text
            dir_parsed = json.loads(dir_text)
            print(f"  type: {dir_parsed['type']}, children count: {len(dir_parsed['children'])}")
            for child in dir_parsed["children"]:
                print(f"    - {child['name']} ({child['type']})")

            # write_memory
            print("\n--- write_memory ---")
            write_result = await session.call_tool(
                "write_memory",
                arguments={
                    "content": "Python\u5b66\u4e60\u7b14\u8bb0\u5185\u5bb9",
                    "path": "/02-\u5b66\u4e60/Python",
                    "tags": ["\u5b66\u4e60"],
                },
            )
            write_text = write_result.content[0].text
            write_parsed = json.loads(write_text)
            print(f"  status: {write_parsed['status']}, path: {write_parsed['path']}")

            # read_memory
            print("\n--- read_memory ---")
            read_result = await session.call_tool(
                "read_memory", arguments={"path": "/02-\u5b66\u4e60/Python"}
            )
            read_text = read_result.content[0].text
            print(f"  content (first 200 chars): {read_text[:200]}")
            assert "Python\u5b66\u4e60\u7b14\u8bb0\u5185\u5bb9" in read_text

            # write_memory without path
            print("\n--- write_memory (no path) ---")
            no_path_result = await session.call_tool(
                "write_memory", arguments={"content": "some content"}
            )
            no_path_text = no_path_result.content[0].text
            no_path_parsed = json.loads(no_path_text)
            print(f"  status: {no_path_parsed['status']}")
            assert no_path_parsed["status"] == "need_path"

            # write_memory depth exceeded
            print("\n--- write_memory (depth exceeded) ---")
            deep_result = await session.call_tool(
                "write_memory",
                arguments={"content": "test", "path": "/a/b/c/d/e/f/g/h"},
            )
            deep_text = deep_result.content[0].text
            print(f"  result: {deep_text}")
            assert "error" in deep_text or "\u8d85\u8fc7" in deep_text

            # update existing page
            print("\n--- write_memory (update/merge) ---")
            update_result = await session.call_tool(
                "write_memory",
                arguments={"content": "\u65b0\u589e\u5185\u5bb9", "path": "/02-\u5b66\u4e60/Python"},
            )
            update_text = update_result.content[0].text
            update_parsed = json.loads(update_text)
            print(f"  status: {update_parsed['status']}")

            read_updated = await session.call_tool(
                "read_memory", arguments={"path": "/02-\u5b66\u4e60/Python"}
            )
            updated_text = read_updated.content[0].text
            assert "Python\u5b66\u4e60\u7b14\u8bb0\u5185\u5bb9" in updated_text
            assert "\u65b0\u589e\u5185\u5bb9" in updated_text
            print("  merge verified: old + new content both present")

            # get_directory after writes
            print("\n--- get_directory (after writes) ---")
            dir_after = await session.call_tool("get_directory", arguments={"path": "/02-\u5b66\u4e60"})
            dir_after_text = dir_after.content[0].text
            dir_after_parsed = json.loads(dir_after_text)
            child_names = [c["name"] for c in dir_after_parsed["children"]]
            print(f"  children: {child_names}")
            assert "Python.md" in child_names

            # ---------- Test Prompts ----------
            print("\n=== 2. Test Prompts ===")
            prompts = await session.list_prompts()
            print(f"Found {len(prompts.prompts)} prompts:")
            for p in prompts.prompts:
                print(p)
                args = [arg.name for arg in p.arguments] if p.arguments else []
                print(f"  - {p.name}(args: {args or 'none'})")

            # core_principles prompt
            print("\n--- core_principles ---")
            principles = await session.get_prompt("core_principles")
            principles_text = ""
            for msg in principles.messages:
                if hasattr(msg.content, "text"):
                    principles_text += msg.content.text
            print(f"  total length: {len(principles_text)} chars")
            assert "\u8bb0\u5fc6\u7ba1\u7406\u89c4\u5219" in principles_text
            print("  verified: core principles content present")

            print("\n=== All tests passed! ===")


if __name__ == "__main__":
    asyncio.run(main())
