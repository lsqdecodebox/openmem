# OpenMem v2 技术架构、数据流图与伪代码

---

## 一、技术架构

### 1.1 整体分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    客户端层 (Client Layer)                │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │ Claude Desktop │  │   OpenCode    │  │  Obsidian   │  │
│  └───────┬───────┘  └───────┬───────┘  └──────┬──────┘  │
│          │                  │                  │         │
│          └──────────────────┼──────────────────┘         │
│                             │ MCP协议 (stdio/SSE)        │
├─────────────────────────────┼─────────────────────────────┤
│                    协议接入层 (Protocol Layer)            │
│                             │                             │
│                ┌────────────▼────────────┐                │
│                │      FastMCP 实例        │                │
│                │  ┌───────────────────┐  │                │
│                │  │ @mcp.tool() 注册   │  │                │
│                │  │  - get_directory   │  │                │
│                │  │  - read_memory     │  │                │
│                │  │  - write_memory    │  │                │
│                │  ├───────────────────┤  │                │
│                │  │ @mcp.prompt() 注册 │  │                │
│                │  │  - core_principles │  │                │
│                │  └───────────────────┘  │                │
│                └────────────┬────────────┘                │
├─────────────────────────────┼─────────────────────────────┤
│                  核心业务层 (Business Layer)               │
│                             │                             │
│                ┌────────────▼────────────┐                │
│                │    WikiStore 存储引擎    │                │
│                │  ┌───────────────────┐  │                │
│                │  │ 目录导航服务       │  │                │
│                │  │ 页面读写服务       │  │                │
│                │  │ 快照管理服务       │  │                │
│                │  │ 核心提示词服务     │  │                │
│                │  └───────────────────┘  │                │
│                └────────────┬────────────┘                │
├─────────────────────────────┼─────────────────────────────┤
│                基础设施层 (Infrastructure Layer)           │
│                             │                             │
│  ┌──────────────┐ ┌────────▼────────┐ ┌──────────────┐   │
│  │  utils.py    │ │  文件系统 (FS)   │ │  配置中心    │   │
│  │ Front Matter │ │  wiki-root/      │ │ openmem.json │   │
│  │ 路径校验     │ │  .snapshots/     │ │              │   │
│  │ 合并策略     │ │                  │ │              │   │
│  └──────────────┘ └─────────────────┘ └──────────────┘   │
├───────────────────────────────────────────────────────────┤
│                  启动初始化层 (Bootstrap Layer)            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  initializer.py                                    │   │
│  │  ensure_config → ensure_wiki_root → ensure_prompts │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

### 1.2 模块职责矩阵

| 模块 | 职责 | 依赖 | 被依赖 |
|------|------|------|--------|
| `main.py` | FastMCP实例创建、工具注册、日志配置、启动入口 | initializer, store | 外部启动 |
| `initializer.py` | 启动初始化：配置文件、Wiki根目录、核心提示词文件 | frontmatter | main |
| `store.py` | 文件系统存储层：目录导航、页面读写、快照管理、核心提示词读取 | utils | main |
| `utils.py` | 工具函数：Front Matter解析、路径校验、合并策略 | frontmatter, mistune | store |
| `__init__.py` | 包初始化，暴露版本号 | 无 | 外部导入 |

### 1.3 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| MCP框架 | FastMCP >= 0.1.0 | MCP协议实现，工具/资源/Prompt注册 |
| Front Matter | python-frontmatter >= 1.0.0 | Markdown YAML头部解析与生成 |
| Markdown解析 | mistune >= 3.0.0 | 正文内容解析（用于内容分析/字数统计） |
| 配置管理 | python-dotenv >= 1.0.0 | 环境变量加载 |
| HTTP客户端 | openai >= 1.0.0 | 预留LLM调用能力（当前未使用） |
| 运行时 | Python >= 3.10 | 类型注解（list[str]等） |
| 日志 | Python标准库 logging + RotatingFileHandler | 日志轮转输出 |

### 1.4 关键设计决策

1. **纯文件系统存储**：无数据库、无索引、无缓存，所有数据以Markdown文件存储
2. **客户端LLM驱动调度**：核心提示词通过MCP Prompt暴露给客户端LLM，由LLM完成分类/合并/写入位置等决策
3. **7层深度限制**：在utils层做路径校验，store层调用前强制校验
4. **写入前自动快照**：在store.write_memory内部，任何文件修改前先创建快照
5. **缺目录自动创建**：写入时若父目录不存在，逐级自动创建
6. **Obsidian原生兼容**：标准Markdown + YAML Front Matter，Obsidian可直接打开

---

## 二、数据流图

### 2.1 系统级数据流总览

```
                    ┌─────────────┐
                    │  用户/LLM   │
                    └──────┬──────┘
                           │ 自然语言指令
                           ▼
                    ┌─────────────┐    核心提示词注入
                    │ 客户端LLM   │◄──────────────────┐
                    │(Claude等)   │                    │
                    └──────┬──────┘                    │
                           │ MCP Tool Call             │
                           ▼                           │
            ┌──────────────────────────┐               │
            │     FastMCP 协议层       │               │
            │  get_directory           │               │
            │  read_memory             │    @mcp.prompt│
            │  write_memory            │───────────────┘
            └────────────┬─────────────┘
                         │
                         ▼
            ┌──────────────────────────┐
            │      WikiStore           │
            │  ┌───────┐ ┌──────────┐  │
            │  │ 读取  │ │ 写入     │  │
            │  │ 操作  │ │ 操作     │  │
            │  └───┬───┘ └────┬─────┘  │
            │      │          │        │
            │      ▼          ▼        │
            │  ┌──────────────────┐    │
            │  │  utils.py 校验   │    │
            │  │  - 路径深度检查  │    │
            │  │  - Front Matter  │    │
            │  │  - 合并策略      │    │
            │  └──────────────────┘    │
            └────────────┬─────────────┘
                         │
            ┌────────────▼─────────────┐
            │    文件系统 (wiki-root)   │
            │  ┌─────────┐ ┌────────┐  │
            │  │  .md    │ │.snap-  │  │
            │  │  页面   │ │shots/  │  │
            │  └─────────┘ └────────┘  │
            └──────────────────────────┘
```

