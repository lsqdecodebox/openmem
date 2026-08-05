# OpenMem 双系统技术架构

> 本文档定义 openmem(MCP 记忆引擎)与 openmem-web(Web 前端系统)的边界、职责、复用方式与权限模型。

---

## 一、设计动机

OpenMem v2.2.1 的核心价值是"纯文件系统、零外部依赖、Obsidian 原生兼容"。若将 Web 前端、用户管理、opencode 对话等能力直接揉入 openmem,会破坏其极简设计原则。因此拆分为两个独立系统,各自演进、协议级解耦。

拆分合理性对照:

| 维度 | openmem (MCP服务) | openmem-web (Web系统) |
|------|------|------|
| 服务对象 | LLM 客户端(Claude/OpenCode) | 人类用户(浏览器) |
| 协议 | MCP(stdio / streamable-http) | HTTP + WebSocket |
| 核心职责 | 记忆读写引擎 | 知识浏览/编辑/对话/用户管理 |
| 依赖约束 | 极简无依赖(设计核心) | 可引入 FastAPI/前端框架 |
| 部署形态 | 后台服务 | Web 服务 + 静态资源 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│  浏览器 (人类用户)                                    │
│  ┌──────────────────────────────────────────────┐   │
│  │  openmem-web 前端 (index.html 演进)          │   │
│  │  - 知识树 / 知识图谱 / 编辑 / 对话 / 权限     │   │
│  └────────────────┬─────────────────────────────┘   │
└───────────────────┼─────────────────────────────────┘
                    │ HTTP / WebSocket
                    │ (Web 层用户登录态: JWT)
                    ▼
┌─────────────────────────────────────────────────────┐
│  openmem-web 后端 (FastAPI)                          │
│  - 登录 / 用户管理 / 对话编排 / 图谱聚合             │
│  - 持有"系统级 API Key"代表服务身份调用 MCP          │
│  - Web 用户权限二次校验(独立于 MCP 权限)             │
└────────────────┬────────────────────────────────────┘
                 │ MCP streamable-http
                 │ (Bearer 系统级 API Key)
                 ▼
