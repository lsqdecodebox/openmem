# OpenMem

基于 MCP 协议的个人 Wiki 记忆系统。LLM 客户端（Claude Desktop / OpenCode 等）通过 MCP Tool/Prompt 接口读写 Wiki 页面，实现持久化记忆。

## 快速开始

### 安装

```bash
pip install -e .
```

含开发依赖（测试）：

```bash
pip install -e ".[dev]"
```

### 独立使用

默认以 stdio 本地模式启动：

```bash
openmem
```

以 streamable-http 远程模式启动：

```bash
openmem --remote
# 服务将在 http://127.0.0.1:6000/mcp 启动
```

远程模式参数可通过命令行覆盖（优先级高于配置文件）：

```bash
openmem --remote --host 0.0.0.0 --port 9000 --path /api
```

参数优先级：**命令行 > 配置文件 > 默认值**

### 客户端std模式使用

**Claude Desktop** — 编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "openmem": {
      "command": "openmem",
      "args": []
    }
  }
}
```

**OpenCode** — 在 `.opencode.json` 中配置：

local 模式（推荐，免认证）：
```json
{
  "mcp": {
    "openmem": {
      "type": "local",
      "command": ["openmem"]
    }
  }
}
```

remote 模式（需 openmem 服务端以 `openmem --remote` 启动，需 Bearer Key 认证）：
```json
{
  "mcp": {
    "openmem": {
      "type": "remote",
      "url": "http://127.0.0.1:6000/mcp",
      "headers": {
        "Authorization": "Bearer om_xxxxxxxx"
      }
    }
  }
}
```

> remote 模式下所有请求必须携带 `Authorization: Bearer <api_key>` 头，无 Key 或无效 Key 将被协议层 401 拒绝。stdio 本地模式默认 admin，无需认证。

智能体提示词配置：将system_prompt.md的信息配置至系统提示词上，例如 agents.md

### 知识库可视化

使用obsidian软件打开 wiki_root文件夹，默认位于 `~/.config/openmem/wiki `

## 首次启动

首次运行时自动初始化：

1. 生成配置文件 `~/.config/openmem/openmem.json`
2. 创建 Wiki 根目录（默认 `./wiki`）

## MCP 接口

### 工具（Tools）

| 工具              | 参数                                      | 说明                                                               |
| --------------- | --------------------------------------- | ---------------------------------------------------------------- |
| `get_directory` | `path`（默认 `/`）                          | 获取目录结构树，含每个条目的 summary/type/level；不返回 `images/files/videos` 资产目录；目录下若有 `summary.md` 则上提为目录节点的 summary/tags；返回 JSON 字符数超 `max_chars` 时自底向上压缩最底层目录的非 summary 文件，压缩后目录节点新增 `_compressed_filecount` 与 `_compressed_filenames`（截断 50 字） |
| `read_memory`   | `path`                                  | 读取页面完整内容（含 Front Matter）；路径首段为 `images/files/videos` 时报错；可读取 `summary.md` |
| `write_memory`  | `content`, `path?`, `tags?`, `summary?` | 覆盖写入记忆；path 为空时返回 `need_path` 提示；路径首段为 `images/files/videos` 时报错；更新前自动快照；缺目录自动创建；summary 为空时自动生成；路径以 `/summary` 结尾时强制 `type=directory_summary` 且正文清空（用于生成目录元数据） |
| `write_asset`   | `source`, `path`, `filename`, `type?`, `overwrite?` | 写入二进制资产到 `images/files/videos` 目录；`type` 默认 `files`               |
| `read_asset`    | `path`                                  | 读取资产元信息（绝对路径、相对路径、文件大小）                                          |

## 权限认证

### 模式差异

| 模式 | 认证 | 默认角色 |
| --- | --- | --- |
| stdio 本地（`openmem`） | 无需认证 | admin（信任本机） |
| remote 远程（`openmem --remote`） | 强制 Bearer Key | 由 Key 映射的角色决定 |

### 权限矩阵

| 角色 | get_directory | read_memory | read_asset | write_memory | write_asset |
| --- |:---:|:---:|:---:|:---:|:---:|
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| user | ✓ | ✓ | ✓ | ✗ | ✗ |
| 无 Key / 无效 Key（remote） | — 协议层 401 拒绝 — | | | | |

### users.json 格式

密钥映射表存储在 `~/.config/openmem/users.json`，手动编辑后热生效（无需重启）：

```json
{
  "users": [
    {
      "api_key": "om_xxxxxxxx",
      "username": "admin",
      "role": "admin",
      "status": "active",
      "created_at": "2026-08-05T10:00:00",
      "note": "管理员"
    },
    {
      "api_key": "om_user_yyyyyyyy",
      "username": "claude-desktop",
      "role": "user",
      "status": "active",
      "created_at": "2026-08-05T10:00:00",
      "applicantCode": "APP-2026-001",
      "note": "只读客户端"
    }
  ]
}
```

### 首次启动

首次运行且 `users.json` 不存在时自动引导 admin：

1. 优先读环境变量 `OPENMEM_ADMIN_API_KEY`
2. 无环境变量则生成 `om_<32hex>` 随机 Key（不含角色信息），在控制台**一次性打印**

### 认证服务（grant 端点）

remote 模式下提供 `POST /auth/grant` 端点，供内部系统按需申请 user 级 API Key。该端点为 FastMCP `custom_route`，**不经过 TokenVerifier**，可在无 Key 时访问（否则陷入"没 Key 无法获取 Key"的死循环）。

**请求**

```
POST /auth/grant
Content-Type: application/json

