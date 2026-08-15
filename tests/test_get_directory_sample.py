#!/usr/bin/env python
"""单独测试 get_directory 输出样例脚本

构造一套完整的示例 Wiki 数据（含嵌套目录和页面），
然后直接调用 WikiStore.get_directory() 查看输出格式。
"""

import json
import shutil
import tempfile
from pathlib import Path

import frontmatter

# 确保项目根目录在 sys.path 中
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from openmem.store import WikiStore


def create_sample_page(
    file_path: Path,
    title: str,
    content: str,
    page_type: str = "page",
    level: int = 1,
    summary: str | None = None,
    tags: list[str] | None = None,
):
    """创建一个带 frontmatter 的示例 Markdown 页面"""
    post = frontmatter.Post(content)
    post.metadata = {
        "title": title,
        "type": page_type,
        "level": level,
        "summary": summary or (content[:50] + "..." if len(content) > 50 else content),
        "tags": tags or [],
    }
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        frontmatter.dump(post, f)


def build_sample_wiki(wiki_root: Path):
    """在 wiki_root 下构造一套完整的示例数据结构"""

    # ---------- 根目录核心文件（corepage）----------
    create_sample_page(
        wiki_root / "记忆管理规则.md",
        title="记忆管理规则",
        page_type="corepage",
        level=1,
        summary="记忆系统的核心管理规则，定义写入、分类和检索的基本原则。",
        tags=["核心", "规则"],
        content="# 记忆管理规则\n\n## 核心原则\n1. 结构化存储\n2. 层级限制不超过7层\n3. 自动快照备份\n4. 合并优先",
    )

    create_sample_page(
        wiki_root / "Agent行为指南.md",
        title="Agent行为指南",
        page_type="corepage",
        level=1,
        summary="Agent写入行为规范与决策边界，定义主动写入与禁止写入场景。",
        tags=["核心", "指南"],
        content="# Agent行为指南\n\n## 主动写入场景\n1. 用户明确要求记录\n2. 用户提到重要偏好\n3. 用户请求保存笔记",
    )

    # ---------- 00-个人 目录 ----------
    personal_dir = wiki_root / "00-个人"
    create_sample_page(
        personal_dir / "个人信息.md",
        title="个人信息",
        page_type="page",
        level=2,
        summary="用户基本个人信息与联系方式。",
        tags=["个人", "资料"],
        content="# 个人信息\n\n- 姓名：用户示例\n- 角色：软件工程师\n- 语言：中文/英文",
    )

    # 00-个人/偏好 子目录
    pref_dir = personal_dir / "偏好"
    create_sample_page(
        pref_dir / "沟通风格.md",
        title="沟通风格",
        page_type="page",
        level=3,
        summary="用户偏好的沟通方式与回复风格。",
        tags=["偏好", "沟通"],
        content="# 沟通风格\n\n- 回复简洁直接\n- 代码示例优先\n- 技术讨论深入细节",
    )
    create_sample_page(
        pref_dir / "编辑器与工具.md",
        title="编辑器与工具",
        page_type="page",
        level=3,
        summary="日常使用的编辑器、终端、开发工具配置。",
        tags=["偏好", "工具"],
        content="# 编辑器与工具\n\n- 主力编辑器：VS Code / Neovim\n- 终端：iTerm2 + zsh\n- 包管理：uv / pnpm",
    )

    # ---------- 01-工作 目录 ----------
    work_dir = wiki_root / "01-工作"
    create_sample_page(
        work_dir / "项目列表.md",
        title="项目列表",
        page_type="page",
        level=2,
        summary="当前进行中与已完成的工作项目概览。",
        tags=["工作", "项目"],
        content="# 项目列表\n\n## 进行中\n- 项目A：MCP 记忆系统开发\n## 已完成\n- 项目B：搜索平台优化",
    )

    # 01-工作/项目A 子目录（多层级）
    proj_dir = work_dir / "项目A-MCP记忆系统"
    create_sample_page(
        proj_dir / "需求文档.md",
        title="需求文档",
        page_type="page",
        level=3,
        summary="MCP 记忆系统的功能需求与设计目标。",
        tags=["项目", "需求"],
        content="# 需求文档\n\n## 核心功能\n1. 目录浏览 get_directory\n2. 页面读写 read_memory / write_memory\n3. 二进制资产写入 write_asset",
    )
    create_sample_page(
        proj_dir / "技术方案.md",
        title="技术方案",
        page_type="page",
        level=3,
        summary="基于 FastMCP + frontmatter 的技术实现方案。",
        tags=["项目", "架构"],
        content="# 技术方案\n\n- 框架：FastMCP\n- 存储：文件系统 + Markdown + Front Matter\n- 快照：自动定时快照 + 过期清理",
    )

    # 01-工作/项目A/会议 子目录（第4层）
    meeting_dir = proj_dir / "会议记录"
    create_sample_page(
        meeting_dir / "2026-08-01-技术评审.md",
        title="2026-08-01 技术评审",
        page_type="page",
        level=4,
        summary="MCP 记忆系统架构评审会议要点与决议。",
        tags=["会议", "评审"],
        content="# 技术评审会议 2026-08-01\n\n## 决议\n1. 采用文件系统存储而非数据库\n2. max_depth 限制为 7 层\n3. 启用快照机制",
    )

    # ---------- 02-学习 目录 ----------
    study_dir = wiki_root / "02-学习"
    create_sample_page(
        study_dir / "Python学习笔记.md",
        title="Python学习笔记",
        page_type="page",
        level=2,
        summary="Python 3.10+ 新特性与最佳实践笔记。",
        tags=["学习", "Python"],
        content="# Python学习笔记\n\n## match-case 模式匹配\n使用 match-case 替代多层 if-elif。",
    )
    create_sample_page(
        study_dir / "MCP协议理解.md",
        title="MCP协议理解",
        page_type="page",
        level=2,
        summary="Model Context Protocol 的核心概念与交互流程。",
        tags=["学习", "MCP"],
        content="# MCP协议理解\n\n## 生命周期\n1. initialize 握手\n2. tools/list 发现\n3. tools/call 调用",
    )

    # ---------- 03-资源 目录 ----------
    res_dir = wiki_root / "03-资源"
    create_sample_page(
        res_dir / "常用链接.md",
        title="常用链接",
        page_type="page",
        level=2,
        summary="日常开发常用的文档和工具链接汇总。",
        tags=["资源", "链接"],
        content="# 常用链接\n\n- Python Docs: https://docs.python.org\n- FastMCP Repo: https://github.com/punkpeye/fastmcp",
    )

    # ---------- 资产目录（空目录也会被列出）----------
    (wiki_root / "images").mkdir(parents=True, exist_ok=True)
    (wiki_root / "files").mkdir(parents=True, exist_ok=True)


