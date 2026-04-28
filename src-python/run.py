"""
LovelyRes Python 后端启动入口脚本。

=== 用途 ===

该文件是 Python 后端的唯一启动入口。执行方式：

    python src-python/run.py

或直接在当前目录下：

    python run.py

=== 与 uvicorn 及 app.main 的关系 ===

uvicorn 是一个基于 asyncio 的 ASGI 服务器，用于托管 FastAPI 应用。
本脚本通过 uvicorn.run() 启动 app.main 模块中的 FastAPI 实例（模块路径 "app.main:app"）。

- app.main 模块（src-python/app/main.py）创建 FastAPI() 实例并注册路由
- 该实例的变量名为 "app"，uvicorn 通过 "app.main:app" 字符串引用定位

=== 前端连接方式 ===

前端开发服务器（通常为 Vite / Next.js dev server）运行在 localhost:3000，
后端 API 运行在 localhost:3001。前端的 API 请求通过代理或直接配置 baseURL
指向 http://localhost:3001/api/v1/... 与后端通信。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        # === uvicorn.run() 参数说明 ===
        # app="app.main:app"
        #     FastAPI 应用实例的导入路径。
        #     "app.main" = src-python/app/main.py 模块
        #     ":app"    = 该模块中名为 "app" 的 FastAPI() 实例
        "app.main:app",
        # host="127.0.0.1"
        #     绑定本地回环地址，仅允许本机访问。
        #     如需局域网内其他设备访问，可改为 "0.0.0.0"。
        host="127.0.0.1",
        # port=3001
        #     HTTP 服务监听端口。
        #     前端开发服务器默认在 3000，此处用 3001 避免端口冲突。
        port=3001,
        # reload=True
        #     开启热重载：当 src-python/ 下的 .py 文件发生变更时，
        #     uvicorn 自动重启服务，无需手动停止/启动。
        #     生产环境应设为 False。
        reload=True,
        # log_level="info"
        #     日志级别为 info，输出请求路径、状态码等基本信息。
        #     调试时可改为 "debug" 获取更详细的日志。
        log_level="info",
    )
