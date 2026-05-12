# SDIT Code Wiki

> **SDIT** (Security Detection & Incident Toolkit) — Linux 应急响应与安全评估工具  
> 版本: 0.55.0 | 架构: Vue 3 + FastAPI + Tauri

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 整体架构](#2-整体架构)
- [3. 技术栈与依赖](#3-技术栈与依赖)
- [4. 目录结构](#4-目录结构)
- [5. 前端模块详解](#5-前端模块详解)
  - [5.1 核心层 (core)](#51-核心层-core)
  - [5.2 UI 层 (ui)](#52-ui-层-ui)
  - [5.3 SSH 模块 (ssh)](#53-ssh-模块-ssh)
  - [5.4 远程操作模块 (remote)](#54-远程操作模块-remote)
  - [5.5 安全检测模块 (detection)](#55-安全检测模块-detection)
  - [5.6 应急响应模块 (emergency)](#56-应急响应模块-emergency)
  - [5.7 AI 模块 (ai)](#57-ai-模块-ai)
  - [5.8 API 通信层 (api)](#58-api-通信层-api)
  - [5.9 设置模块 (settings)](#59-设置模块-settings)
  - [5.10 系统信息模块 (system)](#510-系统信息模块-system)
  - [5.11 渗透测试模块 (payloader)](#511-渗透测试模块-payloader)
  - [5.12 工具模块 (utils)](#512-工具模块-utils)
  - [5.13 配置层 (config)](#513-配置层-config)
- [6. 后端模块详解](#6-后端模块详解)
  - [6.1 应用入口 (main.py)](#61-应用入口-mainpy)
  - [6.2 API 路由层 (routers/api.py)](#62-api-路由层-routersapipy)
  - [6.3 SSH 管理服务 (services/ssh_manager.py)](#63-ssh-管理服务-servicesssh_managerpy)
  - [6.4 SSH 连接配置管理 (services/ssh_connection_manager.py)](#64-ssh-连接配置管理-servicesssh_connection_managerpy)
  - [6.5 安全检测服务 (services/detection_manager.py)](#65-安全检测服务-servicesdetection_managerpy)
  - [6.6 文件分析服务 (services/file_analysis.py)](#66-文件分析服务-servicesfile_analysispy)
  - [6.7 日志分析服务 (services/log_analysis.py)](#67-日志分析服务-serviceslog_analysispy)
  - [6.8 设置服务 (services/settings.py)](#68-设置服务-servicessettingspy)
  - [6.9 主题管理服务 (services/theme_manager.py)](#69-主题管理服务-servicestheme_managerpy)
  - [6.10 设备信息服务 (services/device_info.py)](#610-设备信息服务-servicesdevice_infopy)
  - [6.11 窗口管理服务 (services/window_manager.py)](#611-窗口管理服务-serviceswindow_managerpy)
  - [6.12 加密工具 (utils/crypto.py)](#612-加密工具-utilscryptopy)
  - [6.13 系统字体工具 (utils/system_fonts.py)](#613-系统字体工具-utilssystem_fontspy)
  - [6.14 数据模型 (models/types.py)](#614-数据-modelstypepy)
  - [6.15 渗透测试 Agent (services/pentest_agent/)](#615-渗透测试-agent-servicespentest_agent)
  - [6.16 技能引擎 (services/skill_engine/)](#616-技能引擎-servicesskill_engine)
- [7. 前后端通信机制](#7-前后端通信机制)
- [8. Skills 技能体系](#8-skills-技能体系)
- [9. 模块依赖关系图](#9-模块依赖关系图)
- [10. 项目运行方式](#10-项目运行方式)
- [11. 测试体系](#11-测试体系)
- [12. CI/CD 流程](#12-cicd-流程)

---

## 1. 项目概述

SDIT 是一款面向 Linux 服务器的安全应急响应与评估工具，提供以下核心能力：

| 能力 | 说明 |
|------|------|
| **SSH 远程管理** | 通过 SSH 连接远程 Linux 服务器，执行命令、管理终端会话 |
| **SFTP 文件管理** | 远程文件浏览、上传/下载、压缩/解压、权限修改 |
| **安全检测** | 端口扫描、用户审计、后门检测、进程分析、文件权限检查等 20+ 检测项 |
| **应急响应** | 预置应急命令库，支持按系统类型自动匹配命令，一键执行 |
| **日志审计** | 系统日志 / journalctl 日志读取、过滤、分析 |
| **渗透测试** | AI 驱动的自动化渗透测试 Agent，支持多轮规划与执行 |
| **AI 辅助** | 集成 LLM 大模型，提供智能分析、命令建议、日志解读 |
| **Payload 生成** | Web/内网渗透载荷生成与编码工具 |

项目采用 **前后端分离** 架构：
- **前端**: Vue 3 + TypeScript + Vite，运行于 Tauri 桌面容器或浏览器
- **后端**: Python FastAPI，提供 REST API + WebSocket，负责 SSH 连接管理与业务逻辑

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Tauri / Browser                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Vue 3 前端 (Vite 构建)                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ Dashboard│ │ SSH Term │ │ SFTP File│ │ Detection│  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ Emergency│ │ Log Audit│ │ Payloader│ │ AI Chat  │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                        │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │  Core: SDITApp → StateManager → ModernUIRenderer│   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │  PythonApi (HTTP/WS) ←→ Python Backend          │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │ HTTP / WebSocket                  │
│                          ▼                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           Python FastAPI 后端 (port 3001)              │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐ │  │
│  │  │ API Router │ │ WebSocket  │ │ Pentest Agent      │ │  │
│  │  │ (/api/v1)  │ │ (/ws/*)    │ │ (LLM + Skill)      │ │  │
│  │  └────────────┘ └────────────┘ └────────────────────┘ │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐ │  │
│  │  │ SSHManager │ │ Detection  │ │ Skill Engine       │ │  │
│  │  │ (asyncssh) │ │ Manager    │ │ (Loader + Matcher) │ │  │
│  │  └────────────┘ └────────────┘ └────────────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │ SSH / SFTP                        │
│                          ▼                                   │
│                  ┌──────────────────┐                        │
│                  │  Remote Linux    │                        │
│                  │  Server          │                        │
│                  └──────────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 技术栈与依赖

### 前端依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| `vue` | ^3.5.13 | UI 框架 |
| `@tauri-apps/api` | ^2.10.1 | Tauri 桌面 API (窗口控制、对话框等) |
| `xterm` | ^5.3.0 | 终端模拟器 |
| `xterm-addon-fit` | ^0.8.0 | 终端自适应尺寸 |
| `marked` | ^15.0.12 | Markdown 渲染 |
| `@icon-park/vue-next` | ^1.4.2 | 图标库 |
| `vite` | ^6.0.3 | 构建工具 |
| `typescript` | ~5.6.2 | 类型系统 |
| `vitest` | ^4.1.4 | 单元测试 |

### 后端依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| `fastapi` | >=0.115.0 | Web 框架 |
| `uvicorn` | >=0.34.0 | ASGI 服务器 |
| `asyncssh` | >=2.18.0 | 异步 SSH 客户端 |
| `paramiko` | >=3.5.0 | SSH 客户端 (备用) |
| `cryptography` | >=43.0.0 | 加密/解密 |
| `pydantic` | >=2.10.0 | 数据模型与校验 |
| `httpx` | >=0.27.0 | HTTP 客户端 (AI 代理) |
| `websockets` | >=14.0 | WebSocket 支持 |
| `tomli` | >=2.0.0 | TOML 解析 (工具注册) |

---

## 4. 目录结构

```
SDIT/
├── src/                          # 前端源码 (Vue 3 + TypeScript)
│   ├── main.ts                   # 前端入口文件
│   ├── modules/                  # 功能模块
│   │   ├── core/                 # 核心层 (App, StateManager)
│   │   ├── ui/                   # UI 渲染与页面管理
│   │   ├── ssh/                  # SSH 终端管理
│   │   ├── remote/               # 远程操作 (SFTP, 连接管理)
│   │   ├── detection/            # 安全检测
│   │   ├── emergency/            # 应急响应
│   │   ├── ai/                   # AI 服务
│   │   ├── api/                  # API 通信层
│   │   ├── settings/             # 设置管理
│   │   ├── system/               # 系统信息
│   │   ├── payloader/            # 渗透载荷生成
│   │   └── utils/                # 工具函数
│   ├── components/               # Vue 组件
│   ├── config/                   # 配置文件
│   ├── css/                      # 全局样式
│   ├── styles/                   # 模块样式
│   ├── shims/                    # Tauri API 类型垫片
│   ├── types/                    # 全局类型声明
│   └── assets/                   # 静态资源
├── src-python/                   # Python 后端源码
│   ├── run.py                    # 后端启动入口
│   ├── app/
│   │   ├── main.py               # FastAPI 应用定义
│   │   ├── models/               # 数据模型
│   │   ├── routers/              # API 路由
│   │   ├── services/             # 业务服务
│   │   │   ├── ssh_manager.py    # SSH 连接管理
│   │   │   ├── ssh_connection_manager.py  # SSH 配置持久化
│   │   │   ├── detection_manager.py       # 安全检测
│   │   │   ├── file_analysis.py           # 文件分析
│   │   │   ├── log_analysis.py            # 日志分析
│   │   │   ├── settings.py                # 应用设置
│   │   │   ├── theme_manager.py           # 主题管理
│   │   │   ├── device_info.py             # 设备信息
│   │   │   ├── window_manager.py          # 窗口管理
│   │   │   ├── pentest_agent/             # 渗透测试 Agent
│   │   │   └── skill_engine/              # 技能引擎
│   │   └── utils/                # 工具函数
│   ├── tests/                    # 后端测试
│   ├── pyproject.toml            # Python 项目配置
│   └── requirements.txt          # Python 依赖
├── skills/                       # 技能定义文件
│   ├── builtin/                  # 内置技能
│   ├── experimental/             # 实验性技能
│   ├── imported/                 # 导入技能
│   └── generated/                # 自动生成技能
├── public/                       # 公共静态资源
├── docs/                         # 项目文档
├── .github/workflows/            # CI/CD 工作流
├── package.json                  # 前端项目配置
├── vite.config.ts                # Vite 构建配置
├── tsconfig.json                 # TypeScript 配置
├── index.html                    # 主页面入口
├── ssh-terminal.html             # SSH 终端独立页面
├── start.bat                     # Windows 一键启动脚本
└── start_linux.py                # Linux 一键启动脚本
```

---

## 5. 前端模块详解

### 5.1 核心层 (core)

#### `SDITApp` — [app.ts](file:///d:/项目/new/new/src/modules/core/app.ts)

应用主类，负责初始化和协调所有模块。

| 属性 | 类型 | 说明 |
|------|------|------|
| `stateManager` | `StateManager` | 全局状态管理器 |
| `modernUIRenderer` | `ModernUIRenderer` | UI 渲染器 |
| `themeManager` | `ThemeManager` | 主题管理器 |
| `sshManager` | `SSHManager` | SSH 管理器 (public) |
| `settingsManager` | `SettingsManager` | 设置管理器 |
| `systemInfoManager` | `SystemInfoManager` | 系统信息管理器 |

| 方法 | 说明 |
|------|------|
| `initialize()` | 初始化应用：状态管理器 → UI 渲染器 → 主题 → 设置 → SSH 终端 → 恢复连接 → 渲染 UI → 绑定事件 |
| `render()` | 渲染应用界面 (标题栏 + 侧边栏 + 主工作区) |
| `switchToPage(pageId)` | 切换当前页面，更新状态和导航 |
| `setTheme(theme)` | 设置主题并持久化到后端 |
| `toggleTheme()` | 在 light/dark 之间切换主题 |
| `handleSSHConnect()` | 处理 SSH 连接请求 |
| `handleSSHDisconnect()` | 处理 SSH 断开请求 |

#### `StateManager` — [stateManager.ts](file:///d:/项目/new/new/src/modules/core/stateManager.ts)

继承自 `EventEmitter<AppState>`，管理全局应用状态。

| 核心状态字段 | 类型 | 默认值 | 说明 |
|-------------|------|--------|------|
| `theme` | `'light' \| 'dark'` | `'light'` | 当前主题 |
| `uiMode` | `UIMode` | `'classic'` | UI 模式 |
| `isConnected` | `boolean` | `false` | SSH 连接状态 |
| `currentServer` | `string \| undefined` | - | 当前服务器名 |
| `serverInfo` | `ServerInfo \| undefined` | - | 服务器详情 |
| `loading` | `boolean` | `false` | 加载状态 |
| `currentPage` | `AppPage` | `'dashboard'` | 当前页面 |

| 方法 | 说明 |
|------|------|
| `initialize()` | 从 localStorage 和后端加载状态 |
| `setState(partial)` | 更新状态并通知监听器 |
| `setTheme(theme)` | 设置主题并应用到 DOM |
| `setConnected(isConnected, server?, serverInfo?)` | 设置连接状态 |
| `setCurrentPage(page)` | 切换当前页面 |
| `savePageState(pageId, partial)` | 保存页面级状态 |
| `getPageState(pageId)` | 获取页面级状态 |

---

### 5.2 UI 层 (ui)

#### `ModernUIRenderer` — [modernUIRenderer.ts](file:///d:/项目/new/new/src/modules/ui/modernUIRenderer.ts)

核心 UI 渲染器，负责生成所有页面的 HTML 结构。

| 方法 | 说明 |
|------|------|
| `renderTitleBar()` | 渲染标题栏 (窗口控制 + 连接信息 + 主题切换) |
| `renderSidebar()` | 渲染侧边导航栏 |
| `renderMainWorkspace()` | 渲染主工作区 |
| `renderGlobalModals()` | 渲染全局模态框 |
| `switchToPage(pageId)` | 切换页面内容 |
| `updateState(state)` | 根据状态更新 UI |
| `renderSettingsPage()` | 渲染设置页面 |

#### 页面类型 — [pageTypes.ts](file:///d:/项目/new/new/src/modules/ui/pageTypes.ts)

| 页面 ID | 标题 | 说明 |
|---------|------|------|
| `dashboard` | 系统监控 | 服务器资源监控仪表盘 |
| `system-info` | 资源监控 | CPU/内存/磁盘/网络详细信息 |
| `ssh-terminal` | SSH终端 | 交互式 SSH 终端 |
| `remote-operations` | 文件分析 | SFTP 文件管理器 |
| `emergency-commands` | 应急响应 | 应急命令库与执行 |
| `log-analysis` | 日志审计 | 系统日志分析 |
| `quick-detection` | 安全评估 | 安全检测与评估 |
| `database` | 数据库 | 数据库管理 |
| `payloader` | 渗透测试 | Payload 生成工具 |

#### 工作区组件

| 文件 | 说明 |
|------|------|
| `WorkspaceRoot.vue` | 工作区根 Vue 组件，管理页面路由和渲染 |
| `LegacyPageHost.vue` | 旧版页面宿主组件，桥接非 Vue 页面 |
| `mountWorkspaceRoot.ts` | 挂载工作区根元素到 DOM |

#### 其他 UI 模块

| 文件 | 说明 |
|------|------|
| `dashboardRenderer.ts` | 仪表盘页面渲染 |
| `databaseRenderer.ts` | 数据库页面渲染 |
| `logAnalysisRenderer.ts` | 日志分析页面渲染 |
| `emergencyModal.ts` | 应急命令执行模态框 |
| `sshConnectionDialog.ts` | SSH 连接对话框 |
| `fileContextMenu.ts` | 文件右键菜单 |
| `sftpContextMenu.ts` | SFTP 右键菜单 |
| `uploadModal.ts` | 文件上传模态框 |
| `compressModal.ts` | 压缩操作模态框 |
| `extractModal.ts` | 解压操作模态框 |
| `fileDetailsModal.ts` | 文件详情模态框 |
| `permissionsModal.ts` | 权限修改模态框 |
| `fileViewerModal.ts` | 文件查看器模态框 |
| `commandHistoryModal.ts` | 命令历史模态框 |
| `theme.ts` | 主题管理器 (ThemeManager 类) |
| `iconMapping.ts` | 文件图标映射 |
| `navigationConfig.ts` | 导航栏配置 |

---

### 5.3 SSH 模块 (ssh)

#### `SSHManager` — [sshManager.ts](file:///d:/项目/new/new/src/modules/ssh/sshManager.ts)

前端 SSH 管理器，协调连接管理器和终端管理器。

| 方法 | 说明 |
|------|------|
| `connect(connectionId)` | 通过连接配置 ID 建立 SSH 连接 |
| `disconnect()` | 断开 SSH 连接 |
| `getConnections()` | 获取已保存的连接列表 |
| `fetchSystemSummary()` | 获取系统摘要信息 |
| `executeCommand(command)` | 执行远程命令 |

#### 其他 SSH 文件

| 文件 | 说明 |
|------|------|
| `sshTerminalManager.ts` | SSH 终端会话管理 (创建/关闭/输入/输出) |
| `connectionManager.ts` | SSH 连接配置管理 (前端侧) |
| `commandHints.ts` | 命令提示与补全 |

---

### 5.4 远程操作模块 (remote)

#### `RemoteOperationsManager` — [remoteOperationsManager.ts](file:///d:/项目/new/new/src/modules/remote/remoteOperationsManager.ts)

统一协调 SSH 连接、SFTP 文件管理和终端操作的管理器。

| 职责 | 说明 |
|------|------|
| 连接状态管理 | 监听 SSH 连接状态变化，通知 UI 更新 |
| SFTP 文件列表 | 监听文件列表变化，触发 UI 刷新 |
| 终端历史 | 管理终端会话历史记录 |

#### `SftpManager` — [sftpManager.ts](file:///d:/项目/new/new/src/modules/remote/sftpManager.ts)

远程文件操作管理器。

| 方法 | 说明 |
|------|------|
| `listFiles(path)` | 列出远程目录文件 |
| `navigateTo(path)` | 导航到指定路径 |
| `handleFileClick(file)` | 处理文件点击 (目录进入/文件查看) |
| `refresh()` | 刷新当前目录 |

#### `SSHConnectionManager` — [sshConnectionManager.ts](file:///d:/项目/new/new/src/modules/remote/sshConnectionManager.ts)

前端侧 SSH 连接操作管理器，处理实际连接/断开/状态检查。

| 方法 | 说明 |
|------|------|
| `connect(params)` | 建立 SSH 连接 |
| `disconnect()` | 断开连接 |
| `checkConnectionStatus()` | 检查连接状态 |
| `updateLastActivity()` | 更新最后活动时间 |

#### `TerminalManager` — [terminalManager.ts](file:///d:/项目/new/new/src/modules/remote/terminalManager.ts)

终端会话管理，处理终端创建、输入输出和 WebSocket 通信。

---

### 5.5 安全检测模块 (detection)

#### `QuickDetectionManager` — [quickDetectionManager.ts](file:///d:/项目/new/new/src/modules/detection/quickDetectionManager.ts)

安全检测管理器，提供 20+ 安全检测能力。

| 检测类别 | 检测项 |
|---------|--------|
| **入侵检测** | 端口扫描、用户审计、后门检测、进程分析、文件权限、SSH 审计、日志分析、防火墙检查 |
| **性能检测** | CPU 测试、内存测试、磁盘测试、网络测试 |
| **基线检测** | 密码策略、Sudo 配置、PAM 配置、账户锁定、SELinux 状态、内核参数、系统更新、不必要服务、自启动服务、审计配置、历史审计、NTP 配置、DNS 配置 |

| 方法 | 说明 |
|------|------|
| `loadDetectionRules()` | 加载检测规则 |
| `executeDetection(ruleId)` | 执行指定检测 |
| `generateReport(results)` | 生成检测报告 |
| `exportReport(format)` | 导出报告 (JSON/HTML/PDF) |

---

### 5.6 应急响应模块 (emergency)

#### `EmergencyPageManager` — [emergencyPageManager.ts](file:///d:/项目/new/new/src/modules/emergency/emergencyPageManager.ts)

应急响应页面管理器。

| 方法 | 说明 |
|------|------|
| `searchCommands(query)` | 搜索应急命令 |
| `detectSystemType()` | 检测远程系统类型 |
| `loadAccountList()` | 加载系统账号列表 |
| `executeCommand(command, username?)` | 执行应急命令 |

#### 其他文件

| 文件 | 说明 |
|------|------|
| `commands.ts` | 应急命令定义 (按类别/系统类型分组) |
| `commandAdapter.ts` | 命令适配器 (根据系统类型调整命令) |

---

### 5.7 AI 模块 (ai)

#### `AIService` — [aiService.ts](file:///d:/项目/new/new/src/modules/ai/aiService.ts)

AI 辅助分析服务。

| 方法 | 说明 |
|------|------|
| `configureModel(config)` | 配置 AI 模型参数 |
| `testConnection()` | 测试 AI 服务连接 |
| `generateSolution(context)` | 根据上下文生成解决方案 |
| `analyzeLog(logContent)` | 分析日志内容 |
| `analyzeCommandOutput(output)` | 分析命令输出 |

---

### 5.8 API 通信层 (api)

#### `PythonApi` — [python-api.config.ts](file:///d:/项目/new/new/src/config/python-api.config.ts)

前端与 Python 后端通信的核心适配层，将所有后端 API 调用封装为类型安全的异步方法。

**通信方式**: HTTP REST + WebSocket  
**基础 URL**: 开发环境 `/api/v1` (Vite 代理) / 生产环境 `http://127.0.0.1:3001/api/v1`

| API 分组 | 主要方法 |
|---------|---------|
| 窗口控制 | `minimizeWindow()`, `toggleMaximize()`, `closeWindow()`, `openDevtools()` |
| 对话框 | `openDialog()`, `saveDialog()` |
| 主题管理 | `getThemeSettings()`, `setCurrentTheme()` |
| 设置管理 | `getAppSettings()`, `saveAppSettings()`, `readSettingsFile()`, `writeSettingsFile()` |
| SSH 连接 | `sshConnectWithAuth()`, `sshDisconnect()`, `sshGetConnectionStatus()`, `sshTestConnection()` |
| SSH 命令 | `sshExecuteCommand()`, `sshExecuteDashboardCommandDirect()`, `sshExecuteEmergencyCommandDirect()` |
| SFTP 操作 | `sftpListFiles()`, `sftpReadFile()`, `sftpWriteFile()`, `sftpUpload()`, `sftpDownload()`, `sftpCreateDirectory()`, `sftpCompress()`, `sftpExtract()`, `sftpChmod()`, `sftpGetFileDetails()` |
| 安全检测 | `detectPortScan()`, `detectUserAudit()`, `detectBackdoor()`, ... (20+ 检测方法) |
| 终端管理 | `sshCreateTerminalSession()`, `sshCloseTerminalSession()`, `sshSendInput()` |
| 日志分析 | `readSystemLog()`, `readJournalctlLog()`, `listLogFiles()` |
| 渗透测试 | `pentestStart()`, `pentestStatus()`, `pentestStop()`, `pentestGetReport()`, `pentestHistory()` |
| 加密/设备 | `getRsaPublicKey()`, `getDeviceUuid()` |

导出单例: `pythonApi`

---

### 5.9 设置模块 (settings)

#### `SettingsManager` — [settingsManager.ts](file:///d:/项目/new/new/src/modules/settings/settingsManager.ts)

应用设置管理器，负责设置的加载、保存和应用。

| 方法 | 说明 |
|------|------|
| `initialize()` | 初始化设置管理器 |
| `loadSettings()` | 从后端加载设置 |
| `saveSettings()` | 保存设置到后端 |
| `updateSetting(key, value)` | 更新单个设置项 |
| `getSetting(key)` | 获取设置值 |
| `applySettingsToUI()` | 将设置应用到界面 |

#### `SettingsPageManager` — [settingsPageManager.ts](file:///d:/项目/new/new/src/modules/settings/settingsPageManager.ts)

设置页面管理器，处理设置页面的交互逻辑。

---

### 5.10 系统信息模块 (system)

#### `SystemInfoManager` — [systemInfoManager.ts](file:///d:/项目/new/new/src/modules/system/systemInfoManager.ts)

系统信息管理器，获取和缓存远程服务器的系统信息。

| 方法 | 说明 |
|------|------|
| `getSystemInfo()` | 获取完整系统信息 |
| `getSystemSummary()` | 获取系统摘要 (CPU/内存/磁盘/网络) |
| `loadDetailedInfo(tab)` | 按 tab 懒加载详细系统信息 |

---

### 5.11 渗透测试模块 (payloader)

#### 页面组件

| 文件 | 说明 |
|------|------|
| `PayloaderPage.vue` | 渗透载荷生成页面主组件 |
| `components/PayloaderContent.vue` | 内容区域组件 |
| `components/PayloaderToolbar.vue` | 工具栏组件 |
| `components/EncodingTools.vue` | 编码工具组件 |

#### 数据层

| 文件 | 说明 |
|------|------|
| `types.ts` | Payload 类型、编码类型、工具命令类型定义 |
| `data/webPayloads.ts` | Web 渗透载荷数据 |
| `data/intranetPayloads.ts` | 内网渗透载荷数据 |
| `data/toolCommands.ts` | 工具命令数据 |
| `data/navigation.ts` | 导航菜单配置 |

#### 状态管理

| 文件 | 说明 |
|------|------|
| `composables/usePayloaderState.ts` | Vue 组合式 API，管理 Payloader 状态 |

#### 工具函数

| 文件 | 说明 |
|------|------|
| `utils/encoding.ts` | 编码/解码工具 (Base64, URL, Hex, Unicode 等) |
| `utils/encoding.test.ts` | 编码工具单元测试 |

---

### 5.12 工具模块 (utils)

#### `EventEmitter<T>` — [EventEmitter.ts](file:///d:/项目/new/new/src/modules/utils/EventEmitter.ts)

泛型事件发射器，是状态管理和模块间通信的基础。

| 方法 | 说明 |
|------|------|
| `addListener(listener)` | 添加事件监听器 |
| `removeListener(listener)` | 移除事件监听器 |
| `emit(data)` | 触发事件 (protected) |

#### `aiProxy.ts` — [aiProxy.ts](file:///d:/项目/new/new/src/modules/utils/aiProxy.ts)

AI 代理工具，提供流式调用 AI 接口的能力。

#### 其他工具

| 文件 | 说明 |
|------|------|
| `commandHistoryManager.ts` | 命令历史记录管理 |
| `idGenerator.ts` | 唯一 ID 生成器 |
| `systemDetector.ts` | 系统环境检测 |

---

### 5.13 配置层 (config)

#### `api.config.ts` — [api.config.ts](file:///d:/项目/new/new/src/config/api.config.ts)

旧版 API 配置 (Node.js 后端)，根据环境自动选择 API 地址。

| 环境 | Base URL |
|------|----------|
| development | `http://localhost:3000/api/v1` |
| production | `http://110.42.47.180:3000/api/v1` |

#### `python-api.config.ts` — [python-api.config.ts](file:///d:/项目/new/new/src/config/python-api.config.ts)

Python 后端 API 适配层，当前主要使用的 API 通信层。包含 `PythonApi` 类和 `pythonApi` 单例。

---

## 6. 后端模块详解

### 6.1 应用入口 (main.py)

[main.py](file:///d:/项目/new/new/src-python/app/main.py)

FastAPI 应用定义，包含：

| 组件 | 说明 |
|------|------|
| `app` | FastAPI 实例，标题 "SDIT API"，版本 0.55.0 |
| `lifespan` | 应用生命周期管理：启动时初始化状态，关闭时断开 SSH |
| CORS 中间件 | 允许所有来源的跨域请求 |
| 异常处理器 | `ConnectionError` → 400, `asyncssh.Error` → 400 |
| WebSocket 端点 | `/ws/terminal/{terminal_id}` (终端), `/ws/events` (事件) |
| 健康检查 | `GET /health` |

**WebSocket 终端流程**:
1. 客户端连接 → 检查 SSH 状态
2. 创建 SSH 终端会话 (支持重试)
3. 启动输出读取任务 + 心跳 ping 任务
4. 双向数据转发：客户端输入 → SSH, SSH 输出 → 客户端

---

### 6.2 API 路由层 (routers/api.py)

[api.py](file:///d:/项目/new/new/src-python/app/routers/api.py)

所有 REST API 端点定义，路由前缀 `/api/v1`。

| 端点分组 | 路由 | 说明 |
|---------|------|------|
| 窗口控制 | `POST /window/*` | 最小化/最大化/关闭/开发者工具 |
| 对话框 | `POST /dialog/open`, `POST /dialog/save` | 原生文件对话框 |
| 主题 | `GET /theme/settings`, `POST /theme/set` | 主题获取与设置 |
| 设置 | `GET /settings`, `POST /settings/save` | 应用设置读写 |
| SSH 连接 | `POST /ssh/connect`, `POST /ssh/disconnect` | SSH 连接管理 |
| SSH 命令 | `POST /ssh/execute-command` 等 | 远程命令执行 |
| SFTP | `POST /sftp/*` | 文件操作 (列表/读写/上传/下载/压缩/解压/权限) |
| 安全检测 | `POST /detect/*` | 20+ 安全检测端点 |
| 终端 | `POST /ssh/terminal/*` | 终端会话管理 |
| 日志 | `POST /log/*`, `GET /log/list-files` | 日志读取与分析 |
| 渗透测试 | `POST /agent/pentest/start` 等 | Agent 任务管理 |
| 技能 | `GET /skills`, `POST /skills`, `DELETE /skills/{filename}` | 技能管理 |
| 知识库 | `GET /knowledge-base` 等 | 知识库 CRUD |
| 加密 | `GET /crypto/rsa-public-key` | RSA 公钥获取 |
| 设备 | `GET /device/uuid` | 设备 UUID 获取 |

**关键单例管理**:

| 变量 | 类型 | 说明 |
|------|------|------|
| `_ssh_manager` | `SSHManager` | SSH 实时连接管理器 |
| `_ssh_connection_manager` | `SSHConnectionManager` | SSH 连接配置管理器 |
| `_window_manager` | `WindowManager` | 桌面窗口管理器 |
| `_app_settings` | `AppSettings` | 应用设置单例 |
| `_pentest_tasks` | `dict[str, dict]` | 渗透测试任务注册表 |

---

### 6.3 SSH 管理服务 (services/ssh_manager.py)

[ssh_manager.py](file:///d:/项目/new/new/src-python/app/services/ssh_manager.py)

核心 SSH 连接管理器，基于 `asyncssh` 实现异步 SSH 操作。

| 方法 | 说明 |
|------|------|
| `connect(host, port, username, ...)` | 建立 SSH 连接 (支持密码/密钥/证书认证) |
| `disconnect()` | 断开 SSH 连接 |
| `is_connected()` | 检查连接状态 |
| `execute_command(command)` | 执行远程命令 |
| `execute_dashboard_command(command)` | 执行仪表盘命令 |
| `execute_dashboard_command_as_user(command, username)` | 以指定用户执行命令 |
| `list_sftp_files(path)` | 列出 SFTP 目录文件 |
| `read_sftp_file(path)` | 读取远程文件 |
| `write_sftp_file(path, content)` | 写入远程文件 |
| `upload_file(local, remote, progress_callback?)` | 上传文件 |
| `download_file(remote, local)` | 下载文件 |
| `create_directory(path)` | 创建远程目录 |
| `compress_file(source, target, format)` | 压缩文件/目录 |
| `extract_file(archive, target_dir)` | 解压文件 |
| `chmod_sftp(path, mode)` | 修改文件权限 |
| `get_file_details(path)` | 获取文件详细信息 |
| `create_terminal_session(id, cols, rows)` | 创建终端会话 |
| `close_terminal_session(id)` | 关闭终端会话 |
| `send_terminal_input(id, data)` | 发送终端输入 |
| `read_terminal_output(id, timeout)` | 读取终端输出 |
| `get_connection_status()` | 获取连接状态 |
| `get_connection_health()` | 获取连接健康度 |
| `get_bash_environment_info()` | 获取 Bash 环境信息 |
| `get_command_completion(input)` | 获取命令补全建议 |

---

### 6.4 SSH 连接配置管理 (services/ssh_connection_manager.py)

[ssh_connection_manager.py](file:///d:/项目/new/new/src-python/app/services/ssh_connection_manager.py)

SSH 连接配置的持久化管理，负责连接配置的加密存储、加载和删除。

| 方法 | 说明 |
|------|------|
| `load_connections()` | 加载所有保存的连接配置 |
| `save_connections(connections)` | 保存连接配置列表 |
| `encrypt_password(password)` | 加密密码 |
| `decrypt_password(encrypted)` | 解密密码 |

---

### 6.5 安全检测服务 (services/detection_manager.py)

[detection_manager.py](file:///d:/项目/new/new/src-python/app/services/detection_manager.py)

安全检测业务逻辑层，封装各类安全检测的命令构造和结果解析。

| 检测函数 | 说明 |
|---------|------|
| `detect_port_scan()` | 端口扫描检测 |
| `detect_user_audit()` | 用户审计 |
| `detect_backdoor()` | 后门检测 |
| `detect_process_analysis()` | 进程分析 |
| `detect_file_permission()` | 文件权限检查 |
| `detect_ssh_audit()` | SSH 配置审计 |
| `detect_log_analysis()` | 日志分析 |
| `detect_firewall_check()` | 防火墙检查 |
| `detect_cpu_test()` | CPU 性能测试 |
| `detect_memory_test()` | 内存测试 |
| `detect_disk_test()` | 磁盘测试 |
| `detect_network_test()` | 网络测试 |
| `detect_password_policy()` | 密码策略检查 |
| `detect_sudo_config()` | Sudo 配置检查 |
| `detect_pam_config()` | PAM 配置检查 |
| `detect_account_lockout()` | 账户锁定策略检查 |
| `detect_selinux_status()` | SELinux 状态检查 |
| `detect_kernel_params()` | 内核参数检查 |
| `detect_system_updates()` | 系统更新检查 |
| `detect_unnecessary_services()` | 不必要服务检查 |
| `detect_auto_start_services()` | 自启动服务检查 |
| `detect_audit_config()` | 审计配置检查 |
| `detect_history_audit()` | 历史命令审计 |
| `detect_ntp_config()` | NTP 配置检查 |
| `detect_dns_config()` | DNS 配置检查 |

---

### 6.6 文件分析服务 (services/file_analysis.py)

[file_analysis.py](file:///d:/项目/new/new/src-python/app/services/file_analysis.py)

远程文件安全分析服务，支持多种分析动作。

| 分析动作 | 说明 |
|---------|------|
| `md5` | 计算 MD5 哈希 |
| `sha256` | 计算 SHA-256 哈希 |
| `strings` | 提取可读字符串 |
| `elf` | ELF 二进制分析 |
| 完整分析 | 综合文件类型、权限、哈希、风险指标 |

---

### 6.7 日志分析服务 (services/log_analysis.py)

[log_analysis.py](file:///d:/项目/new/new/src-python/app/services/log_analysis.py)

远程日志分析服务。

| 方法 | 说明 |
|------|------|
| `read_system_log(ssh, path, page, ...)` | 读取系统日志 (支持分页/过滤/日期/级别) |
| `read_journalctl_log(ssh, page, ...)` | 读取 journalctl 日志 |
| `list_log_files(ssh)` | 列出可用日志文件 |
| `get_log_file_info(ssh, path)` | 获取日志文件信息 |

---

### 6.8 设置服务 (services/settings.py)

[settings.py](file:///d:/项目/new/new/src-python/app/services/settings.py)

应用设置管理服务，基于 Pydantic 模型校验。

| 函数 | 说明 |
|------|------|
| `load_settings()` | 加载应用设置 |
| `save_settings(settings)` | 保存应用设置 |
| `read_settings_file()` | 读取设置文件原始内容 |
| `write_settings_file(content)` | 写入设置文件 |

---

### 6.9 主题管理服务 (services/theme_manager.py)

[theme_manager.py](file:///d:/项目/new/new/src-python/app/services/theme_manager.py)

主题管理服务，提供主题配置的获取和切换。

---

### 6.10 设备信息服务 (services/device_info.py)

[device_info.py](file:///d:/项目/new/new/src-python/app/services/device_info.py)

设备信息获取服务，收集设备 UUID、类型和名称。

---

### 6.11 窗口管理服务 (services/window_manager.py)

[window_manager.py](file:///d:/项目/new/new/src-python/app/services/window_manager.py)

桌面窗口管理器，支持窗口最小化、最大化、关闭和开发者工具操作。

---

### 6.12 加密工具 (utils/crypto.py)

[crypto.py](file:///d:/项目/new/new/src-python/app/utils/crypto.py)

加密工具模块，提供 RSA 密钥对生成和密码加密/解密功能。

| 函数 | 说明 |
|------|------|
| `get_rsa_public_key()` | 获取 RSA 公钥 |
| `encrypt_password(password)` | 加密密码 |
| `decrypt_password(encrypted)` | 解密密码 |

---

### 6.13 系统字体工具 (utils/system_fonts.py)

[system_fonts.py](file:///d:/项目/new/new/src-python/app/utils/system_fonts.py)

系统字体检测工具，获取操作系统已安装字体列表。

---

### 6.14 数据模型 (models/types.py)

[types.py](file:///d:/项目/new/new/src-python/app/models/types.py)

Pydantic 数据模型定义，共 30+ 模型类。

| 模型 | 说明 |
|------|------|
| `SSHAccountCredential` | SSH 账号凭据 (用户名/密码/密钥) |
| `SSHConnection` | SSH 连接配置 (含多账号支持) |
| `SSHCommand` | SSH 命令定义 |
| `AppNotification` | 应用通知 |
| `TerminalSession` | 终端会话 |
| `FileTransferTask` | 文件传输任务 |
| `SystemMonitorData` | 系统监控数据 |
| `LogEntry` | 日志条目 |
| `ApiResponse` | 统一 API 响应 |
| `PaginatedResponse` | 分页响应 |
| `TerminalOutput` | 终端输出 |
| `SftpFileInfo` | SFTP 文件信息 |
| `SftpFileDetails` | SFTP 文件详情 |
| `SSHConnectionStatus` | SSH 连接状态 |
| `PortScanResult` | 端口扫描结果 |
| `UserAuditResult` | 用户审计结果 |
| `BackdoorScanResult` | 后门扫描结果 |
| `ProcessAnalysisResult` | 进程分析结果 |
| `FilePermissionResult` | 文件权限检查结果 |
| `SSHAuditResult` | SSH 审计结果 |
| `LogAnalysisResult` | 日志分析结果 |
| `FirewallCheckResult` | 防火墙检查结果 |
| `CpuTestResult` | CPU 测试结果 |
| `MemoryTestResult` | 内存测试结果 |
| `DiskTestResult` | 磁盘测试结果 |
| `NetworkTestResult` | 网络测试结果 |
| `GenericDetectionResult` | 通用检测结果 |
| `FileAnalysisResult` | 文件分析结果 |
| `DeviceInfo` | 设备信息 |

---

### 6.15 渗透测试 Agent (services/pentest_agent/)

AI 驱动的自动化渗透测试框架，支持多轮规划与执行。

#### 架构

```
┌─────────────────────────────────────────────┐
│              Pentest Agent                   │
│                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │ Planner │ →  │Executor │ →  │Reporting│ │
│  │ (规划器) │    │(执行器) │    │(报告器) │ │
│  └─────────┘    └─────────┘    └─────────┘ │
│       │              │                      │
│       ▼              ▼                      │
│  ┌─────────┐    ┌──────────────┐           │
│  │LLMClient│    │ToolRegistry  │           │
│  │(大模型) │    │(工具注册中心)│           │
│  └─────────┘    └──────────────┘           │
│                      │                      │
│                      ▼                      │
│              ┌──────────────┐               │
│              │ Capabilities │               │
│              │ (能力定义)    │               │
│              └──────────────┘               │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │           State (状态管理)            │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

#### 模块说明

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `agent.py` | `run()` | Agent 主入口，驱动规划-执行循环 |
| `state.py` | `State` | 渗透测试状态管理 (阶段/目标/发现/漏洞/凭据/操作记录) |
| `planner.py` | `Planner` | 任务规划器，基于 LLM 生成下一步操作 |
| `executor.py` | `Executor` | 命令执行器，负责工具调用和结果收集 |
| `llm_client.py` | `LLMClient` | LLM 客户端，支持 OpenAI/DeepSeek/Qwen/Ollama |
| `tool_registry.py` | `ToolRegistry` | 工具注册中心，管理可用渗透工具 |
| `capabilities.py` | - | 能力定义，声明系统支持的渗透能力 |
| `reporting.py` | - | 报告生成，输出 Markdown 格式渗透报告 |
| `tools.toml` | - | 工具配置文件 (TOML 格式) |

#### LLM 客户端支持的提供商

| 提供商 | Base URL | 说明 |
|--------|----------|------|
| `openai` | `https://api.openai.com/v1` | OpenAI GPT 系列 |
| `deepseek` | - | DeepSeek 模型 |
| `qwen` | - | 通义千问 |
| `ollama` | - | 本地 Ollama |

#### Agent 执行流程

1. **启动**: 前端调用 `POST /agent/pentest/start`，传入目标、LLM 配置
2. **规划**: Planner 基于 LLM 生成操作计划
3. **执行**: Executor 调用注册工具执行操作
4. **状态更新**: State 持久化到 JSON 文件
5. **报告**: 完成后生成 Markdown 渗透报告
6. **查询**: 前端通过 `GET /agent/pentest/status` 轮询状态

---

### 6.16 技能引擎 (services/skill_engine/)

技能引擎负责技能的加载、解析和匹配，为渗透测试 Agent 提供知识注入。

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `skill_loader.py` | `SkillLoader` | 技能加载器，从文件系统加载技能定义 |
| `skill_matcher.py` | `SkillMatcher` | 技能匹配器，根据目标/场景匹配最佳技能 |
| `skill_md_parser.py` | - | SKILL.md 解析器，将 Markdown 技能文档解析为结构化数据 |

---

## 7. 前后端通信机制

### 7.1 HTTP REST API

前端通过 `PythonApi` 类 (单例 `pythonApi`) 发送 HTTP 请求到后端。

```
前端 (Vue)  →  pythonApi.method()  →  fetch("/api/v1/...")  →  Vite Proxy  →  FastAPI (port 3001)
```

**Vite 代理配置** (开发环境):
- `/api/v1` → `http://127.0.0.1:3001`
- `/ws` → `ws://127.0.0.1:3001`

### 7.2 WebSocket 通信

| 端点 | 用途 | 协议 |
|------|------|------|
| `/ws/terminal/{terminal_id}` | SSH 终端双向通信 | 二进制帧 + JSON 心跳 |
| `/ws/events` | 事件通道 | JSON 消息 |

**终端 WebSocket 流程**:
1. 前端通过 HTTP API 创建终端会话
2. 建立 WebSocket 连接到 `/ws/terminal/{id}`
3. 前端发送键盘输入 (bytes/text)
4. 后端转发到 SSH 通道
5. SSH 输出通过 WebSocket 推送到前端
6. 心跳机制: 客户端 ping → 服务端 pong + 服务端 ping → 客户端 pong

### 7.3 Tauri IPC (兼容层)

项目保留了 Tauri 桌面 API 的 shim 层 (`src/shims/@tauri-apps/api/`)，用于窗口控制和对话框操作。在非 Tauri 环境下，这些调用会被转发到 Python 后端的对应 API。

| Shim 文件 | 原始 Tauri API | 用途 |
|-----------|---------------|------|
| `core.ts` | `@tauri-apps/api/core` | invoke 命令调用 |
| `dialog.ts` | `@tauri-apps/api/dialog` | 文件对话框 |
| `event.ts` | `@tauri-apps/api/event` | 事件系统 |
| `webviewWindow.ts` | `@tauri-apps/api/webviewWindow` | 窗口管理 |

---

## 8. Skills 技能体系

### 8.1 目录结构

```
skills/
├── builtin/                  # 内置技能 (随应用发布)
│   ├── capability-check/     # 能力检查
│   └── remediation-verification/  # 修复验证
├── experimental/             # 实验性技能
│   ├── pentest-recon/        # 渗透侦察
│   ├── pentest-exploit/      # 漏洞利用
│   ├── pentest-lateral/      # 横向移动
│   ├── pentest-post/         # 后渗透
│   ├── pentest-web/          # Web 渗透
│   └── pentest-agent/        # 渗透 Agent
├── imported/                 # 导入技能 (100+ 安全技能)
└── generated/                # 自动生成技能
```

### 8.2 技能文件格式

每个技能目录包含：
- `skill.json` — 技能元数据 (名称/描述/版本/作者/参数)
- `SKILL.md` — 技能详细说明 (可选，Markdown 格式)
- `scripts/` — 技能脚本 (可选)

### 8.3 技能生命周期

1. **加载**: `SkillLoader` 扫描 skills 目录，加载所有 `skill.json`
2. **匹配**: `SkillMatcher` 根据目标/关键词匹配相关技能
3. **注入**: 匹配的技能被注入到渗透测试 Agent 的上下文中
4. **执行**: Agent 根据技能描述生成并执行操作命令

---

## 9. 模块依赖关系图

### 前端模块依赖

```
main.ts
  ├── SDITApp (core)
  │   ├── StateManager (core) ← EventEmitter
  │   ├── ModernUIRenderer (ui)
  │   ├── ThemeManager (ui)
  │   ├── SSHManager (ssh)
  │   │   ├── SSHConnectionManager (remote)
  │   │   └── SSHTerminalManager (ssh)
  │   ├── SettingsManager (settings)
  │   └── SystemInfoManager (system)
  ├── RemoteOperationsManager (remote)
  │   ├── SSHConnectionManager (remote)
  │   ├── SftpManager (remote)
  │   └── TerminalManager (remote)
  ├── EmergencyPageManager (emergency)
  ├── QuickDetectionManager (detection)
  ├── AIService (ai)
  ├── pythonApi (config)
  └── UI Modals (ui/*)
```

### 后端模块依赖

```
main.py (FastAPI)
  ├── routers/api.py
  │   ├── SSHManager (services)
  │   │   └── asyncssh
  │   ├── SSHConnectionManager (services)
  │   │   └── crypto (utils)
  │   ├── DetectionManager (services)
  │   │   └── SSHManager
  │   ├── FileAnalysis (services)
  │   │   └── SSHManager
  │   ├── LogAnalysis (services)
  │   │   └── SSHManager
  │   ├── Settings (services)
  │   ├── ThemeManager (services)
  │   ├── DeviceInfo (services)
  │   ├── WindowManager (services)
  │   ├── PentestAgent (services/pentest_agent)
  │   │   ├── State
  │   │   ├── Planner → LLMClient
  │   │   ├── Executor → ToolRegistry
  │   │   └── Reporting
  │   └── SkillEngine (services/skill_engine)
  │       ├── SkillLoader
  │       ├── SkillMatcher
  │       └── SkillMdParser
  └── models/types.py (Pydantic)
```

### 前后端数据流

```
┌─────────────┐    HTTP/WS     ┌──────────────┐    SSH/SFTP    ┌──────────────┐
│  Vue 前端    │ ───────────→  │  FastAPI 后端 │ ───────────→  │  Linux 服务器 │
│             │ ←─────────── │              │ ←─────────── │              │
│ pythonApi   │    JSON/Bin   │  SSHManager   │    SSH/SFTP   │  sshd        │
└─────────────┘               └──────────────┘               └──────────────┘
```

---

## 10. 项目运行方式

### 环境要求

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Node.js | - | 前端运行时 |
| npm | - | 前端包管理 |
| Python | 3.10+ | 后端运行时 |

### 方式一：一键启动 (推荐)

**Windows**:
```bash
start.bat
```

**Linux**:
```bash
python3 start_linux.py
```

一键脚本会自动：
1. 检查环境依赖
2. 安装前端依赖 (npm)
3. 创建 Python 虚拟环境并安装依赖
4. 释放占用端口
5. 启动后端 (port 3001)
6. 启动前端 (port 1420)

### 方式二：手动启动

**1. 启动 Python 后端**:
```bash
cd src-python
pip install -r requirements.txt
python run.py
# 后端运行在 http://127.0.0.1:3001
```

**2. 启动前端**:
```bash
npm install
npm run dev
# 前端运行在 http://127.0.0.1:1420
```

### 方式三：npm 脚本

```bash
# 前端开发
npm run dev

# 前端构建
npm run build

# 启动 Python 后端
npm run python-backend

# 预览构建结果
npm run preview
```

### 端口配置

| 服务 | 默认端口 | 环境变量 |
|------|---------|---------|
| 前端 (Vite) | 1420 | - |
| 后端 (FastAPI) | 3001 | `PY_BACKEND_PORT` |
| 后端热重载 | 关闭 | `PY_BACKEND_RELOAD=1` 开启 |

### 生产构建

```bash
npm run build
# 输出到 ./dist 目录
# 构建流程: vue-tsc 类型检查 → vite build → terser 压缩 → 代码混淆
```

---

## 11. 测试体系

### 前端测试

- 框架: Vitest + @vue/test-utils
- 覆盖率: @vitest/coverage-v8
- 示例: `src/modules/payloader/utils/encoding.test.ts`

```bash
npm run test          # 运行测试
npm run test:coverage # 运行覆盖率
```

### 后端测试

- 框架: pytest + pytest-asyncio
- 配置: `src-python/pytest.ini`

| 测试文件 | 测试内容 |
|---------|---------|
| `test_ai_chat_proxy_api.py` | AI 聊天代理 API |
| `test_detection_api_errors.py` | 检测 API 错误处理 |
| `test_pentest_agent_grounding.py` | 渗透 Agent 基础能力 |
| `test_pentest_agent_llm_resilience.py` | LLM 容错性 |
| `test_pentest_executor_fallback.py` | 执行器回退机制 |
| `test_pentest_llm_client_retry.py` | LLM 客户端重试 |
| `test_pentest_tool_registry.py` | 工具注册中心 |

```bash
cd src-python
pytest
```

---

## 12. CI/CD 流程

项目使用 GitHub Actions，工作流定义在 `.github/workflows/` 目录。

| 工作流 | 文件 | 说明 |
|--------|------|------|
| CI | `ci.yml` | 持续集成 (代码检查/测试) |
| Release | `release.yml` | 发布构建 |
| Benchmark Gate | `benchmark-gate.yml` | 性能基准门控 |

---

> 文档生成时间: 2026-05-10 | 基于 SDIT v0.55.0 代码库分析