### 2.2 读取流程（get_directory / read_memory）

```
客户端LLM ──调用──► FastMCP ──转发──► get_directory(path) / read_memory(path)
                                              │
                                              ▼
                                    WikiStore.get_directory(path)
                                    WikiStore.read_memory(path)
                                              │
                                    ┌─────────┴─────────┐
                                    │ path == "/" ?      │
                                    │ ├─ 是: wiki_root   │
                                    │ └─ 否: wiki_root/path │
                                    └─────────┬─────────┘
                                              │
                                              ▼
                                    检查路径是否合法（防路径穿越）
                                              │
                                              ▼
                                    ┌─────────┴─────────┐
                                    │ get_directory:     │
                                    │ 遍历目录，读取每个│
                                    │ .md的Front Matter │
                                    │ 构建树形JSON      │
                                    │                   │
                                    │ read_memory:      │
                                    │ 读取完整.md文件   │
                                    │ 返回原始内容      │
                                    └─────────┬─────────┘
                                              │
                                              ▼
                                    返回结果 ──► FastMCP ──► 客户端LLM
```

### 2.3 写入流程（write_memory）

```
客户端LLM ──调用──► FastMCP ──转发──► write_memory(content, path, tags)
                                              │
                                              ▼
                                    WikiStore.write_memory()
                                              │
                                    ┌─────────┴──────────┐
                                    │ 1. path为空?        │
                                    │    → 返回提示，要求 │
                                    │      LLM提供路径    │
                                    │    （由LLM根据核心  │
                                    │      提示词决策）    │
                                    └─────────┬──────────┘
                                              │
                                    ┌─────────▼──────────┐
                                    │ 2. utils校验路径    │
                                    │    - 深度 <= 7?     │
                                    │    - 路径安全?      │
                                    │    - 不含非法字符?  │
                                    └─────────┬──────────┘
                                              │
                                    ┌─────────▼──────────┐
                                    │ 3. 目标文件已存在?  │
                                    │    ├─ 是:           │
                                    │    │  a. 创建快照   │
                                    │    │  b. 读取现有   │
                                    │    │  c. 合并内容   │
                                    │    │  d. 写入文件   │
                                    │    └─ 否:           │
                                    │       a. 缺目录     │
                                    │          自动创建   │
                                    │       b. 生成Front  │
                                    │          Matter     │
                                    │       c. 写入新文件 │
                                    └─────────┬──────────┘
                                              │
                                    ┌─────────▼──────────┐
                                    │ 4. 补全Front Matter │
                                    │    - title          │
                                    │    - type: page     │
                                    │    - level          │
                                    │    - summary        │
                                    │    - tags           │
                                    └─────────┬──────────┘
                                              │
                                              ▼
                                    返回最终路径 ──► FastMCP ──► 客户端LLM
```

### 2.4 核心提示词获取流程（core_principles）

```
客户端LLM ──prompts/list──► FastMCP ──发现──► core_principles prompt
                                                    │
客户端LLM ──prompts/get──► FastMCP ──调用──► core_principles_prompt()
                                                    │
                                                    ▼
                                          WikiStore.get_core_principles()
                                                    │
                                          ┌─────────┴─────────┐
                                          │ 遍历wiki_root下   │
                                          │ 所有一级.md文件   │
                                          │ (非子目录中的)    │
                                          └─────────┬─────────┘
                                                    │
                                                    ▼
                                          读取每个文件完整内容
                                          按文件名排序拼接
                                                    │
                                                    ▼
                                          返回拼接文本 ──► FastMCP ──► 注入LLM上下文
```

### 2.5 快照流程

```
write_memory(修改现有文件)
        │
        ▼
┌───────────────────────────┐
│ 1. 确定快照路径:           │
│    .snapshots/{相对路径}/  │
│    {ISO时间戳}.md          │
│                           │
│ 2. 创建快照目录(含父目录)  │
│                           │
│ 3. 复制当前文件内容到      │
│    快照文件               │
│                           │
│ 4. 记录日志(DEBUG级别)    │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ 后台定时清理线程:          │
│                           │
│ 每 cleanup_interval_minutes│
│ 执行一次:                 │
│                           │
│ 1. 遍历 .snapshots/ 目录  │
│ 2. 对每个快照文件:        │
│    计算文件年龄            │
│    超过 retention_days?   │
│    ├─ 是: 删除快照文件    │
│    └─ 否: 保留            │
│ 3. 清理空目录             │
│ 4. 记录日志(INFO级别)     │
└───────────────────────────┘
```

### 2.6 启动初始化流程

```
main.py 模块加载
    │
    ├── load_config()
    │   ├── ~/.config/openmem/openmem.json 存在?
    │   │   ├── 是: 读取并返回配置dict
    │   │   └── 否: 返回 DEFAULT_CONFIG
    │   └── 返回 config
    │
    ├── setup_logging(config)
    │   ├── 解析日志级别和格式
    │   ├── 创建 StreamHandler (stderr, 始终启用)
    │   ├── file_enabled?
    │   │   ├── 是: 创建 RotatingFileHandler
    │   │   └── 否: 跳过
    │   └── logging.basicConfig()
    │
    ├── initialize(config_path, wiki_root)
    │   ├── ensure_config()
    │   │   └── 配置文件不存在则创建默认配置
    │   ├── ensure_wiki_root()
    │   │   └── mkdir -p wiki_root
    │   └── ensure_core_prompts()
    │       └── 遍历 CORE_PROMPTS，逐一检查并创建
    │
    ├── WikiStore(wiki_root, max_depth, snapshot_cfg)
    │   └── 初始化快照清理定时器
    │
    └── FastMCP 注册工具和Prompt
        ├── @mcp.tool() get_directory
        ├── @mcp.tool() read_memory
        ├── @mcp.tool() write_memory
        └── @mcp.prompt() core_principles

服务就绪，等待客户端连接 (stdio)
```

