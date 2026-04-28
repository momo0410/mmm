"""路由包 - FastAPI API 路由定义

依赖: fastapi>=0.115.0, app.services.*, app.models.*
连接: 被 app.main.py 注册到 FastAPI 应用实例
作用: 定义所有 HTTP REST API 端点 (前缀 /api/v1)，将前端请求转发到服务层
"""
