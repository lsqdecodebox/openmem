# OpenMem-MCP 文件存储设计

## 1. 设计原则

### 1.1 核心原则

- **零依赖存储**：纯文件系统存储，无需数据库
- **Obsidian 兼容**：标准 Markdown + Front Matter，可直接在 Obsidian 中编辑
- **原子写入**：写入操作不丢失，防止文件损坏
- **索引维护**：目录索引自动同步，保证一致性

### 1.2 目录结构

```
wiki_root/                    # 配置的 Wiki 根目录
├── 目录.md                   # 根目录索引文件
├── 页面1.md                  # 页面文件
├── 页面2.md                  # 页面文件
├── 子目录A/                  # 子目录
│   ├── 目录.md               # 子目录索引文件
│   ├── 页面A1.md             # 子页面
│   └── 页面A2.md             # 子页面
└── 子目录B/
    ├── 目录.md
    └── ...
```

**关键约定：**
- 每个目录必须包含一个 `目录.md` 文件作为索引
- 根目录同样有 `目录.md`
- 所有文件名以 `.md` 结尾

---

## 2. Front Matter 规范

### 2.1 页面 Front Matter

```yaml
---
title: 页面标题                              # 必填：页面显示标题
path: /子目录/页面文件.md                    # 必填：完整路径
type: page                                  # 必填：固定值 "page"
level: 2                                    # 必填：层级深度（1-7）
parent: /子目录                             # 必填：父目录路径
created_at: "2026-05-25T10:00:00"          # 必填：创建时间 ISO 格式
updated_at: "2026-05-25T10:30:00"          # 必填：更新时间 ISO 格式
summary: 简短描述，不超过150字符              # 必填：内容摘要
tags: [标签1, 标签2]                        # 可选：标签列表
source: Claude对话                          # 可选：内容来源
---
```

### 2.2 目录索引 Front Matter

```yaml
---
title: 目录标题                              # 必填：目录显示名称
path: /子目录                                # 必填：目录路径
type: directory                             # 必填：固定值 "directory"
level: 1                                    # 必填：目录层级（根为1）
parent: /                                   # 必填：父目录路径（根为/）
created_at: "2026-05-25T10:00:00"
updated_at: "2026-05-25T10:30:00"
summary: 目录描述                           # 必填：目录用途说明
tags: []
source: auto
---
```

### 2.3 必填字段清单

| 字段 | 类型 | 页面 | 目录 | 说明 |
|------|------|------|------|------|
| `title` | string | ✓ | ✓ | 显示标题 |
| `path` | string | ✓ | ✓ | 完整路径 |
| `type` | string | ✓ | ✓ | `page` 或 `directory` |
| `level` | int | ✓ | ✓ | 层级深度 |
| `parent` | string | ✓ | ✓ | 父目录路径 |
| `created_at` | string | ✓ | ✓ | ISO 时间戳 |
| `updated_at` | string | ✓ | ✓ | ISO 时间戳 |
| `summary` | string | ✓ | ✓ | 简短描述 ≤150 字符 |
| `tags` | list | ✓ | ✓ | 标签列表 |
| `source` | string | ✓ | ✓ | 来源标识 |

---

## 3. 目录索引文件格式

### 3.1 索引文件内容

`目录.md` 文件包含两部分：

**Front Matter 部分**：目录的元数据

**Markdown 内容部分**：目录中条目的链接列表

```markdown
---
title: 项目
path: /项目
type: directory
level: 1
parent: /
created_at: "2026-05-25T10:00:00"
updated_at: "2026-05-25T10:30:00"
summary: 项目相关文档和笔记
tags: []
source: auto
---

# 项目

- [[项目/openmem-mcp/openmem-mcp 三大 Bug 修复记录|openmem-mcp 三大 Bug 修复记录]]
- [[项目/openmem-mcp/学习笔记|学习笔记]]
```

### 3.2 链接格式

使用 Obsidian 兼容的双链格式：

```
[[绝对路径|显示标题]]
```

| 格式 | 示例 | 说明 |
|------|------|------|
| 目录链接 | `[[/项目/openmem-mcp\|openmem-mcp]]` | 链接到目录（实际指向目录.md） |
| 页面链接 | `[[/项目/openmem-mcp/笔记.md\|笔记]]` | 链接到页面文件 |

---

## 4. 原子写入机制

### 4.1 写入流程

```
原始文件: target.md
临时文件: target.md.tmp
写入流程:

1. 创建临时文件
   └── open("target.md.tmp", "w", encoding="utf-8")

2. 写入完整内容（Front Matter + 正文）
   └── temp_file.write(full_content)

3. 强制刷盘
   └── temp_file.flush()
   └── os.fsync(temp_file.fileno())

4. 原子重命名（POSIX）/ 替换（Windows）
   └── os.replace("target.md.tmp", "target.md")
       或
   └── os.rename("target.md.tmp", "target.md")
```

### 4.2 故障恢复

| 故障点 | 后果 | 恢复方式 |
|--------|------|----------|
| 写入中断 | temp 文件残留 | 下次写入时清理 |
| flush/fsync 失败 | 无影响 | 原文件保持不变 |
| rename 失败 | temp 文件残留 | 下次写入时清理 |
| rename 成功 | 完成 | - |

