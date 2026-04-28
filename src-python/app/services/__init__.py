"""服务层包 - 核心业务逻辑

子模块:
  ssh_manager                 - SSH 连接/终端/SFTP 核心管理器 (依赖: asyncssh>=2.18.0)
  ssh_connection_manager      - SSH 连接配置持久化与 AES-256-GCM 加密 (依赖: cryptography>=43.0.0)
  detection_manager           - 安全基线检测与应急响应检查 (依赖: app.services.ssh_manager)
  file_analysis               - 远程文件安全分析 (依赖: app.services.ssh_manager)
  log_analysis                - 远程系统日志查看与分析 (依赖: app.services.ssh_manager)
  settings                    - 应用设置持久化 (依赖: pydantic>=2.10.0)
  theme_manager               - 主题配色管理 (纯内存，无外部依赖)
  window_manager              - 窗口状态管理 (纯内存，通过 WebSocket 事件通知前端)
  device_info                 - 本机设备信息获取 (依赖: platform, subprocess)
"""
