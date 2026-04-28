"""
LovelyRes 类型定义 —— 从 Rust types.rs 迁移到 Python Pydantic 模型

================================================================================
文件概述 / 架构角色
================================================================================

本文件是整个 LovelyRes 后端的**数据契约层（Data Contract Layer）**，定义了系统
中所有传输和持久化的数据结构。它处于架构的底层，不依赖任何项目内模块，仅依赖
外部三方库（pydantic、uuid、datetime 等），是整个后端的数据基石。

架构层次位置：
    ┌─────────────────────────────────────────┐
    │  app/routers/api.py  (FastAPI 路由层)   │
    │  接收 HTTP 请求，使用本文件类型做验证   │
    └──────────────┬──────────────────────────┘
                   │ 导入使用
    ┌──────────────▼──────────────────────────┐
    │  app/services/*.py  (业务逻辑层)        │
    │  ssh_manager / detection_manager /      │
    │  log_analysis / file_analysis 等        │
    └──────────────┬──────────────────────────┘
                   │ 导入使用
    ┌──────────────▼──────────────────────────┐
    │  app/models/types.py  (当前文件)        │
    │  数据契约层 —— 所有 Pydantic 模型定义   │
    └──────────────┬──────────────────────────┘
                   │ 依赖
    ┌──────────────▼──────────────────────────┐
    │  外部依赖: pydantic, uuid, datetime,    │
    │           typing, enum                  │
    └─────────────────────────────────────────┘

依赖链详细：
  - 上游（谁依赖本文件）：
      * app.routers.api —— 将所有模型用于 FastAPI 路由的请求体验证和响应序列化
      * app.services.ssh_manager —— SSH 连接管理、终端输出、SFTP 文件操作
      * app.services.ssh_connection_manager —— SSH 连接池管理
      * app.services.detection_manager —— 所有安全检测结果的类型定义
      * app.services.log_analysis —— 日志分析结果类型
      * app.services.file_analysis —— 文件安全分析结果类型
      * app.services.device_info —— 设备信息类型
      * tests/* —— 单元测试和集成测试

  - 下游（本文件依赖谁）：
      * pydantic >= 2.x —— 提供 BaseModel、Field 等基类和验证工具
      * uuid —— 为所有持久化对象生成全局唯一 ID
      * datetime —— 时间戳字段
      * typing —— Optional、List、Dict、Any 等类型标注
      * enum —— 枚举类型（虽然当前文件未直接使用 Enum 类，但 import 了以备扩展）

  - 对应 Rust 端：
      * 本文件是从 Rust src-tauri/src/models/types.rs 迁移而来，保持了相同的
        数据结构命名和语义，确保前后端数据契约一致。

外部依赖清单：
  - pydantic  (BaseModel, Field)       — 数据模型基类、字段定义与验证
  - uuid       (uuid4)                 — 生成全局唯一标识符（用于 id 字段）
  - datetime   (datetime)              — 时间戳类型（Python 标准库）
  - enum       (Enum)                  — 枚举基类（Python 标准库，用于后续扩展）
  - typing     (Any, Dict, List, Optional) — 类型标注（Python 标准库）

================================================================================
设计原则
================================================================================

1. 每类模型对应一个现实中的业务概念（SSH 连接、检测结果、日志条目等）
2. 所有持久化的模型都有 id 字段，通过 uuid4 自动生成
3. 时间戳字段统一使用 datetime.utcnow 作为默认工厂函数
4. 类型标注完整，支持 Pydantic 的自动验证和 FastAPI 的自动 OpenAPI 文档生成
5. 与 Rust 端 types.rs 保持一对一的对应关系
"""

# ============================================================================
# 外部依赖导入
# ============================================================================

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ==================== SSH 相关类型 ====================
# 以下类型用于 SSH 连接配置、账号管理与命令定义。
# 被 app.services.ssh_manager、app.services.ssh_connection_manager 和
# app.routers.api 导入使用。