### 4.3 临时文件清理

每次写入前检查并清理同名 temp 文件：

```python
temp_path = target_path.with_suffix(".md.tmp")
if temp_path.exists():
    temp_path.unlink()
```

---

## 5. 路径解析规则

### 5.1 路径类型

| 类型 | 示例 | 说明 |
|------|------|------|
| 绝对路径 | `/项目/openmem-mcp/笔记.md` | 相对于 wiki_root 的完整路径 |
| 相对路径 | `项目/openmem-mcp/笔记.md` | 相对于 wiki_root |
| 目录路径 | `/项目/openmem-mcp` | 不包含 .md |

### 5.2 路径规范化

```
输入: ./项目/openmem-mcp/笔记.md
输出: /项目/openmem-mcp/笔记.md

输入: 项目/openmem-mcp/笔记.md
输出: /项目/openmem-mcp/笔记.md

输入: /项目/openmem-mcp/
输出: /项目/openmem-mcp
```

### 5.3 安全校验

所有路径操作前进行安全校验：

1. **范围检查**：确保路径在 `wiki_root` 内
2. **深度检查**：确保层级不超过 `max_depth`
3. **字符检查**：禁止 `..` 路径遍历
4. **名称检查**：禁止特殊字符

---

## 6. 索引维护策略

### 6.1 创建页面时

```
创建文件: /父目录/新页面.md
    │
    ▼
1. 写入目标文件（Front Matter + content）
    │
    ▼
2. 读取父目录的 目录.md
    │
    ▼
3. 解析现有内容，查找链接列表位置
    │
    ▼
4. 追加新链接: - [[/父目录/新页面|标题]]
    │
    ▼
5. 写回父目录的 目录.md
```

### 6.2 创建目录时

```
创建目录: /新目录
    │
    ▼
1. 创建物理目录
    │
    ▼
2. 创建目录索引: /新目录/目录.md
    ├── Front Matter (type=directory)
    └── Content: # 目录标题
    │
    ▼
3. 更新父目录索引（如果有父目录）
    └── 追加: - [[/新目录|目录标题]]
```

### 6.3 更新页面时

更新页面内容时，**不**修改父目录索引，因为：
- 页面路径不变
- 页面标题可能改变，但需要显式调用 `update_memory` 时才更新索引

---

## 7. 文件操作 API

### 7.1 FileStore 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `read_page(path)` | 读取页面 | `frontmatter.Post` |
| `read_directory(path)` | 读取目录索引 | `str` (原始内容) |
| `create_page(...)` | 创建页面 | `bool` |
| `create_directory(...)` | 创建目录 | `bool` |
| `update_page(path, content)` | 更新页面 | `bool` |
| `list_directory_items(path)` | 列出目录条目 | `list[dict]` |
| `export_wiki(output_path)` | 导出 ZIP | `str` |

### 7.2 目录列表项结构

```python
{
  "title": str,    # 从 Front Matter 读取
  "path": str,     # 完整路径
  "summary": str,  # 摘要
  "type": str      # "page" 或 "directory"
}
```

---

## 8. 层级深度管理

### 8.1 深度计算

```
level = 路径中的目录层级数

/                   -> level 0
/项目               -> level 1
/项目/openmem-mcp   -> level 2
/项目/openmem-mcp/笔记.md -> level 2
```

### 8.2 深度限制

- `max_depth` 默认值为 7
- 创建时校验：`level <= max_depth`
- 搜索时作为递归终止条件

### 8.3 Front Matter 中的 level

| 场景 | level 值 |
|------|----------|
| 根目录索引 | 0 |
| 根目录下的页面 | 1 |
| 一级子目录下的页面 | 2 |
| 深层嵌套以此类推 | ... |

---

## 9. 与 Obsidian 的兼容性

### 9.1 双向兼容

| 特性 | OpenMem-MCP | Obsidian |
|------|-------------|----------|
| Markdown | ✓ | ✓ |
| Front Matter | ✓ | ✓ |
| 双链 `[[]]` | ✓ | ✓ |
| 自动补全 | ✗ | ✓ |
| 图谱视图 | ✗ | ✓ |

### 9.2 互操作注意事项

1. **双向链接**：Obsidian 创建的链接符合格式，可以被 FileStore 解析
2. **外部编辑**：在 Obsidian 中编辑的文件，重新加载时 Front Matter 会被正确解析
3. **索引同步**：在 Obsidian 中创建目录后，需要手动调用 `create_directory` 或重启服务以更新索引
4. **文件移动**：不建议直接在文件系统移动文件，会导致索引不同步

---

## 10. 备份与恢复

### 10.1 导出备份

使用 `export_wiki` 工具导出完整 ZIP 包：

```bash
zip -r wiki_backup.zip ./wikitest0525
```

### 10.2 恢复备份

解压到 `wiki_root` 目录：

```bash
unzip wiki_backup.zip -d ./wikitest0525
```

### 10.3 增量备份建议

建议定期使用 `export_wiki` 工具导出增量备份，因为：
- 纯文件方式无数据库，备份简单
- ZIP 格式便于传输和存储
- 可保留版本历史