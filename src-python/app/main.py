import asyncio
import json
from contextlib import asynccontextmanager
import asyncssh
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers.api import router, init_state, _ssh_manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_state()
    print("LovelyRes Python 后端已启动")
    yield
    if _ssh_manager and _ssh_manager.is_connected():
        await _ssh_manager.disconnect()
    print("LovelyRes Python 后端已关闭")
app = FastAPI(
    title="LovelyRes API",
    description="LovelyRes - Linux 应急响应工具 Python 后端",
    version="0.55.0",
    lifespan=lifespan,
)
@app.exception_handler(ConnectionError)
async def handle_connection_error(_, exc: ConnectionError):
    detail = str(exc).strip() or "没有活动的 SSH 连接"
    return JSONResponse(status_code=400, content={"detail": detail})
@app.exception_handler(asyncssh.Error)
async def handle_asyncssh_error(_, exc: asyncssh.Error):
    detail = str(exc).strip() or "SSH 连接异常"
    return JSONResponse(status_code=400, content={"detail": detail})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
@app.websocket("/ws/terminal/{terminal_id}")
async def websocket_terminal(websocket: WebSocket, terminal_id: str):
    await websocket.accept()
    print(f"WebSocket 终端连接: {terminal_id}")
    if not _ssh_manager or not _ssh_manager.is_connected():
        await websocket.close(code=1001, reason="没有活动的 SSH 连接")
        return
    try:
        await _ssh_manager.create_terminal_session(terminal_id, 80, 24)
    except Exception as e:
        await websocket.close(code=1001, reason=str(e))
        return
    async def read_output():
        try:
            while True:
                data = await _ssh_manager.read_terminal_output(terminal_id)
                if data:
                    await websocket.send_bytes(data)
                await asyncio.sleep(0.01)
        except Exception:
            pass
    output_task = asyncio.create_task(read_output())
    try:
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
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "LovelyRes Python Backend",
        "version": "0.55.0",
        "ssh_connected": _ssh_manager.is_connected() if _ssh_manager else False,
    }