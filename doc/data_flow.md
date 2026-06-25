# OpenMem-MCP 数据流

## 1. 写操作数据流

### 1.1 添加记忆 (`add_memory`)

```
用户请求: 添加记忆 "今天学习了 Python 的装饰器"
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ add_memory(content="今天学习了 Python 的装饰器",           │
│            suggested_path=None, tags=None)                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Engine Layer: WriteEngine.add_memory()                    │
│                                                              │
│ Step 1: suggested_path 为空，进入 _find_best_location()     │
│                                                              │
│ Step 2: 从根目录开始渐进式导航                               │
│                                                              │
│   Level 1: 根目录 "/"                                       │
│     ├── FileStore.list_directory_items("/")                │
│     │   返回: [哲学/, 项目/, 三面镜子.md, ...]               │
│     ├── LLMClient.select_best_match()                      │
│     │   Query: "今天学习了 Python 的装饰器"                  │
│     │   Candidates: [哲学/, 项目/, 三面镜子.md, ...]        │
│     │   选择最相关的目录或页面 (top_k=2)                     │
│     └── 假设选择 "项目/"                                    │
│                                                              │
│   Level 2: "项目/"                                         │
│     ├── FileStore.list_directory_items("/项目")            │
│     │   返回: [openmem-mcp/, 其他项目/]                     │
│     ├── LLMClient.select_best_match()                      │
│     │   选择 "openmem-mcp/"                                │
│     └── 递归进入                                           │
│                                                              │
│   Level 3: "项目/openmem-mcp/"                             │
│     ├── FileStore.list_directory_items(...)                │
│     │   返回: [..., openmem-mcp 三大 Bug 修复记录.md]       │
│     ├── LLMClient.select_best_match()                      │
│     │   无合适子项 → 停止导航                               │
│     └── 在此目录下创建新页面                                │
│                                                              │
│ Step 3: 生成 Front Matter                                   │
│   title: 根据内容由 LLM 生成                               │
│   path: /项目/openmem-mcp/2026-05-25-Python装饰器学习.md   │
│   type: page                                               │
│   level: 3                                                │
│   parent: /项目/openmem-mcp                                │
│   summary: 由 LLMClient.generate_summary() 生成            │
│   tags: [default_tags]                                    │
│   source: "auto"                                          │
│   created_at: current_timestamp                            │
│   updated_at: current_timestamp                            │
│                                                              │
│ Step 4: FileStore.create_page()                            │
│   ├── 创建物理文件                                         │
│   ├── 写入 Front Matter + content                          │
│   ├── 更新父目录 目录.md 的索引条目                         │
│   └── 返回创建结果                                         │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Service Layer                                              │
│                                                              │
│ FileStore                                                   │
│   write_file(target_path, content)                        │
│     ├── 创建 temp 文件                                     │
│     ├── 写入内容                                           │
│     ├── fsync 刷盘                                         │
│     └── 原子重命名                                         │
│                                                              │
│ LLMClient                                                   │
│   chat_completion(prompt, model=small)                    │
│     ├── 构建 messages                                      │
│     ├── 调用 OpenAI API                                    │
│     └── 返回 JSON 解析结果                                 │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Storage Layer                                              │
│                                                              │
│ Filesystem                                                  │
│   写入: /wiki_root/项目/openmem-mcp/2026-05-25-xxx.md     │
│   更新: /wiki_root/项目/openmem-mcp/目录.md               │
│                                                              │
│ LLM API                                                     │
│   HTTP POST → OpenAI 兼容 API                              │
└──────────────────────────────────────────────────────────┘
```

### 1.2 更新记忆 (`update_memory`)

```
用户请求: 更新 /项目/openmem-mcp/学习笔记.md，合并新内容
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ update_memory(path="/项目/openmem-mcp/学习笔记.md",        │
│              content="新内容...", mode="merge")           │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Engine Layer: WriteEngine.update_memory()                  │
│                                                              │
│ Step 1: FileStore.read_page() → 读取现有内容               │
│                                                              │
│ Step 2: 根据 mode 执行更新                                  │
│                                                              │
│   mode = "merge":                                         │
│     ├── LLMClient 生成合并提示词                           │
│     │   "请将新内容[xxx]智能合并到现有内容[yyy]中..."      │
│     ├── LLMClient.chat_completion(model=large)            │
│     └── 使用 LLM 返回的合并结果                            │
│                                                              │
│   mode = "append":                                        │
│     └── 直接拼接: existing_content + "\n" + new_content   │
│                                                              │
│   mode = "overwrite":                                     │
│     └── 直接替换为 new_content                             │
│                                                              │
│ Step 3: FileStore.update_page()                            │
│   ├── 保留原有 Front Matter                                │
│   ├── 更新 content 和 updated_at                          │
│   └── 写回文件                                             │
└──────────────────────────┬───────────────────────────────┘
```

