# OpenMem-MCP API 参考手册

## 1. 概述

OpenMem-MCP 通过 FastMCP 框架暴露 8 个工具，供 AI 助手通过 MCP 协议调用。所有工具均通过标准输入/输出（stdio）以 JSON-RPC 格式通信。

### 1.1 工具列表

| 工具名 | 函数 | 类别 | 说明 |
|--------|------|------|------|
| `add_memory` | `WriteEngine.add_memory()` | 写 | 添加新记忆，自动分类到最佳 Wiki 位置 |
| `update_memory` | `WriteEngine.update_memory()` | 写 | 更新现有页面（merge/append/overwrite） |
| `search_memories` | `ReadEngine.search()` | 读 | 渐进式搜索，从根目录逐层查找 |
| `get_page` | `FileStore.read_page()` | 读 | 获取指定页面的完整内容 |
| `get_directory` | `FileStore.list_directory_items()` | 读 | 浏览目录结构 |
| `create_directory` | `WriteEngine.create_directory()` | 写 | 创建新目录及其索引 |
| `run_health_check` | `HealthEngine.run_check()` | 维护 | 执行 Wiki 健康检查 |
| `export_wiki` | `FileStore.export_wiki()` | 维护 | 导出 Wiki 为 ZIP 压缩包 |

---

## 2. 工具详解

### 2.1 add_memory

添加新记忆，LLM 自动分类到最佳 Wiki 位置。

**函数签名：**
```python
def add_memory(content: str, suggested_path: str | None = None, tags: list[str] | None = None, source: str = "auto") -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | `str` | 是 | - | 要添加的记忆内容（Markdown 格式） |
| `suggested_path` | `str \| None` | 否 | `None` | 建议路径，如 `/哲学/寓言`，可包含目录或具体文件名 |
| `tags` | `list[str] \| None` | 否 | `None` | 标签列表，为空则使用 `default_tags` |
| `source` | `str` | 否 | `"auto"` | 内容来源标识 |

**行为说明：**

1. **无 `suggested_path`**：从根目录开始渐进式导航，LLM 逐层选择最匹配的子目录，直到找到合适位置创建新页面
2. **有 `suggested_path`**：
   - 路径以 `.md` 结尾：直接作为目标文件路径
     - 文件已存在：调用 `update_memory` 进行 merge 更新
     - 文件不存在：创建新页面
   - 路径为目录：在该目录下创建以日期命名的新页面

**返回：** 创建结果描述字符串，包含新页面的路径

**示例：**

```json
{
  "tool": "add_memory",
  "arguments": {
    "content": "今天学习了 Python 装饰器，装饰器是一种修改函数行为的强大工具。",
    "suggested_path": null,
    "tags": ["Python", "学习"]
  }
}
```

---

### 2.2 update_memory

更新现有页面的内容。

**函数签名：**
```python
def update_memory(path: str, content: str, mode: str = "merge") -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `str` | 是 | - | 要更新页面的完整路径 |
| `content` | `str` | 是 | - | 新内容 |
| `mode` | `str` | 否 | `"merge"` | 更新模式：`merge`/`append`/`overwrite` |

**更新模式：**

| 模式 | 行为 |
|------|------|
| `merge` | LLM 智能将新内容合并到现有内容中（默认） |
| `append` | 直接追加到现有内容末尾 |
| `overwrite` | 完全替换现有内容 |

**返回：** 更新结果描述字符串

**示例：**

```json
{
  "tool": "update_memory",
  "arguments": {
    "path": "/项目/openmem-mcp/学习笔记.md",
    "content": "新增内容：装饰器的高级用法...",
    "mode": "merge"
  }
}
```

---

### 2.3 search_memories

在 Wiki 中渐进式搜索记忆。

