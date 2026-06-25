# OpenMem - 个人 Wiki 记忆 MCP 工具

纯 LLM 驱动的个人知识库管理系统，通过 MCP（Model Context Protocol）协议为 AI 助手提供记忆存储和检索能力。

## 功能特性

- **自动分类**：通过 LLM 智能分析内容，自动归类到最合适的目录位置
- **渐进式搜索**：从根目录开始逐层搜索，快速定位相关记忆
- **Front Matter 管理**：自动维护 Markdown 文件的元数据
- **Obsidian 集成**：可直接用 Obsidian 打开和编辑所有记忆文件
- **健康检查**：定期检查 Wiki 结构完整性，修复损坏的链接和缺失的元数据
- **导出备份**：一键导出整个知识库为 ZIP 文件

## 安装

```bash
pip install openmem-mcp
```

或开发模式：

```bash
cd openmem-mcp
pip install -e .
```

## 配置

### 1. 首次运行

直接运行 `python -m openmem`，程序会自动复制配置模板到 `~/.config/openmem/openmem.json`。

```bash
python -m openmem
# 输出：已复制配置文件模板到: ~/.config/openmem/openmem.json
# 请编辑该文件，填入您的 LLM API 密钥后再运行。
```

### 2. 编辑配置文件

编辑 `~/.config/openmem/openmem.json`，填入您的 LLM API 密钥：

```json
{
  "wiki_root": "./wiki",
  "max_depth": 7,
  "default_tags": [],
  "llm": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "your-api-key-here",
    "small_model": "gpt-4o-mini",
    "large_model": "gpt-4o",
    "timeout": 30
  },
  "logging": {
    "level": "INFO"
  }
}
```

### 3. 配置方式优先级

1. 环境变量 `OPENMEM_CONFIG` 指定的路径
2. `~/.config/openmem/openmem.json`（默认）

## 运行

```bash
python -m openmem
```

## OpenCode 集成配置

1. 打开 OpenCode
2. 点击左下角的设置图标
3. 选择 **MCP 服务器**
4. 点击 **添加服务器**
5. 选择 **命令行** 类型
6. 填写以下配置：
   - **名称**：Personal Wiki Memory
   - **命令**：python
   - **参数**：`-m openmem`
   - **工作目录**：您的 openmem-mcp 目录
7. 点击 **保存**
8. 重启 OpenCode

## 使用示例

### 添加记忆

```
帮我添加一条记忆：2026年5月25日，我完成了个人Wiki MCP工具的开发。
```

### 搜索记忆

```
搜索一下关于MCP工具开发的记录
```

### 获取目录结构

```
获取根目录的结构
```

### 更新记忆

```
更新记忆"/00-个人/学习/Python学习笔记.md"，添加FastMCP的使用方法。
```

### 运行健康检查

```
运行健康检查
```

## Obsidian 集成

1. 打开 Obsidian
2. 选择 **打开文件夹作为库**
3. 选择您的 `wiki_root` 目录（默认是 `./wiki`）
4. 现在您可以在 Obsidian 中直接查看和编辑所有记忆文件

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `add_memory` | 添加新记忆，自动分类到最合适的 Wiki 位置 |
| `update_memory` | 更新指定路径的 Wiki 页面 |
| `search_memories` | 搜索记忆，从根目录开始渐进式查找 |
| `get_page` | 获取指定路径的完整页面内容 |
| `get_directory` | 获取指定目录的结构和内容列表 |
| `create_directory` | 创建新目录和对应的目录.md |
| `run_health_check` | 运行完整的 Wiki 健康检查 |
| `export_wiki` | 导出整个 Wiki 为 ZIP 文件 |

## 项目结构

```
openmem-mcp/
├── openmem/
│   ├── __init__.py       # 包入口
│   ├── __main__.py       # python -m openmem 入口
│   ├── config.py         # 配置文件管理
│   ├── file_store.py     # 文件系统操作层
│   ├── llm_client.py     # OpenAI 兼容 LLM 客户端
│   ├── write_engine.py   # 写入引擎（渐进式匹配+编辑）
│   ├── read_engine.py    # 读取引擎（渐进式搜索）
│   ├── health_engine.py  # 健康检查引擎
│   └── main.py           # MCP 服务主入口
├── tests/                # 测试目录
├── pyproject.toml        # 包构建配置
├── openmem.json.example  # 配置文件模板
└── README.md
```

## 注意事项

- 所有操作都通过 MCP 工具进行，不要手动修改 Front Matter 中的元数据
- 目录深度最多 7 层，超过会被拒绝
- 建议定期运行健康检查，确保 Wiki 结构完整
- 可以使用 Git 备份整个 `wiki_root` 目录
- 如果使用本地 LLM，请确保 `base_url` 和模型名称正确
