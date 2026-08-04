import json
import logging
import sys
from pathlib import Path

import frontmatter

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "wiki_root": "~/.openmem/wiki",
    "max_depth": 7,
    "max_chars": 100000,
    "snapshot": {
        "enabled": True,
        "cleanup_interval_minutes": 10,
        "retention_days": 7,
        "schedule_enabled": True,
    },
    "default_tags": [],
    "remote": {
        "host": "127.0.0.1",
        "port": 6000,
        "path": "/mcp",
    },
    "logging": {
        "level": "INFO",
        "file_enabled": True,
        "file_path": "~/.openmem/logs/openmem.log",
        "max_file_size_mb": 10,
        "backup_count": 5,
        "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    },
}


# CORE_PROMPTS 改为 rule.md 内容
CORE_PROMPTS = {
    "记忆管理规则.md": {
        "title": "记忆管理规则",
        "type": "corepage",
        "summary": "记忆系统的核心管理规则，定义写入、分类和检索的基本原则。",
        "tags": ["核心", "规则"],
        "content": (
            "# 记忆管理规则\n\n"
            "## 核心原则\n\n"
            "1. **结构化存储**：所有记忆必须存放在明确的分类目录下\n"
            "2. **层级限制**：目录深度不超过7层\n"
            "3. **自动快照**：更新已有内容前自动创建快照备份\n"
            "4. **合并优先**：更新内容时优先合并，避免重复\n\n"
            "## 写入规则\n\n"
            "- 写入前先确认目标路径\n"
            "- 同一主题的内容应合并到同一页面\n"
            "- 使用标签辅助分类和检索\n"
        ),
    },
    "用户偏好习惯.md": {
        "title": "用户偏好习惯",
        "type": "corepage",
        "summary": "用户的沟通风格与个人偏好记录。",
        "tags": ["核心", "偏好"],
        "content": (
            "# 用户偏好习惯\n\n"
            "## 沟通风格\n\n"
            "- 请根据用户实际使用逐步记录偏好\n\n"
            "## 工作习惯\n\n"
            "- 请根据用户实际使用逐步记录\n"
        ),
    },
    "Agent行为指南.md": {
        "title": "Agent行为指南",
        "type": "corepage",
        "summary": "Agent写入行为规范与决策边界。",
        "tags": ["核心", "指南"],
        "content": (
            "# Agent行为指南\n\n"
            "## 主动写入场景\n\n"
            "1. 用户明确要求记录某条信息\n"
            "2. 用户提到重要的偏好或习惯\n"
            "3. 用户请求保存学习笔记或总结\n\n"
            "## 禁止写入场景\n\n"
            "1. 未经用户确认的推测性内容\n"
            "2. 敏感信息（密码、密钥等）\n"
            "3. 临时性对话内容\n\n"
            "## 分类决策\n\n"
            "- 根据内容主题选择合适的目录\n"
            "- 不确定时优先放入更通用的分类\n"
            "- 可参考已有目录结构进行归类\n"
        ),
    },
    "Wiki整理指南.md": {
        "title": "Wiki整理指南",
        "type": "corepage",
        "summary": "Wiki目录结构整理与内容归并规范。",
        "tags": ["核心", "整理"],
        "content": (
            "# Wiki整理指南\n\n"
            "## 整理原则\n\n"
            "1. **一致性**：同类内容使用相同的目录结构\n"
            "2. **简洁性**：目录名称简短且表意明确\n"
            "3. **可扩展**：预留子目录扩展空间\n\n"
            "## 推荐目录结构\n\n"
            "- `00-个人/` - 个人信息、偏好、习惯\n"
            "- `01-工作/` - 工作项目、会议记录\n"
            "- `02-学习/` - 学习笔记、知识积累\n"
            "- `03-资源/` - 常用资源、工具链接\n\n"
            "## 归并规则\n\n"
            "- 相关内容合并到同一页面\n"
            "- 超过500字的页面考虑拆分为子页面\n"
            "- 定期清理过时内容\n"
        ),
    },
}


def ensure_config(config_path: Path) -> Path:
    if config_path.exists():
        logger.info("配置文件已存在")
        return config_path

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        logger.info("已创建默认配置文件")
    except (PermissionError, OSError) as e:
        print(
            f"[openmem] 警告：无法创建配置文件 {config_path}（{e}），"
            "将使用内置默认配置",
            file=sys.stderr,
        )
    return config_path


def ensure_wiki_root(wiki_root: Path):
    try:
        wiki_root.mkdir(parents=True, exist_ok=True)
        logger.info("Wiki根目录已就绪")
    except (PermissionError, OSError) as e:
        print(
            f"[openmem] 错误：无法创建Wiki根目录 {wiki_root}（{e}）。\n"
            "请检查目录权限，或在配置文件中修改 wiki_root 路径指向可写位置。",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_core_prompts(wiki_root: Path):
    for filename, prompt_data in CORE_PROMPTS.items():
        file_path = wiki_root / filename

        if file_path.exists():
            logger.info(f"核心提示词文件已存在: {filename}")
            continue

        post = frontmatter.Post(prompt_data["content"])
        post.metadata = {
            "title": prompt_data["title"],
            "type": "corepage",
            "level": 1,
            "summary": prompt_data["summary"],
            "tags": prompt_data["tags"],
        }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            frontmatter.dump(post, f)
        logger.info(f"已创建核心提示词文件: {filename}")


def initialize(config_path: Path, wiki_root: Path):
    logger.info("开始启动初始化...")
    ensure_config(config_path)
    ensure_wiki_root(wiki_root)
    # ensure_core_prompts(wiki_root)
    logger.info("启动初始化完成")
