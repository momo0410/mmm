# LovelyRes

LovelyRes 是一个面向 Linux 主机应急响应、安全检查和远程运维的跨平台工具。项目采用 **Vue 3 + TypeScript + Vite** 构建前端界面，使用 **Python FastAPI** 提供后端 API，并通过 SSH、SFTP、WebSocket 和 Agent 工作流完成远程主机连接、命令执行、日志分析、文件分析、安全检测与整改辅助。

> 当前项目版本：`0.55.0`

## 项目特点

- **跨平台前端界面**：基于 Vue 3、TypeScript、Vite，包含仪表盘、SSH 终端、SFTP 文件管理、AI 命令中心、Payloader 等功能页面。
- **Python FastAPI 后端**：统一承载 SSH/SFTP、系统检测、日志读取、文件分析、AI Agent、整改报告等 API。
- **SSH 实时终端**：通过 WebSocket 实现远程终端实时输入输出，支持独立终端页面。
- **SFTP 文件管理**：支持目录浏览、文件读写、上传下载、压缩解压、权限修改等操作。
- **安全检测能力**：覆盖端口扫描、用户审计、后门排查、进程分析、文件权限、SSH 审计、防火墙、资源检测、口令策略、PAM、SELinux、内核参数、系统更新、审计配置等场景。
- **日志与文件分析**：支持系统日志、journalctl、指定日志文件读取，以及独立文件安全分析。
- **AI Agent 工作流**：集成主机上下文构建、工具注册、技能系统、自动整改建议、整改报告和选中项执行能力。
- **多页面构建**：包含 `index.html`、`ssh-terminal.html`、`container-terminal.html` 等入口。

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite 6
- xterm.js
- @icon-park
- marked
- @tauri-apps/api
- vite-plugin-bundle-obfuscator

### 后端

- Python 3.8+
- FastAPI
- Uvicorn
- Pydantic v2
- asyncssh
- paramiko
- cryptography
- aiofiles
- WebSocket

## 目录结构

```text
.
├── index.html                         # 主页面入口
├── ssh-terminal.html                  # SSH 终端独立页面
├── container-terminal.html            # 容器终端独立页面
├── package.json                       # 前端依赖与脚本
├── vite.config.ts                     # Vite 多页面与代理配置
├── tsconfig.json                      # TypeScript 配置
├── public/                            # 静态资源
├── dist/                              # 构建输出目录
├── docs/                              # 文档资料
├── exp/                               # 实验/辅助资源
├── Payloader-main/                    # Payloader 相关资源
├── sync-backup/                       # 同步/合并备份目录
├── src/                               # 前端源码
│   ├── assets/                        # 前端资源
│   ├── components/                    # Vue 组件
│   ├── config/                        # API 适配、配置项
│   ├── css/                           # 基础样式
│   ├── styles/                        # 模块样式
│   ├── types/                         # 类型定义
│   └── modules/                       # 前端业务模块
│       ├── ai/                        # AI 命令中心与 Agent 服务
│       ├── api/                       # API 封装
│       ├── auth/                      # 用户/认证相关逻辑
│       ├── core/                      # 应用核心与状态管理
│       ├── crypto/                    # 加密相关逻辑
│       ├── detection/                 # 安全检测模块
│       ├── emergency/                 # 应急响应功能
│       ├── payloader/                 # Payload/工具库页面
│       ├── remote/                    # SFTP/远程文件管理
│       ├── settings/                  # 设置管理
│       ├── ssh/                       # SSH 连接管理
│       ├── system/                    # 系统信息
│       ├── ui/                        # UI 渲染器与导航
│       └── utils/                     # 工具函数
└── src-python/                        # Python FastAPI 后端
    ├── run.py                         # 后端启动入口
    ├── requirements.txt               # Python 依赖
    ├── tests/                         # 后端测试目录（223 个测试）
    └── app/
        ├── main.py                    # FastAPI 应用入口
        ├── routers/
        │   └── api.py                 # 主要 API 路由
        ├── models/                    # Pydantic/业务类型
        ├── services/                  # SSH、检测、日志、Agent 等服务
        │   └── agent/                 # Agent 工作流核心
        │       ├── application/       # AgentApplicationService（/api/v1/agent/run 入口）
        │       ├── planning/          # PlanBuilder（规划层）
        │       ├── execution_modes/   # 执行模式策略（ExternalWeb/HostRuntime/TargetRuntime/TargetViaSSH）
        │       ├── research/          # ResearchRouter（研究路由）
        │       ├── reporting/         # ReportBuilder（报告生成层）
        │       ├── orchestrator.py    # 编排器（薄化后仅保留流程编排）
        │       └── schemas.py         # 数据结构定义
        └── utils/                     # 加密、字体、系统工具
```