{
  "applicantCode": "APP-2026-001",   // 必填，发证凭证，由内部系统发送
  "username": "claude-desktop",       // 可选，users.json 标识
  "note": "内部系统发放"               // 可选备注
  // 联调期可追加任意字段（如 timestamp/signature），不会报错
}
```

**响应**

```json
{
  "api_key": "om_a1b2c3d4e5f6...",
  "role": "user",
  "username": "claude-desktop",
  "status": "active",
  "applicantCode": "APP-2026-001",
  "created_at": "2026-08-05T10:00:00",
  "is_new": true
}
```

| 状态码 | 含义 |
| --- | --- |
| 200 | 签发成功（`is_new=true`）或幂等命中（`is_new=false`，返回同一个 key） |
| 400 | applicantCode 为空 / 请求体非合法 JSON |
| 403 | grant 服务被配置禁用（`auth.grant.enabled=false`） |
| 422 | 请求体校验失败（缺 applicantCode） |
| 500 | users.json 写入失败 |

**核心规则**

- **只签发 user 角色**：永不签发 admin，申请到的 Key 仅可调用只读工具（`get_directory` / `read_memory` / `read_asset`）
- **幂等**：同一 `applicantCode` 再次请求返回**同一个** Key，不签发新 Key（`applicantCode` 作为幂等键写入 users.json）
- **凭证不校验**：`applicantCode` 由内部系统发送，端点当前不校验合法性（信任内网/本机调用方）；凭证校验逻辑封装在 `validate_applicant()` 钩子函数中，联调期改规则只动这一处
- **字段透传**：请求体用 Pydantic `extra="allow"`，联调期追加的字段不报错、不丢失

**curl 示例**

```bash
curl -X POST http://127.0.0.1:6000/auth/grant \
  -H "Content-Type: application/json" \
  -d '{"applicantCode":"APP-2026-001","username":"claude-desktop"}'
