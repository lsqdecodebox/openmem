# 前端系统架构方案

## 一、技术栈选型

| 类别          | 技术选型                       | 选型理由                        |
| ----------- | -------------------------- | --------------------------- |
| 核心框架        | React 18 + TypeScript      | 类型安全，生态成熟，组件化开发效率高          |
| 构建工具        | Vite 5                     | 冷启动快，HMR 响应及时，开发体验好         |
| UI 组件库      | Ant Design 5               | 组件齐全，Tree、Table、Modal 等开箱即用 |
| 路由管理        | React Router v6            | 声明式路由，支持嵌套路由与权限守卫           |
| 状态管理        | Zustand                    | 轻量无样板代码，支持持久化，适合中小规模系统      |
| Markdown 编辑 | @uiw/react-md-editor       | 双栏编辑预览，支持工具栏，轻量易集成          |
| 知识图谱        | react-force-graph          | 基于 Three.js，力导向布局，支持节点交互    |
| HTTP 请求     | Axios                      | 拦截器统一处理鉴权、错误、Loading        |
| 样式方案        | Tailwind CSS + CSS Modules | 原子化快速布局，组件内样式隔离             |
| 代码规范        | ESLint + Prettier + Husky  | 统一代码风格，提交前自动校验              |

---

## 二、整体目录结构

```
src/
├── assets/ # 静态资源（图标、全局样式）
├── components/ # 全局公共组件
│ ├── Layout/ # 整体布局组件
│ │ ├── SideTabBar # 左侧标签栏
│ │ └── MainContent # 右侧主内容容器
│ ├── FileTree/ # 通用文件树组件（复用）
│ └── AuthGuard/ # 权限路由守卫
├── pages/ # 页面模块
│ ├── KnowledgeTree/ # 知识树页面
│ ├── KnowledgeGraph/ # 知识图谱页面
│ ├── KnowledgeEdit/ # 知识编辑页面
│ ├── DialogueEdit/ # 对话编辑页面
│ └── Permission/ # 权限管控页面
├── store/ # Zustand 状态管理
│ ├── useAuthStore # 用户/权限状态
│ ├── useFileStore # 文件数据状态
│ └── useUiStore # UI 交互状态
├── api/ # 接口请求封装
│ ├── request.ts # Axios 实例与拦截器
│ ├── auth.ts # 登录/注册/权限接口
│ ├── file.ts # 文件/文件夹接口
│ └── dialogue.ts # 对话编辑接口
├── types/ # TypeScript 类型定义
├── utils/ # 工具函数（权限判断、格式化等）
├── hooks/ # 自定义 Hooks
├── router/ # 路由配置
└── App.tsx / main.tsx # 入口文件
```

---

## 三、页面布局架构

### 3.1 整体布局结构

采用**左侧垂直标签栏 + 右侧主内容区**的经典左右分栏布局：

```
┌──────────┬──────────────────────────────────┐
│ 知识树 │ │
│ 知识图谱 │ 主内容区域 │
│ 知识编辑 │ (自适应宽度) │
│ 对话编辑 │ │
│ 权限管控 │ │
└──────────┴──────────────────────────────────┘
```

**布局实现要点：**

- 左侧标签栏固定宽度 `80px`，垂直排列 5 个 Tab 项，带图标+文字
- 右侧主内容区 `flex: 1`，占满剩余空间，内部可滚动
- 使用 `Layout` 组件统一包裹所有页面，避免重复代码
- 顶部可选增加用户信息栏（头像、昵称、修改密码入口）
  
  ### 3.2 左侧标签栏（SideTabBar）
  
  ```tsx
  // 核心配置
  const tabItems = [
  { key: 'tree', label: '知识树', icon: <TreeOutlined />, path: '/tree' },
  { key: 'graph', label: '知识图谱', icon: <NodeIndexOutlined />, path: '/graph' },
  { key: 'edit', label: '知识编辑', icon: <EditOutlined />, path: '/edit' },
  { key: 'dialogue', label: '对话编辑', icon: <MessageOutlined />, path: '/dialogue' },
  { key: 'permission', label: '权限管控', icon: <LockOutlined />, path: '/permission', role: 'admin' },
  ]
  ```
- 权限管控 Tab 仅管理员可见，通过 `role` 字段控制渲染
- 当前选中项高亮，点击切换路由
- 支持 Tooltip 提示完整名称

---

## 四、各模块详细设计

### 4.1 知识树页面

**布局：左右分栏**

