# 纯文件系统驱动的Wiki式记忆MCP工具（极简无依赖）


## 一、架构概览

```mermaid
flowchart TD
    A[智能体端<br/>Claude / OpenCode] --> B[MCP协议接入层<br/>FastMCP]
    A -->|LLM+核心提示词<br/>完成调度决策| A

    subgraph 记忆核心业务层
        C1[获取Wiki层级文件列表]
        C2[读取某一个Wiki文件]
        C3[写入Wiki文件<br/>缺目录自动创建]
    end

    B --> C1
    B --> C2
    B --> C3
    B --> C4[获取核心提示词<br/>暴露给客户端LLM]

    C1 --> D[文件系统存储层<br/>Obsidian原生兼容]
    C2 --> D
    C3 --> D
    C4 --> D1[核心提示词文件<br/>一级目录下所有.md文件]
    D --> D2[Wiki目录层级<br/>最多7层]
    D --> D3[标准Wiki页面<br/>纯Markdown+强制Front Matter]
    D --> D4[快照存档<br/>可配置间隔与保留期]

    E[配置中心<br/>~/.config/openmem/openmem.json] -.-> C1
    E -.-> C2
    E -.-> C3
    E -.-> C4

    F[Obsidian 客户端] --> D
```


## 二、文件系统存储层

### 2.1 根目录结构

```
wiki-root/
├── 记忆管理规则.md              # 核心提示词：记忆分类、合并、过期等管理规则
├── 用户偏好习惯.md              # 核心提示词：用户沟通风格、习惯表达、个人偏好
├── Agent行为指南.md             # 核心提示词：Agent写入行为规范与决策边界
├── Wiki整理指南.md              # 核心提示词：Wiki结构整理与内容归并规范
├── 00-个人/                    # 一级目录
│   ├── 健康.md
│   └── 学习/                   # 二级目录
│       └── Python学习笔记.md
├── 01-工作/
│   └── 项目A.md
└── 02-知识库/
```

### 2.2 核心提示词文件

位于Wiki根目录（一级目录）下的所有 `.md` 文件均为核心提示词文件。核心提示词**允许写入流程内部逻辑读取**，但其主要使用方式是**通过MCP接口直接暴露给客户端**（如Claude），由客户端LLM结合提示词完成调度决策（如何分类、是否合并、写入哪里等）。

**核心提示词文件列表**（并列关系，各司其职）：

| 文件 | 职责 | 说明 |
|------|------|------|
| `记忆管理规则.md` | 记忆分类与合并 | 定义记忆的层次、分类、合并、过期等管理规则 |
| `用户偏好习惯.md` | 用户个性化 | 记录用户沟通风格、习惯表达、个人偏好等 |
| `Agent行为指南.md` | 写入行为规范 | 定义Agent写入行为规范、决策边界、何时主动/被动写入 |
| `Wiki整理指南.md` | 结构整理与归并 | 定义Wiki目录结构整理、内容归并、冗余消除等规范 |

**`记忆管理规则.md` 内容示例**：

```markdown
---
title: 记忆管理规则
type: corepage
level: 1
summary: "记忆系统的核心管理规则，指导所有写入和合并决策。"
tags: ["核心", "规则"]
---
# 记忆管理规则

## 核心原则
记忆有层次和顺序，但是内容精简不重叠。

## 单篇原则
每篇笔记仅讲述一个概念/方法/知识点。

## 合并原则
若以下四项中任意三项相同，则需要合并：
- 主体（谁/什么）
- 核心动作（做什么）
- 特点/条件（在什么情况下）
- 结论/观点（结果是什么）
```

**`用户偏好习惯.md` 内容示例**：

```markdown
---
title: 用户偏好习惯
type: corepage
level: 1
summary: "用户的沟通风格与个人偏好记录。"
tags: ["核心", "偏好"]
---
# 用户偏好习惯

## 沟通风格
- 偏好简洁直接的回答
- 不喜欢过多寒暄和解释

## 工作习惯
- 使用4空格缩进
- 函数名驼峰命名，变量名下划线命名
```

**`Agent行为指南.md` 内容示例**：

```markdown
---
title: Agent行为指南
type: corepage
level: 1
summary: "Agent写入行为规范与决策边界。"
tags: ["核心", "指南"]
---
# Agent行为指南

## 主动写入场景
- 用户明确要求记住某事
- 用户纠正Agent的错误认知

## 被动写入场景
- 仅在用户触发时写入，不主动猜测

## 写入边界
- 不记录临时性对话上下文
- 不记录已过期的任务信息
```

**`Wiki整理指南.md` 内容示例**：

```markdown
---
title: Wiki整理指南
type: corepage
level: 1
summary: "Wiki目录结构整理与内容归并规范，指导Agent定期维护知识库结构清晰与内容精简。"
tags: ["核心", "整理"]
---
# Wiki整理指南

## 整理原则

### 结构原则
- 目录层级不超过7层，优先3层以内组织
- 同一主题的内容归入同一目录，不同主题分目录存放
- 目录命名使用"序号-名称"格式，如"01-工作"、"02-学习"
- 空目录应当删除，避免结构冗余

### 归并原则
- 遵循"记忆管理规则"中的合并原则
- 两篇页面若主题高度重叠，应合并为一篇
- 合并后保留信息更完整的版本作为基底，补充另一篇的独特内容
- 合并完成后，将冗余页面内容迁移并删除原页面

### 单篇原则
- 每篇页面仅讲述一个概念/方法/知识点
- 页面内容超过500字时，考虑拆分为子页面
- 页面内容不足20字时，考虑归并到相关父页面或兄弟页面

## 整理流程

### 第一步：扫描目录结构
- 从根目录开始，递归遍历所有目录和页面
- 记录每个目录下的页面数量和子目录数量
- 识别空目录（无子目录且无页面）和层级过深的目录（超过5层）

### 第二步：检查单篇规范
- 找出内容超过500字的页面，标记为待拆分候选
- 找出内容不足20字的页面，标记为待归并候选

### 第三步：检查归并需求
- 遍历同一目录下的所有页面，比较主题重叠度
- 依据"记忆管理规则"中的合并原则（四项中任意三项相同则合并），标记需合并的页面组

### 第四步：执行整理
- 对待归并页面：将内容合并到信息更完整的页面，补充另一篇的独特内容，删除冗余页面
- 对待拆分页面：按子主题拆分为子页面，在原页面保留概览和子页面链接
- 对空目录：直接删除
- 对层级过深的目录：将深层页面提升到更合理的层级

### 第五步：验证与收尾
- 确认整理后所有页面Front Matter字段完整（title、type、level、summary、tags）
- 确认目录结构符合"序号-名称"命名规范
- 确认无孤立页面（内容未被任何其他页面引用且不在合理目录下的页面）

## 注意事项
- 整理前务必确认快照机制已启用，确保可恢复
- 一次整理操作涉及的页面不超过10篇，避免大规模变动
- 核心提示词文件（一级目录下.md文件）不参与整理归并
- 整理过程中如发现用户偏好信息，应更新到"用户偏好习惯.md"
```