┌─────────────────────────────────────────────────────┐
│  openmem (现有,增强权限层)                            │
│  - FastMCP + 5 工具 + core_principles prompt         │
│  - 权限认证中间件(API Key → 角色)                    │
│  - users.json (API Key 映射表,本地存储,定期同步NAS)  │
│  - 本地文件系统 wiki_root                            │
└─────────────────────────────────────────────────────┘
```

---

## 三、系统边界与职责

### 3.1 openmem(MCP 记忆引擎)

**保留现有能力**:
- 5 个 MCP 工具:`get_directory` / `read_memory` / `write_memory` / `write_asset` / `read_asset`
- 1 个 prompt:`core_principles`
- 快照机制、路径校验、压缩披露、corepage 初始化

**新增能力(需求1)**:
- API Key 认证中间件
- 用户密钥映射表 `users.json`(本地存储)
- 工具级权限校验:普通/无权限用户仅能调用 `get_directory` / `read_asset` / `read_memory`;管理员可调用 `write_memory` / `write_asset`
- NAS 同步脚本(独立 shell,不进主进程)

### 3.2 openmem-web(Web 系统)

**五大功能模块(需求2)**:

| 模块 | 后端能力 | 前端 Tab |
|------|---------|---------|
| a) 知识树 | 调用 MCP `get_directory` 聚合 + 渐进式披露 | 知识树 |
| b) 知识图谱 | 扫描 wiki_root 提取 `[[wikilink]]` 双链 + 目录父子结构,聚合成图数据 | 知识图谱 |
| c) opencode 对话 | 子进程管理 opencode CLI,stdout 流式转发到前端(SSE/WebSocket) | 对话编辑 |
| d) 用户权限管理 | CRUD 用户、角色分配、注册审核 | 权限管控 |
| e) 用户登录 | 用户名+密码登录,签发 JWT,前端 localStorage 存储 | 登录页 |

**前端形态**:由现有 `index.html` 演进,拆分为 `index.html + js/*.js + css/*.css`,仍走 CDN(Tailwind/ECharts),不引入构建工具。

---

## 四、系统间复用方式(已确认:方案 A 松耦合)

**决策**:openmem-web 通过 MCP streamable-http 协议级调用 openmem,不直接 import openmem 代码。

### 4.1 调用链路

```
Web前端 → openmem-web后端 → MCP HTTP请求(Bearer 系统级APIKey) → openmem
```

### 4.2 系统级 API Key

- openmem-web 启动时从配置读取一个 `OPENMEM_API_KEY`(admin 角色)
- 所有对 openmem 的 MCP 调用均携带此 Key
- openmem 层只识别"这是 openmem-web 服务身份",不感知具体 Web 用户

### 4.3 为什么不直接 import WikiStore(方案 B)

| 关注点 | 方案A(MCP协议) | 方案B(代码import) |
|--------|---------------|-------------------|
| 解耦度 | 协议级,可独立部署/升级 | 代码级,版本强绑定 |
| 并发安全 | 单进程(openmem)管理文件锁 | 两进程共享文件系统需自处理 |
| 权限复用 | 完整复用 openmem 权限/快照/校验 | 需在 Web 层重新实现 |
| 部署灵活 | openmem 可放服务器,Web 放另一台 | 必须同机 |
| 性能 | 多一跳 HTTP | 直调函数 |

方案 A 性能略低但解耦与安全更优,且 MCP streamable-http 已是 openmem v2 原生能力,无需改造协议层。

---

## 五、权限模型(已确认:两层独立)

### 5.1 两层权限的职责划分

```
┌──────────────────────────────────────────────┐
│  Web 层权限 (openmem-web 自管)                │
│  - 对象:人类用户 (admin/internal/guest)       │
│  - 存储:Web 后端 users 表 (数据库或文件)      │
│  - 校验:JWT 解析 → 用户角色 → 路由级权限      │
│  - 粒度:页面可见性、编辑按钮显隐、对话发起权   │
└────────────────┬─────────────────────────────┘
                 │ Web 后端统一以"系统级 API Key"
                 │ 调用 openmem MCP
                 ▼
┌──────────────────────────────────────────────┐
│  MCP 层权限 (openmem 自管)                    │
│  - 对象:客户端/服务 (openmem-web、Claude等)  │
│  - 存储:users.json (API Key 映射表)          │
│  - 校验:HTTP Bearer → API Key → 角色         │
│  - 粒度:工具级 (read类 vs write类)           │
└──────────────────────────────────────────────┘
```

### 5.2 角色与权限矩阵

**MCP 层(openmem)**:

| 角色 | get_directory | read_memory | read_asset | write_memory | write_asset |
|------|:---:|:---:|:---:|:---:|:---:|
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| user | ✓ | ✓ | ✓ | ✗ | ✗ |
| (未认证) | ✗ | ✗ | ✗ | ✗ | ✗ |

> stdio 本地模式默认 admin(本机信任,无需 Key)

**Web 层(openmem-web)**:

| 角色 | 浏览知识树 | 知识图谱 | 编辑页面 | opencode对话 | 用户管理 |
|------|:---:|:---:|:---:|:---:|:---:|
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| internal | ✓ | ✓ | ✓ | ✓ | ✗ |
| guest | ✓ | ✓ | ✗ | ✗ | ✗ |

### 5.3 首次部署 admin 创建流程

1. openmem 首次启动时,若 `users.json` 不存在:
   - 从环境变量 `OPENMEM_ADMIN_API_KEY` 读取,创建默认 admin
   - 无环境变量则在控制台打印一次性随机 API Key
2. openmem-web 首次启动时,若用户表为空:
   - 从环境变量 `OPENMEM_WEB_ADMIN_PASSWORD` 读取,创建默认 Web admin
   - 无环境变量则在控制台打印一次性随机密码

---

## 六、系统命名与位置(已确认)

### 6.1 命名

- **MCP 服务**:`openmem`(保持不变)
- **Web 系统**:`openmem-web`

### 6.2 仓库位置

两个仓库平级,各自独立:

```
E:\users\LinSQ06.CATLBATTERY\Documents\lingodeCodeBox\
├── openmem/              ← 现有,增强权限层
│   ├── openmem/
│   ├── doc/
│   │   └── architecture_v3.md   ← 本文档
│   ├── tests/
│   └── pyproject.toml
└── openmem-web/          ← 新建仓库
    ├── backend/          ← FastAPI 后端
    ├── frontend/         ← 前端静态资源(index.html 演进)
    ├── docs/
    └── pyproject.toml
```

### 6.3 部署形态

- **单机部署**(默认):openmem 与 openmem-web 同机,通过 `127.0.0.1:6000` 通信
- **分布式部署**(可选):openmem 部署在 NAS 或服务器,openmem-web 部署在 Web 节点,通过内网通信

---

## 七、openmem 权限增强需求(需求1 细化)

> **已实施 (v2.3.0)**：基于 FastMCP 原生 `auth=TokenVerifier` 实现，无 anonymous 角色（无 Key 协议层 401）。NAS 同步采用方案 a（纯外部脚本）。以下为原始设计，实际落地见 `openmem/auth.py` 与 `scripts/sync_to_nas.{sh,ps1}`。

### 7.1 配置扩展

`openmem.json` 新增字段:

```json
{
  "auth": {
    "enabled": true,
    "users_file": "~/.openmem/users.json",
    "stdio_default_role": "admin",
    "nas_sync": {
      "enabled": false,
      "script_path": "./scripts/sync_to_nas.sh",
      "schedule": "0 2 * * *"
    }
  }
}
```

### 7.2 users.json 格式

```json
{
  "users": [
    {
      "api_key": "om_xxxxxxxx",
      "username": "openmem-web",
      "role": "admin",
      "status": "active",
      "created_at": "2026-08-05T10:00:00",
      "note": "openmem-web 服务身份"
    },
    {
      "api_key": "om_user_yyyyyyyy",
      "username": "claude-desktop",
      "role": "user",
      "status": "active",
      "created_at": "2026-08-05T10:00:00",
      "note": "Claude Desktop 客户端"
    }
  ]
}
```

### 7.3 认证流程伪代码

```
FUNCTION authenticate(request) -> role:
  IF transport == "stdio":
    RETURN config.auth.stdio_default_role   # 本机默认 admin

  api_key = request.headers.get("Authorization")  # Bearer xxx
  IF NOT api_key:
    RAISE Unauthorized

  user = users_json.find(api_key=api_key)
  IF NOT user OR user.status != "active":
    RAISE Unauthorized

  RETURN user.role

FUNCTION check_permission(tool_name, role):
  IF role == "admin": RETURN True
  IF role == "user" AND tool_name IN {get_directory, read_memory, read_asset}:
    RETURN True
  RETURN False
```

### 7.4 NAS 同步

- 独立 shell 脚本 `scripts/sync_to_nas.sh`,使用 rsync
- 由系统定时任务调用(Windows Task / cron),不进 openmem 主进程
- 同步内容:`users.json` + `wiki_root/`(可选)

---

## 八、openmem-web 功能模块设计

### 8.1 后端模块清单

```
openmem-web/backend/
├── main.py                  # FastAPI 入口
├── config.py                # 配置加载
├── auth/
│   ├── jwt.py               # JWT 签发/校验
│   ├── password.py          # bcrypt 哈希
│   └── dependency.py        # FastAPI 依赖注入:当前用户
├── models/
│   ├── user.py              # 用户模型
│   └── session.py           # 对话会话模型
├── routers/
│   ├── auth.py              # /api/auth/login, /logout
│   ├── users.py             # /api/users CRUD(管理员)
│   ├── wiki.py              # /api/wiki/tree, /page, /save
│   ├── graph.py             # /api/graph/nodes, /edges
│   └── dialogue.py          # /api/dialogue (SSE 流式)
├── services/
│   ├── mcp_client.py        # 封装对 openmem 的 MCP 调用
│   ├── graph_builder.py     # 扫描 wiki 提取双链与目录结构
│   └── opencode_runner.py   # opencode 子进程管理 + stdout 流转发
└── storage/
    └── users.json 或 sqlite # Web 用户存储
```

### 8.2 前端结构

```
openmem-web/frontend/
├── index.html               # 入口(由原 index.html 演进)
├── css/
│   └── main.css
├── js/
│   ├── api.js               # 后端 API 封装
│   ├── auth.js              # 登录态管理
│   ├── tree.js              # 知识树组件
│   ├── graph.js             # ECharts 知识图谱
│   ├── editor.js            # Markdown 编辑器
│   ├── dialogue.js          # 对话组件(SSE 接收)
│   └── admin.js             # 用户管理界面
└── login.html               # 独立登录页
```

### 8.3 关键接口契约

| 方法 | 路径 | 权限 | 说明 |
|------|------|:---:|------|
| POST | `/api/auth/login` | 公开 | 用户名密码登录,返回 JWT |
| GET | `/api/wiki/tree` | 已登录 | 调 MCP `get_directory`,返回树 JSON |
| GET | `/api/wiki/page?path=xxx` | 已登录 | 调 MCP `read_memory` |
| POST | `/api/wiki/page` | internal+ | 调 MCP `write_memory` |
| GET | `/api/graph` | 已登录 | 返回 `{nodes, edges}` 图数据 |
| POST | `/api/dialogue` | internal+ | SSE 流,转发 opencode 输出 |
| GET | `/api/users` | admin | 用户列表 |
| POST | `/api/users` | admin | 新建用户 |
| PUT | `/api/users/{id}` | admin | 编辑用户/重置密码 |

### 8.4 opencode 集成方式

- 后端 `opencode_runner.py` 以子进程启动 opencode CLI
- 捕获 stdout,通过 SSE(Server-Sent Events)推流到前端
- 前端 `EventSource` 接收,逐字渲染
- 会话历史存 Web 后端(不入 wiki,避免污染记忆)

---

## 九、版本演进路径

| 阶段 | openmem | openmem-web |
|------|---------|-------------|
| 当前 | v2.2.1(5工具+快照+压缩) | -(仅 index.html demo) |
| v3.0 | + API Key 认证 + users.json + NAS同步脚本 | 骨架搭建 + 登录 + 知识树 |
| v3.1 | - | + 编辑 + 知识图谱 |
| v3.2 | - | + opencode 对话 |
| v3.3 | - | + 用户管理界面完善 |

---

## 十、待确认事项

- Q4(实施顺序):暂忽略,后续单独规划
- opencode 在目标环境的形态(CLI 工具 / 常驻服务):实施 v3.2 时确认
- Web 用户存储介质(JSON 文件 / SQLite):实施 v3.0 时确认