- 左侧：可折叠文件树（Ant Design Tree 组件）
- 右侧：选中文件的详情信息面板
  **核心功能：**
1. **文件树**
   - 支持文件夹展开/折叠（`Tree` 组件原生支持）
   - 节点区分文件夹图标与文件图标
   - 支持懒加载子节点（大数据量场景）
   - 点击节点切换右侧详情
2. **文件详情**
   - 文件名、创建时间、更新时间、大小
   - 文件内容摘要（前 N 行预览）
   - 关联文件列表（反向链接）
     **数据结构：**
     
     ```typescript
     interface TreeNode {
     id: string;
     name: string;
     type: 'folder' | 'file';
     children?: TreeNode[];
     parentId: string | null;
     createdAt: string;
     updatedAt: string;
     }
     ```
     
     ### 4.2 知识图谱页面
     
     **布局：全屏图谱 + 右侧信息抽屉**
     **核心功能：**
3. **图谱渲染**（react-force-graph）
   - 节点：文件 = 圆形节点，文件夹 = 方形节点
   - 连线：文件间的引用关系 / 所属文件夹关系
   - 力导向布局，支持拖拽、缩放、悬停高亮
   - 点击节点高亮关联节点与连线
4. **交互能力**
   - 双击节点跳转至对应文件详情
   - 搜索框按文件名定位节点并居中
   - 图例说明节点类型与连线含义
5. **数据来源**
   - 后端返回文件关联关系数组：`{ source, target, relation }`
   - 前端转换为图谱所需的 `nodes` + `links` 格式
     **参考 Obsidian 特性：**
- 节点大小对应文件被引用次数
- 不同颜色区分文件夹层级 / 文件标签
- 悬停显示文件标题与简要信息
  
  ### 4.3 知识编辑页面
  
  **布局：左侧文件树 + 右侧 Markdown 编辑器**
  **核心功能：**
1. **左侧文件树**（复用 `FileTree` 组件）
   - 右键菜单：新建文件、新建文件夹、重命名、删除
   - 支持拖拽调整文件位置
2. **右侧编辑器**（@uiw/react-md-editor）
   - 双栏模式：左侧编辑、右侧实时预览
   - 工具栏：标题、加粗、列表、链接、图片、代码块
   - 自动保存（防抖 2s）+ 手动保存按钮
   - 编辑状态提示（未保存 · 已保存）
3. **文件头部**
   - 文件名可编辑
   - 最后保存时间显示
     
     ### 4.4 对话编辑页面
     
     **布局：对话列表 + 对话内容区 + OpenCode 调用区**
     **核心功能：**
4. **左侧对话历史列表**
   - 新建对话、删除对话、重命名对话
   - 按时间倒序排列
5. **右侧对话主区域**
   - 消息气泡展示（用户 / 系统角色）
   - 输入框支持多行文本
   - 代码块高亮渲染
6. **OpenCode 系统集成**
   - 通过封装后的 API 接口调用
   - 支持传入当前编辑的文件内容作为上下文
   - 流式响应（SSE）逐字渲染回复
   - 代码结果支持一键复制、插入到编辑器
     **调用封装示例：**
     
     ```typescript
     // api/dialogue.ts
     export const sendMessage = (params: {
     conversationId: string;
     content: string;
     fileContext?: string;
     }) => {
     return request.post('/opencode/chat', params, {
     responseType: 'stream',
     });
     };
     ```
     
     ### 4.5 权限管控页面
     
     **布局：Tab 切换（用户管理 / 注册审核 / 修改密码）**
     **核心功能与权限划分：**
     
     | 功能          | 管理员 | 内部用户 | 外部用户(未注册) |
     | ----------- | --- | ---- | --------- |
     | 查看用户列表      | ✅   | ❌    | ❌         |
     | 修改用户角色      | ✅   | ❌    | ❌         |
     | 重置用户密码      | ✅   | ❌    | ❌         |
     | 注册审核（通过/拒绝） | ✅   | ❌    | ❌         |
     | 修改自己密码      | ✅   | ✅    | ❌         |
     | 查看知识树       | ✅   | ✅    | ✅         |
     | 查看知识图谱      | ✅   | ✅    | ✅         |
     | 知识编辑        | ✅   | ✅    | ❌         |
     | 对话编辑        | ✅   | ✅    | ❌         |
     | 权限管控入口      | ✅   | ❌    | ❌         |
     | **页面组成：**   |     |      |           |