> **扩展规则**：用户可自行在Wiki根目录下新增 `.md` 文件作为新的核心提示词，系统自动识别一级目录下所有 `.md` 文件为核心提示词，无需额外配置。

### 2.3 Wiki页面Front Matter规范

使用 `python-frontmatter` 库解析Markdown文件的YAML头部，所有Markdown文件必须包含以下Front Matter字段：

```markdown
---
title: Python学习笔记
type: page
level: 3
summary: "Python基础语法、常用库介绍和学习资源汇总。包含NumPy、Pandas等数据科学库的使用方法。"
tags: ["python", "编程", "学习"]
---
# Python学习笔记
## 基础语法
Python是一种解释型、面向对象的高级编程语言...
```

**字段说明**：
| 字段 | 说明 | 强制 |
|------|------|------|
| `title` | 页面标题 | ✅ |
| `type` | 类型：`page` | ✅ |
| `level` | 层级：1-7 | ✅ |
| `summary` | 100字以内摘要 | ✅ |
| `tags` | 标签列表 | ✅ |



### 2.4 7层深度限制

- 根目录文件：level=1
- 一级子目录内文件：level=2
- ...
- 最深层级：level=7
- 任何尝试创建超过7层目录的操作都会被拒绝


## 三、记忆核心业务层

### 3.1 获取Wiki层级文件列表（get_directory）

获取指定目录下的文件和子目录列表，用于导航和浏览Wiki结构。

```python
@mcp.tool()
def get_directory(path: str = "/") -> str:
    """
    获取指定目录的层级文件列表

    Args:
        path: 目录路径，默认根目录

    Returns:
        目录结构和子条目列表（含每个条目的title、summary、type、level）
    """
    pass
```

**返回格式**（树形目录结构，递归展示子条目）：
```json
{
    "path": "/",
    "name": "wiki-root",
    "type": "directory",
    "children": [
        {
            "name": "记忆管理原则.md",
            "type": "page",
            "level": 1,
            "title": "记忆管理原则",
            "summary": "记忆系统的核心管理原则"
        },
        {
            "name": "00-个人",
            "type": "directory",
            "level": 1,
            "children": [
                {
                    "name": "健康.md",
                    "type": "page",
                    "level": 2,
                    "title": "健康",
                    "summary": "健康记录与运动计划"
                },
                {
                    "name": "学习",
                    "type": "directory",
                    "level": 2,
                    "children": [
                        {
                            "name": "Python学习笔记.md",
                            "type": "page",
                            "level": 3,
                            "title": "Python学习笔记",
                            "summary": "Python基础语法与常用库介绍"
                        }
                    ]
                }
            ]
        },
        {
            "name": "01-工作",
            "type": "directory",
            "level": 1,
            "children": [
                {
                    "name": "项目A.md",
                    "type": "page",
                    "level": 2,
                    "title": "项目A",
                    "summary": "项目A的进展与关键信息"
                }
            ]
        },
        {
            "name": "02-知识库",
            "type": "directory",
            "level": 1,
            "children": []
        }
    ]
}
```

### 3.2 读取某一个Wiki文件（read_memory）

读取指定路径的Wiki页面完整内容，包括Front Matter和正文。

```python
@mcp.tool()
def read_memory(path: str) -> str:
    """
    读取指定路径的完整Wiki页面内容

    Args:
        path: 页面完整路径，如"/00-个人/学习/Python学习笔记"

    Returns:
        页面完整内容，包括Front Matter
    """
    pass
```

### 3.3 写入Wiki文件（write_memory）

写入操作允许内部读取核心提示词，但调度决策主要由客户端LLM（结合核心提示词）完成。

```python
@mcp.tool()
def write_memory(content: str, path: str = None, tags: list[str] = None) -> str:
    """
    写入记忆

    Args:
        content: 要写入的记忆内容
        path: 目标路径，如"/00-个人/学习/Python学习笔记"。为空时自动分类
        tags: 可选的标签列表

    Returns:
        最终页面路径
    """
    pass
```

**缺目录自动创建**：若目标路径的父目录不存在，自动逐级创建目录

### 3.4 核心提示词

核心提示词存储在Wiki一级目录下的所有 `.md` 文件中，**通过MCP接口直接暴露给客户端LLM**，由客户端LLM结合提示词完成调度决策。写入流程内部也允许读取核心提示词。

关于暴露方式的选择分析（详见3.5节）：

```python
@mcp.prompt(name="core_principles")
def core_principles_prompt() -> str:
    """
    获取所有核心提示词，供客户端LLM用于调度决策

    Returns:
        所有核心提示词的完整内容，按文件名排列拼接
    """
    pass
```

### 3.5 核心提示词暴露方式分析：Prompt vs Resource vs Tool

核心提示词需要暴露给客户端LLM，MCP协议提供三种机制，分析如下：