---

## 三、每个代码文件的伪代码

### 3.1 `openmem/__init__.py`

```python
# 伪代码: 包初始化，暴露版本号

__version__ = "0.1.0"
```

---

### 3.2 `openmem/main.py`

```python
# 伪代码: 主入口 - FastMCP实例、工具注册、日志配置、启动

import json, logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastmcp import FastMCP
from openmem.initializer import initialize, DEFAULT_CONFIG
from openmem.store import WikiStore

# ── 全局常量 ──
mcp = FastMCP("Personal Wiki Memory")
CONFIG_PATH = Path.home() / ".config" / "openmem" / "openmem.json"

# ── 函数: 加载配置 ──
FUNCTION load_config() -> dict:
    IF CONFIG_PATH exists:
        READ json from CONFIG_PATH
        RETURN dict
    ELSE:
        RETURN DEFAULT_CONFIG

# ── 函数: 配置日志 ──
FUNCTION setup_logging(config: dict):
    log_cfg = config.get("logging", DEFAULT_CONFIG["logging"])
    level = 解析日志级别字符串
    fmt = 日志格式模板

    handlers = [StreamHandler()]  # stderr，始终启用

    IF log_cfg.file_enabled:
        log_path = Path(log_cfg.file_path)
        CREATE log_path 的父目录
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes = max_file_size_mb * 1024 * 1024,
            backupCount = backup_count,
            encoding = "utf-8"
        )
        SET file_handler formatter
        APPEND file_handler TO handlers

    logging.basicConfig(level=level, format=fmt, handlers=handlers)

# ── 模块级执行: 启动序列 ──
config = load_config()
setup_logging(config)
wiki_root = Path(config.wiki_root)
initialize(CONFIG_PATH, wiki_root)
store = WikiStore(wiki_root, max_depth=config.max_depth, snapshot_cfg=config.snapshot)

# ── MCP工具: 获取目录 ──
@mcp.tool()
FUNCTION get_directory(path: str = "/") -> str:
    """
    获取指定目录的层级文件列表

    Args:
        path: 目录路径，默认根目录

    Returns:
        目录结构和子条目列表（含每个条目的title、summary、type、level）
    """
    RETURN store.get_directory(path)

# ── MCP工具: 读取记忆 ──
@mcp.tool()
FUNCTION read_memory(path: str) -> str:
    """
    读取指定路径的完整Wiki页面内容

    Args:
        path: 页面完整路径，如"/00-个人/学习/Python学习笔记"

    Returns:
        页面完整内容，包括Front Matter
    """
    RETURN store.read_memory(path)

# ── MCP工具: 写入记忆 ──
@mcp.tool()
FUNCTION write_memory(content: str, path: str = None, tags: list[str] = None) -> str:
    """
    写入记忆（缺目录自动创建，更新前自动快照）

    Args:
        content: 要写入的记忆内容
        path: 目标路径，如"/00-个人/学习/Python学习笔记"。为空时自动分类
        tags: 可选的标签列表

    Returns:
        最终页面路径
    """
    RETURN store.write_memory(content=content, path=path, tags=tags)

# ── MCP Prompt: 核心提示词 ──
@mcp.prompt(name="core_principles", description="记忆系统核心提示词，供LLM调度决策")
FUNCTION core_principles_prompt() -> str:
    """
    获取所有核心提示词（一级目录下所有.md文件的内容合集），供客户端LLM用于调度决策

    Returns:
        所有核心提示词的完整内容，按文件名排列拼接
    """
    RETURN store.get_core_principles()
```

---

### 3.3 `openmem/initializer.py`

```python
# 伪代码: 启动初始化 - 配置文件、Wiki根目录、核心提示词文件

import json, shutil, logging
from pathlib import Path
import frontmatter

logger = logging.getLogger(__name__)

# ── 默认配置 ──
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

# ── 核心提示词模板 ──
CORE_PROMPTS = {
    "记忆管理规则.md": {
        title: "记忆管理规则",
        type: "corepage",
        summary: "记忆系统的核心管理规则...",
        tags: ["核心", "规则"],
        content: "# 记忆管理规则\n\n## 核心原则\n..."
    },
    "用户偏好习惯.md": {
        title: "用户偏好习惯",
        type: "corepage",
        summary: "用户的沟通风格与个人偏好记录。",
        tags: ["核心", "偏好"],
        content: "# 用户偏好习惯\n\n## 沟通风格\n..."
    },
    "Agent行为指南.md": {
        title: "Agent行为指南",
        type: "corepage",
        summary: "Agent写入行为规范与决策边界。",
        tags: ["核心", "指南"],
        content: "# Agent行为指南\n\n## 主动写入场景\n..."
    },
    "Wiki整理指南.md": {
        title: "Wiki整理指南",
        type: "corepage",
        summary: "Wiki目录结构整理与内容归并规范...",
        tags: ["核心", "整理"],
        content: "# Wiki整理指南\n\n## 整理原则\n..."
    }
}

# ── 函数: 确保配置文件存在 ──
FUNCTION ensure_config(config_path: Path) -> Path:
    IF config_path exists:
        logger.info("配置文件已存在")
        RETURN config_path

    CREATE config_path 的父目录
    WRITE DEFAULT_CONFIG as JSON to config_path (indent=4, ensure_ascii=False)
    logger.info("已创建默认配置文件")
    RETURN config_path

# ── 函数: 确保Wiki根目录存在 ──
FUNCTION ensure_wiki_root(wiki_root: Path):
    CREATE wiki_root (parents=True, exist_ok=True)
    logger.info("Wiki根目录已就绪")

# ── 函数: 确保核心提示词文件存在 ──
FUNCTION ensure_core_prompts(wiki_root: Path):
    FOR EACH (filename, prompt_data) IN CORE_PROMPTS:
        file_path = wiki_root / filename

        IF file_path exists:
            logger.info("核心提示词文件已存在: {filename}")
            CONTINUE

        # 构造Front Matter + 正文
        post = frontmatter.Post(prompt_data.content)
        post.metadata = {
            "title": prompt_data.title,
            "type": "corepage",
            "level": 1,
            "summary": prompt_data.summary,
            "tags": prompt_data.tags
        }

        CREATE file_path 的父目录
        WRITE frontmatter.dump(post) to file_path
        logger.info("已创建核心提示词文件: {filename}")

# ── 函数: 执行完整初始化 ──
FUNCTION initialize(config_path: Path, wiki_root: Path):
    logger.info("开始启动初始化...")
    ensure_config(config_path)
    ensure_wiki_root(wiki_root)
    ensure_core_prompts(wiki_root)
    logger.info("启动初始化完成")
```