class SSHAccountCredential(BaseModel):
    """SSH 账号凭证模型

    表示一个 SSH 连接下的单个账号认证信息，支持三种认证方式：
      - password: 密码认证（默认）
      - key: 密钥文件认证
      - certificate: 证书认证

    本类被 SSHConnection.accounts 列表引用，实现多账号管理功能。
    当用户在一个 SSHConnection 中配置多个登录账号时，每个账号
    对应一个本类的实例。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）
    使用方:
      - SSHConnection.accounts —— 存储多个账号凭证
      - SSHConnection.migrate_legacy_account() —— 从旧数据迁移时创建实例
      - SSHConnection.get_active_account() / get_default_account() —— 检索账号
    """

    # 登录用户名
    username: str
    # 认证类型：password（密码）/ key（密钥）/ certificate（证书）
    auth_type: str = "password"
    # 加密后的密码（仅 password 模式使用）
    encrypted_password: Optional[str] = None
    # 私钥文件路径（仅 key 模式使用）
    key_path: Optional[str] = None
    # 密钥口令（仅 key 模式使用，用于解密受保护的私钥）
    key_passphrase: Optional[str] = None
    # 证书文件路径（仅 certificate 模式使用）
    certificate_path: Optional[str] = None
    # 是否为该连接的默认账号（多账号时只有一个为 True）
    is_default: bool = True
    # 账号描述（如 "生产环境账号"、"备份账号" 等）
    description: Optional[str] = None


class SSHConnection(BaseModel):
    """SSH 连接配置模型

    表示一个 SSH 连接的完整配置，包括目标主机、端口、认证信息等。
    支持单账号（向后兼容）和多账号两种模式。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）
    使用方:
      - app.services.ssh_connection_manager —— 连接池管理，创建/维护连接
      - app.services.ssh_manager —— SSH 核心操作，执行命令和文件传输
      - app.routers.api —— FastAPI 路由，处理前端 CRUD 请求
      - app.services.settings —— 持久化存储连接配置
    """

    # 连接唯一标识，使用 uuid4 自动生成
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 连接显示名称
    name: str = "新连接"
    # 目标主机地址（IP 或域名）
    host: str = "localhost"
    # SSH 端口，默认 22
    port: int = 22

    # ======== 单账号字段（向后兼容，旧版使用） ========
    username: str = "root"
    auth_type: str = "password"
    encrypted_password: Optional[str] = None
    key_path: Optional[str] = None
    key_passphrase: Optional[str] = None
    certificate_path: Optional[str] = None

    # ======== 多账号支持 ========
    # 多账号凭证列表，每个元素为一个 SSHAccountCredential
    accounts: List[SSHAccountCredential] = Field(default_factory=list)
    # 当前活动账号的用户名（与某个 SSHAccountCredential.username 对应）
    active_account: Optional[str] = None

    # ======== 连接状态 ========
    # 当前是否已建立连接（运行态状态，不持久化）
    is_connected: bool = False
    # 上次连接成功的时间
    last_connected: Optional[datetime] = None
    # 用户自定义标签
    tags: Optional[List[str]] = None

    def migrate_legacy_account(self):
        """将旧的单账号数据迁移到多账号模式

        当从旧版配置文件加载数据时，旧数据只使用单账号字段
        （username、auth_type 等），而新版使用 accounts 列表。
        本方法检测如果 accounts 为空但旧字段有值，则自动创建一个
        默认的 SSHAccountCredential 并加入 accounts 列表。

        调用方:
          - app.services.ssh_connection_manager —— 加载连接配置时自动调用
          - app.routers.api —— 创建/更新连接时可能触发
        """
        if not self.accounts and self.username:
            account = SSHAccountCredential(
                username=self.username,
                auth_type=self.auth_type,
                encrypted_password=self.encrypted_password,
                key_path=self.key_path,
                key_passphrase=self.key_passphrase,
                certificate_path=self.certificate_path,
                is_default=True,
                description="默认账号（从旧数据迁移）",
            )
            self.accounts.append(account)
            self.active_account = self.username

    def get_default_account(self) -> Optional[SSHAccountCredential]:
        """获取默认账号

        遍历 accounts 列表，返回第一个 is_default=True 的账号。
        如果没有设置默认账号则返回 None。

        调用方:
          - SSHConnection.get_active_account() —— 当未设置 active_account 时的回退逻辑
          - app.services.ssh_manager —— 建立连接时选择认证信息
          - app.routers.api —— 展示当前连接使用的账号
        """
        for a in self.accounts:
            if a.is_default:
                return a
        return None

    def get_active_account(self) -> Optional[SSHAccountCredential]:
        """获取当前活动账号

        优先返回 active_account 对应的账号，如果 active_account 未设置
        或找不到匹配账号，则回退到 get_default_account()。

        调用方:
          - app.services.ssh_manager —— 获取当前连接使用的认证凭据
          - app.routers.api —— 获取当前活跃账号信息返回给前端
        """
        if self.active_account:
            for a in self.accounts:
                if a.username == self.active_account:
                    return a
        return self.get_default_account()

    def set_active_account(self, username: str) -> bool:
        """设置活动账号

        将指定 username 的账号设为当前活动账号（仅修改 active_account 字段的引用，
        不修改 SSHAccountCredential 对象的 is_default 属性）。

        参数:
          username: 要激活的账号用户名

        返回:
          bool: 成功找到并设置返回 True，否则返回 False

        调用方:
          - app.routers.api —— 用户在前端切换活动账号时调用
          - app.services.ssh_manager —— 需要切换认证凭据时调用
        """
        for a in self.accounts:
            if a.username == username:
                self.active_account = username
                return True
        return False