#### 方案一：`@mcp.prompt()`（推荐）

```python
@mcp.prompt(name="core_principles", description="记忆系统核心提示词，包含记忆管理规则、用户偏好、行为指南、整理指南")
def core_principles_prompt() -> str:
    """获取所有核心提示词，供LLM调度决策"""
    return store.get_core_principles()
```

**优势**：
- **语义最匹配**：核心提示词本身就是"提示词"，用prompt注册语义完全对齐
- **客户端原生支持**：Claude Desktop等客户端会通过 `prompts/list` 自动发现可用prompt，用户可直接选择注入对话
- **LLM自动获取**：客户端LLM可在对话开始时主动获取prompt内容，无需用户手动触发工具调用
- **支持多prompt**：可将4个核心提示词文件分别注册为独立prompt，客户端按需选择

**劣势**：
- 客户端对prompt的支持程度不一，部分客户端可能不会自动注入prompt到上下文

#### 方案二：`@mcp.resource()`

```python
@mcp.resource("wiki://core-principles", name="core_principles", mime_type="text/markdown")
def core_principles_resource() -> str:
    """核心提示词资源"""
    return store.get_core_principles()
```

**优势**：
- **语义较匹配**：核心提示词可视为"可读取的数据资源"
- **客户端自动发现**：客户端通过 `resources/list` 可发现资源，部分客户端会自动订阅资源变更
- **支持MIME类型**：可声明为 `text/markdown`，客户端可正确渲染

**劣势**：
- Resource的语义是"数据源"，不如prompt的"提示词"语义精确
- 客户端不一定自动读取resource内容注入LLM上下文，可能需要用户手动引用
- Resource更偏向"文件/数据"的读取，核心提示词需要"注入LLM上下文"的行为特征

#### 方案三：`@mcp.tool()`（当前方案）

```python
@mcp.tool()
def get_core_principles() -> str:
    """获取所有核心提示词"""
    return store.get_core_principles()
```

**优势**：
- 实现最简单，客户端普遍支持tool调用

**劣势**：
- **语义不匹配**：Tool的语义是"执行操作"，获取提示词不涉及任何副作用操作
- **需要主动调用**：客户端LLM需要先调用tool才能获取提示词，增加了调用链路
- **浪费token**：LLM需要先决定调用tool → 执行tool → 读取结果 → 再做决策，多一轮交互

#### 结论

| 维度 | Prompt | Resource | Tool |
|------|--------|----------|------|
| 语义匹配度 | ★★★ 完全匹配 | ★★ 数据源 | ★ 操作 |
| LLM自动获取 | ★★ 部分客户端支持 | ★ 需手动引用 | ★ 需主动调用 |
| 客户端兼容性 | ★★ 主流客户端支持 | ★★ 主流客户端支持 | ★★★ 普遍支持 |
| 调用效率 | ★★ 直接注入上下文 | ★★ 需引用 | ★ 多一轮交互 |

**推荐方案**：使用 `@mcp.prompt()` 注册核心提示词。若需兼容性保底，可同时用 `@mcp.tool()` 暴露，但主入口为prompt。

> **注意**：具体采用哪种方案需结合目标客户端（Claude Desktop、OpenCode等）对prompt/resource的实际支持情况决定。如果客户端不支持自动注入prompt，退而使用tool方案。


## 四、快照存档机制

### 4.1 核心规则

- 文件的**每次改动**前，对原文件创建快照存档
- 快照存储在Wiki根目录下的 `.snapshots/` 隐藏目录中
- 快照按时间和文件路径组织

### 4.2 快照目录结构

```
wiki-root/
├── .snapshots/
│   └── 00-个人/
│       └── 学习/
│           └── Python学习笔记/
│               ├── 2026-07-03T10-00-00.md
│               ├── 2026-07-03T10-30-00.md
│               └── 2026-07-03T11-00-00.md
```

### 4.3 定期清理

- 每 **10分钟** 执行一次清理检查（可配置）
- 快照保留 **7天**（可配置）
- 超过保留期的快照自动删除

### 4.4 配置项

配置文件位于 `Path.home() / ".config" / "openmem" / "openmem.json"`，不在Wiki根目录内：

```json
{
    "wiki_root": "./wikitest0525",
    "max_depth": 7,
    "snapshot": {
        "enabled": true,
        "cleanup_interval_minutes": 10,
        "retention_days": 7
    },
    "default_tags": [],
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


## 五、日志策略

### 5.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| `DEBUG` | 详细调试信息，开发阶段使用 | 文件Front Matter解析细节、目录遍历过程 |
| `INFO` | 关键操作记录，生产环境默认级别 | 页面创建/更新/删除、快照创建、搜索执行 |
| `WARNING` | 异常但可恢复的情况 | 合并冲突自动解决、快照清理跳过被占用文件 |
| `ERROR` | 操作失败 | 文件写入失败、路径超7层限制、权限不足 |

### 5.2 日志输出目标

| 输出目标 | 说明 | 配置项 |
|----------|------|--------|
| **控制台（stderr）** | 始终启用，用于开发调试 | 不可关闭 |
| **文件** | 可选启用，按天轮转 | `logging.file_enabled`、`logging.file_path` |

### 5.3 文件日志轮转策略

- **单文件大小上限**：`max_file_size_mb`（默认10MB），超过后自动轮转
- **保留文件数**：`backup_count`（默认5个），即 `openmem.log` + 5个历史文件
- **轮转命名**：`openmem.log` → `openmem.log.1` → `openmem.log.2` → ...
- **最老文件自动删除**：超过 `backup_count` 的历史文件自动清理

### 5.4 日志格式

```
2026-07-03 10:30:00,123 | INFO     | openmem.write | 创建页面: /00-个人/学习/Python学习笔记
2026-07-03 10:30:01,456 | WARNING  | openmem.merge | 合并冲突自动解决: /01-工作/项目A
2026-07-03 10:30:02,789 | ERROR    | openmem.store | 写入失败: 权限不足 /02-知识库/机密.md
```

格式模板：`%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`

### 5.5 关键操作的日志记录点

| 操作 | 日志级别 | 记录内容 |
|------|----------|----------|
| 页面创建 | INFO | 路径、标题、来源 |
| 页面更新 | INFO | 路径、模式（merge/append/overwrite） |
| 页面合并 | INFO | 源路径、目标路径、合并策略 |
| 快照创建 | DEBUG | 源路径、快照文件路径 |
| 快照清理 | INFO | 清理数量、释放空间 |
| 目录自动创建 | INFO | 创建的目录路径 |
| 7层深度拒绝 | WARNING | 被拒绝的路径、当前深度 |
| 搜索执行 | INFO | 查询关键词、结果数量、耗时 |
| 健康检查 | INFO | 检查结果摘要 |
| 导出执行 | INFO | 导出路径、文件数量、总大小 |
| 文件写入失败 | ERROR | 路径、错误原因 |
| 配置加载 | INFO | 配置文件路径、关键参数 |


## 六、MCP工具接口汇总

```python
from fastmcp import FastMCP

