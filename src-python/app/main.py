"""LovelyRes Python 后端 - FastAPI 主应用入口

============================================================
作用
============================================================
此文件是 Python 后端的启动入口，负责:
1. 创建 FastAPI 应用实例
2. 管理应用生命周期（启动初始化、关闭清理）
3. 注册全局异常处理器（SSH连接错误、asyncssh协议错误）
4. 配置 CORS 跨域中间件（允许前端 5173/1420 端口访问）
5. 注册 REST API 路由（来自 app.routers.api）
6. 注册 WebSocket 端点（实时终端 I/O、事件推送通道）
7. 提供健康检查端点 (/health)

依赖关系:
  - fastapi>=0.115.0          -> FastAPI 框架，构建 HTTP REST API
  - uvicorn>=0.34.0           -> ASGI 服务器，通过 run.py 启动
  - asyncssh>=2.18.0          -> SSH 协议库，用于异常捕获和 WebSocket 终端
  - uvicorn[standard]         -> 支持 WebSocket 的 ASGI 服务器
  - app.routers.api           -> 路由模块，导入 router 和全局状态

被依赖:
  - run.py                    -> 通过 uvicorn.run("app.main:app") 启动本应用
  - 前端 Vue 应用             -> 通过 HTTP REST API (端口3001) 和 WebSocket 通信

架构说明:
  前端 (Vue3/Vite, 端口5173) --HTTP/WS--> 后端 (FastAPI, 端口3001) --SSH--> 目标服务器
                                        |
                                        +-- 本机文件系统 (设置读写、字体获取)

从 Rust Tauri 后端迁移到 Python FastAPI 后，原 Tauri 命令全部改为 HTTP API 端点。
WebSocket 用于实时终端（xterm.js）的输入输出流和事件推送（pong/theme-change等）。
"""

import asyncio
import json
from contextlib import asynccontextmanager