class SSHCommand(BaseModel):
    """SSH 命令配置模型

    表示一条预定义的 SSH 命令模板，用户可以创建、收藏和管理常用命令。
    用于快速执行功能，避免重复输入。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）
    使用方:
      - app.routers.api —— 命令的 CRUD 操作（创建、读取、更新、删除）
      - app.services.ssh_manager —— 执行命令时引用
      - app.services.settings —— 持久化存储命令配置
    """

    # 命令唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 命令显示名称
    name: str = "新命令"
    # 实际执行的命令文本
    command: str = "echo 'Hello World'"
    # 命令描述
    description: str = "示例命令"
    # 命令分类（如 "系统信息"、"安全检测"、"网络" 等）
    category: str = "其他"
    # 是否收藏（收藏的命令在前端优先展示）
    favorite: bool = False


# ==================== 通用类型 ====================
# 以下类型是系统级别的通用数据结构，被多个模块共享使用。
# 包括通知、终端会话、文件传输、监控、日志、API 响应等。


class AppNotification(BaseModel):
    """应用通知模型

    表示系统产生的一条应用级通知，用于前端展示提醒信息。
    支持四种类型：info（信息）、success（成功）、warning（警告）、error（错误）。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）、datetime（时间戳）
    使用方:
      - app.routers.api —— 向前端推送通知数据
      - app.services.* —— 各服务产生通知时实例化
    """

    # 通知唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 通知标题
    title: str = ""
    # 通知正文
    message: str = ""
    # 通知类型：info / success / warning / error
    notification_type: str = "info"
    # 通知产生时间
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # 是否已读
    read: bool = False


class TerminalSession(BaseModel):
    """终端会话模型

    表示一个活跃的 SSH 终端会话。每个 SSH 连接可以有多个终端会话。
    会话绑定到特定的 connection_id，用于标识该终端属于哪个 SSH 连接。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）、datetime（时间戳）
    使用方:
      - app.services.ssh_manager —— 创建、管理和销毁终端会话
      - app.routers.api —— 前端展示和管理终端标签页
    """

    # 会话唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 会话显示名称（通常显示在终端标签页上）
    name: str = ""
    # 关联的 SSH 连接 ID，引用 SSHConnection.id
    connection_id: str = ""
    # 会话创建时间
    created: datetime = Field(default_factory=datetime.utcnow)
    # 最后活动时间（用于检测空闲会话）
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    # 会话是否活跃
    is_active: bool = True


class FileTransferTask(BaseModel):
    """文件传输任务模型

    表示一个文件上传或下载任务。支持进度跟踪和状态管理。
    状态流转：pending → in_progress → completed / failed

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）、datetime（时间戳）
    使用方:
      - app.services.ssh_manager —— SFTP 文件传输时创建和更新任务状态
      - app.routers.api —— 前端展示文件传输进度
    """

    # 任务唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 源文件路径
    source_path: str = ""
    # 目标文件路径
    destination_path: str = ""
    # 传输类型：upload（上传）/ download（下载）
    transfer_type: str = "upload"
    # 任务状态：pending / in_progress / completed / failed
    status: str = "pending"
    # 传输进度（0.0 ~ 1.0）
    progress: float = 0.0
    # 文件总大小（字节）
    file_size: int = 0
    # 已传输大小（字节）
    transferred_size: int = 0
    # 任务创建时间
    created: datetime = Field(default_factory=datetime.utcnow)
    # 任务完成时间
    completed: Optional[datetime] = None
    # 错误消息（失败时填充）
    error_message: Optional[str] = None


