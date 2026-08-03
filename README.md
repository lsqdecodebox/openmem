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

local 模式（推荐）：
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

remote 模式（需 openmem 服务端以 `openmem --remote` 启动）：
```json
{
  "mcp": {
    "openmem": {
      "type": "remote",
      "url": "http://127.0.0.1:6000/mcp"
    }
  }
}
```

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
| `get_directory` | `path`（默认 `/`）                          | 获取目录结构树，含每个条目的 title/summary/type/level                          |
| `read_memory`   | `path`                                  | 读取页面完整内容（含 Front Matter）                                         |
| `write_memory`  | `content`, `path?`, `tags?`, `summary?` | 覆盖写入记忆；path 为空时返回 `need_path` 提示；更新前自动快照；缺目录自动创建；summary 为空时自动生成 |

## 配置

配置文件路径：`~/.config/openmem/openmem.json`

```json
{
  "wiki_root": "./wiki",
  "max_depth": 7,
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
| `snapshot.enabled`                  | `true`   | 是否启用写入前快照    |
| `snapshot.cleanup_interval_minutes` | `10`     | 快照清理定时器间隔    |
| `snapshot.retention_days`           | `7`      | 快照保留天数       |
| `logging.file_enabled`              | `true`   | 是否启用日志文件输出   |
| `remote.host`                      | `"127.0.0.1"` | remote 模式下绑定的主机地址（可被 `--host` 覆盖） |
| `remote.port`                      | `6000`   | remote 模式下的监听端口（可被 `--port` 覆盖） |
| `remote.path`                      | `"/mcp"` | remote 模式下的 HTTP 端点路径（可被 `--path` 覆盖） |

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
| `test_mcp_api.py`     | MCP API | 直接调用 store 方法验证接口契约                 |
| `test_mcp_client.py`  | MCP 客户端 | 通过 `fastmcp.Client` 模拟客户端连接，走完整协议链路 |

## 项目结构

```
openmem/
├── __init__.py       # 版本号
├── main.py           # FastMCP 入口、工具/Prompt 注册、日志配置
├── initializer.py    # 启动初始化：配置文件、Wiki 根目录、核心提示词
├── store.py          # WikiStore：目录导航、页面读写、快照管理
└── utils.py          # 工具函数：路径校验、Front Matter、合并策略
```



## 其他资料

https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