import asyncssh
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 从 routers/api.py 导入路由和共享状态
# router: 所有 /api/v1/* HTTP 端点
# init_state: 应用启动时初始化所有全局单例（SSHManager, SSHConnectionManager, AppSettings 等）
# _ssh_manager: SSH 核心管理器单例，用于 WebSocket 终端和健康检查
from app.routers.api import router, init_state, _ssh_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（FastAPI lifespan 上下文管理器）

    启动阶段:
      1. 调用 init_state() 初始化全局单例:
         - SSHManager: SSH 连接/命令执行/终端/SFTP
         - SSHConnectionManager: SSH 配置持久化与密码加密
         - WindowManager: 窗口管理（通过 WebSocket 通知前端）
         - AppSettings: 从磁盘加载应用设置 (settings.json)
      2. 打印启动日志

    关闭阶段:
      1. 清理所有终端会话
      2. 断开 SSH 连接
      3. 关闭 SFTP 客户端
      4. 打印关闭日志
    """
    # ===== 启动时初始化 =====
    init_state()
    print("LovelyRes Python 后端已启动")
    yield
    # ===== 关闭时清理 =====
    if _ssh_manager and _ssh_manager.is_connected():
        await _ssh_manager.disconnect()
    print("LovelyRes Python 后端已关闭")


# ===== FastAPI 应用实例 =====
# 创建 FastAPI 应用，设置元数据供 Swagger UI (/docs) 和 ReDoc (/redoc) 使用
app = FastAPI(
    title="LovelyRes API",
    description="LovelyRes - Linux 应急响应工具 Python 后端",
    version="0.55.0",
    lifespan=lifespan,
)


# ===== 全局异常处理器 =====

@app.exception_handler(ConnectionError)
async def handle_connection_error(_, exc: ConnectionError):
    """捕获 ConnectionError 异常（SSH未连接时抛出），返回 HTTP 400

    触发场景:
      - 在未建立 SSH 连接时调用 SFTP 文件操作
      - 在未建立 SSH 连接时执行远程命令
      - SSH 连接意外断开后的后续操作

    返回: JSON {"detail": "没有活动的 SSH 连接"}，HTTP 状态码 400
    """
    detail = str(exc).strip() or "没有活动的 SSH 连接"
    return JSONResponse(status_code=400, content={"detail": detail})


@app.exception_handler(asyncssh.Error)
async def handle_asyncssh_error(_, exc: asyncssh.Error):
    """捕获 asyncssh 协议异常（SFTP 错误、连接断开等），返回 HTTP 400

    触发场景:
      - SFTP 操作失败（文件不存在、权限不足、路径错误等）
      - SSH 连接被远程主机关闭
      - SSH 协议协商失败

    返回: JSON {"detail": "SSH 连接异常"}，HTTP 状态码 400
    """
    detail = str(exc).strip() or "SSH 连接异常"
    return JSONResponse(status_code=400, content={"detail": detail})


# ===== CORS 跨域中间件配置 =====
# CORS：与 allow_origins=["*"] 组合时不可启用 allow_credentials，否则浏览器会拒绝
#（ACAO 为 * 时不能带 Access-Control-Allow-Credentials: true），前端 fetch 表现为 Failed to fetch。
# 此配置允许任何前端来源（开发时 Vite 的 5173、生产时 Tauri WebView 的 1420 等）访问后端 API。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 注册 REST API 路由 =====
# 所有路由前缀为 /api/v1，由 app.routers.api 模块定义
# 包含: SSH连接管理、SFTP文件操作、安全检测、日志分析、主题设置、设备信息、AI代理等
app.include_router(router)


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/terminal/{terminal_id}")
async def websocket_terminal(websocket: WebSocket, terminal_id: str):
    """WebSocket 实时终端端点 — 前端 xterm.js 与远程 SSH PTY 之间的双向数据通道

    连接: 前端 Vue 组件 -> WebSocket (/ws/terminal/{id}) -> SSHManager 终端会话 -> 远程服务器 PTY

    工作流程:
      1. 前端 WebSocket 连接到此端点，传递唯一的 terminal_id
      2. 后端接受连接后，检查 SSH 是否已建立
      3. 通过 SSHManager.create_terminal_session() 在远程服务器上创建 PTY 伪终端
      4. 启动异步 output_task：持续从 SSH PTY stdout 读取数据，通过 WebSocket 推送给前端
      5. 主循环：接收前端通过 WebSocket 发来的键盘输入数据，写入 SSH PTY stdin
      6. WebSocket 断开时：取消 output_task，关闭终端会话

    依赖:
      - _ssh_manager (SSHManager): 全局 SSH 管理器单例
      - asyncssh: SSH PTY 创建与数据传输
      - asyncio: 异步任务管理（output_task）

    参数:
      terminal_id: 终端唯一标识符，前端 xterm.js 实例的 ID
    """
    await websocket.accept()
    print(f"WebSocket 终端连接: {terminal_id}")

    if not _ssh_manager or not _ssh_manager.is_connected():
        await websocket.close(code=1001, reason="没有活动的 SSH 连接")
        return

    # 在远程服务器上创建 PTY 伪终端会话（80列x24行）
    try:
        await _ssh_manager.create_terminal_session(terminal_id, 80, 24)
    except Exception as e:
        await websocket.close(code=1001, reason=str(e))
        return

    async def read_output():
        """异步任务：持续从 SSH PTY stdout 读取数据并推送到 WebSocket

        循环读取终端输出（每次最多4096字节），间隔10ms防止CPU空转。
        任何异常都会静默退出，由外层 finally 块负责清理。
        """
        try:
            while True:
                data = await _ssh_manager.read_terminal_output(terminal_id)
                if data:
                    await websocket.send_bytes(data)
                await asyncio.sleep(0.01)
        except Exception:
            pass

    # 启动输出读取任务（不阻塞主循环）
    output_task = asyncio.create_task(read_output())

    try:
        # 主循环：持续接收前端通过 WebSocket 发来的键盘输入
        while True:
            data = await websocket.receive_bytes()
            await _ssh_manager.send_terminal_input(terminal_id, data)
    except WebSocketDisconnect:
        print(f"WebSocket 终端断开: {terminal_id}")
    except Exception as e:
        print(f"WebSocket 终端错误: {e}")
    finally:
        output_task.cancel()
        await _ssh_manager.close_terminal_session(terminal_id)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket 事件推送通道 — 服务端向客户端推送应用级事件

    连接: 前端 Vue 应用 -> WebSocket (/ws/events) -> 后端事件通道

    用途:
      - 主题变更通知 (theme-changed)
      - 窗口操作通知 (window-minimize, window-close 等)
      - 心跳检测 (ping/pong)
      - 其他服务端主动推送的事件

    当前实现为简单的心跳响应（等待客户端发送 {"type":"ping"}，回复 {"type":"pong"}）。
    未来可扩展为真正的服务端主动推送（如连接状态变化通知、检测完成通知等）。
    """
    await websocket.accept()
    print("WebSocket 事件通道连接")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            event_type = msg.get("type", "")

            if event_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        print("WebSocket 事件通道断开")
    except Exception as e:
        print(f"WebSocket 事件通道错误: {e}")


# ==================== 健康检查端点 ====================

@app.get("/health")
async def health_check():
    """健康检查端点 — 供外部监控/负载均衡器检测后端服务存活状态

    连接: 外部监控系统 -> GET /health -> 返回服务状态 JSON

    返回字段:
      - status: "ok" 表示服务正常
      - service: 服务名称 "LovelyRes Python Backend"
      - version: 版本号
      - ssh_connected: 当前是否有活动的 SSH 连接

    GET /health (无需认证，无需参数)
    """
    return {
        "status": "ok",
        "service": "LovelyRes Python Backend",
        "version": "0.55.0",
        "ssh_connected": _ssh_manager.is_connected() if _ssh_manager else False,
    }