## 环境要求

- Node.js 18+
- npm 9+ 或兼容的包管理器
- Python 3.8+
- Windows、Linux 或 macOS
- 可访问目标 Linux 主机的 SSH 网络环境

推荐在开发环境中分别启动后端和前端：

- 后端默认监听：`http://127.0.0.1:3001`
- 前端开发服务器默认监听：`http://127.0.0.1:1420`
- Vite 已配置 `/api/v1` 代理到后端 `http://127.0.0.1:3001`

## 快速开始

### 方式一：使用启动脚本（Windows）

项目根目录双击 `start.bat` 或在终端执行：

```bash
start.bat
```

该脚本会自动：
- 检查 Python 和 Node.js 环境
- 安装缺失的依赖
- 释放占用端口
- 并行启动前后端服务
- 实时显示服务输出

> 需要 Windows Terminal 和 PowerShell 7

### 方式二：手动启动

#### 1. 安装前端依赖

```bash
npm install
```

#### 2. 安装 Python 后端依赖

```bash
cd src-python
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. 启动 Python 后端

在项目根目录执行：

```bash
npm run python-backend
```

或进入后端目录执行：

```bash
cd src-python
python run.py
```

启动后可访问健康检查：

```text
http://127.0.0.1:3001/health
```

#### 4. 启动前端开发服务

另开一个终端，在项目根目录执行：

```bash
npm run dev
```

访问：

```text
http://127.0.0.1:1420
```

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动 Vite 前端开发服务 |
| `npm run build` | 执行 TypeScript 类型检查并构建生产包 |
| `npm run python-backend` | 启动 Python FastAPI 后端 |
| `cd src-python && python run.py` | 直接启动后端 |
| `cd src-python && python -m pytest tests/ -v` | 运行后端测试 |
| `npx vitest` | 运行前端测试（Vitest） |

## 前后端通信

前端通过 HTTP API 与 FastAPI 后端通信，主要 API 前缀为：

```text
/api/v1
```

Vite 开发服务中已配置代理：

```ts
server: {
  port: 1420,
  strictPort: true,
  proxy: {
    "/api/v1": {
      target: "http://127.0.0.1:3001",
      changeOrigin: true,
    },
  },
}
```

实时通信使用 WebSocket：

| 地址 | 说明 |
| --- | --- |
| `/ws/terminal/{terminal_id}` | SSH 终端实时输入输出 |
| `/ws/events` | 后端事件通道 |

## 后端 API 能力概览

FastAPI 路由主要集中在 `src-python/app/routers/api.py`，核心能力包括：

### 窗口与设置

- 窗口最小化、最大化、关闭、打开开发工具
- 主题读取与切换
- 应用设置读取、保存、配置文件读写
- 系统字体列表
- 设备 UUID
- RSA 公钥

### SSH 连接

- 保存和读取 SSH 连接配置
- 密码加密/解密
- SSH 连接、测试连接、断开连接
- 直接连接模式
- 命令执行
- Dashboard、应急响应、安全检测专用命令执行
- 连接状态检测
- Shell 性能诊断
- 系统类型检测

### SSH 终端

- 创建终端会话
- 关闭单个或全部终端
- 发送终端输入
- 命令补全
- WebSocket 实时输出

### SFTP 文件操作

- 文件列表
- 文件读取/写入
- 上传/下载
- 创建目录
- 压缩/解压
- chmod 权限修改
- 文件详情
- 临时文件保存

### 安全检测

- 端口扫描
- 用户审计
- 后门检测
- 进程分析
- 文件权限检查
- SSH 审计
- 日志分析
- 防火墙检查
- CPU、内存、磁盘、网络测试
- 密码策略
- sudo 配置
- PAM 配置
- 账号锁定策略
- SELinux 状态
- 内核参数
- 系统更新
- 不必要服务
- 开机自启动服务
- audit 配置
- history 审计
- NTP/DNS 配置

### 日志与文件分析

- 系统日志读取
- journalctl 日志读取
- 日志文件列表
- 日志文件信息
- 文件安全分析
- 独立文件分析

### AI 与 Agent

- AI Web Research
- AI Chat Proxy
- Agent 任务执行
- Agent 上下文读取
- Agent 工具列表
- Agent 技能列表
- SSH/用户/防火墙/日志等快捷检查
- 主机快速研判
- 自动整改建议
- 整改报告生成
- 选中整改项执行

## 前端模块说明

### `src/modules/core`

应用核心逻辑、状态管理和主要应用类。旧代码中仍存在全局对象依赖，例如：

```ts
(window as any).app
```

开发新功能时需要注意不要破坏这些历史入口。

### `src/modules/ui`

导航、Dashboard、现代 UI 渲染器和页面渲染逻辑。新增 UI 前建议优先检查这里是否已有可复用渲染器。

### `src/modules/ai`

AI 命令中心、Agent 服务、Agent 类型定义等。该模块采用分层架构：

| 文件 | 职责 |
|------|------|
| `agentService.ts` | 薄 façade，对外兼容调用 |
| `agentClient.ts` | Transport/invoke 调用层 |
| `agentSettingsAccessor.ts` | Settings JSON 读取解析 |
| `agentTaskFactory.ts` | 任务 payload 构造 |
| `agentDebugLogger.ts` | Debug 日志输出 |
| `agentTypes.ts` | 类型定义 |

该模块负责将用户输入转为后端 Agent 请求，并渲染执行过程、结果、整改建议等内容。

### `src/modules/remote`

SFTP 文件管理、远程文件操作、上传下载和文件详情能力。

### `src/modules/ssh`

SSH 连接、终端会话、命令执行等前端管理逻辑。

### `src/modules/payloader`

Payload、工具命令、Web/内网场景相关页面与数据。

### `src/config`

统一 API 适配、Python API 配置和前后端调用桥接逻辑。前端调用后端时优先通过这里的适配层。

## 配置说明

### 后端地址

开发环境下前端通过 Vite 代理访问后端，因此通常不需要在前端手动写死后端地址。默认配置：

```text
前端：http://127.0.0.1:1420
后端：http://127.0.0.1:3001
API ：/api/v1
```

### CORS

后端 `src-python/app/main.py` 当前允许所有来源访问：

```py
allow_origins=["*"]
allow_credentials=False
```

如用于生产环境，建议按实际部署域名收紧 CORS。

### 构建混淆

`vite.config.ts` 中配置了 `vite-plugin-bundle-obfuscator`，仅在生产构建时启用，用于一定程度降低前端产物可读性。

## 构建生产版本

```bash
npm run build
```

构建输出目录：

```text
dist/
```

构建包含多个入口：

- `index.html`
- `ssh-terminal.html`
- `container-terminal.html`

> 注意：当前仓库可能存在历史 TypeScript 类型问题。如果构建失败，请先根据 `vue-tsc` 输出修复类型错误，再重新执行构建。

## 测试

### 后端测试

当前后端已有 223 个 pytest 测试，覆盖 Agent 工作流核心模块：

```bash
cd src-python
python -m pytest tests/ -v
```

测试结果：**223 passed, 0 failed**

#### 已覆盖模块

| 模块 | 测试文件 | 测试数 |
|------|----------|--------|
| PlanBuilder | test_plan_builder.py | 4 |
| AgentApplicationService | test_agent_application_service.py | 8 |
| Agent API 契约 | test_agent_api_contract.py | 2 |
| Execution Mode Factory | test_execution_mode_factory.py | 4 |
| Execution Mode Strategies | test_execution_mode_strategies.py | 17 |
| Research Router | test_research_router_integration.py | 11 |
| Orchestrator Strategy Integration | test_orchestrator_execution_mode_integration.py | 1 |
| ReportBuilder | test_report_builder.py | 9 |
| Finding Normalizer | test_finding_normalizer.py | 9 |
| Remediation Report Builder | test_remediation_report_builder.py | 4 |
| Summary Builder | test_summary_builder.py | 7 |
| Final Status Resolver | test_final_status_resolver.py | 7 |
| Reporting Module (集成) | test_reporting_module.py | 20 |
| Orchestrator Ephemeral Skills | test_orchestrator_ephemeral_skills.py | 14 |
| Orchestrator Policy Integration | test_orchestrator_policy_integration.py | 8 |
| Auto Remediation Dynamic Steps | test_auto_remediation_dynamic_steps.py | 15 |

#### 运行方式

```bash
# 运行全部测试
cd src-python
python -m pytest tests/ -v