mcp = FastMCP("Personal Wiki Memory")

# 记忆核心业务层 - 3个核心功能
@mcp.tool()
def get_directory(path: str = "/") -> str:
    """获取Wiki层级文件列表（树形目录结构）"""
    pass

@mcp.tool()
def read_memory(path: str) -> str:
    """读取记忆"""
    pass

@mcp.tool()
def write_memory(content: str, path: str = None, tags: list[str] = None) -> str:
    """写入记忆（缺目录自动创建，更新前自动快照）"""
    pass

# 核心提示词暴露 - 推荐使用prompt
@mcp.prompt(name="core_principles", description="记忆系统核心提示词，供LLM调度决策")
def core_principles_prompt() -> str:
    """获取所有核心提示词，供客户端LLM用于调度决策"""
    pass

```


## 七、项目代码骨架

### 7.1 模块结构

```
openmem-mcp/
├── pyproject.toml                  # 项目元数据与依赖声明
├── openmem/
│   ├── __init__.py             # 包初始化，暴露版本号
│   ├── main.py                 # 主入口：FastMCP实例、工具注册、日志配置、启动
│   ├── initializer.py          # 启动初始化：配置文件、Wiki根目录、核心提示词
│   ├── store.py                # 文件系统存储层：目录导航、页面读写、快照管理
│   └── utils.py                # 工具函数：Front Matter解析、路径校验、合并策略
└── tests/
    ├── test_initializer.py
    ├── test_mcp_api.py
    ├── test_store.py
    └── test_utils.py
```

### 7.1.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "openmem-mcp"
version = "0.1.0"
description = "LLM驱动的个人Wiki记忆MCP工具"
requires-python = ">=3.10"
dependencies = [
    "fastmcp>=0.1.0",
    "openai>=1.0.0",
    "python-frontmatter>=1.0.0",
    "mistune>=3.0.0",
    "python-dotenv>=1.0.0",
]

[tool.setuptools.packages.find]
where = ["."]
namespaces = false
```

### 7.2 启动初始化模块（initializer.py）