def main():
    # 使用临时目录构造示例数据，避免污染真实 wiki
    with tempfile.TemporaryDirectory(prefix="openmem_test_") as tmp:
        wiki_root = Path(tmp) / "wiki"
        wiki_root.mkdir()

        print("=" * 70)
        print(f"[1/3] 构造示例 Wiki 数据于临时目录: {wiki_root}")
        print("=" * 70)
        build_sample_wiki(wiki_root)

        # 打印实际磁盘结构供对比
        print("\n磁盘上的实际文件树：")
        for p in sorted(wiki_root.rglob("*")):
            rel = p.relative_to(wiki_root)
            indent = "  " * (len(rel.parts) - 1)
            marker = "[D]" if p.is_dir() else "[F]"
            print(f"  {indent}{marker} {rel.name}")

        # ---------- 实例化 WikiStore ----------
        print("\n" + "=" * 70)
        print("[2/3] 实例化 WikiStore 并调用 get_directory(/)")
        print("=" * 70)
        store = WikiStore(wiki_root=wiki_root, max_depth=7, snapshot_cfg={"enabled": False})

        # 测试1: 根目录
        root_output = store.get_directory("/")
        print("\n>>>>> get_directory('/') 输出:")
        print(root_output)

        # 解析并检查字段完整性
        root_data = json.loads(root_output)
        print(f"\n根目录解析成功：path={root_data['path']}, children数={len(root_data['children'])}")
        print(f"顶层字段: {sorted(root_data.keys())}")

        # ---------- 测试2: 子目录 ----------
        print("\n" + "=" * 70)
        print("[3/3] 调用 get_directory('/01-工作/项目A-MCP记忆系统')")
        print("=" * 70)
        sub_output = store.get_directory("/01-工作/项目A-MCP记忆系统")
        print("\n>>>>> 子目录输出:")
        print(sub_output)

        # ---------- 测试3: 错误场景 ----------
        print("\n" + "=" * 70)
        print("补充：错误场景输出样例")
        print("=" * 70)
        print("\n不存在的目录:")
        print(store.get_directory("/不存在/的/路径"))
        print("\n指向文件而非目录:")
        print(store.get_directory("/记忆管理规则.md"))  # 会被 _resolve_path 当作目录但它是文件

        print("\n✅ 测试完成。临时目录已自动清理。")


if __name__ == "__main__":
    main()