---

## 2. 读操作数据流

### 2.1 搜索记忆 (`search_memories`)

```
用户请求: 搜索 "Python 装饰器"
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ search_memories(query="Python 装饰器", max_depth=7,       │
│                 max_results=3)                            │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Engine Layer: ReadEngine.search()                          │
│                                                              │
│ Step 1: 初始化结果列表                                      │
│   results = []                                            │
│   current_path = "/"                                      │
│   level = 1                                               │
│                                                              │
│ Step 2: 递归搜索 (Depth-First with LLM guidance)          │
│                                                              │
│   _search_recursive(query, current_path, results, ...)    │
│                                                              │
│   ├── FileStore.list_directory_items("/")                 │
│   │   读取根目录 目录.md                                   │
│   │   返回条目: [哲学/, 项目/, 三面镜子.md, ...]           │
│   │                                                          │
│   ├── LLMClient.select_best_match(query, candidates)      │
│   │   让 LLM 决定哪些条目与 "Python 装饰器" 相关            │
│   │   选择 top_k=2 最相关的条目                            │
│   │                                                          │
│   ├── 对每个选中条目:                                      │
│   │                                                          │
│   │   如果是目录:                                          │
│   │     ├── 检查 level < max_depth                        │
│   │     ├── 递归调用 _search_recursive()                   │
│   │     └── 继续深入下一层                                 │
│   │                                                          │
│   │   如果是页面:                                          │
│   │     ├── FileStore.read_page()                          │
│   │     └── results.append(page_content)                  │
│   │                                                          │
│   └── 重复直到:                                            │
│       - 遍历完所有层级，或                                 │
│       - results 达到 max_results                          │
│                                                              │
│ Step 3: 合成最终答案                                       │
│   LLMClient.chat_completion(                              │
│     messages=[                                            │
│       {"role": "system", "content": "你是一个百科助手..."},│
│       {"role": "user", "content": "根据以下搜索结果..."}   │
│     ],                                                     │
│     model=large                                           │
│   )                                                        │
│                                                              │
│ 返回: LLM 合成的答案字符串                                 │
└──────────────────────────┬───────────────────────────────┘
```

### 2.2 获取页面 (`get_page`)

```
用户请求: 获取 /项目/openmem-mcp/学习笔记.md
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ get_page(path="/项目/openmem-mcp/学习笔记.md")             │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Service Layer: FileStore.read_page()                      │
│                                                              │
│ Step 1: 路径解析                                           │
│   ├── 转换为绝对路径                                       │
│   └── 校验 wiki_root 范围内                               │
│                                                              │
│ Step 2: 读取文件                                           │
│   ├── open(path, "r", encoding="utf-8")                   │
│   └── frontmatter.parse() 分离 Front Matter 和正文         │
│                                                              │
│ 返回: frontmatter.Post 对象                                │
│   ├── .metadata: {title, path, type, level, ...}         │
│   └── .content: Markdown 正文内容                         │
└──────────────────────────────────────────────────────────┘
```

### 2.3 获取目录 (`get_directory`)