```python
import json
import shutil
import logging
from pathlib import Path
import frontmatter

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "wiki_root": "./wiki",
    "max_depth": 7,
    "snapshot": {
        "enabled": True,
        "cleanup_interval_minutes": 10,
        "retention_days": 7
    },
    "default_tags": [],
    "logging": {
        "level": "INFO",
        "file_enabled": True,
        "file_path": "./logs/openmem.log",
        "max_file_size_mb": 10,
        "backup_count": 5,
        "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    }
}

CORE_PROMPTS = {
    "记忆管理规则.md": {
        "title": "记忆管理规则",
        "summary": "记忆系统的核心管理规则，指导所有写入和合并决策。",
        "tags": ["核心", "规则"],
        "content": (
            "# 记忆管理规则\n\n"
            "## 核心原则\n"
            "记忆有层次和顺序，但是内容精简不重叠。\n\n"
            "## 单篇原则\n"
            "每篇笔记仅讲述一个概念/方法/知识点。\n\n"
            "## 合并原则\n"
            "若以下四项中任意三项相同，则需要合并：\n"
            "- 主体（谁/什么）\n"
            "- 核心动作（做什么）\n"
            "- 特点/条件（在什么情况下）\n"
            "- 结论/观点（结果是什么）"
        )
    },
    "用户偏好习惯.md": {
        "title": "用户偏好习惯",
        "summary": "用户的沟通风格与个人偏好记录。",
        "tags": ["核心", "偏好"],
        "content": (
            "# 用户偏好习惯\n\n"
            "## 沟通风格\n"
            "- 偏好简洁直接的回答\n"
            "- 不喜欢过多寒暄和解释\n\n"
            "## 工作习惯\n"
            "- 使用4空格缩进\n"
            "- 函数名驼峰命名，变量名下划线命名"
        )
    },
    "Agent行为指南.md": {
        "title": "Agent行为指南",
        "summary": "Agent写入行为规范与决策边界。",
        "tags": ["核心", "指南"],
        "content": (
            "# Agent行为指南\n\n"
            "## 主动写入场景\n"
            "- 用户明确要求记住某事\n"
            "- 用户纠正Agent的错误认知\n\n"
            "## 被动写入场景\n"
            "- 仅在用户触发时写入，不主动猜测\n\n"
            "## 写入边界\n"
            "- 不记录临时性对话上下文\n"
            "- 不记录已过期的任务信息"
        )
    },
    "Wiki整理指南.md": {
        "title": "Wiki整理指南",
        "summary": "Wiki目录结构整理与内容归并规范，指导Agent定期维护知识库结构清晰与内容精简。",
        "tags": ["核心", "整理"],
        "content": (
            "# Wiki整理指南\n\n"
            "## 整理原则\n\n"
            "### 结构原则\n"
            "- 目录层级不超过7层，优先3层以内组织\n"
            "- 同一主题的内容归入同一目录，不同主题分目录存放\n"
            "- 目录命名使用\"序号-名称\"格式，如\"01-工作\"、\"02-学习\"\n"
            "- 空目录应当删除，避免结构冗余\n\n"
            "### 归并原则\n"
            "- 遵循\"记忆管理规则\"中的合并原则\n"
            "- 两篇页面若主题高度重叠，应合并为一篇\n"
            "- 合并后保留信息更完整的版本作为基底，补充另一篇的独特内容\n"
            "- 合并完成后，将冗余页面内容迁移并删除原页面\n\n"
            "### 单篇原则\n"
            "- 每篇页面仅讲述一个概念/方法/知识点\n"
            "- 页面内容超过500字时，考虑拆分为子页面\n"
            "- 页面内容不足20字时，考虑归并到相关父页面或兄弟页面\n\n"
            "## 整理流程\n\n"
            "### 第一步：扫描目录结构\n"
            "- 从根目录开始，递归遍历所有目录和页面\n"
            "- 记录每个目录下的页面数量和子目录数量\n"
            "- 识别空目录（无子目录且无页面）和层级过深的目录（超过5层）\n\n"
            "### 第二步：检查单篇规范\n"
            "- 找出内容超过500字的页面，标记为待拆分候选\n"
            "- 找出内容不足20字的页面，标记为待归并候选\n\n"
            "### 第三步：检查归并需求\n"
            "- 遍历同一目录下的所有页面，比较主题重叠度\n"
            "- 依据\"记忆管理规则\"中的合并原则，标记需合并的页面组\n\n"
            "### 第四步：执行整理\n"
            "- 对待归并页面：合并到信息更完整的页面，删除冗余页面\n"
            "- 对待拆分页面：按子主题拆分为子页面，原页面保留概览\n"
            "- 对空目录：直接删除\n"
            "- 对层级过深的目录：提升深层页面到更合理层级\n\n"
            "### 第五步：验证与收尾\n"
            "- 确认Front Matter字段完整\n"
            "- 确认目录命名规范\n"
            "- 确认无孤立页面\n\n"
            "## 注意事项\n"
            "- 整理前务必确认快照机制已启用，确保可恢复\n"
            "- 一次整理操作涉及的页面不超过10篇，避免大规模变动\n"
            "- 核心提示词文件（一级目录下.md文件）不参与整理归并\n"
            "- 整理过程中如发现用户偏好信息，应更新到\"用户偏好习惯.md\""
        )
    }
}


def ensure_config(config_path: Path) -> Path:
    if config_path.exists():
        logger.info(f"配置文件已存在: {config_path}")
        return config_path

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    logger.info(f"已创建默认配置文件: {config_path}")
    return config_path


def ensure_wiki_root(wiki_root: Path):
    wiki_root.mkdir(parents=True, exist_ok=True)
    logger.info(f"Wiki根目录已就绪: {wiki_root}")


def ensure_core_prompts(wiki_root: Path):
    for filename, prompt_data in CORE_PROMPTS.items():
        file_path = wiki_root / filename
        if file_path.exists():
            logger.info(f"核心提示词文件已存在: {file_path}")
            continue

        post = frontmatter.Post(prompt_data["content"])
        post.metadata["title"] = prompt_data["title"]
        post.metadata["type"] = "corepage"
        post.metadata["level"] = 1
        post.metadata["summary"] = prompt_data["summary"]
        post.metadata["tags"] = prompt_data["tags"]

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            frontmatter.dump(post, f)
        logger.info(f"已创建核心提示词文件: {file_path}")


def initialize(config_path: Path, wiki_root: Path):
    logger.info("开始启动初始化...")

    config_path = ensure_config(config_path)
    ensure_wiki_root(wiki_root)
    ensure_core_prompts(wiki_root)

    logger.info("启动初始化完成")
```

### 7.3 主入口（main.py）

```python
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastmcp import FastMCP

from openmem.initializer import initialize, DEFAULT_CONFIG
from openmem.store import WikiStore

mcp = FastMCP("Personal Wiki Memory")

config_path = Path.home() / ".config" / "openmem" / "openmem.json"


def load_config() -> dict:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG


def setup_logging(config: dict):
    log_cfg = config.get("logging", DEFAULT_CONFIG["logging"])
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    handlers = [logging.StreamHandler()]

    if log_cfg.get("file_enabled", True):
        log_path = Path(log_cfg.get("file_path", "./logs/openmem.log"))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=log_cfg.get("max_file_size_mb", 10) * 1024 * 1024,
            backupCount=log_cfg.get("backup_count", 5),
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(fmt))
        handlers.append(file_handler)

    logging.basicConfig(level=level, format=fmt, handlers=handlers)


config = load_config()
setup_logging(config)

wiki_root = Path(config.get("wiki_root", "./wiki"))
initialize(config_path, wiki_root)

store = WikiStore(wiki_root, max_depth=config.get("max_depth", 7), snapshot_cfg=config.get("snapshot"))


@mcp.tool()
def get_directory(path: str = "/") -> str:
    """
    获取指定目录的层级文件列表

    Args:
        path: 目录路径，默认根目录

    Returns:
        目录结构和子条目列表（含每个条目的title、summary、type、level）
    """
    return store.get_directory(path)


@mcp.tool()
def read_memory(path: str) -> str:
    """
    读取指定路径的完整Wiki页面内容

    Args:
        path: 页面完整路径，如"/00-个人/学习/Python学习笔记"

    Returns:
        页面完整内容，包括Front Matter
    """
    return store.read_memory(path)


@mcp.tool()
def write_memory(content: str, path: str = None, tags: list[str] = None) -> str:
    """
    写入记忆（缺目录自动创建，更新前自动快照）

    Args:
        content: 要写入的记忆内容
        path: 目标路径，如"/00-个人/学习/Python学习笔记"。为空时自动分类
        tags: 可选的标签列表

    Returns:
        最终页面路径
    """
    return store.write_memory(content=content, path=path, tags=tags)


@mcp.prompt(name="core_principles", description="记忆系统核心提示词，供LLM调度决策")
def core_principles_prompt() -> str:
    """
    获取所有核心提示词（一级目录下所有.md文件的内容合集），供客户端LLM用于调度决策

    Returns:
        所有核心提示词的完整内容，按文件名排列拼接
    """
    return store.get_core_principles()
```

