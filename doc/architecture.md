# OpenMem-MCP 技术架构

## 1. 项目概述

OpenMem-MCP 是一个基于 **Model Context Protocol (MCP)** 的个人 Wiki 记忆管理系统。它通过 MCP 协议向 AI 助手（如 OpenCode）暴露一系列工具，实现对本地文件系统上 Markdown Wiki 的读写、检索和维护。

### 1.1 核心目标

- **零依赖存储**：纯文件系统，无需数据库
- **混合驱动**：搜索和写入决策由 LLM 驱动，目录浏览等简单操作由文件系统直接驱动
- **渐进式加载**：按需逐层读取目录，避免全量扫描
- **Obsidian 兼容**：标准 Markdown + Front Matter，可直接在 Obsidian 中编辑

### 1.2 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| MCP 框架 | FastMCP >= 0.1.0 | MCP 服务器框架，暴露工具接口 |
| LLM 客户端 | OpenAI SDK >= 1.0.0 | 兼容任意 OpenAI 格式的 API |
| Markdown 解析 | mistune >= 3.0.0 | Markdown 解析 |
| Front Matter 处理 | python-frontmatter >= 1.0.0 | YAML 元数据读写 |
| 配置加载 | python-dotenv >= 1.0.0 | 环境变量加载 |
| 运行环境 | Python >= 3.10 | 编程语言 |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     AI Assistant                         │
│                   (OpenCode / Claude)                    │
└─────────────────────────┬───────────────────────────────┘
                          │ MCP Protocol (JSON-RPC over stdio)
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  FastMCP Server (main.py)                │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │                  Tool Layer                      │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │   │
│   │  │ add_     │ │ update_  │ │ search_          │ │   │
│   │  │ memory   │ │ memory   │ │ memories         │ │   │
│   │  ├──────────┤ ├──────────┤ ├──────────────────┤ │   │
│   │  │ get_page │ │ get_     │ │ create_          │ │   │
│   │  │          │ │ directory│ │ directory        │ │   │
│   │  ├──────────┤ ├──────────┤ ├──────────────────┤ │   │
│   │  │ run_     │ │ export_  │ │                  │ │   │
│   │  │ health_  │ │ wiki     │ │                  │ │   │
│   │  │ check    │ │          │ │                  │ │   │
│   │  └──────────┘ └──────────┘ └──────────────────┘ │   │
│   └─────────────────────────────────────────────────┘   │
│                          │                               │
│   ┌─────────────────────────────────────────────────┐   │
│   │                 Engine Layer                     │   │
│   │  ┌──────────────┐  ┌────────────┐               │   │
│   │  │ WriteEngine  │  │ ReadEngine │               │   │
│   │  │ (write_      │  │ (read_     │               │   │
│   │  │  engine.py)  │  │  engine.py)│               │   │
│   │  └──────┬───────┘  └─────┬──────┘               │   │
│   │  ┌──────┴───────────────┴──────┐                │   │
│   │  │      HealthEngine           │                │   │
│   │  │   (health_engine.py)        │                │   │
│   │  └──────────┬──────────────────┘                │   │
│   └─────────────┼───────────────────────────────────┘   │
│                 │                                       │
│   ┌─────────────┴───────────────────────────────────┐   │
│   │              Service Layer                       │   │
│   │  ┌──────────────┐  ┌──────────────┐             │   │
│   │  │  FileStore   │  │  LLMClient   │             │   │
│   │  │ (file_store  │  │ (llm_client  │             │   │
│   │  │  .py)        │  │  .py)        │             │   │
│   │  └──────┬───────┘  └──────┬───────┘             │   │
│   └─────────┼────────────────┼──────────────────────┘   │
└─────────────┼────────────────┼──────────────────────────┘
              │                │
              ▼                ▼
