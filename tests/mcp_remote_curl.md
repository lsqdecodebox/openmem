# MCP Remote 请求 curl 指令

本文档基于 `tests/mcp_client_test.py` 测试脚本，整理 openmem remote（streamable-http）模式下的 curl 请求指令，对应测试脚本的 7 个测试步骤。

## 项目背景

**openmem** 是基于 MCP 协议的个人 Wiki 记忆系统（FastMCP 框架），支持 stdio 本地模式与 `streamable-http` 远程模式。

`tests/mcp_client_test.py` 通过 `fastmcp.Client` 对 remote 服务进行 7 项测试：

1. `initialize` — 握手并获取服务器能力
2. `tools/list` — 列出所有工具
3. `tools/call` — 对无必填参数的工具用空参数调用
4. `prompts/list` — 列出所有提示词
5. `prompts/get` — 对无必填参数的 prompt 获取内容
6. `resources/list` — 列出所有资源
7. `resources/read` — 读取每个资源

## 测试服务配置

参考 `tests/mcp_servers.json` 中 `enable=true` 的 remote 服务 `openmem-sit-remote`：

| 配置项 | 值 |
| --- | --- |
| URL | `http://10.59.7.249:6000/mcp` |
| 认证 | `Bearer om_04350ab4f6d696760e04d45a0f095828` |

## MCP streamable-http 协议要点

- **传输**：HTTP POST + JSON-RPC 2.0，端点 `/mcp`
- **认证**：`Authorization: Bearer <api_key>`（remote 必需，否则 401）
- **会话**：`initialize` 响应头返回 `Mcp-Session-Id`，**后续请求需回带**该 header
- **初始化序列**：`initialize` → `notifications/initialized` → 其他方法
- **响应格式**：可能为 SSE（`text/event-stream`），加 `-i` 便于看 header、加 `-N` 流式输出

## curl 与 fastmcp Client 的认证机制差异

curl 与 `fastmcp.Client` 走的是两条完全不同的认证注入路径，这正是 `tests/mcp_client_test.py` remote 模式曾失败、而 curl 成功的根因。

| 维度 | curl / opencode | fastmcp `Client` |
| --- | --- | --- |
| 认证字段来源 | `headers.Authorization`（opencode 风格配置） | `auth=` 形参 |
| 注入方式 | 调用方手动加 `-H "Authorization: Bearer xxx"` 头 | 内部经 `StreamableHttpTransport._set_auth` → `BearerAuth.auth_flow` 自动拼头 |
| token 格式 | 完整 `Bearer om_xxx` 字符串 | 纯 token `om_xxx`（不含 `Bearer ` 前缀） |
| 签名支持 `headers=` | — | **不支持**，`Client.__init__` 无此形参 |

**机制要点**：

- `fastmcp.Client` 签名仅 `auth: httpx.Auth | Literal["oauth"] | str | None`，**不接受 `headers=`**
- 当 `auth` 传入 `str` 时，`StreamableHttpTransport._set_auth` 将其包装为 `BearerAuth(token)`
- `BearerAuth.auth_flow` 执行时会 **再次拼接** `f"Bearer {token}"`，因此传入的 token 必须是**去掉 `Bearer ` 前缀的纯值**
- 若直接把 `"Bearer om_xxx"` 当 token 传入，最终请求头会变成 `Authorization: Bearer Bearer om_xxx`，服务端 401

**对 `mcp_servers.json` 配置的影响**：

opencode 风格配置把认证写在 `headers.Authorization`（含 `Bearer ` 前缀），而 `fastmcp.Client` 无法直接消费。`tests/mcp_client_test.py` 的 `test_remote_server` 需做两步额外转换：

1. 从 `headers.Authorization` 剥掉 `"Bearer "` 前缀，得到纯 token
2. 通过 `Client(url, auth=token)` 传入，由 fastmcp 内部完成头注入

详见 `tests/mcp_client_test.py:417-426` 的注释。

## 环境变量定义

```bash
URL="http://10.59.7.249:6000/mcp"
KEY="om_04350ab4f6d696760e04d45a0f095828"
SID=""  # 从 initialize 响应头提取后手动赋值
```

```bash
URL="https://ipaassit.catl.com/gateway/office/ipaas/PKL/mcp"
KEY="om_04350ab4f6d696760e04d45a0f095828"
SID=""  # 从 initialize 响应头提取后手动赋值
```

## 步骤 1 — initialize（握手，对应测试 [1/7]）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

> **从响应头中提取 `Mcp-Session-Id` 的值**，赋给 `SID` 变量供后续使用。

## 步骤 2 — notifications/initialized（完成握手）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

## 步骤 3 — tools/list（对应测试 [2/7]）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

## 步骤 4 — tools/call（对应测试 [3/7]，调无必填参数工具 `get_directory`）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_directory","arguments":{}}}'
```

> `read_memory` / `write_memory` / `write_asset` / `read_asset` 均有必填参数，测试脚本会跳过。如需手动调用 `read_memory`：
>
> ```bash
> -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_memory","arguments":{"path":"/记忆管理规则"}}}'
> ```

## 步骤 5 — prompts/list（对应测试 [4/7]）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"prompts/list"}'
```

## 步骤 6 — prompts/get（对应测试 [5/7]，调 `core_principles`）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":5,"method":"prompts/get","params":{"name":"core_principles"}}'
```

## 步骤 7 — resources/list（对应测试 [6/7]）

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":6,"method":"resources/list"}'
```

## 步骤 8 — resources/read（对应测试 [7/7]）

openmem 未注册 `@mcp.resource`，`resources/list` 会返回空数组，因此无需调用。如未来有资源，形如：

```bash
curl -i -N -X POST "$URL" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":7,"method":"resources/read","params":{"uri":"mem://xxx"}}'
```

## 使用提示

1. **本地服务**：将 `URL` 替换为 `http://127.0.0.1:6000/mcp`，`KEY` 换成本地 `users.json` 中的 admin key（或设 `auth.enabled=false` 跳过认证）。
2. **响应解析**：若服务端返回 SSE 流（`text/event-stream`），实际 JSON-RPC 结果在 `data:` 行内，需提取。若想强制纯 JSON，可尝试只发 `Accept: application/json`（取决于 FastMCP 版本是否允许）。
3. **会话关闭**：测试结束可发 `DELETE /mcp` 带 `Mcp-Session-Id` 头主动结束会话：
   ```bash
   curl -i -X DELETE "$URL" \
     -H "Authorization: Bearer $KEY" \
     -H "Mcp-Session-Id: $SID"
   ```
4. **PowerShell 适配**：在 Windows PowerShell 中使用 curl 时，建议用 `curl.exe` 显式调用（避免 `Invoke-WebRequest` 别名冲突），且 JSON body 中的双引号需转义或改用单引号包裹整体参数。