### 7.4 启动流程

```mermaid
flowchart TD
    A[main.py 模块加载] --> B[load_config<br/>加载配置文件]
    B --> B1{配置文件是否存在?}
    B1 -->|是| B2[读取 openmem.json]
    B1 -->|否| B3[使用 DEFAULT_CONFIG]
    B2 --> C[setup_logging<br/>配置日志系统]
    B3 --> C
    C --> C1[创建控制台 Handler]
    C --> C2{file_enabled?}
    C2 -->|是| C3[创建 RotatingFileHandler]
    C2 -->|否| C4[跳过文件日志]
    C3 --> D[initialize<br/>启动初始化]
    C4 --> D
    D --> D1[ensure_config<br/>确保配置文件存在]
    D1 --> D2[ensure_wiki_root<br/>确保Wiki根目录存在]
    D2 --> D3[ensure_core_prompts<br/>确保核心提示词文件存在]
    D3 --> E[创建 WikiStore 实例]
    E --> F[注册 MCP 工具接口]
    F --> G[服务就绪，等待客户端连接]
```

**详细步骤**：

1. **加载配置**（`load_config`）
   - 检查 `~/.config/openmem/openmem.json` 是否存在
   - 存在则读取，不存在则使用 `DEFAULT_CONFIG` 默认值

2. **配置日志**（`setup_logging`）
   - 根据配置设置日志级别和格式
   - 始终启用控制台输出（stderr）
   - 若 `file_enabled` 为 true，创建 `RotatingFileHandler`，按大小轮转

3. **启动初始化**（`initialize`）
   - `ensure_config`：若配置文件不存在，自动创建默认配置文件
   - `ensure_wiki_root`：创建Wiki根目录（含父目录）
   - `ensure_core_prompts`：遍历 `CORE_PROMPTS` 字典，逐一检查核心提示词文件是否存在，不存在则自动创建（含Front Matter）

4. **创建存储实例**
   - 实例化 `WikiStore`，传入 `wiki_root`、`max_depth`、`snapshot_cfg` 参数
   - WikiStore 内部初始化快照清理定时器（若快照启用）

5. **注册MCP接口**
   - 注册 `get_directory`、`read_memory`、`write_memory` 三个核心业务工具接口
   - 注册 `core_principles_prompt` prompt接口，暴露核心提示词给客户端LLM用于调度决策

6. **服务就绪**
   - FastMCP 实例启动，通过 stdio 等传输方式等待客户端连接

### 7.5 安装

```bash
pip install openmem-mcp
```

或开发模式：

```bash
cd openmem-mcp
pip install -e .
```



## 八、核心优势总结

1. **极致简单**：没有数据库、没有LLM依赖、没有索引、没有缓存，只有文件系统
2. **100%可控**：没有后台进程、没有自动同步，所有操作显式可见
3. **零锁定**：所有数据都是标准Markdown，随时可用任何编辑器打开
4. **完美Obsidian集成**：不需要任何插件，所有功能都是Obsidian原生支持
5. **强制规范**：所有文件都遵循统一格式，结构清晰、易于维护
6. **记忆不重叠**：核心提示词通过MCP Prompt直接暴露给客户端LLM，由LLM驱动合并与分类决策，确保内容精简不冗余
7. **安全可恢复**：每次改动自动快照，可配置保留策略


## 附录A：FastMCP 使用指南

> 基于 fastmcp 3.3.1 源码分析整理，涵盖工具名称、描述、参数说明、日志、资源、Prompt 等配置方法。

### A.1 工具注册（@mcp.tool）

#### A.1.1 工具名称

通过 `@mcp.tool(name="xxx")` 显式指定；不指定则默认使用函数名。

```python
# 方式1：显式指定名称
@mcp.tool(name="add_memory")
def add_memory(content: str) -> str:
    pass

# 方式2：位置参数指定名称
@mcp.tool("add_memory")
def add_memory(content: str) -> str:
    pass

# 方式3：不指定，默认函数名 "add_memory"
@mcp.tool()
def add_memory(content: str) -> str:
    pass
```

**源码位置**：`fastmcp/tools/function_tool.py:214` — `func_name = metadata.name or parsed_fn.name`

#### A.1.2 工具描述

通过 `@mcp.tool(description="xxx")` 显式指定；不指定则自动从函数 docstring 解析首段文本。

```python
# 方式1：显式指定描述
@mcp.tool(description="添加新记忆，自动分类到最合适的Wiki位置")
def add_memory(content: str) -> str:
    pass

# 方式2：从docstring自动提取
@mcp.tool()
def add_memory(content: str) -> str:
    """
    添加新记忆，自动分类到最合适的Wiki位置
    """
    pass
```

**优先级**：`description` 参数 > docstring 首段文本

**源码位置**：`fastmcp/tools/function_tool.py:268-270`
```python
description=metadata.description
if metadata.description is not None
else parsed_fn.description,
```

其中 `parsed_fn.description` 来自 docstring 解析（详见 A.1.3）。

#### A.1.3 参数说明

参数说明通过 **docstring 的 Args 段落** 配置，底层使用 `griffe` 库解析，支持 Google、NumPy、Sphinx 三种格式（按序尝试，取首个成功解析到参数描述的）。

**Google 风格（推荐）**：

```python
@mcp.tool()
def search_memories(query: str, max_depth: int = 7, max_results: int = 3) -> str:
    """
    搜索记忆，从根目录开始渐进式查找

    Args:
        query: 搜索查询关键词
        max_depth: 最大搜索深度，默认7
        max_results: 最多返回结果数，默认3

    Returns:
        结构化的搜索结果
    """
    pass
```