┌─────────────────┐  ┌──────────────────┐
│   Filesystem    │  │  LLM API         │
│   (Wiki 目录)    │  │  (OpenAI 兼容)    │
└─────────────────┘  └──────────────────┘
```

### 2.1 分层职责

| 层级 | 模块 | 职责 |
|------|------|------|
| **Tool Layer** | `main.py` | MCP 工具注册、参数校验、错误处理 |
| **Engine Layer** | `write_engine.py` | 写操作：记忆添加、更新、目录创建 |
| | `read_engine.py` | 读操作：渐进式搜索、结果合成 |
| | `health_engine.py` | 健康检查：完整性校验 |
| **Service Layer** | `file_store.py` | 文件系统 I/O、Front Matter 处理 |
| | `llm_client.py` | LLM API 调用、双模型策略 |

### 2.2 LLM 使用分布

| MCP 工具 | LLM 使用 | 说明 |
|----------|---------|------|
| `add_memory` | **是** | 渐进式导航、标题生成、摘要生成 |
| `update_memory` | **是**（merge 模式） | 内容智能合并 |
| `search_memories` | **是** | 目录匹配、答案合成 |
| `get_page` | 否 | 直接读取文件 |
| `get_directory` | **否** | 直接遍历文件系统 |
| `create_directory` | **否** | 目录创建和索引更新 |
| `run_health_check` | **否** | 文件完整性检查 |
| `export_wiki` | **否** | ZIP 压缩打包 |

**关键说明：**
- 所有 LLM 决策由 `LLMClient` 模块封装
- 读操作中，`get_page` 直接读文件，`search_memories` 才用 LLM 做渐进式导航
- 写操作中，`add_memory` 默认走 LLM 渐进式分类，指定 `suggested_path` 时可跳过 LLM

---

## 3. 核心模块设计

### 3.1 Config (`config.py`)

配置管理模块，负责加载和持久化 `openmem.json`。

**关键属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `wiki_root` | `Path` | Wiki 存储根目录的绝对路径 |
| `max_depth` | `int` | 最大目录嵌套深度（默认 7） |
| `default_tags` | `list[str]` | 新页面的默认标签 |
| `llm_config` | `dict` | LLM 配置（base_url, api_key, model 等） |
| `logging_level` | `str` | 日志级别 |

**配置加载流程：**

```
main.py 启动
    │
    ▼
Config("openmem.json")
    │
    ├── 解析 JSON 文件
    ├── 计算 wiki_root 的绝对路径
    └── 校验必填字段
```

### 3.2 FileStore (`file_store.py`)

文件存储层，封装所有文件系统操作。

**核心方法：**

| 方法 | 说明 | 关键行为 |
|------|------|----------|
| `read_page(path)` | 读取页面 | 返回 `frontmatter.Post` 对象 |
| `read_directory(path)` | 读取目录 | 返回目录 `目录.md` 内容 |
| `create_page(...)` | 创建页面 | 生成 Front Matter + 写入 + 更新父目录索引 |
| `create_directory(...)` | 创建目录 | 创建文件夹 + `目录.md` |
| `update_page(...)` | 更新页面 | 保留原始 Front Matter，更新内容 |
| `list_directory_items(path)` | 列出目录条目 | 解析 `目录.md`，返回结构化列表 |
| `export_wiki(output_path)` | 导出 Wiki | 压缩为 ZIP 归档 |

**原子写入机制：**

```
写入流程：
1. 生成带 .tmp 后缀的临时文件
2. 写入完整内容
3. fsync 确保刷盘
4. 原子重命名覆盖原文件
```

**目录索引维护：**

```
创建页面/目录时自动触发：
1. 写入目标文件
2. 读取父目录的 目录.md
3. 添加新条目 [[相对路径|标题]]
4. 写回 目录.md
```

### 3.3 LLMClient (`llm_client.py`)

LLM 客户端，封装 OpenAI 兼容 API 的调用。

**双模型策略：**

| 模型 | 用途 | 特点 |
|------|------|------|
| `small_model` | 标题生成、摘要创建、目录匹配 | 快速、低成本 |
| `large_model` | 内容合并、搜索答案合成 | 更强推理能力 |

**核心方法：**

| 方法 | 使用的模型 | 说明 |
|------|-----------|------|
| `chat_completion(messages, ...)` | 可配置 | 通用对话补全 |
| `generate_summary(content, max_length)` | small | 生成内容摘要 |
| `select_best_match(query, candidates, top_k)` | small | 从候选项中选择最相关项 |

### 3.4 WriteEngine (`write_engine.py`)

写引擎，处理所有写操作，包含 LLM 引导的路径选择逻辑。

**`add_memory` 流程：**

```
add_memory(content, suggested_path=None, tags=None, source="auto")
    │
    ├── suggested_path 不为空?
    │   ├── 是 → _add_to_path()
    │   │   ├── 路径以 .md 结尾 → 直接作为目标页面
    │   │   │   ├── 页面已存在 → merge 模式更新
    │   │   │   └── 页面不存在 → 创建新页面
    │   │   └── 路径为目录 → 在该目录下创建新页面
    │   │
    │   └── 否 → _find_best_location_and_add()
    │       └── 渐进式导航（见下方详细说明）
    │
    └── 返回结果字符串