```

**安全提示**：grant 端点本身无认证（依赖 `applicantCode` 不校验），信任边界在网络层。openmem remote 默认绑定 `127.0.0.1`，仅本机可访问；内部系统应通过内网/本机调用。不需要时可在配置中关闭。

### NAS 同步

`scripts/sync_to_nas.sh`（Linux/macOS，rsync）和 `scripts/sync_to_nas.ps1`（Windows，robocopy）提供 users.json + wiki 至 NAS 的同步骨架。由 OS 定时任务（cron / Task Scheduler）驱动，不进 openmem 主进程。编辑脚本内变量填入实际 NAS 地址即可使用。

## 配置

配置文件路径：`~/.config/openmem/openmem.json`

```json
{
  "wiki_root": "./wiki",
  "max_depth": 7,
  "max_chars": 500000,
  "snapshot": {
    "enabled": true,
    "cleanup_interval_minutes": 10,
    "retention_days": 7
  },
  "default_tags": [],
  "remote": {
    "host": "127.0.0.1",
    "port": 6000,
    "path": "/mcp"
  },
  "auth": {
    "enabled": true,
    "users_file": "~/.config/openmem/users.json",
    "stdio_default_role": "admin",
    "grant": {
      "enabled": true
    }
  },
  "logging": {
    "level": "INFO",
    "file_enabled": true,
    "file_path": "./logs/openmem.log",
    "max_file_size_mb": 10,
    "backup_count": 5,
    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
  }
}
```

| 字段                                  | 默认值      | 说明           |
| ----------------------------------- | -------- | ------------ |
| `wiki_root`                         | `./wiki` | Wiki 文件存储根目录 |
| `max_depth`                         | `7`      | 目录最大层级深度     |
| `max_chars`                         | `500000` | `get_directory` 返回 JSON 字符数上限，超限后自底向上压缩最底层目录的非 summary 文件 |
| `snapshot.enabled`                  | `true`   | 是否启用写入前快照    |
| `snapshot.cleanup_interval_minutes` | `10`     | 快照清理定时器间隔    |
| `snapshot.retention_days`           | `7`      | 快照保留天数       |
| `logging.file_enabled`              | `true`   | 是否启用日志文件输出   |
| `remote.host`                      | `"127.0.0.1"` | remote 模式下绑定的主机地址（可被 `--host` 覆盖） |
| `remote.port`                      | `6000`   | remote 模式下的监听端口（可被 `--port` 覆盖） |
| `remote.path`                      | `"/mcp"` | remote 模式下的 HTTP 端点路径（可被 `--path` 覆盖） |
| `auth.enabled`                     | `true`  | 是否启用 remote 认证；`false` 时 remote 也免认证（调试用） |
| `auth.users_file`                  | `"~/.config/openmem/users.json"` | 密钥映射表路径，与 `openmem.json` 同目录 |
| `auth.stdio_default_role`          | `"admin"` | stdio 本地模式默认角色（信任本机） |
| `auth.grant.enabled`               | `true`  | 是否开启 `/auth/grant` 认证服务端点；`false` 时端点返回 403 |

> 启动模式通过命令行 `--remote` 开关控制，不再使用配置文件。旧版配置中的 `transport` 字段已废弃，保留不报错但不生效。

## 存储结构

```
wiki/                          ← wiki_root
├── 记忆管理规则.md             ← 核心提示词 
├── 用户偏好习惯.md
├── Agent行为指南.md
├── Wiki整理指南.md
├── 01-工作/                   ← 用户分类目录
│   └── 项目A.md
├── 02-学习/
│   └── Python.md
├── images/                    ← 资产目录（仅 write_asset/read_asset 可访问）
│   └── 01-工作/项目A/diagram.png
├── files/
│   └── 01-工作/项目A/spec.pdf
├── videos/
│   └── 02-学习/demo.mp4
└── .snapshots/                ← 快照目录（自动管理）
    └── 01-工作/
        └── 项目A/
            └── 2026-07-06T12-00-00.md