---

### 3.4 `openmem/store.py`

```python
# 伪代码: 文件系统存储层 - 目录导航、页面读写、快照管理

import json, shutil, logging, threading
from datetime import datetime, timedelta
from pathlib import Path
import frontmatter

from openmem.utils import (
    validate_path_depth,
    sanitize_path,
    parse_frontmatter,
    build_frontmatter,
    merge_content,
    compute_level,
    count_content_chars
)

logger = logging.getLogger(__name__)

# ── 类: WikiStore 存储引擎 ──
CLASS WikiStore:
    FIELDS:
        wiki_root: Path             # Wiki根目录绝对路径
        max_depth: int              # 最大目录深度（默认7）
        snapshot_enabled: bool      # 快照是否启用
        cleanup_interval: int       # 快照清理间隔（分钟）
        retention_days: int         # 快照保留天数
        _cleanup_timer: threading.Timer  # 清理定时器

    # ── 构造函数 ──
    CONSTRUCTOR(wiki_root: Path, max_depth: int = 7, snapshot_cfg: dict = None):
        self.wiki_root = wiki_root.resolve()
        self.max_depth = max_depth

        # 解析快照配置
        IF snapshot_cfg:
            self.snapshot_enabled = snapshot_cfg.get("enabled", True)
            self.cleanup_interval = snapshot_cfg.get("cleanup_interval_minutes", 10)
            self.retention_days = snapshot_cfg.get("retention_days", 7)
        ELSE:
            self.snapshot_enabled = True
            self.cleanup_interval = 10
            self.retention_days = 7

        # 启动快照清理定时器
        IF self.snapshot_enabled:
            self._start_cleanup_timer()

    # ── 方法: 获取目录列表 ──
    METHOD get_directory(path: str = "/") -> str:
        """
        获取指定目录的层级文件列表（树形结构）
        """
        target_dir = self._resolve_path(path)

        IF NOT target_dir.exists():
            RETURN error_json("目录不存在: {path}")

        IF NOT target_dir.is_dir():
            RETURN error_json("路径不是目录: {path}")

        result = self._build_directory_tree(target_dir)
        RETURN json.dumps(result, ensure_ascii=False, indent=2)

    # ── 方法: 读取记忆 ──
    METHOD read_memory(path: str) -> str:
        """
        读取指定路径的完整Wiki页面内容
        """
        # 解析路径，补全.md后缀
        file_path = self._resolve_page_path(path)

        IF NOT file_path.exists():
            RETURN error_json("页面不存在: {path}")

        IF NOT file_path.is_file():
            RETURN error_json("路径不是文件: {path}")

        # 读取完整内容（Front Matter + 正文）
        content = file_path.read_text(encoding="utf-8")
        logger.debug("读取页面: {path}")
        RETURN content

    # ── 方法: 写入记忆 ──
    METHOD write_memory(content: str, path: str = None, tags: list[str] = None) -> str:
        """
        写入记忆（缺目录自动创建，更新前自动快照）
        """
        # 1. path为空时，返回提示要求LLM提供路径
        IF path IS None OR path.strip() == "":
            RETURN json.dumps({
                "status": "need_path",
                "message": "请指定写入路径。请参考核心提示词中的分类规则，确定目标路径。"
            })

        # 2. 校验路径
        path = sanitize_path(path)
        validation = validate_path_depth(path, self.max_depth)
        IF NOT validation.valid:
            logger.warning("路径深度超限: {path}")
            RETURN error_json("路径深度超过{max_depth}层限制")

        # 3. 解析目标文件路径
        file_path = self._resolve_page_path(path)

        # 4. 文件已存在 → 快照 + 合并写入
        IF file_path.exists():
            # 4a. 创建快照
            self._create_snapshot(file_path)

            # 4b. 读取现有内容并合并
            existing = parse_frontmatter(file_path)
            merged_content = merge_content(existing.body, content)
            merged_tags = list(set(existing.metadata.get("tags", []) + (tags or [])))

            # 4c. 更新Front Matter
            existing.metadata["tags"] = merged_tags
            existing.metadata["summary"] = self._generate_summary(merged_content)
            existing.body = merged_content

            # 4d. 写入
            WITH OPEN file_path AS f:
                frontmatter.dump(existing, f)

            logger.info("更新页面: {path}, 模式: merge")

        # 5. 文件不存在 → 新建
        ELSE:
            # 5a. 缺目录自动创建
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("自动创建目录: {file_path.parent}")

            # 5b. 构建Front Matter
            level = compute_level(path)
            title = self._extract_title(path)
            summary = self._generate_summary(content)

            post = frontmatter.Post(content)
            post.metadata = {
                "title": title,
                "type": "page",
                "level": level,
                "summary": summary,
                "tags": tags or []
            }

            # 5c. 写入
            WITH OPEN file_path AS f:
                frontmatter.dump(post, f)

            logger.info("创建页面: {path}")

        RETURN json.dumps({"status": "ok", "path": path}, ensure_ascii=False)

    # ── 方法: 获取核心提示词 ──
    METHOD get_core_principles() -> str:
        """
        读取Wiki根目录下所有一级.md文件内容，按文件名排序拼接
        """
        parts = []
        md_files = SORTED(wiki_root.glob("*.md")) BY filename

        FOR EACH md_file IN md_files:
            content = md_file.read_text(encoding="utf-8")
            filename = md_file.stem
            parts.APPEND("## {filename}\n\n{content}")

        RETURN "\n\n---\n\n".join(parts)

    # ── 内部方法: 解析路径 ──
    METHOD _resolve_path(path: str) -> Path:
        """
        将Wiki路径解析为文件系统路径
        "/" → wiki_root
        "/00-个人/学习" → wiki_root / "00-个人" / "学习"
        """
        IF path == "/" OR path == "":
            RETURN self.wiki_root
        RETURN self.wiki_root / path.lstrip("/")

    # ── 内部方法: 解析页面路径（补.md后缀）──
    METHOD _resolve_page_path(path: str) -> Path:
        """
        将Wiki页面路径解析为.md文件路径
        """
        resolved = self._resolve_path(path)
        IF resolved.suffix != ".md":
            resolved = resolved.with_suffix(".md")
        RETURN resolved

    # ── 内部方法: 构建目录树 ──
    METHOD _build_directory_tree(dir_path: Path) -> dict:
        """
        递归构建目录树结构
        """
        result = {
            "path": self._relative_path(dir_path),
            "name": dir_path.name OR "wiki-root",
            "type": "directory",
            "children": []
        }

        FOR EACH entry IN SORTED(dir_path.iterdir()):
            # 跳过隐藏目录(.snapshots等)
            IF entry.name.startswith("."):
                CONTINUE

            IF entry.is_dir():
                child = {
                    "name": entry.name,
                    "type": "directory",
                    "level": compute_level(self._relative_path(entry)),
                    "children": self._build_directory_tree(entry)["children"]
                }
                result.children.APPEND(child)

            ELIF entry.is_file() AND entry.suffix == ".md":
                fm = parse_frontmatter(entry)
                child = {
                    "name": entry.name,
                    "type": fm.metadata.get("type", "page"),
                    "level": fm.metadata.get("level", 1),
                    "title": fm.metadata.get("title", entry.stem),
                    "summary": fm.metadata.get("summary", "")
                }
                result.children.APPEND(child)

        RETURN result

    # ── 内部方法: 创建快照 ──
    METHOD _create_snapshot(file_path: Path):
        """
        对文件创建快照存档
        """
        IF NOT self.snapshot_enabled:
            RETURN

        rel_path = file_path.relative_to(self.wiki_root)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        # 快照路径: wiki-root/.snapshots/{相对路径不含.md}/{时间戳}.md
        snapshot_dir = self.wiki_root / ".snapshots" / rel_path.with_suffix("")
        snapshot_path = snapshot_dir / "{timestamp}.md"

        # 创建快照目录
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 复制当前文件到快照
        shutil.copy2(file_path, snapshot_path)

        logger.debug("创建快照: {snapshot_path}")

    # ── 内部方法: 启动快照清理定时器 ──
    METHOD _start_cleanup_timer():
        """
        启动后台定时清理线程
        """
        def cleanup():
            self._cleanup_snapshots()
            # 重新启动定时器
            self._cleanup_timer = threading.Timer(
                self.cleanup_interval * 60,
                cleanup
            )
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()

        self._cleanup_timer = threading.Timer(
            self.cleanup_interval * 60,
            cleanup
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()
        logger.info("快照清理定时器已启动，间隔: {cleanup_interval}分钟")

    # ── 内部方法: 清理过期快照 ──
    METHOD _cleanup_snapshots():
        """
        清理超过保留期的快照文件
        """
        snapshots_dir = self.wiki_root / ".snapshots"
        IF NOT snapshots_dir.exists():
            RETURN

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        freed_bytes = 0

        FOR EACH snapshot_file IN snapshots_dir.rglob("*.md"):
            file_mtime = datetime.fromtimestamp(snapshot_file.stat().st_mtime)
            IF file_mtime < cutoff:
                freed_bytes += snapshot_file.stat().st_size
                snapshot_file.unlink()
                deleted_count += 1

        # 清理空目录
        FOR EACH dir_path IN SORTED(snapshots_dir.rglob("*"), reverse=True):
            IF dir_path.is_dir() AND NOT list(dir_path.iterdir()):
                dir_path.rmdir()

        IF deleted_count > 0:
            logger.info("快照清理: 删除{deleted_count}个快照，释放{freed_bytes}字节")

    # ── 内部方法: 计算相对路径 ──
    METHOD _relative_path(full_path: Path) -> str:
        rel = full_path.relative_to(self.wiki_root)
        RETURN "/" + str(rel).replace("\\", "/")

    # ── 内部方法: 从路径提取标题 ──
    METHOD _extract_title(path: str) -> str:
        """
        从路径最后一段提取标题
        "/00-个人/学习/Python学习笔记" → "Python学习笔记"
        """
        parts = path.strip("/").split("/")
        last = parts[-1] IF parts ELSE "未命名"
        RETURN Path(last).stem

    # ── 内部方法: 生成摘要 ──
    METHOD _generate_summary(content: str) -> str:
        """
        从内容生成100字以内摘要
        截取正文前100字符
        """
        plain = 去除Markdown标记(content)
        RETURN plain[:100] + ("..." IF len(plain) > 100 ELSE "")
```