**NumPy 风格**：

```python
@mcp.tool()
def search_memories(query, max_depth=7, max_results=3):
    """
    搜索记忆，从根目录开始渐进式查找

    Parameters
    ----------
    query : str
        搜索查询关键词
    max_depth : int, optional
        最大搜索深度，默认7
    max_results : int, optional
        最多返回结果数，默认3

    Returns
    -------
    str
        结构化的搜索结果
    """
    pass
```

**Sphinx 风格**：

```python
@mcp.tool()
def search_memories(query, max_depth=7, max_results=3):
    """
    搜索记忆，从根目录开始渐进式查找

    :param query: 搜索查询关键词
    :param max_depth: 最大搜索深度，默认7
    :param max_results: 最多返回结果数，默认3
    :return: 结构化的搜索结果
    """
    pass
```

**Pydantic Field 描述**（优先级高于 docstring）：

```python
from pydantic import Field

@mcp.tool()
def add_memory(
    content: str = Field(description="要添加的记忆内容"),
    path: str = Field(default=None, description="可选的建议路径，如'/00-个人/学习'"),
) -> str:
    pass
```

**优先级**：`Field(description=...)` / `Annotated[type, "描述"]` > docstring Args 段落

**源码位置**：
- docstring 解析：`fastmcp/utilities/docstring_parsing.py` — `parse_docstring()` 函数
- 参数描述注入 JSON Schema：`fastmcp/tools/function_parsing.py` 中，docstring Args 的描述仅在该参数尚未有 description 时注入（不会覆盖 Field 描述）

#### A.1.4 参数类型与 JSON Schema

FastMCP 使用 Pydantic 的 `TypeAdapter` 自动从 Python 类型注解生成 JSON Schema，客户端看到的所有参数信息（类型、描述、默认值、必填/选填）均由此生成。

```python
@mcp.tool()
def write_memory(
    content: str,                                    # 必填，类型string
    path: str = None,                                # 选填，类型string|null
    tags: list[str] = None,                          # 选填，类型array of string
) -> str:
    pass
```

客户端收到的 `inputSchema` 大致为：
```json
{
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "要写入的记忆内容"},
        "path": {"type": "string", "description": "目标路径", "default": null},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"}
    },
    "required": ["content"]
}
```


### A.2 资源注册（@mcp.resource）

#### A.2.1 基本用法

```python
@mcp.resource("wiki://config")
def get_config() -> str:
    """获取当前Wiki配置信息"""
    return "..."
```

#### A.2.2 可配置参数

```python
@mcp.resource(
    uri="wiki://page/{path}",        # 资源URI（必填），支持模板参数
    name="get_page",                 # 资源名称，默认函数名
    title="Wiki页面",                # 显示标题
    description="获取Wiki页面内容",   # 描述，fallback到docstring
    mime_type="text/markdown",       # MIME类型，默认text/plain
    tags={"wiki", "page"},           # 标签集合
    icons=None,                      # 图标列表
    annotations=None,                # MCP Annotations对象
    meta=None,                       # 自定义元数据字典
)
def get_page(path: str) -> str:
    pass
```

#### A.2.3 URI 模板语法（RFC 6570 子集）

| 语法 | 说明 | 示例 |
|------|------|------|
| `{var}` | 路径参数，匹配单个段 | `wiki://page/{path}` → `wiki://page/Python学习笔记` |
| `{var*}` | 通配路径参数，匹配多段 | `wiki://file/{path*}` → `wiki://file/00-个人/学习/笔记` |
| `{?var1,var2}` | 查询参数，必须为可选参数 | `wiki://search/{query}{?limit,offset}` → `wiki://search/python?limit=10` |

**模板参数约束**：
- URI 中的路径参数必须覆盖函数的所有必填参数
- 查询参数（`{?...}`）对应的函数参数必须有默认值
- URI 参数名中连字符自动转下划线匹配 Python 参数名（如 `{user-id}` 对应 `user_id`）

```python
@mcp.resource("wiki://search/{query}{?limit,offset}")
def search(query: str, limit: int = 10, offset: int = 0) -> str:
    """搜索Wiki内容"""
    pass
```

#### A.2.4 资源 vs 资源模板

FastMCP 自动区分：
- **无参数的资源**（函数无参数且 URI 无 `{}`）：注册为静态 `FunctionResource`
- **有参数的资源**（URI 含 `{}` 或函数有参数）：注册为 `FunctionResourceTemplate`

**源码位置**：`fastmcp/resources/function_resource.py:274-311`


### A.3 Prompt 注册（@mcp.prompt）

#### A.3.1 基本用法

```python
@mcp.prompt(name="summarize", description="总结文档内容")
def summarize_prompt(document: str, max_length: int = 100) -> str:
    """
    生成文档摘要

    Args:
        document: 要总结的文档内容
        max_length: 摘要最大长度
    """
    return f"请总结以下内容，控制在{max_length}字以内：\n{document}"
```

#### A.3.2 可配置参数

```python
@mcp.prompt(
    name="summarize",                # Prompt名称，默认函数名
    title="文档摘要",                 # 显示标题
    description="总结文档内容",        # 描述，fallback到docstring
    icons=None,                      # 图标列表
    tags={"summary"},                # 标签集合
    meta=None,                       # 自定义元数据字典
)
def summarize_prompt(document: str) -> str:
    pass
```

#### A.3.3 返回值类型

Prompt 函数可返回以下类型：
- `str`：自动包装为单条 user Message
- `list[Message | str]`：转换为 Message 列表
- `PromptResult`：直接使用

#### A.3.4 参数说明注入

与 Tool 相同，Prompt 的参数说明也从 docstring Args 段落解析并注入到 `PromptArgument.description` 中。对于非 string 类型的参数，FastMCP 会自动在描述末尾追加 JSON Schema 信息，帮助客户端以字符串格式传参。

**源码位置**：`fastmcp/prompts/function_prompt.py:208-259`

#### A.3.5 限制