**函数签名：**
```python
def search_memories(query: str, max_depth: int = 7, max_results: int = 3) -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | `str` | 是 | - | 搜索查询文本 |
| `max_depth` | `int` | 否 | `7` | 最大搜索深度 |
| `max_results` | `int` | 否 | `3` | 最大返回结果数量 |

**搜索算法：**

1. 从根目录 `/` 开始读取 `目录.md`
2. LLM 选择 top-2 最匹配当前查询的条目
3. 对选中的目录递归深入，对选中的页面读取内容
4. 直到达到 `max_depth` 或收集足够结果
5. LLM 合成最终答案

**返回：** LLM 合成的答案字符串

**示例：**

```json
{
  "tool": "search_memories",
  "arguments": {
    "query": "Python 装饰器",
    "max_depth": 7,
    "max_results": 3
  }
}
```

---

### 2.4 get_page

获取指定页面的完整内容。

**函数签名：**
```python
def get_page(path: str) -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `str` | 是 | - | 页面完整路径 |

**返回：** 页面完整内容，包含 Front Matter 元数据 + Markdown 正文

**返回格式：**
```
---
title: 页面标题
path: /路径
type: page
level: 2
parent: /父路径
created_at: "2026-05-25T10:00:00"
updated_at: "2026-05-25T10:30:00"
summary: 简短描述
tags: [标签1, 标签2]
source: auto
---

# 页面正文
Markdown 内容...
```

**示例：**

```json
{
  "tool": "get_page",
  "arguments": {
    "path": "/项目/openmem-mcp/学习笔记.md"
  }
}
```

---

### 2.5 get_directory

浏览目录结构，获取目录下所有条目。

**函数签名：**
```python
def get_directory(path: str = "/") -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `str` | 否 | `"/"` | 目录路径，默认为根目录 |

**实现说明：**

- **不使用 LLM**：纯文件系统操作，直接遍历目录读取每个文件的 Front Matter
- **数据来源**：遍历文件系统 `os.scandir` / `Path.iterdir`，而非解析 `目录.md` 中的链接文本
- **读取方式**：遍历到的每个 `.md` 文件都会读取其 Front Matter 获取 `title`、`summary`、`type`

**返回：** 格式化的目录条目列表（Markdown 格式字符串）

**返回格式：**
```
# 目录: /项目

- [directory] openmem-mcp: openmem-mcp 项目文档
  路径: /项目/openmem-mcp
- [page] 学习笔记: Python 学习笔记
  路径: /项目/openmem-mcp/学习笔记.md
```

**示例：**

```json
{
  "tool": "get_directory",
  "arguments": {
    "path": "/项目"
  }
}
```

---

### 2.6 create_directory

创建新目录及其索引文件。

**函数签名：**
```python
def create_directory(path: str, title: str, summary: str) -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | `str` | 是 | - | 目录路径 |
| `title` | `str` | 是 | - | 目录标题 |
| `summary` | `str` | 是 | - | 目录描述 |

**行为说明：**

1. 验证路径层级不超过 `max_depth`
2. 验证父目录存在
3. 创建物理目录
4. 创建 `目录.md` 索引文件（包含 Front Matter）
5. 更新父目录的 `目录.md`，添加新目录条目

**返回：** 创建结果描述字符串

**示例：**

```json
{
  "tool": "create_directory",
  "arguments": {
    "path": "/哲学/寓言",
    "title": "寓言",
    "summary": "寓言故事收藏"
  }
}
```

---

### 2.7 run_health_check

执行 Wiki 健康检查，验证结构完整性。

**函数签名：**
```python
def run_health_check() -> str
```

**参数：** 无

**返回：** JSON 格式的健康检查报告

**返回格式：**
```json
{
  "total_files": 15,
  "total_directories": 5,
  "errors": [
    "/项目/orphan.md 缺少必要的 Front Matter 字段: parent"
  ],
  "warnings": [
    "/未命名.md 正文内容过短（少于20字符）"
  ],
  "suggestions": []
}
```

**检查项：**

| 级别 | 检查项 | 说明 |
|------|--------|------|
| Error | 缺少 `目录.md` | 目录下不存在索引文件 |
| Error | Front Matter 必填字段缺失 | path/type/parent/title 缺失 |
| Error | 目录层级超限 | level > max_depth |
| Warning | 正文内容过短 | content 长度 < 20 字符 |
| Warning | 摘要过长 | summary 长度 > 150 字符 |

**示例：**