---

### 3.5 `openmem/utils.py`

```python
# 伪代码: 工具函数 - Front Matter解析、路径校验、合并策略

import re
import logging
from pathlib import Path
from dataclasses import dataclass
import frontmatter
import mistune

logger = logging.getLogger(__name__)

# ── 数据类: 路径校验结果 ──
@dataclass
CLASS PathValidation:
    valid: bool
    depth: int
    message: str

# ── 函数: 路径深度校验 ──
FUNCTION validate_path_depth(path: str, max_depth: int = 7) -> PathValidation:
    """
    校验路径深度是否超过限制
    根目录下文件: level=1
    一级子目录内文件: level=2
    最深: level=7
    """
    IF path == "/" OR path == "":
        RETURN PathValidation(valid=True, depth=0, message="根目录")

    # 去除首尾斜杠，按斜杠分割
    parts = path.strip("/").split("/")
    depth = len(parts)

    IF depth > max_depth:
        RETURN PathValidation(
            valid=False,
            depth=depth,
            message="路径深度{depth}超过最大限制{max_depth}"
        )

    RETURN PathValidation(valid=True, depth=depth, message="校验通过")

# ── 函数: 路径安全化 ──
FUNCTION sanitize_path(path: str) -> str:
    """
    清理路径，防止路径穿越攻击
    - 去除 .. 和 . 段
    - 去除连续斜杠
    - 去除首尾空白
    """
    IF NOT path:
        RETURN path

    # 规范化斜杠
    path = path.replace("\\", "/")
    # 去除连续斜杠
    path = re.sub(r'/+', '/', path)

    # 分段过滤
    parts = path.split("/")
    safe_parts = []
    FOR part IN parts:
        IF part == ".." OR part == ".":
            CONTINUE
        IF part.strip():
            safe_parts.APPEND(part.strip())

    result = "/".join(safe_parts)
    IF path.startswith("/"):
        result = "/" + result

    RETURN result

# ── 函数: 计算层级 ──
FUNCTION compute_level(path: str) -> int:
    """
    根据路径计算页面层级
    "/" → 1
    "/00-个人" → 1 (根目录下文件)
    "/00-个人/学习" → 2
    "/00-个人/学习/Python" → 3
    """
    IF path == "/" OR path == "":
        RETURN 1
    parts = path.strip("/").split("/")
    RETURN len(parts)

# ── 函数: 解析Front Matter ──
FUNCTION parse_frontmatter(file_path: Path) -> frontmatter.Post:
    """
    解析Markdown文件的Front Matter和正文
    """
    WITH OPEN file_path AS f:
        post = frontmatter.load(f)
    RETURN post

# ── 函数: 构建Front Matter ──
FUNCTION build_frontmatter(title: str, type: str, level: int, summary: str, tags: list[str]) -> dict:
    """
    构建标准的Front Matter元数据字典
    """
    RETURN {
        "title": title,
        "type": type,
        "level": level,
        "summary": summary,
        "tags": tags
    }

# ── 函数: 内容合并 ──
FUNCTION merge_content(existing_body: str, new_content: str) -> str:
    """
    将新内容合并到现有正文中
    策略：追加新内容，用分隔线区分

    若新内容与现有内容高度重叠，则仅保留差异部分
    """
    # 去除首尾空白
    existing = existing_body.strip()
    new = new_content.strip()

    # 新内容为空 → 保留原内容
    IF NOT new:
        RETURN existing

    # 原内容为空 → 使用新内容
    IF NOT existing:
        RETURN new

    # 简单重叠检测：新内容是否为原内容的子串
    IF new IN existing:
        RETURN existing  # 新内容已包含在原文中

    # 追加合并，用分隔线分隔
    RETURN existing + "\n\n---\n\n" + new

# ── 函数: 统计正文字数 ──
FUNCTION count_content_chars(content: str) -> int:
    """
    统计Markdown正文的有效字符数（去除标记符号）
    """
    # 使用mistune渲染为纯文本
    renderer = mistune.create_markdown(renderer=mistune.PlainRenderer())
    plain_text = renderer(content)
    RETURN len(plain_text.strip())

# ── 函数: 校验Front Matter完整性 ──
FUNCTION validate_frontmatter(metadata: dict) -> tuple[bool, list[str]]:
    """
    校验Front Matter是否包含所有必需字段
    必需字段: title, type, level, summary, tags
    """
    required_fields = ["title", "type", "level", "summary", "tags"]
    missing = []

    FOR field IN required_fields:
        IF field NOT IN metadata OR metadata[field] IS None:
            missing.APPEND(field)

    is_valid = len(missing) == 0
    RETURN (is_valid, missing)

# ── 函数: 检查是否为核心提示词文件 ──
FUNCTION is_core_page(file_path: Path, wiki_root: Path) -> bool:
    """
    判断文件是否为核心提示词文件
    条件：位于wiki_root直接子目录下且为.md文件
    """
    IF file_path.suffix != ".md":
        RETURN False
    RETURN file_path.parent == wiki_root
```