- **用户管理**：Table 展示用户列表，操作列含角色切换、禁用、重置密码
- **注册审核**：待审核用户列表，通过/拒绝操作
- **修改密码**：所有登录用户可见，仅修改自身密码

---

## 五、路由与权限控制

### 5.1 路由配置

```typescript
// router/index.tsx
const routes = [
 { path: '/', element: <Navigate to="/tree" replace /> },
 {
 path: '/',
 element: <MainLayout />, // 包含左侧标签栏的布局
 children: [
 { path: 'tree', element: <KnowledgeTree /> },
 { path: 'graph', element: <KnowledgeGraph /> },
 { path: 'edit', element: <KnowledgeEdit />, meta: { requiresAuth: true } },
 { path: 'dialogue', element: <DialogueEdit />, meta: { requiresAuth: true } },
 { path: 'permission', element: <Permission />, meta: { requiresAuth: true, role: 'admin' } },
 ],
 },
 { path: '/login', element: <Login /> },
 { path: '/register', element: <Register /> },
 { path: '*', element: <NotFound /> },
];
```

### 5.2 权限守卫实现

使用高阶组件 `AuthGuard` 包裹需要鉴权的路由：

```typescript
const AuthGuard = ({ children, requiredRole }) => {
 const { user, isLoggedIn } = useAuthStore();

if (!isLoggedIn) {
 return <Navigate to="/login" replace />;
 }

if (requiredRole && user.role !== requiredRole) {
 message.error('无权限访问');
 return <Navigate to="/tree" replace />;
 }

return children;
};
```

### 5.3 未登录用户处理

- 知识树、知识图谱页面公开访问，无需登录
- 点击"知识编辑"、"对话编辑"时弹出登录提示或跳转登录页
- 左侧标签栏中，无权限项可置灰或隐藏（建议隐藏，保持界面简洁）

---

## 六、状态管理设计

### 6.1 认证状态（useAuthStore）

```typescript
interface AuthState {
 user: UserInfo | null;
 token: string | null;
 isLoggedIn: boolean;
 login: (token, user) => void;
 logout: () => void;
 updateUser: (partial) => void;
}
```

- 持久化到 `localStorage`，刷新页面不丢失登录态
- Axios 拦截器自动携带 token
  
  ### 6.2 文件状态（useFileStore）
  
  ```typescript
  interface FileState {
  treeData: TreeNode[];
  selectedFileId: string | null;
  currentFileContent: string;
  expandedKeys: string[];
  setTreeData: (data) => void;
  selectFile: (id) => void;
  updateFileContent: (content) => void;
  toggleExpand: (keys) => void;
  }
  ```
- 文件树数据全局共享，知识树/知识编辑/知识图谱共用
- 避免重复请求，减少组件间传参
  
  ### 6.3 UI 状态（useUiStore）
- 侧边栏折叠状态
- 当前激活 Tab
- 全局 Loading
- 消息提示队列

---

## 七、核心交互流程

### 7.1 文件操作流程

1. 进入页面 → 调用接口获取文件树 → 存入 `useFileStore`
2. 点击文件夹 → 展开/折叠 → 更新 `expandedKeys`
3. 点击文件 → 设置 `selectedFileId` → 右侧加载详情/编辑器内容
4. 编辑保存 → 调用更新接口 → 刷新树节点更新时间
   
   ### 7.2 权限校验流程
5. 页面加载 → 从 localStorage 恢复用户信息
6. 路由切换 → `AuthGuard` 校验登录态与角色
7. 接口请求 → Axios 拦截器携带 token
8. 后端返回 401/403 → 统一处理：登出 / 提示无权限
   
   ### 7.3 图谱数据流程
9. 进入图谱页 → 调用接口获取文件关联关系
10. 前端转换为 `nodes` + `links` 格式
11. 初始化力导向图渲染
12. 点击节点 → 联动文件树定位并高亮

---

## 八、后续扩展建议

1. **性能优化**：文件树数据量大时启用虚拟滚动（`rc-virtual-list`）
2. **多标签页**：编辑器支持打开多个文件 Tab
3. **版本历史**：Markdown 文件增加版本记录与回滚
4. **快捷键**：保存（Ctrl+S）、搜索（Ctrl+P）等常用操作
5. **暗黑模式**：跟随系统或手动切换，适配 Ant Design 主题
6. **移动端适配**：左侧标签栏改为底部 Tab 或抽屉式
   需要我针对某个模块给出更详细的代码实现（比如文件树组件、权限守卫、图谱接入）吗？