class SystemMonitorData(BaseModel):
    """系统监控数据模型

    表示一次系统资源采样的快照数据，包括 CPU、内存、磁盘、网络等指标。
    通常由远程主机的监控命令（如 top、free、df、netstat）产生。

    外部依赖: pydantic.BaseModel（基类）、datetime（时间戳）
    使用方:
      - app.services.ssh_manager —— 执行监控命令后解析输出并实例化
      - app.routers.api —— 前端监控面板展示系统状态
    """

    # 采样时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # CPU 使用率（百分比，0~100）
    cpu_usage: float = 0.0
    # 内存使用率（百分比，0~100）
    memory_usage: float = 0.0
    # 磁盘使用率（百分比，0~100）
    disk_usage: float = 0.0
    # 网络入站流量（字节）
    network_in: int = 0
    # 网络出站流量（字节）
    network_out: int = 0
    # 系统负载均值（1分钟、5分钟、15分钟）
    load_average: List[float] = Field(default_factory=list)
    # 当前进程总数
    process_count: int = 0


class LogEntry(BaseModel):
    """日志条目模型

    表示后端系统产生的一条结构化日志记录。用于前端日志查看器。
    支持自定义元数据字典，可扩展携带额外信息。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）、datetime（时间戳）
    使用方:
      - app.routers.api —— 日志查询接口返回
      - app.services.* —— 各服务产生日志时实例化
    """

    # 日志唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 日志时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # 日志级别：debug / info / warning / error / critical
    level: str = "info"
    # 日志来源模块（如 "ssh_manager", "detection_manager"）
    source: str = ""
    # 日志消息正文
    message: str = ""
    # 附加元数据（可携带任意结构化信息）
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    """API 响应包装器模型

    统一的 API 响应格式，所有 FastAPI 路由的返回值都应包装为此格式。
    提供 ok() 和 err() 两个工厂类方法简化构造。

    外部依赖: pydantic.BaseModel（基类）、datetime（时间戳）
    使用方:
      - app.routers.api —— 所有 API 端点的最终返回值格式
      - tests/* —— 测试断言中检查响应格式
    """

    # 请求是否成功
    success: bool = True
    # 响应数据（成功时填充）
    data: Optional[Any] = None
    # 错误消息（失败时填充）
    error: Optional[str] = None
    # 响应时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def ok(cls, data: Any = None) -> "ApiResponse":
        """创建成功响应

        参数:
          data: 要返回的数据（任意类型）

        返回:
          ApiResponse 实例，success=True

        调用方:
          - app.routers.api 中所有成功返回的端点
          - 各服务层内部方法需要返回统一响应时
        """
        return cls(success=True, data=data)

    @classmethod
    def err(cls, error: str) -> "ApiResponse":
        """创建错误响应

        参数:
          error: 错误描述文字

        返回:
          ApiResponse 实例，success=False

        调用方:
          - app.routers.api 中所有异常处理和错误返回
          - 各服务层需要上报错误时
        """
        return cls(success=False, error=error)


class PaginationParams(BaseModel):
    """分页参数模型

    表示前端传来的分页请求参数，用于控制列表接口的返回范围。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.routers.api —— 各列表端点的查询参数（FastAPI Query 依赖注入）
    """

    # 当前页码（从 1 开始）
    page: int = 1
    # 每页条数
    page_size: int = 20
    # 排序字段名
    sort_by: Optional[str] = None
    # 排序方向：asc（升序）或 desc（降序）
    sort_order: Optional[str] = "asc"


class PaginatedResponse(BaseModel):
    """分页响应模型

    表示分页列表接口的返回格式，包含数据列表和分页元信息。

    外部依赖: pydantic.BaseModel（基类）、math（在 create 方法中计算总页数）
    使用方:
      - app.routers.api —— 所有分页列表端点的返回格式
    """

    # 当前页的数据列表
    items: List[Any] = Field(default_factory=list)
    # 数据总条数
    total: int = 0
    # 当前页码
    page: int = 1
    # 每页条数
    page_size: int = 20
    # 总页数（根据 total 和 page_size 计算）
    total_pages: int = 0

    @classmethod
    def create(
        cls, items: list, total: int, page: int, page_size: int
    ) -> "PaginatedResponse":
        """创建分页响应实例

        根据给定的数据列表和分页元信息构造响应，自动计算总页数。

        参数:
          items: 当前页的数据列表
          total: 数据总条数
          page: 当前页码
          page_size: 每页条数

        返回:
          PaginatedResponse 实例，包含自动计算的总页数

        调用方:
          - app.routers.api 中各分页端点（如 SSH 连接列表、日志列表等）
          - app.services.* 中需要返回分页数据的内部方法
        """
        import math

        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class SearchFilter(BaseModel):
    """搜索过滤器模型

    表示前端传来的搜索过滤条件，支持多维度组合过滤。
    用于在列表接口中筛选数据。

    外部依赖: pydantic.BaseModel（基类）、datetime（日期范围）
    使用方:
      - app.routers.api —— 搜索端点的查询参数
      - app.services.* —— 各服务层的过滤逻辑使用此模型
    """

    # 全文搜索关键词
    query: Optional[str] = None
    # 分类过滤
    category: Optional[str] = None
    # 状态过滤
    status: Optional[str] = None
    # 起始时间过滤
    date_from: Optional[datetime] = None
    # 结束时间过滤
    date_to: Optional[datetime] = None
    # 标签过滤（可多选）
    tags: Optional[List[str]] = None