---

### 3.6 `tests/test_initializer.py`

```python
# 伪代码: 初始化模块测试

FUNCTION test_ensure_config_creates_default():
    """
    测试: 配置文件不存在时，自动创建默认配置
    """
    GIVEN 临时目录 AS tmp
    config_path = tmp / "openmem.json"

    result = ensure_config(config_path)

    ASSERT config_path exists
    ASSERT json.loads(config_path) == DEFAULT_CONFIG
    ASSERT result == config_path

FUNCTION test_ensure_config_skips_existing():
    """
    测试: 配置文件已存在时，不覆盖
    """
    GIVEN 临时目录 AS tmp
    config_path = tmp / "openmem.json"
    WRITE {"wiki_root": "./custom"} TO config_path

    ensure_config(config_path)

    ASSERT json.loads(config_path)["wiki_root"] == "./custom"

FUNCTION test_ensure_wiki_root_creates_directory():
    """
    测试: Wiki根目录不存在时自动创建
    """
    GIVEN 临时目录 AS tmp
    wiki_root = tmp / "new-wiki"

    ensure_wiki_root(wiki_root)

    ASSERT wiki_root exists
    ASSERT wiki_root is directory

FUNCTION test_ensure_core_prompts_creates_files():
    """
    测试: 核心提示词文件不存在时自动创建
    """
    GIVEN 临时目录 AS tmp AS wiki_root

    ensure_core_prompts(wiki_root)

    FOR EACH filename IN CORE_PROMPTS:
        file_path = wiki_root / filename
        ASSERT file_path exists
        post = parse_frontmatter(file_path)
        ASSERT post.metadata["type"] == "corepage"
        ASSERT post.metadata["level"] == 1

FUNCTION test_ensure_core_prompts_skips_existing():
    """
    测试: 核心提示词文件已存在时不覆盖
    """
    GIVEN 临时目录 AS tmp AS wiki_root
    WRITE "custom content" TO wiki_root / "记忆管理规则.md"

    ensure_core_prompts(wiki_root)

    content = (wiki_root / "记忆管理规则.md").read_text()
    ASSERT "custom content" IN content

FUNCTION test_initialize_full_flow():
    """
    测试: 完整初始化流程
    """
    GIVEN 临时目录 AS tmp
    config_path = tmp / "openmem.json"
    wiki_root = tmp / "wiki"

    initialize(config_path, wiki_root)

    ASSERT config_path exists
    ASSERT wiki_root exists
    ASSERT all core prompt files exist in wiki_root
```