# 运行指定模块测试
python -m pytest tests/test_report_builder.py -v

# 运行带覆盖率报告
python -m pytest tests/ --cov=app/services/agent
```

### 前端测试

项目使用 Vitest + Vue Test Utils 进行前端测试：

```bash
npx vitest
```

或运行单次测试：

```bash
npx vitest tests/agentService.test.ts
```

#### 已覆盖模块

| 模块 | 测试文件 | 测试数 |
|------|----------|--------|
| AgentClient | agentClient.test.ts | - |
| AgentService | agentService.test.ts | - |
| AgentTaskFactory | agentTaskFactory.test.ts | - |

后续建议：

- 增加更多 UI 组件测试
- 后端增加 SSH/SFTP/Agent 集成测试
- 为 PolicyGuard 增加更多边界测试

## 开发规范

### 前端

- 使用 Vue 3 Composition API 和 TypeScript。
- 新增 Vue 组件建议使用 `<script setup lang="ts">`。
- API 调用优先走 `src/config` 下的统一适配层。
- 新功能 UI 优先复用 `src/modules/ui` 中已有渲染器和布局。
- 尽量避免新增 `any`，确实需要时应控制作用域。
- 注意历史代码中存在手动 DOM 操作和全局 `window` 对象依赖。

### 后端

- 使用 FastAPI + Pydantic。
- SSH 相关逻辑优先放在 `src-python/app/services/`。
- API 路由集中维护在 `src-python/app/routers/api.py`。
- 所有外部输入都应进行校验，错误信息避免泄露敏感信息。
- 异步逻辑优先使用 `async/await`。

### Git 与生成文件

`.gitignore` 当前忽略 Python 字节码缓存：

```gitignore
__pycache__/
*.py[cod]
*$py.class
```

建议不要提交以下类型文件：

- `node_modules/`
- `.env`
- 私钥、证书、账号密码
- Python `__pycache__`
- 临时日志
- 本地 IDE 缓存

## 安全注意事项

- 不要将 SSH 密码、私钥、API Key、LLM Token、生产配置提交到仓库。
- 对远程命令执行能力保持谨慎，特别是 Agent 自动整改和选中整改项执行功能。
- 生产环境应限制 CORS、鉴权、日志敏感信息输出和可访问的后端地址。
- SFTP 写文件、chmod、压缩/解压等操作建议在 UI 层加入二次确认。
- AI 生成的整改建议应经过人工确认后再执行。

## 常见问题

### 1. 前端页面报 `Failed to fetch`

请确认 Python 后端已经启动，并且监听在：

```text
http://127.0.0.1:3001
```

同时确认前端开发服务通过 `npm run dev` 启动，Vite 代理正常工作。

### 2. WebSocket 终端无法连接

请先在应用中建立有效 SSH 连接。后端的终端 WebSocket 依赖当前活动 SSH 会话。

### 3. SSH 连接成功但页面信息不刷新

可切换 Dashboard、系统信息或 AI 命令中心页面触发刷新。如果仍异常，请检查浏览器控制台和后端日志。

### 4. `npm run build` 失败

构建命令会先运行 `vue-tsc --noEmit`，因此 TypeScript 类型错误会阻止构建。请根据输出逐项修复。

### 5. Python 依赖安装失败

建议确认 Python 版本、pip 版本和网络环境。必要时先升级 pip：

```bash
python -m pip install --upgrade pip
```

### 6. Windows PowerShell 无法激活虚拟环境

如果执行 `Activate.ps1` 被策略阻止，可临时调整当前进程策略：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

### Agent 架构（四步重构后）

后端 Agent 工作流经过四步重构后，已形成清晰的分层架构：

```
┌─────────────────────────────────────────────────────────┐
│ API 入口层                                               │
│ AgentApplicationService (/api/v1/agent/run)              │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│ 编排层                                                    │
│ orchestrator.py (仅保留流程编排，不再承担具体实现)          │
│ ├── ResearchRouter (独立研究路由)                         │
│ └── ReportBuilder (独立报告生成)                          │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│ 策略层                                                    │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│ │ ExternalWeb  │ │ HostRuntime  │ │ TargetRuntime    │  │
│ └──────────────┘ └──────────────┘ └──────────────────┘  │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ TargetViaSSH                                         │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### 第一步：PlanBuilder 抽出