- 不支持 `*args` 和 `**kwargs`
- Lambda 函数必须显式提供 `name`


### A.4 日志配置

#### A.4.1 FastMCP 内置日志系统

FastMCP 使用 `fastmcp.settings`（`Settings` 类实例）控制日志行为，所有设置均可通过环境变量覆盖：

| 设置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `log_enabled` | `FASTMCP_LOG_ENABLED` | `True` | 是否启用日志 |
| `log_level` | `FASTMCP_LOG_LEVEL` | `"INFO"` | 日志级别 |
| `enable_rich_logging` | `FASTMCP_ENABLE_RICH_LOGGING` | `True` | 是否使用 Rich 格式化输出 |
| `enable_rich_tracebacks` | `FASTMCP_ENABLE_RICH_TRACEBACKS` | `True` | 是否使用 Rich 异常追踪 |

**在代码中获取 logger**：

```python
from fastmcp.utilities.logging import get_logger
logger = get_logger(__name__)  # 返回名为 "fastmcp.{模块名}" 的 logger
```

**手动配置日志**：

```python
from fastmcp.utilities.logging import configure_logging

configure_logging(
    level="DEBUG",                    # 日志级别
    enable_rich_tracebacks=True,      # Rich异常追踪
)
```

**运行时修改设置**：

```python
import fastmcp
fastmcp.settings.log_level = "DEBUG"   # 自动生效
fastmcp.settings.log_enabled = False   # 关闭日志
```

**源码位置**：
- Settings 定义：`fastmcp/settings.py:136-181`
- 日志配置函数：`fastmcp/utilities/logging.py:29-113`

#### A.4.2 与项目自定义日志的关系

本项目（openmem）在 `main.py` 中使用 Python 标准 `logging` 模块自行配置日志，独立于 FastMCP 内置日志：

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_path), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
```

两者共存时，FastMCP 的 logger（`fastmcp.*`）由 FastMCP 内部管理，项目自身的 logger（`openmem.*`）由项目 `logging.basicConfig` 管理，互不干扰。

#### A.4.3 MCP 协议日志（发送给客户端）

FastMCP 支持通过 MCP 协议向客户端发送日志消息，由 `client_log_level` 设置控制：

| 设置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `client_log_level` | `FASTMCP_CLIENT_LOG_LEVEL` | `None` | 发送给客户端的最低日志级别 |

可选值：`"debug"` / `"info"` / `"notice"` / `"warning"` / `"error"` / `"critical"` / `"alert"` / `"emergency"`

设为 `None` 则不主动发送日志给客户端。


### A.5 快速对照表

| 客户端可见项 | 配置位置 | 优先级 |
|-------------|---------|--------|
| 工具名称 | `@mcp.tool(name="...")` → 函数名 | name参数 > 函数名 |
| 工具描述 | `@mcp.tool(description="...")` → docstring首段 | description参数 > docstring |
| 参数名称 | Python 函数参数名 | — |
| 参数类型 | Python 类型注解（经 Pydantic TypeAdapter 生成 JSON Schema） | — |
| 参数描述 | `Field(description=...)` → docstring Args 段落 | Field > docstring Args |
| 参数必填/选填 | 函数签名默认值（无默认值=必填） | — |
| 资源名称 | `@mcp.resource(uri, name="...")` → 函数名 | name参数 > 函数名 |
| 资源描述 | `@mcp.resource(..., description="...")` → docstring | description参数 > docstring |
| 资源 MIME 类型 | `@mcp.resource(..., mime_type="...")` | 显式指定 > `text/plain` |
| Prompt 名称 | `@mcp.prompt(name="...")` → 函数名 | name参数 > 函数名 |
| Prompt 描述 | `@mcp.prompt(description="...")` → docstring | description参数 > docstring |
| Prompt 参数描述 | docstring Args 段落 | 与 Tool 相同 |


### A.6 装饰器参数总览

#### @mcp.tool() 完整参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` / 位置参数 | `str` | 函数名 | 工具名称 |
| `title` | `str` | `None` | 显示标题 |
| `description` | `str` | docstring | 工具描述 |
| `version` | `str \| int` | `None` | 工具版本号 |
| `icons` | `list[Icon]` | `None` | 图标列表 |
| `tags` | `set[str]` | `None` | 标签集合 |
| `annotations` | `ToolAnnotations \| dict` | `None` | MCP 工具行为注解 |
| `output_schema` | `dict` | 自动推断 | 输出 JSON Schema |
| `meta` | `dict` | `None` | 自定义元数据 |
| `enabled` | `bool` | `True` | 是否启用 |
| `timeout` | `float` | `None` | 执行超时（秒） |
| `run_in_thread` | `bool` | `True` | 同步函数是否在线程池执行 |
| `auth` | `AuthCheck \| list` | `None` | 授权检查 |

#### @mcp.resource() 完整参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `uri`（必填） | `str` | — | 资源 URI，支持模板参数 |
| `name` | `str` | 函数名 | 资源名称 |
| `title` | `str` | `None` | 显示标题 |
| `description` | `str` | docstring | 资源描述 |
| `version` | `str \| int` | `None` | 资源版本号 |
| `icons` | `list[Icon]` | `None` | 图标列表 |
| `mime_type` | `str` | `"text/plain"` | MIME 类型 |
| `tags` | `set[str]` | `None` | 标签集合 |
| `annotations` | `Annotations \| dict` | `None` | MCP 资源注解 |
| `meta` | `dict` | `None` | 自定义元数据 |

#### @mcp.prompt() 完整参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` / 位置参数 | `str` | 函数名 | Prompt 名称 |
| `title` | `str` | `None` | 显示标题 |
| `description` | `str` | docstring | Prompt 描述 |
| `version` | `str \| int` | `None` | 版本号 |
| `icons` | `list[Icon]` | `None` | 图标列表 |
| `tags` | `set[str]` | `None` | 标签集合 |
| `meta` | `dict` | `None` | 自定义元数据 |
