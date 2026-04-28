"""LovelyRes Python 后端应用程序包

============================================================
架构概览
============================================================
此包是 LovelyRes（Linux 应急响应工具）的 Python 后端服务。

前端: Vue 3 + Vite + TypeScript (src/ 目录)
后端: FastAPI + uvicorn 异步 HTTP 服务器 (src-python/ 目录)
通信: 前端通过 HTTP REST API (端口3001) 和 WebSocket 与后端交互
SSH: 后端通过 asyncssh 连接到目标 Linux 服务器执行应急响应检测命令

依赖链:
  app.main        -> FastAPI 应用入口，管理生命周期
  app.routers.api -> HTTP API 路由，将前端请求映射到服务层
  app.services.*  -> 业务逻辑服务层（SSH管理、安全检测、日志分析等）
  app.models.*    -> Pydantic 数据模型，用于请求/响应序列化与验证
  app.utils.*     -> 工具模块（RSA加密、系统字体获取）

从 Rust Tauri 后端迁移至 Python FastAPI，原 Rust 代码位于项目根目录的
src-tauri/ 中（已废弃），仅保留 src/ 中的 Vue 前端代码。
"""