class AppEvent(BaseModel):
    """应用事件模型

    表示系统内部产生的一个事件，用于事件驱动架构中的消息传递。
    可用于 WebSocket 推送、事件总线等场景。

    外部依赖: pydantic.BaseModel（基类）、uuid（id 生成）、datetime（时间戳）
    使用方:
      - app.routers.api —— 通过 WebSocket 或 SSE 向前端推送事件
      - app.services.* —— 各服务产生事件时实例化
    """

    # 事件唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # 事件类型（如 "connection_lost", "detection_complete" 等）
    event_type: str = ""
    # 事件来源模块
    source: str = ""
    # 事件携带的数据（任意类型）
    data: Any = None
    # 事件产生时间
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BashEnvironmentInfo(BaseModel):
    """Bash 环境信息模型

    表示远程主机 Bash Shell 的环境变量快照。
    通过 SSH 执行 env/set 命令获取，用于了解远程环境配置。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.ssh_manager —— 获取远程环境信息时实例化并返回
      - app.routers.api —— 前端展示远程主机环境信息
    """

    # Bash 版本号
    bash_version: str = ""
    # Shell 类型（如 bash、zsh、sh）
    shell_type: str = "bash"
    # 命令提示符格式（PS1 环境变量）
    ps1: str = ""
    # 当前工作目录（PWD 环境变量）
    pwd: str = ""
    # 用户主目录（HOME 环境变量）
    home: str = ""
    # 当前用户名（USER 环境变量）
    user: str = ""
    # 主机名（HOSTNAME 环境变量）
    hostname: str = ""
    # PATH 环境变量
    path: str = ""


class CommandCompletion(BaseModel):
    """命令补全建议模型

    表示终端命令补全的结果，包含补全建议列表和当前输入前缀。
    前端根据此数据展示自动补全下拉菜单。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.ssh_manager —— 根据用户输入生成补全建议列表
      - app.routers.api —— 将补全结果返回给前端终端组件
    """

    # 补全建议列表（如 ["ls", "lsblk", "lscpu"]）
    completions: List[str] = Field(default_factory=list)
    # 用户当前输入的前缀文本
    prefix: str = ""


# ==================== SSH 管理器类型 ====================
# 以下类型用于 SSHManager 服务的输入输出数据结构。
# 被 app.services.ssh_manager 直接导入使用。


class TerminalOutput(BaseModel):
    """终端输出模型

    表示一次 SSH 命令执行后的终端输出结果，包含命令文本、输出内容和退出码。

    外部依赖: pydantic.BaseModel（基类）、datetime（时间戳）
    使用方:
      - app.services.ssh_manager —— 执行远程命令后封装结果返回
      - app.routers.api —— 向前端终端组件传递命令执行结果
    """

    # 执行的命令文本
    command: str = ""
    # 命令的标准输出内容
    output: str = ""
    # 命令退出码（0 表示成功，非 0 表示失败）
    exit_code: Optional[int] = None
    # 命令完成时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls, command: str, output: str, exit_code: Optional[int] = None
    ) -> "TerminalOutput":
        """创建终端输出实例的工厂方法

        参数:
          command: 执行的命令文本
          output: 命令的输出内容
          exit_code: 命令的退出码（可选）

        返回:
          TerminalOutput 实例

        调用方:
          - app.services.ssh_manager —— 执行命令后封装结果
        """
        return cls(command=command, output=output, exit_code=exit_code)