- `PlanBuilder` 从 orchestrator 独立，负责 PlannerOutput → Plan 转换
- `AgentApplicationService` 接管 `/api/v1/agent/run`，提供 disable/error/run 三种响应
- 保持 `/api/v1/agent/run` 契约不变

#### 第二步：执行模式策略化

- `execution_modes/` 目录引入策略模式：
  - `ExternalWebStrategy` - 外部 Web 研究模式
  - `HostRuntimeStrategy` - 主机运行时模式
  - `TargetRuntimeStrategy` - 目标运行时模式
  - `TargetViaSSHStrategy` - SSH 远程目标模式
- `ResearchRouter` 独立，直接调用各 research service
- orchestrator.run() 使用 strategy 主路径，不再有大段 mode-specific if/elif

#### 第三步：ReportBuilder 抽出

- `reporting/` 目录包含：
  - `report_builder.py` - 报告构建主入口
  - `finding_normalizer.py` - finding 标准化与去重
  - `remediation_report_builder.py` - 修复报告生成
  - `summary_builder.py` - 摘要构建
  - `final_status_resolver.py` - 最终状态判定
  - `traces_builder.py` - 追踪构建
- orchestrator.py 仅保留薄兼容入口，不再承担报告生成细节

#### 第四步：前端 agentService.ts 分层

- `agentService.ts` 从 359 行精简到 137 行（薄 façade）
- 新增文件：
  - `agentClient.ts` - Transport/invoke 调用层
  - `agentSettingsAccessor.ts` - Settings JSON 读取解析
  - `agentTaskFactory.ts` - 任务 payload 构造
  - `agentDebugLogger.ts` - Debug 日志输出
- 对外调用方式完全兼容，UI 层无需修改

## 版本与许可证

- 项目版本：`0.56.0`
- 许可证文件：`LICENSE`

## 维护建议

- 将构建产物和缓存文件从版本控制中彻底清理。
- 为前端核心模块补充类型约束，减少 `window as any` 使用。
- 为 SSH/SFTP/Agent 能力增加自动化测试。
- 拆分过大的渲染器文件，逐步迁移到 Vue 组件。
- 将后端 API 文档通过 FastAPI OpenAPI/Swagger 作为开发入口。

# mmm