```

**渐进式导航算法：**

```
_find_best_location_and_add(content)
    │
    level = 1
    current_path = "/"
    │
    while level < max_depth:
        │
        ├── 列出当前目录所有子条目
        │
        ├── LLM 选择最匹配的子条目
        │   ├── 选到目录 → 递归进入，level + 1
        │   └── 选到页面 → 在该目录下创建
        │
        └── 无匹配项 / 到达最大深度
            └── 在当前目录创建新页面
```

**`update_memory` 三种模式：**

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `merge` | LLM 智能合并新旧内容 | 补充信息、修正内容 |
| `append` | 追加到末尾 | 添加笔记附录 |
| `overwrite` | 完全替换 | 重写或更正 |

### 3.5 ReadEngine (`read_engine.py`)

读引擎，处理搜索操作，使用深度优先渐进式遍历。

**搜索算法：**

```
search(query, max_depth=7, max_results=3)
    │
    _search_recursive(query, "/", results, max_depth, level=1)
    │
    ├── 读取当前目录条目
    │
    ├── LLM 选择 top-2 最相关条目
    │   ├── 选到目录 → 递归深入
    │   │   ├── 超过 max_depth → 停止
    │   │   └── 未超过 → 继续深入
    │   │
    │   └── 选到页面 → 读取内容，加入 results
    │
    └── 遍历完成 → _generate_answer()
        └── LLM 合成最终答案
```

**关键特性：**

- 每次搜索从根目录重新开始，无缓存
- 每层最多选择 2 个候选项
- 结果数量上限由 `max_results` 控制
- 最终答案由 large model 合成

### 3.6 HealthEngine (`health_engine.py`)

健康检查引擎，验证 Wiki 结构完整性。

**检查项：**

| 检查项 | 级别 | 触发条件 |
|--------|------|----------|
| 缺少 `目录.md` | Error | 目录下无索引文件 |
| Front Matter 缺少必填字段 | Error | path/type/parent/title 缺失 |
| 超过最大深度 | Error | 目录层级 > max_depth |
| 内容过短 | Warning | 正文 < 20 字符 |
| 摘要过长 | Warning | summary > 150 字符 |

---

## 4. 数据模型

### 4.1 Front Matter 元数据

每个 Wiki 文件（页面或目录索引）必须包含以下 YAML Front Matter：

```yaml
---
title: 页面标题
path: /绝对/路径
type: page            # page | directory
level: 2              # 嵌套层级（1-7）
parent: /父目录       # 父目录路径
created_at: "2026-05-25T10:00:00"
updated_at: "2026-05-25T10:30:00"
summary: 简短描述     # 不超过 150 字符
tags: [标签1, 标签2]
source: auto          # 内容来源
---
```

### 4.2 目录索引文件 (`目录.md`)

每个目录下的索引文件，格式示例：

```markdown
---
title: 项目
path: /项目
type: directory
level: 2
parent: /
created_at: "2026-05-25T10:00:00"
updated_at: "2026-05-25T10:30:00"
summary: 项目相关文档
tags: []
source: auto
---

# 项目

- [[项目/openmem-mcp/openmem-mcp 三大 Bug 修复记录|openmem-mcp 三大 Bug 修复记录]]
```

---

## 5. 依赖关系

```
main.py
  ├── config.py
  │   └── openmem.json
  ├── file_store.py
  │   └── python-frontmatter
  ├── llm_client.py
  │   └── openai
  ├── write_engine.py
  │   ├── file_store.py
  │   └── llm_client.py
  ├── read_engine.py
  │   ├── file_store.py
  │   └── llm_client.py
  └── health_engine.py
      └── file_store.py
```

---

## 6. 配置参考

### `openmem.json`

```json
{
  "wiki_root": "./wikitest0525",
  "max_depth": 7,
  "default_tags": [],
  "llm": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "small_model": "gpt-4o-mini",
    "large_model": "gpt-4o",
    "timeout": 30
  },
  "logging": {
    "level": "INFO"
  }
}
```

### 环境变量

可通过 `.env` 文件覆盖配置中的 `api_key`：
```
OPENAI_API_KEY=sk-...
```