class SftpFileInfo(BaseModel):
    """SFTP 文件信息模型

    表示远程主机文件系统中的一个文件或目录的简要信息。
    用于目录列表展示（ls 命令的结果）。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.ssh_manager —— SFTP 列出目录时封装文件信息
      - app.routers.api —— 前端文件浏览器中展示文件列表
    """

    # 文件/目录名称
    name: str = ""
    # 完整路径
    path: str = ""
    # 文件类型：file / directory / symlink / other
    file_type: str = "file"
    # 是否为目录
    is_dir: bool = False
    # 文件大小（字节）
    size: int = 0
    # 最后修改时间（格式化的字符串）
    modified: Optional[str] = None
    # 文件权限（如 "rwxr-xr-x"）
    permissions: Optional[str] = None


class SftpFileDetails(BaseModel):
    """SFTP 文件详情模型

    表示远程主机文件系统中单个文件的详细属性信息，比 SftpFileInfo 包含更多字段。
    用于文件属性面板展示（ls -l 或 stat 命令的结果）。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.ssh_manager —— 获取文件详细属性时返回
      - app.routers.api —— 前端文件详情面板展示
    """

    # 文件/目录名称
    name: str = ""
    # 完整路径
    path: str = ""
    # 文件类型
    file_type: str = "file"
    # 文件大小（字节）
    size: int = 0
    # 文件权限字符串
    permissions: str = ""
    # 文件所有者
    owner: Optional[str] = None
    # 文件所属用户组
    group: Optional[str] = None
    # 创建时间（格式化的字符串）
    created: Optional[str] = None
    # 最后修改时间（格式化的字符串）
    modified: Optional[str] = None
    # 最后访问时间（格式化的字符串）
    accessed: Optional[str] = None


class SSHConnectionStatus(BaseModel):
    """SSH 连接状态模型

    表示一个 SSH 连接的当前运行状态信息，用于状态监控面板。
    区别于 SSHConnection（持久化配置），本类是运行时的即时状态快照。

    外部依赖: pydantic.BaseModel（基类）、datetime（时间戳）
    使用方:
      - app.services.ssh_manager —— 定期采集连接状态后返回
      - app.routers.api —— 前端连接状态面板实时展示
    """

    # 当前是否已连接
    connected: bool = False
    # 目标主机
    host: str = ""
    # 目标端口
    port: int = 22
    # 当前登录的用户名
    username: str = ""
    # 连接最后活跃时间
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class ConnectionInfo(BaseModel):
    """连接信息模型

    表示建立 SSH 连接所需的摘要信息，用于传递连接参数。
    是 SSHManager 内部在建立连接前使用的轻量信息结构。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.ssh_manager —— 内部建立连接时传递连接参数
    """

    # 目标主机
    host: str = ""
    # 目标端口
    port: int = 22
    # 用户名
    username: str = ""
    # 认证方式（password / key / certificate）
    auth_method: str = ""


# ==================== 检测结果类型 ====================
# 以下类型用于安全检测和性能检测模块的结果封装。
# 对应 Rust 端 detection_manager 中的各种检测结果结构体。
# 被 app.services.detection_manager 导入使用。
# 检测结果的风险等级统一分为: low / medium / high / critical