---

### 3.7 `tests/test_store.py`

```python
# 伪代码: 存储层测试

CLASS TestWikiStore:
    SETUP:
        GIVEN 临时目录 AS tmp AS wiki_root
        创建核心提示词文件
        store = WikiStore(wiki_root, max_depth=7)

    FUNCTION test_get_directory_root():
        """
        测试: 获取根目录列表
        """
        result_json = store.get_directory("/")
        result = json.loads(result_json)

        ASSERT result["type"] == "directory"
        ASSERT result["children"] contains core prompt files

    FUNCTION test_get_directory_subdirectory():
        """
        测试: 获取子目录列表
        """
        CREATE wiki_root / "00-个人" / "健康.md" WITH Front Matter

        result_json = store.get_directory("/00-个人")
        result = json.loads(result_json)

        ASSERT result["children"] has item with name "健康.md"

    FUNCTION test_read_memory_existing():
        """
        测试: 读取已存在的页面
        """
        CREATE wiki_root / "00-个人" / "测试.md" WITH content "Hello World"

        content = store.read_memory("/00-个人/测试")

        ASSERT "Hello World" IN content

    FUNCTION test_read_memory_nonexistent():
        """
        测试: 读取不存在的页面返回错误
        """
        result = store.read_memory("/不存在的路径")

        ASSERT "error" IN result OR "不存在" IN result

    FUNCTION test_write_memory_create_new():
        """
        测试: 创建新页面（缺目录自动创建）
        """
        result = store.write_memory(
            content="新内容",
            path="/01-工作/项目B",
            tags=["工作"]
        )

        ASSERT file wiki_root / "01-工作" / "项目B.md" exists
        post = parse_frontmatter(wiki_root / "01-工作" / "项目B.md")
        ASSERT post.metadata["type"] == "page"
        ASSERT post.metadata["tags"] == ["工作"]

    FUNCTION test_write_memory_update_existing():
        """
        测试: 更新已存在的页面（自动快照+合并）
        """
        CREATE wiki_root / "01-工作" / "项目A.md" WITH content "原始内容"

        result = store.write_memory(
            content="新增内容",
            path="/01-工作/项目A"
        )

        # 验证快照已创建
        ASSERT .snapshots directory contains backup
        # 验证内容已合并
        post = parse_frontmatter(wiki_root / "01-工作" / "项目A.md")
        ASSERT "原始内容" IN post.body
        ASSERT "新增内容" IN post.body

    FUNCTION test_write_memory_depth_exceeded():
        """
        测试: 超过7层深度时拒绝写入
        """
        deep_path = "/a/b/c/d/e/f/g/h"  # 8层

        result = store.write_memory(content="test", path=deep_path)

        ASSERT "error" IN result OR "超过" IN result

    FUNCTION test_write_memory_no_path():
        """
        测试: path为空时返回need_path提示
        """
        result = store.write_memory(content="test", path=None)

        result_dict = json.loads(result)
        ASSERT result_dict["status"] == "need_path"

    FUNCTION test_get_core_principles():
        """
        测试: 获取核心提示词合集
        """
        result = store.get_core_principles()

        ASSERT "记忆管理规则" IN result
        ASSERT "用户偏好习惯" IN result
        ASSERT "Agent行为指南" IN result
        ASSERT "Wiki整理指南" IN result

    FUNCTION test_snapshot_created_before_update():
        """
        测试: 更新文件前自动创建快照
        """
        CREATE wiki_root / "测试.md" WITH content "v1"

        store.write_memory(content="v2", path="/测试")

        snapshot_dir = wiki_root / ".snapshots" / "测试"
        ASSERT snapshot_dir exists
        snapshots = list(snapshot_dir.glob("*.md"))
        ASSERT len(snapshots) == 1
        ASSERT "v1" IN snapshots[0].read_text()

    FUNCTION test_snapshot_cleanup():
        """
        测试: 过期快照自动清理
        """
        # 创建一个超过保留期的快照
        old_snapshot = wiki_root / ".snapshots" / "测试" / "2020-01-01T00-00-00.md"
        CREATE old_snapshot WITH content "old"

        store._cleanup_snapshots()

        ASSERT NOT old_snapshot exists
```

---

### 3.8 `tests/test_mcp_api.py`