```
用户请求: 浏览 /项目 目录
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ get_directory(path="/项目")                                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Service Layer: FileStore.list_directory_items()           │
│                                                              │
│ Step 1: 读取目录 目录.md（验证目录存在）                     │
│   └── FileStore.read_directory("/项目")                    │
│                                                              │
│ Step 2: 直接遍历文件系统目录                                │
│   abs_dir_path = self.wiki_root / "项目"                   │
│   for item in abs_dir_path.iterdir():                      │
│     ├── 跳过: 目录.md、隐藏文件(.开头)                      │
│     │                                                       │
│     ├── 子目录:                                            │
│     │   ├── 读取 子目录/目录.md 的 Front Matter            │
│     │   └── 提取 title, path, summary, type="directory"    │
│     │                                                       │
│     └── .md 文件:                                          │
│         ├── 读取文件的 Front Matter                         │
│         └── 提取 title, path, summary, type="page"         │
│                                                              │
│ 返回: 格式化的 Markdown 字符串                              │
│   # 目录: /项目                                             │
│   - [directory] openmem-mcp: 描述                           │
│     路径: /项目/openmem-mcp                                 │
│   - [page] 笔记.md: 描述                                    │
│     路径: /项目/笔记.md                                     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 目录创建数据流

### 3.1 创建目录 (`create_directory`)

```
用户请求: 创建 /哲学/寓言 目录
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ create_directory(path="/哲学/寓言", title="寓言",         │
│                  summary="寓言故事收藏")                  │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Engine Layer: WriteEngine.create_directory()               │
│                                                              │
│ Step 1: 验证路径合法性                                     │
│   ├── 确保不超过 max_depth                                │
│   ├── 确保父目录 /哲学 存在                                │
│   └── 确保目录 /哲学/寓言 不存在                          │
│                                                              │
│ Step 2: 创建物理目录                                       │
│   └── os.makedirs(wiki_root + "/哲学/寓言")               │
│                                                              │
│ Step 3: 生成目录索引文件                                   │
│   Front Matter:                                           │
│     title: 寓言                                            │
│     path: /哲学/寓言                                       │
│     type: directory                                       │
│     level: 2                                              │
│     parent: /哲学                                          │
│     summary: 寓言故事收藏                                  │
│     created_at: current_timestamp                          │
│     updated_at: current_timestamp                          │
│                                                              │
│   Content:                                                │
│     # 寓言                                                 │
│     （空内容）                                             │
│                                                              │
│ Step 4: 写入门户.md 文件                                   │
│                                                              │
│ Step 5: 更新父目录索引                                     │
│   FileStore._update_directory_index()                      │
│   └── 在 /哲学/目录.md 中添加条目                          │
│                                                              │
│ 返回: 创建成功信息                                         │
└──────────────────────────────────────────────────────────┘
```

---

## 4. 健康检查数据流

### 4.1 运行健康检查 (`run_health_check`)

```
用户请求: 执行健康检查
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ run_health_check()                                        │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Engine Layer: HealthEngine.run_check()                     │
│                                                              │
│ Step 1: 初始化报告结构                                     │
│   {                                                       │
│     total_files: 0,                                      │
│     total_directories: 0,                                │
│     errors: [],                                          │
│     warnings: [],                                        │
│     suggestions: []                                      │
│   }                                                       │
│                                                              │
│ Step 2: 递归遍历 wiki_root                                │
│                                                              │
│   for each item in wiki_root:                             │
│     ├── 如果是文件 (.md):                                 │
│     │   ├── 读取 frontmatter                              │
│     │   ├── 检查必填字段存在                              │
│     │   ├── 检查 level <= max_depth                      │
│     │   ├── 检查 summary 长度 <= 150                     │
│     │   └── 检查 content 长度 >= 20                      │
│     │                                                       │
│     └── 如果是目录:                                       │
│         ├── 检查是否存在 目录.md                          │
│         ├── 递归进入子目录                                │
│         └── 计数 +1                                       │
│                                                              │
│ Step 3: 返回完整报告                                       │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Wiki 导出数据流

### 5.1 导出 Wiki (`export_wiki`)

```
用户请求: 导出 Wiki 到 wiki_export.zip
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Tool Layer: main.py                                       │
│ export_wiki(output_path="wiki_export.zip")                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Service Layer: FileStore.export_wiki()                    │
│                                                              │
│ Step 1: 创建 ZIP 文件                                      │
│   zipfile.ZipFile(output_path, "w", ZIP_DEFLATED)         │
│                                                              │
│ Step 2: 递归添加所有文件                                   │
│   for root, dirs, files in os.walk(wiki_root):            │
│     for file in files:                                    │
│       ├── 计算相对路径                                     │
│       └── zipfile.write(full_path, relative_path)         │
│                                                              │
│ Step 3: 关闭 ZIP                                          │
│                                                              │
│ 返回: ZIP 文件路径                                         │
└──────────────────────────────────────────────────────────┘
```

---

## 6. 关键设计模式

### 6.1 渐进式加载 (Progressive Loading)

```
搜索从根目录开始，逐层深入
每次只读取当前目录的 目录.md
每层由 LLM 决定下一个进入哪个子目录
避免全量扫描大型 Wiki
```

### 6.2 双模型策略 (Dual Model Tier)

```
Small Model (gpt-4o-mini):
  └── 轻量任务：分类、匹配、摘要生成

Large Model (gpt-4o):
  └── 重度任务：内容合并、答案合成、复杂推理
```

### 6.3 原子写入 (Atomic Write)

```
写入流程:
  1. 创建 temp 文件 (xxx.md.tmp)
  2. 写入完整内容
  3. os.fsync() 确保刷盘
  4. os.rename() 原子替换原文件

防止:
  - 写入中断导致文件损坏
  - 读取到半写状态的文件
```

### 6.4 索引维护 (Index Maintenance)

```
每次创建/删除文件时:
  1. 更新直接父目录的 目录.md
  2. 追加 [[path|title]] 格式链接

保证:
  - 目录索引始终反映实际内容
  - Obsidian 可正确显示双向链接
```