class PortScanResult(BaseModel):
    """端口扫描结果模型

    表示远程主机的端口扫描检测结果。检测开放端口的数量和分布，
    评估安全风险等级。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行端口扫描后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 开放端口列表，每个元素为 {"port": int, "service": str, ...}
    open_ports: List[Dict[str, Any]] = Field(default_factory=list)
    # 开放端口总数
    total_open: int = 0
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class UserAuditResult(BaseModel):
    """用户审计结果模型

    表示远程主机的用户账号审计结果。检测可疑用户、
    权限异常账号、可登录账号等安全风险。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行用户审计后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 所有用户列表
    users: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险用户列表（如 root 可登录、无密码用户等）
    risk_users: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class BackdoorScanResult(BaseModel):
    """后门检测结果模型

    表示远程主机的后门程序扫描结果。检测可疑文件、
    异常进程、不寻常的网络连接等入侵迹象。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行后门扫描后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 可疑文件列表
    suspicious_files: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class ProcessAnalysisResult(BaseModel):
    """进程分析结果模型

    表示远程主机的运行进程分析结果。检测可疑进程、
    异常资源消耗、隐藏进程等安全风险。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行进程分析后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 所有进程列表
    processes: List[Dict[str, Any]] = Field(default_factory=list)
    # 可疑进程列表
    suspicious_processes: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class FilePermissionResult(BaseModel):
    """文件权限检测结果模型

    表示远程主机的关键文件权限检测结果。检测 SUID/SGID、
    全局可写文件、敏感文件权限过大等安全风险。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行文件权限检测后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 风险文件列表（权限不当的文件）
    risky_files: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class SSHAuditResult(BaseModel):
    """SSH 审计结果模型

    表示远程主机的 SSH 服务配置审计结果。检测弱加密算法、
    root 远程登录、密码认证等安全配置问题。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行 SSH 审计后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # SSH 配置问题列表
    config_issues: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class LogAnalysisResult(BaseModel):
    """日志分析结果模型（检测场景）

    表示远程主机系统日志的安全分析结果。检测暴力破解、
    异常登录、权限提升等安全事件。

    注意：此类型用于检测模块（detection_manager 中的 log analysis 检测项），
    与下方的 LogAnalysisOutput（用于独立的日志分析功能）不同。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行日志安全分析后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 日志条目列表
    entries: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class FirewallCheckResult(BaseModel):
    """防火墙检查结果模型

    表示远程主机防火墙配置的检查结果。检测防火墙状态、
    规则配置、开放端口策略等网络安全状态。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行防火墙检查后封装结果
      - app.routers.api —— 前端安全检测报告展示
    """

    # 防火墙状态（如 "active" / "inactive"）
    status: str = ""
    # 防火墙规则列表
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""


class CpuTestResult(BaseModel):
    """CPU 测试结果模型

    表示远程主机 CPU 性能测试结果。包含 CPU 型号信息和当前使用率。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行 CPU 测试后封装结果
      - app.routers.api —— 前端性能测试报告展示
    """

    # CPU 信息（如型号、核心数等）
    cpu_info: str = ""
    # CPU 当前使用率（百分比）
    cpu_usage: float = 0.0
    # 详细测试说明
    details: str = ""


class MemoryTestResult(BaseModel):
    """内存测试结果模型

    表示远程主机内存性能测试结果。包含总内存、已用内存、空闲内存
    和使用率百分比。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行内存测试后封装结果
      - app.routers.api —— 前端性能测试报告展示
    """

    # 总内存大小（格式化的字符串，如 "7.6G"）
    total: str = ""
    # 已用内存大小
    used: str = ""
    # 空闲内存大小
    free: str = ""
    # 内存使用率（百分比，0~100）
    usage_percent: float = 0.0
    # 详细测试说明
    details: str = ""


class DiskTestResult(BaseModel):
    """磁盘测试结果模型

    表示远程主机磁盘使用情况测试结果。包含各挂载点的磁盘使用信息。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行磁盘测试后封装结果
      - app.routers.api —— 前端性能测试报告展示
    """

    # 各磁盘分区信息列表
    disks: List[Dict[str, Any]] = Field(default_factory=list)
    # 详细测试说明
    details: str = ""


class NetworkTestResult(BaseModel):
    """网络测试结果模型

    表示远程主机网络性能测试结果。包含网卡信息和当前网络连接状态。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 执行网络测试后封装结果
      - app.routers.api —— 前端性能测试报告展示
    """

    # 网卡信息列表
    interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    # 当前网络连接列表
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    # 详细测试说明
    details: str = ""


class GenericDetectionResult(BaseModel):
    """通用检测结果模型（基线检测）

    表示一个通用格式的安全检测结果，用于各类基线检测项。
    每个检测项通过 title 标识，status 表示检测状态
    （pass 通过 / fail 失败 / warn 警告 / info 信息），
    并提供修复建议列表。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.detection_manager —— 各类基线检测统一使用此模型
      - app.routers.api —— 前端安全检测报告展示
    """

    # 检测项标题（如 "密码复杂度检测"、"sudoers 配置检查"）
    title: str = ""
    # 检测状态：pass / fail / warn / info
    status: str = "info"
    # 检测结果详情列表
    items: List[Dict[str, Any]] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细检测说明
    details: str = ""
    # 修复建议列表
    suggestions: List[str] = Field(default_factory=list)


# ==================== 日志分析类型 ====================
# 以下类型用于独立的日志分析功能（区别于检测模块中的 LogAnalysisResult）。
# 被 app.services.log_analysis 导入使用。


class LogAnalysisEntry(BaseModel):
    """日志分析条目模型

    表示日志文件中的单行记录及其分析结果。包含原文、日志级别和高亮标记。
    日志级别可用于过滤（如只显示 ERROR 级别），highlighted 表示该行
    是否匹配用户的搜索条件，前端据此决定是否高亮显示。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.log_analysis —— 解析日志文件后逐行封装
      - app.routers.api —— 前端日志查看器展示
    """

    # 日志行原文
    line: str = ""
    # 日志级别（由解析器识别，如 INFO / WARN / ERROR）
    level: str = "info"
    # 是否匹配高亮条件（如包含关键词）
    highlighted: bool = False
    # 该行日志的时间戳（如从日志行中解析出来）
    timestamp: Optional[str] = None


class LogAnalysisOutput(BaseModel):
    """日志分析输出模型

    表示一次日志文件分析的完整输出结果。包含统计信息
    （总行数、高亮行数）、所有日志条目列表和文件元信息。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.log_analysis —— 分析完成后返回整体结果
      - app.routers.api —— 前端日志分析页面展示
    """

    # 日志总行数
    total_count: int = 0
    # 高亮匹配的行数
    highlighted_count: int = 0
    # 所有日志条目列表
    entries: List[LogAnalysisEntry] = Field(default_factory=list)
    # 文件元信息（如文件名、大小、修改时间等）
    file_info: Optional[Dict[str, Any]] = None


class LogFileInfo(BaseModel):
    """日志文件信息模型

    表示远程主机上一个可读取的日志文件的基本信息。
    用于日志文件浏览器，列出所有可用的日志文件供用户选择分析。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.log_analysis —— 扫描 /var/log 等目录后列出文件
      - app.routers.api —— 前端日志文件选择器展示
    """

    # 日志文件完整路径
    path: str = ""
    # 日志文件名
    name: str = ""
    # 文件大小（字节）
    size: int = 0
    # 最后修改时间（格式化的字符串）
    modified: str = ""
    # 文件是否可读
    readable: bool = True


# ==================== 文件分析类型 ====================
# 以下类型用于文件安全分析功能。
# 被 app.services.file_analysis 导入使用。


class FileAnalysisResult(BaseModel):
    """文件安全分析结果模型

    表示对远程主机上单个文件的安全分析结果。包含文件属性信息
    （大小、权限、所有者等）、各哈希算法的校验值、以及
    安全风险标记（SUID/SGID、全局可写、隐藏文件等）。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.file_analysis —— 对文件进行安全分析后返回
      - app.routers.api —— 前端文件安全分析页面展示
    """

    # 文件路径
    path: str = ""
    # 文件类型（如 "binary", "script", "config", "log" 等）
    file_type: str = ""
    # 文件大小（字节）
    size: int = 0
    # 文件权限字符串
    permissions: str = ""
    # 文件所有者
    owner: str = ""
    # 文件所属用户组
    group: str = ""
    # MD5 哈希值
    hash_md5: Optional[str] = None
    # SHA-1 哈希值
    hash_sha1: Optional[str] = None
    # SHA-256 哈希值
    hash_sha256: Optional[str] = None
    # 文件最后修改时间
    modified: Optional[str] = None
    # 文件创建时间
    created: Optional[str] = None
    # 文件最后访问时间
    accessed: Optional[str] = None
    # 文件是否设置了 SUID 位（安全风险标记）
    is_suid: bool = False
    # 文件是否设置了 SGID 位（安全风险标记）
    is_sgid: bool = False
    # 文件是否全局可写（安全风险标记）
    is_world_writable: bool = False
    # 文件是否为隐藏文件（以 . 开头）
    is_hidden: bool = False
    # 风险指标列表（如 ["suid_root", "world_writable"]）
    risk_indicators: List[str] = Field(default_factory=list)
    # 风险等级：low / medium / high / critical
    risk_level: str = "low"
    # 详细分析说明
    details: str = ""


# ==================== 设备信息类型 ====================
# 以下类型用于采集和管理远程主机设备信息。
# 被 app.services.device_info 导入使用。


class DeviceInfo(BaseModel):
    """设备信息模型

    表示一台远程主机的基本设备标识信息。包含设备的唯一标识符（UUID）、
    设备类型和显示名称。用于设备管理和多主机识别场景。

    外部依赖: pydantic.BaseModel（基类）
    使用方:
      - app.services.device_info —— 采集远程主机标识信息后封装
      - app.routers.api —— 前端设备列表和管理界面展示
      - app.services.settings —— 设备信息持久化存储
    """

    # 设备全局唯一标识符（可来源于系统 systemd-machine-id 或手动生成）
    device_uuid: str = ""
    # 设备类型（如 "linux_server", "router", "vm" 等）
    device_type: str = ""
    # 设备显示名称（用户自定义的友好名称）
    device_name: str = ""