```json
{
  "tool": "run_health_check",
  "arguments": {}
}
```

---

### 2.8 export_wiki

将整个 Wiki 导出为 ZIP 压缩包。

**函数签名：**
```python
def export_wiki(output_path: str = "wiki_export.zip") -> str
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `output_path` | `str` | 否 | `"wiki_export.zip"` | 输出文件路径 |

**返回：** 导出结果描述字符串，包含 ZIP 文件路径

**示例：**

```json
{
  "tool": "export_wiki",
  "arguments": {
    "output_path": "wiki_backup.zip"
  }
}
```

---

## 3. 错误处理

### 3.1 错误类型

| 错误类型 | 说明 | 处理方式 |
|----------|------|----------|
| `FileNotFoundError` | 页面或目录不存在 | 提示用户检查路径 |
| `PermissionError` | 无读写权限 | 检查文件权限 |
| `ValueError` | 参数校验失败 | 检查参数格式和范围 |
| `DepthLimitError` | 超过最大深度限制 | 减少嵌套层级 |
| `DuplicateError` | 页面/目录已存在 | 使用更新模式或更换路径 |

### 3.2 错误响应格式

所有工具在出错时返回错误描述字符串，格式如下：

```
[Error] 错误类型: 详细错误信息
```

例如：
```
[Error] FileNotFoundError: 页面不存在: /项目/openmem-mcp/不存在的页面.md
```

---

## 4. 使用示例

### 4.1 添加记忆并自动分类

```
用户: 帮我记住今天学习的 Python 装饰器知识
AI: 调用 add_memory(content="今天学习了 Python 装饰器...", suggested_path=null, tags=null)
```

### 4.2 指定路径添加记忆

```
用户: 把这个笔记添加到 /项目/Python/装饰器.md
AI: 调用 add_memory(content="装饰器学习笔记...", suggested_path="/项目/Python/装饰器.md")
```

### 4.3 搜索记忆

```
用户: 搜索关于 Python 装饰器的笔记
AI: 调用 search_memories(query="Python 装饰器", max_depth=7, max_results=3)
```

### 4.4 更新记忆

```
用户: 更新 /项目/Python/装饰器.md，补充装饰器的实际应用场景
AI: 调用 update_memory(path="/项目/Python/装饰器.md", content="补充内容...", mode="merge")
```

### 4.5 浏览目录

```
用户: 查看 /项目 目录下有什么
AI: 调用 get_directory(path="/项目")
```

### 4.6 查看页面

```
用户: 查看 /项目/Python/装饰器.md 的完整内容
AI: 调用 get_page(path="/项目/Python/装饰器.md")
```

### 4.7 创建目录

```
用户: 创建一个 /读书笔记 目录
AI: 调用 create_directory(path="/读书笔记", title="读书笔记", summary="阅读心得和笔记")
```

### 4.8 健康检查

```
用户: 检查一下我的 Wiki 是否有问题
AI: 调用 run_health_check()
```

### 4.9 导出备份

```
用户: 导出我的 Wiki 进行备份
AI: 调用 export_wiki(output_path="wiki_backup.zip")
```

---

## 5. 配置说明

### 5.1 MCP 服务配置

在 OpenCode 中配置 MCP 服务器：

```json
{
  "mcpServers": {
    "openmem": {
      "command": "python",
      "args": ["/path/to/openmem-mcp/main.py"],
      "cwd": "/path/to/openmem-mcp"
    }
  }
}
```

### 5.2 配置文件

`openmem.json` 配置项说明：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `wiki_root` | `string` | Wiki 根目录路径（相对于脚本目录或绝对路径） |
| `max_depth` | `int` | 最大目录嵌套深度（默认 7） |
| `default_tags` | `list[string]` | 新页面默认标签 |
| `llm.base_url` | `string` | LLM API 端点 |
| `llm.api_key` | `string` | API 密钥 |
| `llm.small_model` | `string` | 轻量模型名称 |
| `llm.large_model` | `string` | 重型模型名称 |
| `llm.timeout` | `int` | API 请求超时（秒） |
| `logging.level` | `string` | 日志级别 |