```

每个 .md 文件为标准 Markdown + YAML Front Matter，可直接用 Obsidian 打开：

```markdown
---
title: 项目A
type: page
level: 2
summary: 项目进度记录...
tags:
- 工作
---
项目进度记录
```

## 核心机制

- **写入前快照** — 更新已有页面时，自动将旧版复制到 `.snapshots/` 下，按 ISO 时间戳命名
- **覆盖写入** — 新内容直接覆盖现有正文，不做合并
- **缺目录自动创建** — 写入路径的父目录不存在时逐级创建
- **路径安全校验** — 防路径穿越，目录深度不超过 7 层

## 资产管理

系统支持三类二进制资产：`images`、`files`、`videos`，分别存储在 `wiki_root` 下的同名目录。

### 接口隔离规则

| 操作                | 允许的接口                       | 禁止的接口                        |
| ------------------- | -------------------------------- | --------------------------------- |
| 读写 Wiki 页面(.md) | `read_memory` / `write_memory`   | —                                 |
| 读写二进制资产      | `read_asset` / `write_asset`     | `read_memory` / `write_memory`    |
| 浏览目录结构        | `get_directory`                  | —                                 |

- `get_directory` **不会返回** `images/`、`files/`、`videos/` 目录及其内容
- `read_memory` / `write_memory` 收到首段为这三类名的路径时，直接返回错误，不执行
- 资产路径仅在 Markdown 正文中以相对路径形式引用，例如：

  ```markdown
  ![架构图](images/01-工作/项目A/diagram.png)
  [需求文档](files/01-工作/项目A/spec.pdf)
  ```

- LLM 如需在记忆中引用资产，应：先 `write_asset` 上传文件 → 拿到返回的相对路径 → 在 `write_memory` 的正文里以该相对路径嵌入

## 测试

```bash
pytest tests/ -v
```

测试分层：

| 文件                    | 层级      | 说明                                  |
| --------------------- | ------- | ----------------------------------- |
| `test_utils.py`       | 工具函数    | 路径校验、合并、Front Matter 等              |
| `test_initializer.py` | 初始化     | 配置/Wiki/核心提示词创建                     |
| `test_store.py`       | 存储层     | WikiStore 读写、快照                     |
| `test_auth.py`        | 认证权限    | ApiKeyAuth / UserStore / 权限矩阵 / 首次引导 |
| `test_auth_service.py`| 认证服务    | GrantRequest / grant_user_key 幂等发证 / grant 端点契约 / 端到端权限 |
| `test_mcp_api.py`     | MCP API | 直接调用 store 方法验证接口契约                 |
| `test_mcp_client.py`  | MCP 客户端 | 通过 `fastmcp.Client` 模拟客户端连接，走完整协议链路 |

## 项目结构

```
openmem/
├── __init__.py       # 版本号
├── main.py           # FastMCP 入口、工具/Prompt 注册、日志配置、权限守卫、grant 端点
├── initializer.py    # 启动初始化：配置文件、Wiki 根目录、users.json 引导
├── auth.py           # API Key 认证：ApiKeyAuth / UserStore / 权限矩阵
├── auth_service.py   # 认证服务：grant 端点逻辑（GrantRequest / grant_user_key / 幂等发证）
├── store.py          # WikiStore：目录导航、页面读写、快照管理
└── utils.py          # 工具函数：路径校验、Front Matter、合并策略
```



## 版本历史

### v2.4.0 — 认证服务（grant 端点）

- 新增 `POST /auth/grant` 认证服务端点（FastMCP `custom_route`，不经过 TokenVerifier，可在无 Key 时访问），供内部系统按需申请 user 级 API Key
- 请求体 `applicantCode` 字段作为发证凭证（内部系统发送，当前不校验合法性），同时作为幂等键：同 `applicantCode` 再次请求返回同一个 Key，不签发新 Key
- 永远签发 `user` 角色，永不签发 admin；签发的 Key 写入 `users.json` 并带 `applicantCode` 字段
- 请求体用 Pydantic `extra="allow"` 透传联调期额外字段；凭证校验封装为 `validate_applicant()` 钩子函数，联调改规则只动一处
- 新增 `openmem/auth_service.py` 模块；`openmem/auth.py` 的 `UserStore` 新增 `find_by_applicant` / `add_user` 方法
- `openmem.json` 新增 `auth.grant.enabled` 配置开关
- 新增 `tests/test_auth_service.py` 35 条测试用例

### v2.3.0 — 权限认证

- remote 模式新增 API Key 认证（FastMCP `auth=TokenVerifier`），无 Key / 无效 Key 协议层 401 拒绝
- 权限矩阵：admin 全权；user 只读（`get_directory` / `read_memory` / `read_asset`）；stdio 本地默认 admin 免认证
- 密钥映射表 `users.json`（`~/.config/openmem/`），mtime 缓存热更新，手动编辑无需重启
- 首次启动引导 admin：优先读 `OPENMEM_ADMIN_API_KEY` 环境变量，否则生成随机 Key 并一次性打印
- NAS 同步脚本骨架 `scripts/sync_to_nas.{sh,ps1}`（rsync / robocopy，由 OS 定时器驱动）
- `openmem.json` 新增 `auth` 配置块（`enabled` / `users_file` / `stdio_default_role`）
- 新增 `openmem/auth.py` 模块；`tests/test_auth.py` 18 条测试用例

### v2.0.0 — Remote 模式

- 新增 `streamable-http` 远程模式，通过 `--remote` 开关启动，支持 `--host/--port/--path` 命令行覆盖（优先级：命令行 > 配置文件 > 默认值）
- 废弃配置文件 `transport` 字段，启动模式改由命令行控制；remote 默认端口调整为 `6000`
- 远程模式日志优化：屏蔽 MCP 底层噪声日志、`log_level=warning`、关闭 `access_log`
- 资产读写逻辑梳理与规范
- `get_directory` 渐进式披露与压缩机制（`max_chars` 上限，超限自底向上压缩非 summary 文件）
- OpenCode remote 模式配置示例
- 修复快照 bug、日志 bug；更新默认 wiki 和 log 位置

### v1.0.0 — Local 模式

- 基于 MCP 协议的个人 Wiki 记忆系统，stdio 本地模式启动
- Python 包化，`pip install -e .` 安装，提供 `openmem` 命令
- 五大 MCP 工具：`get_directory` / `read_memory` / `write_memory` / `write_asset` / `read_asset`
- `core_principles` Prompt 接口
- 核心机制：写入前快照、覆盖写入、缺目录自动创建、路径安全校验（目录深度 ≤ 7）
- 资产管理（`images/files/videos` 三类二进制资产，接口隔离规则）
- 配置文件 `openmem.json`，首次启动自动初始化
- 定时快照清理（`cleanup_interval_minutes` / `retention_days`）
- 测试分层（工具函数 / 初始化 / 存储层 / MCP API / MCP 客户端）
- 支持 Obsidian 可视化

## 其他资料

https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