```python
# 伪代码: MCP接口集成测试

CLASS TestMCPAPI:
    SETUP:
        GIVEN 临时目录 AS tmp AS wiki_root
        初始化配置和核心提示词
        store = WikiStore(wiki_root)
        # 直接调用main.py中注册的函数（绕过FastMCP传输层）

    FUNCTION test_get_directory_returns_json():
        """
        测试: get_directory返回合法JSON
        """
        result = get_directory("/")

        parsed = json.loads(result)
        ASSERT parsed["type"] == "directory"
        ASSERT "children" IN parsed

    FUNCTION test_read_memory_returns_content():
        """
        测试: read_memory返回完整Markdown内容
        """
        CREATE test page

        result = read_memory("/测试页面")

        ASSERT "---" IN result  # Front Matter标记
        ASSERT "title:" IN result

    FUNCTION test_write_memory_returns_path():
        """
        测试: write_memory返回最终路径
        """
        result = write_memory(content="测试内容", path="/测试页面")

        parsed = json.loads(result)
        ASSERT parsed["status"] == "ok"
        ASSERT parsed["path"] == "/测试页面"

    FUNCTION test_core_principles_prompt():
        """
        测试: core_principles_prompt返回非空内容
        """
        result = core_principles_prompt()

        ASSERT len(result) > 0
        ASSERT "记忆管理规则" IN result
```

---

### 3.9 `tests/test_utils.py`

```python
# 伪代码: 工具函数测试

FUNCTION test_validate_path_depth_valid():
    """
    测试: 合法深度路径通过校验
    """
    result = validate_path_depth("/a/b/c", max_depth=7)
    ASSERT result.valid == True
    ASSERT result.depth == 3

FUNCTION test_validate_path_depth_exceeded():
    """
    测试: 超过最大深度的路径被拒绝
    """
    result = validate_path_depth("/a/b/c/d/e/f/g/h", max_depth=7)
    ASSERT result.valid == False
    ASSERT result.depth == 8

FUNCTION test_sanitize_path_removes_traversal():
    """
    测试: 去除路径穿越攻击
    """
    result = sanitize_path("/a/../b/./c")
    ASSERT result == "/a/b/c"

FUNCTION test_sanitize_path_normalizes_slashes():
    """
    测试: 规范化斜杠
    """
    result = sanitize_path("//a///b//")
    ASSERT result == "/a/b"

FUNCTION test_compute_level():
    """
    测试: 层级计算
    """
    ASSERT compute_level("/") == 1
    ASSERT compute_level("/a") == 1
    ASSERT compute_level("/a/b") == 2
    ASSERT compute_level("/a/b/c") == 3

FUNCTION test_merge_content_append():
    """
    测试: 内容合并-追加模式
    """
    result = merge_content("原始内容", "新增内容")
    ASSERT "原始内容" IN result
    ASSERT "新增内容" IN result
    ASSERT "---" IN result  # 分隔线

FUNCTION test_merge_content_duplicate():
    """
    测试: 内容合并-重复内容不追加
    """
    result = merge_content("原始内容", "原始内容")
    ASSERT result.count("原始内容") == 1  # 不重复

FUNCTION test_count_content_chars():
    """
    测试: 正文字数统计
    """
    content = "# 标题\n\n这是正文内容"
    count = count_content_chars(content)
    ASSERT count > 0

FUNCTION test_validate_frontmatter_complete():
    """
    测试: Front Matter完整性校验-完整
    """
    metadata = {"title": "test", "type": "page", "level": 1, "summary": "s", "tags": []}
    is_valid, missing = validate_frontmatter(metadata)
    ASSERT is_valid == True
    ASSERT len(missing) == 0

FUNCTION test_validate_frontmatter_incomplete():
    """
    测试: Front Matter完整性校验-缺少字段
    """
    metadata = {"title": "test"}
    is_valid, missing = validate_frontmatter(metadata)
    ASSERT is_valid == False
    ASSERT "type" IN missing
    ASSERT "level" IN missing

FUNCTION test_is_core_page():
    """
    测试: 核心提示词文件判断
    """
    wiki_root = Path("/wiki")
    core_file = wiki_root / "记忆管理规则.md"
    sub_file = wiki_root / "00-个人" / "健康.md"

    ASSERT is_core_page(core_file, wiki_root) == True
    ASSERT is_core_page(sub_file, wiki_root) == False
```

---

## 四、模块间调用关系

```
main.py
  ├── 导入 initializer.py
  │     ├── ensure_config()     → 读写 openmem.json
  │     ├── ensure_wiki_root()  → mkdir wiki-root/
  │     └── ensure_core_prompts()→ 写入 核心提示词.md文件
  │
  ├── 导入 store.py (WikiStore)
  │     ├── get_directory()     → 读取 wiki-root/ 目录结构
  │     │     └── 调用 utils.parse_frontmatter()
  │     │     └── 调用 utils.compute_level()
  │     │
  │     ├── read_memory()       → 读取 wiki-root/xxx.md
  │     │     └── 调用 utils.sanitize_path()
  │     │
  │     ├── write_memory()      → 写入 wiki-root/xxx.md
  │     │     ├── 调用 utils.sanitize_path()
  │     │     ├── 调用 utils.validate_path_depth()
  │     │     ├── 调用 utils.parse_frontmatter()
  │     │     ├── 调用 utils.merge_content()
  │     │     ├── 调用 utils.compute_level()
  │     │     ├── 调用 utils.build_frontmatter()
  │     │     ├── 调用 self._create_snapshot()  → 写入 .snapshots/
  │     │     └── 调用 self._generate_summary()
  │     │
  │     ├── get_core_principles()→ 读取 wiki-root/*.md
  │     │
  │     └── _cleanup_snapshots() → 清理 .snapshots/ 过期文件
  │
  └── 导入 utils.py (工具函数，被store.py间接调用)
        ├── validate_path_depth()
        ├── sanitize_path()
        ├── compute_level()
        ├── parse_frontmatter()
        ├── build_frontmatter()
        ├── merge_content()
        ├── count_content_chars()
        ├── validate_frontmatter()
        └── is_core_page()
```
