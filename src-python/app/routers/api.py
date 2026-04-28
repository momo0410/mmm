"""
LovelyRes HTTP API 路由模块（全部接口定义）
===========================================

本文件是整个 LovelyRes 应用后端最核心的路由文件，集中定义了所有对外暴露的 HTTP API 端点。
前身为 Rust 端 Tauri 命令（lib.rs），现已全部迁移为 FastAPI REST 接口，路径统一挂载在
``/api/v1`` 前缀下。

**模块在整体架构中的位置与角色**：

::

    ┌──────────────┐      HTTP REST       ┌──────────────┐      asyncssh / SFTP      ┌──────────────┐
    │  前端 (Web)   │ ◄──────────────────► │  本模块 (api)  │ ◄───────────────────────► │  目标 Linux   │
    │  Vue/React   │     /api/v1/*        │  FastAPI Router │                          │  服务器       │
    └──────────────┘                      └──────┬─────────┘                          └──────────────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    │            │            │
                              ssh_manager   detection_manager  file_analysis
                              log_analysis   settings        theme_manager
                              window_manager  crypto         device_info

**依赖的外部服务与模块**：

- ``app.services.ssh_manager.SSHManager``：管理 SSH 连接、命令执行、SFTP 文件操作、
  终端会话的生命周期。是本模块的核心依赖。
- ``app.services.ssh_connection_manager.SSHConnectionManager``：管理 SSH 连接的
  持久化存储（保存/加载/加密密码）。
- ``app.services.detection_manager``：安全检测引擎，包含端口扫描、用户审计、
  后门检测、基线检查等 20+ 个检测子命令。
- ``app.services.file_analysis``：远程文件安全分析（ELF 解析、字符串提取、
  病毒扫描等）。
- ``app.services.log_analysis``：远程日志的读取、分页与过滤。
- ``app.services.settings``：应用设置的读写与持久化。
- ``app.services.theme_manager``：前端主题（亮色/暗色）配置。
- ``app.services.device_info``：本地设备指纹生成。
- ``app.services.window_manager``：桌面窗口状态管理（最小化/最大化/关闭）。
- ``app.utils.crypto``：RSA 密钥对管理。
- ``app.utils.system_fonts``：系统字体枚举。

**错误处理体系**：

- ``_wrap_ssh_transport``：统一包装所有涉及 SSH/SFTP 的异步操作，将
  ``ConnectionError``、``asyncssh.Error``、``ValueError`` 映射为 HTTP 400，
  将其他未知异常映射为 HTTP 500 并附带详细信息。
- 各端点内部针对特定错误（如 AI 代理连通性、文件对话框不可用）做单独捕获，
  返回对应的 HTTP 状态码（501/502/403 等）。

**前端使用场景映射**：

- 仪表盘页面：``/ssh/connect``、``/ssh/execute-dashboard-command``、
  ``/ssh/connection-status``、``/ssh/detect-system-type``
- 终端页面：``/ssh/terminal/*``、``/command/completion``
- 文件管理器页面：``/sftp/*``、``/dialog/open``、``/dialog/save``
- 安全检测页面：``/detect/*``、``/file-analysis``
- 日志分析页面：``/log/*``
- AI 对话页面：``/ai/chat-proxy``
- 设置页面：``/settings``、``/theme/*``、``/system/fonts``
"""

from __future__ import annotations

import os
import tempfile
import time
import json
import asyncio
import logging
import urllib.request
import uuid
from types import SimpleNamespace

logger = logging.getLogger(__name__)
import urllib.error
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

import asyncssh
# FastAPI 核心组件：
# - APIRouter: 路由分组器，所有端点通过 router 注册
# - HTTPException: 标准 HTTP 异常，自动序列化为 JSON 错误响应
# - Request: 原始请求对象（本模块暂未直接使用，保留供未来扩展）
# - UploadFile / File / Form: multipart 文件上传支持
# - StreamingResponse: 流式响应（用于 AI SSE 代理）
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field

# ---- 内部模块导入 ----
from app.models.types import (
    SSHConnection,
    TerminalOutput,
)
from app.services import detection_manager, file_analysis, log_analysis
from app.services.ssh_connection_manager import SSHConnectionManager
from app.services.ssh_manager import SSHManager
from app.services.settings import (
    AppSettings,
    load_settings,
    read_settings_file,
    save_settings,
    write_settings_file,
)
from app.services.theme_manager import get_theme_settings
from app.services.device_info import get_device_uuid
from app.services.window_manager import WindowManager
from app.utils.crypto import get_rsa_public_key
from app.utils.system_fonts import get_system_fonts


# ============================================================
# 路由实例化
# ============================================================
# 所有端点统一以 /api/v1 为前缀，tags 用于 FastAPI 自动文档分组
router = APIRouter(prefix="/api/v1", tags=["lovelyres"])

T = TypeVar("T")


# ============================================================
# 辅助函数：SSH 传输层错误统一包装
# ============================================================

async def _wrap_ssh_transport(factory: Callable[[], Awaitable[T]]) -> T:
    """
    SSH/SFTP 操作的统一错误包装器。

    所有需要与远程服务器交互的端点（SFTP 文件操作、文件分析等）都通过此函数
    调用，以保证一致的错误处理行为。

    数据流：
        factory() ──► 返回结果 T（成功）
                   ──► ConnectionError ──► HTTP 400 "没有活动的 SSH 连接"
                   ──► asyncssh.Error ──► HTTP 400（含 SFTP 权限拒绝、连接断开等）
                   ──► ValueError ──► HTTP 400（参数错误，如未知分析动作）
                   ──► 其他 Exception ──► HTTP 500（未知服务器内部错误）

    前端使用方：所有 SFTP / 文件分析端点内部调用。
    """
    try:
        return await factory()
    except ConnectionError as e:
        # 用户尚未在应用中建立 SSH 连接时触发
        msg = str(e) or "没有活动的 SSH 连接，请先在应用中连接 SSH 后再使用 SFTP。"
        raise HTTPException(status_code=400, detail=msg) from e
    except asyncssh.Error as e:
        # 含 SFTPError、DisconnectError 等，统一视为客户端/服务器端协议错误
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        # 参数错误（如未知的分析动作）
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # 兜底捕获，防止任何未预料异常导致 500 无详情返回
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================
# 全局状态管理
# ============================================================
# 以下四个单例在应用启动时由 init_state() 统一初始化，贯穿整个应用生命周期。
# 它们分别负责：SSH 实时连接、SSH 连接配置持久化、桌面窗口控制、应用设置。

_ssh_manager: Optional[SSHManager] = None
"""SSH 实时连接管理器单例，持有当前活动的 SSH/PTY 连接和 SFTP 会话。"""

_ssh_connection_manager: Optional[SSHConnectionManager] = None
"""SSH 连接配置管理器单例，负责连接配置的加密存储、加载、删除等持久化操作。"""

_window_manager: Optional[WindowManager] = None
"""桌面窗口管理器单例，支持最小化、最大化、关闭及开发者工具等窗口操作。"""

_app_settings: Optional[AppSettings] = None
"""应用设置单例（主题、语言、快捷键等），启动时从本地配置文件加载。"""


def init_state():
    """
    初始化应用全局状态（应用启动时调用一次）。

    调用链：
        app.main.lifespan ──► init_state() ──► SSHManager() / SSHConnectionManager()
                                           ──► WindowManager()
                                           ──► load_settings() ──► 本地配置文件

    前端使用方：无（由后端启动流程自动调用）。
    """
    global _ssh_manager, _ssh_connection_manager, _window_manager, _app_settings
    _ssh_manager = SSHManager()
    _ssh_connection_manager = SSHConnectionManager()
    _window_manager = WindowManager()
    _app_settings = load_settings()
    print("LovelyRes Python 后端初始化完成")


def get_ssh_manager() -> SSHManager:
    """
    获取 SSH 管理器单例（延迟断言的线程安全访问器）。

    如果应用尚未初始化完毕就收到请求，返回 HTTP 500 错误，
    提示前端 "SSH管理器未初始化"。
    """
    if _ssh_manager is None:
        raise HTTPException(status_code=500, detail="SSH管理器未初始化")
    return _ssh_manager


def get_connection_manager() -> SSHConnectionManager:
    """
    获取 SSH 连接配置管理器单例。

    如果应用尚未初始化完毕就收到请求，返回 HTTP 500 错误，
    提示前端 "SSH连接管理器未初始化"。
    """
    if _ssh_connection_manager is None:
        raise HTTPException(status_code=500, detail="SSH连接管理器未初始化")
    return _ssh_connection_manager


# ============================================================
# Pydantic 请求模型
# ============================================================
# 以下模型定义了各个端点的请求体结构，FastAPI 自动完成 JSON 反序列化与校验。
# 字段使用 Python 类型注解，Optional 表示可选字段，Field 用于附加约束。

class ConnectDirectRequest(BaseModel):
    """
    直接 SSH 连接请求体（仅密码认证）。

    用于 /ssh/connect-direct 端点（快速直连模式），不支持密钥/证书认证。
    """
    host: str
    """目标服务器 IP 或域名"""
    port: int = 22
    """SSH 端口，默认 22"""
    username: str
    """登录用户名"""
    password: str
    """登录密码（明文传输，建议前端使用加密密码端点）"""


class ConnectWithAuthRequest(BaseModel):
    """
    完整 SSH 连接请求体（支持密码/密钥/证书三种认证方式）。

    用于 /ssh/connect 和 /ssh/test-connection 端点。
    认证方式由 auth_type 字段决定：
    - "password": 使用 password 字段
    - "key": 使用 key_path（私钥路径）和 key_passphrase（密钥密码，可选）
    - "certificate": 使用 certificate_path（证书路径）
    """
    host: str
    """目标服务器 IP 或域名"""
    port: int = 22
    """SSH 端口，默认 22"""
    username: str
    """登录用户名"""
    auth_type: str = "password"
    """认证类型：password / key / certificate"""
    password: Optional[str] = None
    """密码（auth_type=password 时必需）"""
    key_path: Optional[str] = None
    """私钥文件路径（auth_type=key 时必需）"""
    key_passphrase: Optional[str] = None
    """私钥密码（auth_type=key 时可选）"""
    certificate_path: Optional[str] = None
    """证书文件路径（auth_type=certificate 时必需）"""


class ExecuteCommandRequest(BaseModel):
    """
    SSH 命令执行请求体。

    用于所有执行远程命令的端点。如果指定了 username，
    则以该用户身份执行命令（sudo -u），否则以当前 SSH 用户身份执行。
    """
    command: str
    """要执行的 Shell 命令"""
    username: Optional[str] = None
    """以指定用户身份执行（可选），底层使用 sudo -u 实现"""


class SftpWriteRequest(BaseModel):
    """
    SFTP 文件写入请求体。

    用于 /sftp/write-file 端点，向远程服务器写入文本文件。
    """
    path: str
    """远程文件绝对路径"""
    content: str
    """要写入的文本内容（UTF-8 编码后写入）"""


class SftpCompressRequest(BaseModel):
    """
    SFTP 压缩请求体。

    用于 /sftp/compress 端点，将远程文件/目录打包为压缩包。
    """
    source_path: str
    """要压缩的源文件/目录路径"""
    target_path: str
    """压缩后的目标文件路径（含文件名，如 /tmp/backup.tar.gz）"""
    format: str = "tar.gz"
    """压缩格式，当前支持 tar.gz / zip"""


class SftpExtractRequest(BaseModel):
    """
    SFTP 解压请求体。

    用于 /sftp/extract 端点，将远程压缩包解压到指定目录。
    """
    archive_path: str
    """远程压缩包路径"""
    target_dir: str
    """解压目标目录"""
    overwrite: bool = True
    """是否覆盖已存在的文件，默认 True"""


class SftpUploadRequest(BaseModel):
    """
    SFTP 上传请求体（本地文件 → 远程服务器）。

    用于 /sftp/upload 端点，需要先将文件保存到本地临时路径，再上传。
    """
    local_path: str
    """本地文件绝对路径"""
    remote_path: str
    """远程目标路径"""


class SftpDownloadRequest(BaseModel):
    """
    SFTP 下载请求体（远程文件 → 本地）。

    用于 /sftp/download 端点。
    """
    remote_path: str
    """远程文件路径"""
    local_path: str
    """本地保存路径"""


class SftpChmodRequest(BaseModel):
    """
    SFTP 权限修改请求体。

    用于 /sftp/chmod 端点，修改远程文件/目录的 Unix 权限位。
    """
    path: str
    """远程文件/目录路径"""
    mode: int
    """权限模式（八进制，如 0o755 对应十进制 493）"""


class SaveTempFileRequest(BaseModel):
    """
    临时文件保存请求体。

    用于 /sftp/save-temp-file 端点，将 Base64 编码的数据解码后
    保存到系统临时目录，返回临时文件路径供后续上传/下载使用。
    """
    file_name: str
    """文件名"""
    data: str
    """Base64 编码的文件内容"""


class DockerActionRequest(BaseModel):
    """
    Docker 容器操作请求体。

    用于执行 Docker 容器的生命周期操作（启动/停止/重启/暂停/恢复等）。
    """
    container_id: str
    """Docker 容器 ID 或名称"""
    action: str
    """操作类型：start / stop / restart / pause / unpause / remove"""


class DockerLogsOptions(BaseModel):
    """
    Docker 日志查看选项（嵌套在 DockerLogsRequest 内使用）。

    对应于 docker logs 命令的各种过滤参数。
    """
    stdout: bool = True
    """是否包含标准输出日志，默认 True"""
    stderr: bool = True
    """是否包含标准错误日志，默认 True"""
    timestamps: bool = False
    """是否显示时间戳，默认 False"""
    tail: Optional[int] = None
    """只显示最后 N 行日志"""
    since: Optional[str] = None
    """从指定时间开始显示（如 "2024-01-01T00:00:00"）"""
    until: Optional[str] = None
    """显示到指定时间为止（如 "2024-01-02T00:00:00"）"""
    follow: bool = False
    """是否持续跟踪日志输出（类似 tail -f），默认 False"""


class DockerLogsRequest(BaseModel):
    """
    Docker 日志获取请求体。

    用于获取 Docker 容器的运行日志。
    """
    container_id: str
    """Docker 容器 ID 或名称"""
    options: Optional[DockerLogsOptions] = None
    """日志查看选项，为 None 时使用默认选项"""


class DockerExecRequest(BaseModel):
    """
    Docker 容器内命令执行请求体。

    用于在 Docker 容器内部执行 Shell 命令。
    """
    container_id: str
    """Docker 容器 ID 或名称"""
    command: str
    """要在容器内执行的命令"""
    shell: str = "sh"
    """使用的 Shell 类型，默认 sh（也可用 bash）"""


class DockerWriteFileRequest(BaseModel):
    """
    Docker 容器内文件写入请求体。

    用于 /docker/write-file 端点，通过 docker exec 将文本内容写入容器内文件。
    """
    container_id: str
    """Docker 容器 ID 或名称"""
    path: str
    """容器内的目标文件路径"""
    content: str
    """要写入的文本内容"""


class DockerCopyRequest(BaseModel):
    """
    Docker 容器文件复制请求体。

    用于 /docker/copy 端点，在宿主机与容器之间复制文件（docker cp）。
    """
    container_id: str
    """Docker 容器 ID 或名称"""
    direction: str
    """复制方向：to_container（本地→容器）/ from_container（容器→本地）"""
    source: str
    """源路径"""
    target: str
    """目标路径"""


class CreateTerminalSessionRequest(BaseModel):
    """
    终端会话创建请求体。

    用于 /ssh/terminal/create 端点，在已连接的 SSH 服务器上创建一个
    交互式 PTY 终端会话，并指定初始终端尺寸。
    """
    terminal_id: str
    """终端会话的唯一标识（由前端生成 UUID）"""
    cols: int = 80
    """终端列数（每行字符数），默认 80"""
    rows: int = 24
    """终端行数，默认 24"""


class SendTerminalInputRequest(BaseModel):
    """
    终端输入发送请求体。

    用于 /ssh/terminal/send-input 端点，将键盘输入发送到指定终端会话。
    数据包含原始字节，支持 ANSI 转义序列和特殊控制字符。
    """
    terminal_id: str
    """目标终端会话 ID"""
    data: str
    """要发送的输入数据（键盘按键、控制序列等）"""


class SetThemeRequest(BaseModel):
    """
    主题切换请求体。

    用于 /theme/set 端点。
    """
    theme: str
    """主题名称，如 "light" / "dark"，由前端主题管理器定义"""


class SaveSettingsRequest(BaseModel):
    """
    应用设置保存请求体。

    用于 /settings/save 端点，完整覆盖当前应用设置。
    """
    settings: Dict[str, Any]
    """设置键值对字典，会通过 AppSettings.model_validate 校验"""


class WriteSettingsFileRequest(BaseModel):
    """
    设置文件写入请求体。

    用于 /settings/file/write 端点，直接以原始文本形式写入配置文件。
    注意：与 /settings/save 不同，此端点不做 Pydantic 校验。
    """
    content: str
    """配置文件的原始文本内容"""


class EncryptPasswordRequest(BaseModel):
    """
    密码加密请求体。

    用于 /ssh/encrypt-password 端点，对 SSH 密码进行本地对称加密，
    以便安全存储到本地连接配置文件中。
    """
    password: str
    """明文密码"""


class DecryptPasswordRequest(BaseModel):
    """
    密码解密请求体。

    用于 /ssh/decrypt-password 端点，从本地配置文件中读取加密密码后
    解密为明文，用于前端密码框预填充。
    """
    encrypted_password: str
    """已加密的密码字符串"""


class AIProxyRequest(BaseModel):
    """
    AI 聊天代理请求体。

    用于 /ai/chat-proxy 端点，将前端的 AI 请求通过 Python 后端
    代理转发到上游 AI API（如 OpenAI 兼容接口），以规避浏览器的
    CORS 限制和 API Key 暴露风险。

    同时支持流式（SSE）与非流式两种响应模式。
    """
    url: str
    """上游 AI API 的完整 URL（如 https://api.openai.com/v1/chat/completions）"""
    headers: Dict[str, str] = Field(default_factory=dict)
    """转发的 HTTP 请求头（含 Authorization Bearer Token 等）"""
    body: Dict[str, Any] = Field(default_factory=dict)
    """转发的请求体（含 model、messages、stream 等字段）"""
    timeout_seconds: int = 60
    """请求超时时间（秒），默认 60"""


class ReadSystemLogRequest(BaseModel):
    """
    系统日志读取请求体。

    用于 /log/read-system 端点，读取远程服务器上指定路径的日志文件，
    支持分页和关键字/日期过滤。
    """
    log_path: str
    """远程日志文件绝对路径（如 /var/log/syslog）"""
    page: int = 1
    """页码，从 1 开始，默认第 1 页"""
    page_size: int = 100
    """每页行数，默认 100"""
    filter: Optional[str] = None
    """关键字过滤（grep 风格），为 None 时不过滤"""
    date_filter: Optional[str] = None
    """日期过滤（格式如 "2024-01-01"），为 None 时不过滤"""


class ReadJournalctlLogRequest(BaseModel):
    """
    journalctl 日志读取请求体。

    用于 /log/read-journalctl 端点，通过 journalctl 命令读取 systemd
    日志，支持按服务单元、时间范围、关键字进行过滤。
    """
    page: int = 1
    """页码，从 1 开始"""
    page_size: int = 100
    """每页条目数"""
    unit: Optional[str] = None
    """systemd 服务单元名（如 sshd.service），为 None 时显示所有单元"""
    filter: Optional[str] = None
    """关键字过滤，为 None 时不过滤"""
    since: Optional[str] = None
    """起始时间（如 "2024-01-01" 或 "1 hour ago"）"""
    until: Optional[str] = None
    """截止时间（如 "2024-01-02"）"""


class FileAnalysisRequest(BaseModel):
    """
    文件安全分析请求体。

    用于 /file-analysis 和 /file-analysis/independent 端点。
    根据 action 参数执行不同类型的分析（详情见 file_analysis 服务）。
    """
    path: str
    """远程服务器上的文件绝对路径"""
    action: Optional[str] = None
    """可选的分析动作（如 md5 / sha256 / strings / elf 等），
       为 None 时执行完整分析"""


class DialogFilterRequest(BaseModel):
    """
    文件对话框过滤器请求体（嵌套在 OpenDialogRequest / SaveDialogRequest 内）。

    用于定义本地文件对话框的文件类型过滤器，与 tkinter 的 filetypes 参数对应。
    """
    name: Optional[str] = None
    """过滤器显示名称（如 "文本文件"）"""
    extensions: List[str] = Field(default_factory=list)
    """文件扩展名列表（如 [".txt", ".md"]）"""


class OpenDialogRequest(BaseModel):
    """
    打开文件对话框请求体。

    用于 /dialog/open 端点，调起本地操作系统的原生文件选择对话框。
    支持单选/多选文件和目录选择三种模式。
    """
    multiple: bool = False
    """是否允许多选文件，默认 False"""
    directory: bool = False
    """是否选择目录（directory=True 时忽略 multiple 参数），默认 False"""
    filters: List[DialogFilterRequest] = Field(default_factory=list)
    """文件类型过滤器列表"""
    default_path: Optional[str] = None
    """对话框打开时的默认路径"""


class SaveDialogRequest(BaseModel):
    """
    保存文件对话框请求体。

    用于 /dialog/save 端点，调起本地操作系统的原生保存文件对话框。
    """
    filters: List[DialogFilterRequest] = Field(default_factory=list)
    """文件类型过滤器列表"""
    default_path: Optional[str] = None
    """对话框打开时的默认路径和默认文件名"""


# ============================================================
# 辅助函数：本机文件对话框
# ============================================================

def _run_native_dialog(kind: str, options: Dict[str, Any]) -> Any:
    """
    通过 tkinter 调起本机原生文件对话框（在独立线程中运行）。

    这是整个应用中唯一涉及 GUI 的部分，仅用于在非 Web 环境中提供
    "文件夹选择" 和 "文件保存/打开" 功能。基于 tkinter 的 filedialog
    模块实现，不对应用主线程产生阻塞。

    参数:
        kind: 对话框类型：
              "open_file"      - 单选文件
              "open_files"     - 多选文件
              "open_directory" - 选择目录
              "save_file"      - 保存文件
        options: 包含 filters（文件类型过滤）和 default_path（默认路径）

    返回:
        - 单选模式：选中路径的字符串，或 None（用户取消）
        - 多选模式：选中路径的字符串列表，或空列表
        - 选择目录模式：选中的目录路径字符串，或 None

    异常:
        RuntimeError: 当前环境无法导入 tkinter（如纯服务器环境），
                      由调用方转为 HTTP 501。

    数据流:
        OpenDialogRequest / SaveDialogRequest
            ──► _run_native_dialog()
                ──► tkinter.filedialog.askopenfilename / asksaveasfilename / askdirectory
                    ──► 返回选中路径
    """
    try:
        # 仅在需要时导入，避免在无 GUI 环境的服务器启动时就报错
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("当前环境不支持本机文件对话框") from exc

    # 创建隐藏的 Tk 根窗口（filedialog 需要一个父窗口）
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    try:
        # 尝试将对话框置顶（在某些 Linux 桌面环境下可能失效，但不影响功能）
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.update()

    # ---- 解析文件类型过滤器 ----
    # 将内部的 DialogFilterRequest 列表转换为 tkinter 接受的 filetypes 格式
    # 格式: [("描述", "*.ext1 *.ext2"), ...]
    filters = options.get("filters") or []
    filetypes = []
    for item in filters:
        name = item.get("name") or "支持的文件"
        extensions = item.get("extensions") or []
        patterns = []
        for ext in extensions:
            if ext == "*":
                patterns.append("*.*")
            else:
                patterns.append(ext if ext.startswith("*.") else f"*.{ext.lstrip('.')}")
        if patterns:
            filetypes.append((name, " ".join(patterns)))

    # 如果没有指定任何过滤器，默认为"所有文件"
    if not filetypes:
        filetypes = [("所有文件", "*.*")]

    # ---- 解析默认路径 ----
    # 如果是目录则作为 initialdir，如果是文件路径则分离目录和文件名
    initialdir = None
    initialfile = None
    default_path = options.get("default_path")
    if default_path:
        normalized = os.path.normpath(default_path)
        if os.path.isdir(normalized):
            initialdir = normalized
        else:
            initialdir = os.path.dirname(normalized) or None
            initialfile = os.path.basename(normalized) or None

    # 构建对话框参数
    dialog_kwargs: Dict[str, Any] = {"parent": root}
    if initialdir:
        dialog_kwargs["initialdir"] = initialdir
    if initialfile:
        dialog_kwargs["initialfile"] = initialfile
    # 目录选择不需要文件类型过滤器
    if kind != "open_directory":
        dialog_kwargs["filetypes"] = filetypes

    try:
        # 根据 kind 调度不同的对话框函数
        if kind == "open_directory":
            result = filedialog.askdirectory(**dialog_kwargs)
        elif kind == "open_files":
            result = filedialog.askopenfilenames(**dialog_kwargs)
        elif kind == "open_file":
            result = filedialog.askopenfilename(**dialog_kwargs)
        elif kind == "save_file":
            result = filedialog.asksaveasfilename(**dialog_kwargs)
        else:
            raise RuntimeError("不支持的对话框类型")
    finally:
        # 确保无论成功失败都销毁 tkinter 窗口，防止内存泄漏
        root.destroy()

    # 多选返回列表（用户取消时为空元组，转为空列表）
    if kind == "open_files":
        return list(result) if result else []
    # 单选/保存/目录：用户取消时返回空字符串，转为 None
    return result or None


# ============================================================
# 窗口控制端点 (Window Control)
# ============================================================
# 这些端点本身不执行实际的窗口操作，而是通过返回 JSON 事件
# 通知前端（Tauri WebView）执行相应的窗口 API 调用。
# 依赖：app.services.window_manager.WindowManager（后端持有引用，前端执行实际操作）。


@router.post("/window/minimize")
async def minimize_window():
    """
    最小化应用窗口。

    前端使用场景：顶部标题栏的最小化按钮点击事件。
    后端行为：返回 {"event": "window-minimize"} 事件，由前端监听并调用 Tauri window API。
    依赖服务：WindowManager（仅后端记录状态，前端执行实际窗口操作）。
    """
    return {"event": "window-minimize"}


@router.post("/window/toggle-maximize")
async def toggle_maximize():
    """
    切换应用窗口的最大化/还原状态。

    前端使用场景：顶部标题栏的最大化按钮点击事件。
    后端行为：返回 {"event": "window-toggle-maximize"} 事件。
    错误处理：无特殊错误，始终返回事件对象。
    """
    return {"event": "window-toggle-maximize"}


@router.post("/window/close")
async def close_window():
    """
    关闭应用窗口。

    前端使用场景：顶部标题栏的关闭按钮点击事件。
    后端行为：返回 {"event": "window-close"} 事件，前端收到后调用 Tauri 关闭 API。
    """
    return {"event": "window-close"}


@router.post("/window/open-devtools")
async def open_devtools():
    """
    打开浏览器开发者工具（仅开发/调试模式）。

    前端使用场景：菜单栏中的 "开发者工具" 选项。
    后端行为：返回 {"event": "window-open-devtools"} 事件，
    前端收到后调用 Tauri WebView 的开发者工具 API。
    """
    return {"event": "window-open-devtools"}


# ============================================================
# 文件对话框端点 (Native File Dialogs)
# ============================================================
# 在 Tauri 桌面环境下，文件对话框通过 Python tkinter 调起本机原生对话框。
# 对于纯 Web 部署环境，这些端点返回 HTTP 501（不支持）。


@router.post("/dialog/open")
async def open_dialog(req: OpenDialogRequest):
    """
    打开本机文件/目录选择对话框。

    前端使用场景：
    - 文件管理器页面的 "上传文件" 按钮（选择要上传的本地文件）
    - 设置页面的 "选择文件路径" 输入框
    - SFTP 下载时选择本地保存路径

    依赖：tkinter（Python 标准库 GUI 组件）

    数据流：
        OpenDialogRequest（含 multiple/directory/filters/default_path）
            ──► asyncio.to_thread(_run_native_dialog) ──► 在独立线程中运行，
                避免阻塞事件循环
                ──► tkinter.filedialog ──► 返回选中路径
                    ──► 响应: {"path": 路径字符串或 None}

    错误处理：
        - RuntimeError（tkinter 不可用）→ HTTP 501（当前环境不支持本机文件对话框）
        - 其他异常 → HTTP 500（打开文件对话框失败）
    """
    # 根据 directory 和 multiple 参数确定对话框类型
    kind = (
        "open_directory"
        if req.directory
        else "open_files"
        if req.multiple
        else "open_file"
    )
    try:
        # 在独立线程中运行 GUI 操作，避免阻塞 asyncio 事件循环
        path = await asyncio.to_thread(
            _run_native_dialog,
            kind,
            req.model_dump(),
        )
    except RuntimeError as exc:
        # tkinter 不可用（如纯服务器环境）
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"打开文件对话框失败: {exc}"
        ) from exc

    return {"path": path if path else None}


@router.post("/dialog/save")
async def save_dialog(req: SaveDialogRequest):
    """
    打开本机保存文件对话框。

    前端使用场景：
    - SFTP 文件列表右键 "下载" 菜单
    - 日志导出功能
    - 配置备份功能

    依赖：tkinter（Python 标准库 GUI 组件）

    数据流：
        SaveDialogRequest（含 filters/default_path）
            ──► asyncio.to_thread(_run_native_dialog, "save_file")
                ──► tkinter.filedialog.asksaveasfilename
                    ──► 响应: {"path": 保存路径或 None}

    错误处理：
        - RuntimeError（tkinter 不可用）→ HTTP 501
        - 其他异常 → HTTP 500
    """
    try:
        path = await asyncio.to_thread(
            _run_native_dialog,
            "save_file",
            req.model_dump(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"打开保存对话框失败: {exc}"
        ) from exc

    return {"path": path if path else None}


# ============================================================
# 主题管理端点 (Theme Management)
# ============================================================
# 前端主题（亮色/暗色）存储在 AppSettings 中，通过 theme_manager 获取
# 完整的主题 CSS 变量集。

@router.get("/theme/settings")
async def get_theme():
    """
    获取当前主题的完整 CSS 变量配置。

    前端使用场景：
    - 应用启动时加载主题样式
    - 设置页面预览主题效果

    依赖：app.services.theme_manager.get_theme_settings

    数据流：
        GET /api/v1/theme/settings
            ──► 读取 _app_settings.theme（"light" / "dark"）
                ──► get_theme_settings(current_theme) ──► 返回 CSS 变量字典
    """
    current_theme = _app_settings.theme if _app_settings else "light"
    return get_theme_settings(current_theme)


@router.post("/theme/set")
async def set_current_theme(req: SetThemeRequest):
    """
    切换当前主题。

    前端使用场景：设置页面中的亮色/暗色主题切换开关。

    依赖：app.services.settings.save_settings

    数据流：
        POST /api/v1/theme/set { theme: "dark" }
            ──► 更新 _app_settings.theme
                ──► save_settings() 持久化到本地文件
                    ──► 返回 {"event": "theme-changed", "theme": "dark"}
                        前端收到事件后重新加载 CSS 变量
    """
    global _app_settings
    if _app_settings:
        _app_settings.theme = req.theme
        save_settings(_app_settings)
    return {"event": "theme-changed", "theme": req.theme}


# ============================================================
# 设置管理端点 (Settings Management)
# ============================================================
# 负责应用的全局设置（语言、代理、AI Key 等）的读写持久化。

@router.get("/settings")
async def get_app_settings():
    """
    获取当前应用的所有设置项。

    前端使用场景：设置页面加载时读取所有配置项的当前值。

    依赖：app.services.settings.load_settings

    数据流：
        GET /api/v1/settings
            ──► 如果 _app_settings 为 None，从磁盘加载
                ──► 返回 _app_settings.model_dump()（完整设置字典）
    """
    global _app_settings
    if _app_settings is None:
        _app_settings = load_settings()
    return _app_settings.model_dump()


@router.post("/settings/save")
async def save_app_settings(req: SaveSettingsRequest):
    """
    保存应用设置（Pydantic 校验模式）。

    前端使用场景：设置页面点击 "保存" 按钮时调用。

    依赖：app.services.settings.AppSettings / save_settings

    数据流：
        POST /api/v1/settings/save { settings: {...} }
            ──► AppSettings.model_validate() 校验设置合法性
                ──► save_settings() 持久化到本地 JSON 文件
                    ──► 返回 {"success": true}

    错误处理：
        - Pydantic 校验失败 → HTTP 400（字段类型/范围错误）
        - 文件写入失败 → HTTP 500（由 save_settings 内部处理）
    """
    global _app_settings
    try:
        _app_settings = AppSettings.model_validate(req.settings)
        save_settings(_app_settings)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings/file")
async def read_settings():
    """
    读取设置文件的原始文本内容。

    前端使用场景：高级设置页面中的 "编辑配置文件" 功能，
    允许用户直接查看和编辑 JSON 格式的设置文件。

    依赖：app.services.settings.read_settings_file

    数据流：
        GET /api/v1/settings/file
            ──► read_settings_file() ──► 返回 {"content": "..."}（原始 JSON 文本）
    """
    return {"content": read_settings_file()}


@router.post("/settings/file/write")
async def write_settings(req: WriteSettingsFileRequest):
    """
    以原始文本形式写入设置文件（不做 Pydantic 校验）。

    前端使用场景：高级设置页面中用户直接编辑 JSON 配置后保存。

    依赖：app.services.settings.write_settings_file

    数据流：
        POST /api/v1/settings/file/write { content: "..." }
            ──► write_settings_file(content) ──► 覆盖写入本地配置文件
                ──► 返回 {"success": true}

    注意：此端点不做 Pydantic 校验，前端应在写入前自行验证 JSON 格式。
    """
    write_settings_file(req.content)
    return {"success": True}


@router.get("/system/fonts")
async def get_fonts():
    """
    获取系统已安装的字体的列表。

    前端使用场景：终端设置页面的 "字体选择" 下拉框。

    依赖：app.utils.system_fonts.get_system_fonts

    数据流：
        GET /api/v1/system/fonts
            ──► 遍历系统字体目录（Windows: C:\\Windows\\Fonts, Linux: /usr/share/fonts 等）
                ──► 返回 {"fonts": [...]}
    """
    return {"fonts": get_system_fonts()}


# ============================================================
# SSH 连接管理端点 (SSH Connection Management)
# ============================================================
# 管理 SSH 连接配置的 CRUD 操作，包括：
# - 连接列表的加载/保存（持久化到本地加密文件）
# - 密码的加密/解密（用于安全存储）
# - SSH 连接的建立/断开/测试/命令执行
# 依赖：SSHManager（实时连接）、SSHConnectionManager（持久化存储）

@router.get("/ssh/connections")
async def load_ssh_connections():
    """
    加载所有已保存的 SSH 连接配置列表。

    前端使用场景：
    - 连接管理页面展示已保存的服务器列表
    - 快速连接下拉菜单

    依赖：SSHConnectionManager.load_connections

    数据流：
        GET /api/v1/ssh/connections
            ──► connection_manager.load_connections()
                ──► 从本地加密文件读取并解密
                    ──► 返回 [SSHConnection, ...] 序列化列表
    """
    manager = get_connection_manager()
    connections = manager.load_connections()
    return [c.model_dump(mode="json") for c in connections]


@router.post("/ssh/connections/save")
async def save_ssh_connections(connections: List[SSHConnection]):
    """
    保存 SSH 连接配置列表（全量覆盖）。

    前端使用场景：
    - 添加新连接后自动保存
    - 删除/编辑连接后保存
    - 连接排序后保存新顺序

    依赖：SSHConnectionManager.save_connections

    数据流：
        POST /api/v1/ssh/connections/save [SSHConnection, ...]
            ──► connection_manager.save_connections(connections)
                ──► 对密码字段加密后写入本地文件
                    ──► 返回 {"success": true}
    """
    manager = get_connection_manager()
    manager.save_connections(connections)
    return {"success": True}


@router.post("/ssh/encrypt-password")
async def encrypt_password(req: EncryptPasswordRequest):
    """
    对 SSH 密码进行本地对称加密。

    前端使用场景：用户在连接编辑表单中输入密码后，
    在保存到本地配置文件之前，先调用此端点加密。

    依赖：SSHConnectionManager.encrypt_password

    数据流：
        POST /api/v1/ssh/encrypt-password { password: "plaintext" }
            ──► Fernet 对称加密（密钥来自设备 UUID 派生）
                ──► 返回 {"encrypted": "base64密文"}
    """
    manager = get_connection_manager()
    return {"encrypted": manager.encrypt_password(req.password)}


@router.post("/ssh/decrypt-password")
async def decrypt_password(req: DecryptPasswordRequest):
    """
    对已加密的 SSH 密码进行解密。

    前端使用场景：连接列表页面点击某个已保存的连接时，
    预填充密码框（需要解密显示）。

    依赖：SSHConnectionManager.decrypt_password

    数据流：
        POST /api/v1/ssh/decrypt-password { encrypted_password: "base64密文" }
            ──► Fernet 对称解密
                ──► 返回 {"decrypted": "明文密码"}
    """
    manager = get_connection_manager()
    return {"decrypted": manager.decrypt_password(req.encrypted_password)}


@router.post("/ssh/connect")
async def ssh_connect_with_auth(req: ConnectWithAuthRequest):
    """
    建立 SSH 连接（支持密码/密钥/证书认证）。

    这是主要的 SSH 连接入口，也是应用几乎所有功能的前置条件。
    连接成功后，SSHManager 内部会维护该连接直至主动断开或超时。

    前端使用场景：连接管理页面的 "连接" 按钮。

    依赖：SSHManager.connect

    数据流：
        POST /api/v1/ssh/connect { host, port, username, auth_type, password/key_path/... }
            ──► SSHManager.connect() ──► asyncssh 建立 SSH 连接
                ──► 返回 {"message": "连接成功信息"}
                ──► 后续所有 /sftp/* 和 /detect/* 等端点复用此连接

    错误处理：
        - 连接超时 / 认证失败 / 主机不可达 → HTTP 400
        - asyncssh 协议错误 → HTTP 400
    """
    ssh = get_ssh_manager()
    try:
        result = await ssh.connect(
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            private_key=req.key_path,
            key_passphrase=req.key_passphrase,
        )
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ssh/test-connection")
async def ssh_test_connection(req: ConnectWithAuthRequest):
    """
    测试 SSH 连接是否可用（连接后立即断开，不影响当前活动连接）。

    前端使用场景：连接编辑页面中的 "测试连接" 按钮。

    依赖：SSHManager.connect / SSHManager.disconnect

    数据流：
        POST /api/v1/ssh/test-connection { host, port, username, password, ... }
            ──► SSHManager.connect() 尝试连接
                ──► 成功 → SSHManager.disconnect() 立即断开
                    ──► 返回 {"success": true}
                ──► 失败 → 返回 {"success": false}（不抛出 HTTP 异常）

    注意：与 /ssh/connect 不同，此端点失败时返回 success: false 而非 HTTP 400，
    因为测试连接失败是正常的业务流程，不需要前端特殊处理。
    """
    ssh = get_ssh_manager()
    try:
        await ssh.connect(
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            private_key=req.key_path,
            key_passphrase=req.key_passphrase,
        )
        await ssh.disconnect()
        return {"success": True}
    except Exception:
        return {"success": False}


@router.post("/ssh/execute-command")
async def ssh_execute_command(req: ExecuteCommandRequest):
    """
    在已连接的 SSH 服务器上执行 Shell 命令（简单模式）。

    前端使用场景：
    - 终端页面的一键命令快捷按钮
    - AI Agent 生成的命令执行

    依赖：SSHManager.execute_command

    数据流：
        POST /api/v1/ssh/execute-command { command: "ls -la /etc" }
            ──► SSHManager.execute_command()
                ──► 通过 SSH 通道发送命令
                    ──► 服务端执行并返回输出
                        ──► 响应: { output, exit_code, ... }（TerminalOutput 模型）

    注意：此端点创建临时单次会话，命令执行完毕后立即关闭，不像终端会话那样持久。
    """
    ssh = get_ssh_manager()
    result = await ssh.execute_command(req.command)
    return result.model_dump(mode="json")


@router.post("/ssh/disconnect")
async def ssh_disconnect():
    """
    断开当前活动的 SSH 连接。

    前端使用场景：
    - 连接管理页面的 "断开" 按钮
    - 切换到其他服务器时先断开当前连接
    - 应用退出时的清理逻辑

    依赖：SSHManager.disconnect

    数据流：
        POST /api/v1/ssh/disconnect
            ──► SSHManager.disconnect()
                ──► 关闭 SSH 通道和所有终端会话
                    ──► 返回 {"success": true}
    """
    ssh = get_ssh_manager()
    await ssh.disconnect()
    return {"success": True}


# ============================================================
# SSH/SFTP 直接命令端点 (Direct SSH/SFTP Commands)
# ============================================================
# 这些端点提供更细粒度的 SSH 操作，包括：
# - 直接连接（仅密码模式，向后兼容旧版 API）
# - 仪表盘命令执行（以指定用户身份运行）
# - 应急响应命令（支持用户身份切换）
# - AI 生成检测命令执行
# - 连接状态检测
# - SSH 性能诊断
# - 远程系统类型自动识别

@router.post("/ssh/connect-direct")
async def ssh_connect_direct(req: ConnectDirectRequest):
    """
    直接 SSH 连接（仅密码认证，向后兼容简化版 API）。

    前端使用场景：快速连接栏（仅输入 IP/用户名/密码，不需要高级认证选项）。

    依赖：SSHManager.connect

    数据流：同 /ssh/connect，但只使用 password 认证方式。
    """
    ssh = get_ssh_manager()
    try:
        await ssh.connect(
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ssh/disconnect-direct")
async def ssh_disconnect_direct():
    """
    直接断开 SSH 连接（与 /ssh/disconnect 行为一致，向后兼容简化版 API）。

    前端使用场景：快速连接栏的 "断开" 按钮。
    """
    ssh = get_ssh_manager()
    await ssh.disconnect()
    return {"success": True}


@router.post("/ssh/execute-command-direct")
async def ssh_execute_command_direct(req: ExecuteCommandRequest):
    """
    以指定用户身份执行 SSH 命令。

    前端使用场景：
    - 仪表盘中需要以不同权限用户执行命令的场景
    - 例如：以 root 或特定服务用户执行诊断命令

    依赖：SSHManager.execute_dashboard_command_as_user

    数据流：
        POST /api/v1/ssh/execute-command-direct { command, username }
            ──► SSHManager.execute_dashboard_command_as_user()
                ──► 通过 sudo -u <username> 切换用户执行
                    ──► 返回 { output, exit_code }（TerminalOutput）
    """
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command_as_user(req.command, req.username)
    return result.model_dump(mode="json")


@router.post("/ssh/execute-dashboard-command")
async def ssh_execute_dashboard_command(req: ExecuteCommandRequest):
    """
    执行仪表盘命令（以当前 SSH 用户身份，带输出格式化优化）。

    前端使用场景：仪表盘首页的 "系统概览" / "一键检测" 等快捷命令执行。

    依赖：SSHManager.execute_dashboard_command

    数据流：同 /ssh/execute-command，但输出格式针对前端 Dashboard 卡片的展示做了优化。
    """
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")


@router.post("/ssh/execute-emergency-command")
async def ssh_execute_emergency_command(req: ExecuteCommandRequest):
    """
    执行应急响应命令（根据是否指定 username 选择执行模式）。

    前端使用场景：安全事件应急响应面板中的快速操作按钮。
    如果指定了 username，以该用户身份执行；否则以当前 SSH 用户执行。

    依赖：SSHManager.execute_dashboard_command / execute_dashboard_command_as_user
    """
    ssh = get_ssh_manager()
    if req.username:
        result = await ssh.execute_dashboard_command_as_user(req.command, req.username)
    else:
        result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")


@router.post("/ssh/execute-detection-command")
async def execute_detection_command(req: ExecuteCommandRequest):
    """
    执行 AI 生成的检测命令。

    前端使用场景：AI 对话面板中，Agent 分析后返回的检测命令，
    用户点击 "执行" 按钮时调用此端点。

    依赖：SSHManager.execute_dashboard_command

    注意：此端点与 /ssh/execute-dashboard-command 功能相同，但语义上用于 AI
    生成的命令，便于在日志和审计中区分来源。
    """
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")


@router.get("/ssh/connection-status")
async def ssh_get_connection_status():
    """
    获取当前 SSH 连接的详细状态。

    前端使用场景：
    - 仪表盘顶部的连接状态指示器
    - 导航栏中的 "已连接" / "未连接" 状态徽章

    依赖：SSHManager.get_connection_status

    数据流：
        GET /api/v1/ssh/connection-status
            ──► SSHManager.get_connection_status()
                ──► 返回 { connected: bool, host, port, username, connected_at, ... }
                或 None（从未连接过）
    """
    ssh = get_ssh_manager()
    status = await ssh.get_connection_status()
    return status.model_dump(mode="json") if status else None


@router.post("/ssh/test-performance")
async def test_ssh_performance():
    """
    测试当前 SSH 连接的性能（执行一组基准命令并计时）。

    前端使用场景：设置页面中的 "连接性能诊断" 功能。

    依赖：SSHManager.execute_command

    数据流：
        依次执行 4 条简单命令（echo / pwd / date / whoami），
        记录每条命令的耗时，并返回带有分析建议的诊断报告。

    返回内容包含两部分：
        1. 每条命令的耗时
        2. 性能分析建议（如果交互式终端慢但直接命令快，可能原因是什么）
    """
    ssh = get_ssh_manager()
    # 定义性能基准测试用例：命令 + 中文描述
    test_commands = [
        ("echo test", "基础响应测试"),
        ("pwd", "目录查询测试"),
        ("date", "系统时间测试"),
        ("whoami", "用户查询测试"),
    ]

    results = ["=== 直接命令执行性能测试 ==="]
    for cmd, desc in test_commands:
        start = time.time()
        try:
            await ssh.execute_command(cmd)
            duration = time.time() - start
            results.append(f"{desc}: {duration:.3f}s")
        except Exception as e:
            results.append(f"{desc}: 失败 - {e}")

    results.append("\n=== 性能分析建议 ===")
    results.append("如果直接命令执行很快，但交互式终端很慢，问题可能在于:")
    results.append("1. Shell初始化配置(.bashrc, .profile)")
    results.append("2. 复杂的命令提示符(PS1)")
    results.append("3. PTY配置问题")
    results.append("4. 环境变量处理")

    return {"result": "\n".join(results)}


@router.post("/ssh/diagnose-shell-performance")
async def diagnose_shell_performance():
    """
    诊断远程 Shell 配置可能导致的性能问题。

    前端使用场景：终端体验卡顿时的自助诊断工具。

    依赖：SSHManager.execute_command

    检测项包括：
    1. Shell 类型（bash / zsh / fish 等）
    2. .bashrc 文件大小（过于庞大的初始化脚本会拖慢终端）
    3. 命令提示符（PS1）长度（复杂的提示符渲染耗时）
    4. 简单命令响应时间（排除网络延迟后的基准）

    返回：每项检查的结果和耗时。
    """
    ssh = get_ssh_manager()
    results = ["=== Shell性能诊断 ==="]

    tests = [
        ("echo $SHELL", "Shell类型"),
        ("wc -l ~/.bashrc 2>/dev/null || echo 'no .bashrc'", ".bashrc行数"),
        ('echo "PS1长度: ${#PS1}"', "命令提示符"),
        ("true", "简单命令(true)"),
    ]

    for cmd, desc in tests:
        start = time.time()
        try:
            output = await ssh.execute_command(cmd)
            duration = time.time() - start
            results.append(f"{desc}: {output.output.strip()} (耗时: {duration:.3f}s)")
        except Exception as e:
            results.append(f"{desc}失败: {e}")

    return {"result": "\n".join(results)}


@router.get("/ssh/detect-system-type")
async def detect_system_type():
    """
    自动识别远程 Linux 服务器的系统类型（发行版）。

    这是整个应用最关键的端点之一，前端几乎所有功能（安全检测、包管理、服务管理）
    的行为都依据此端点的返回值进行适配。如果没有活动的 SSH 连接，返回 HTTP 400。

    检测流程：
        1. 读取 /etc/os-release（或 /etc/lsb-release）获取发行版 ID、名称、版本
        2. 检测包管理器（apt / yum / dnf / pacman / zypper / apk）
        3. 检测 init 系统（systemd / sysvinit / upstart / openrc）
        4. 根据 ID_LIKE 字段做发行版家族推测（如统信 UOS 识别为 ubuntu-like）

    依赖：SSHManager.execute_dashboard_command

    数据流：
        GET /api/v1/ssh/detect-system-type
            ──► ① cat /etc/os-release ──► 解析发行版信息
            ──► ② 检测包管理器
            ──► ③ ps -p 1 -o comm= ──► 检测 init 系统
            ──► ④ 别名映射与家族推测 ──► 标准化系统类型标识
                ──► 返回 { type, name, version, prettyName, packageManager, initSystem }

    国内发行版特殊支持：
        - 麒麟 (kylin)、统信 (uos/uniontech)、深度 (deepin)
        - 华为 openEuler、龙蜥 (anolis)
    """
    ssh = get_ssh_manager()
    if not ssh.is_connected():
        raise HTTPException(status_code=400, detail="没有活动的 SSH 连接")

    # ---- 步骤 1: 读取操作系统版本信息 ----
    # 优先读取 os-release（systemd 标准），fallback 到 lsb-release
    os_release_cmd = "cat /etc/os-release 2>/dev/null || cat /etc/lsb-release 2>/dev/null || echo 'ID=generic'"
    os_release_output = await ssh.execute_dashboard_command(os_release_cmd)
    os_release_content = os_release_output.output

    # ---- 步骤 2: 检测包管理器 ----
    # 按顺序尝试 which 命令，第一个找到的就是当前系统的包管理器
    pkg_mgr_cmd = "which apt 2>/dev/null && echo 'apt' || which yum 2>/dev/null && echo 'yum' || which dnf 2>/dev/null && echo 'dnf' || which pacman 2>/dev/null && echo 'pacman' || which zypper 2>/dev/null && echo 'zypper' || which apk 2>/dev/null && echo 'apk' || echo 'unknown'"
    pkg_mgr_output = await ssh.execute_dashboard_command(pkg_mgr_cmd)
    package_manager = pkg_mgr_output.output.strip().split("\n")[-1].strip()

    # ---- 步骤 3: 检测 init 系统 ----
    # 通过 ps 查看 PID 1 的进程名称
    init_output = await ssh.execute_dashboard_command("ps -p 1 -o comm= 2>/dev/null")
    init_str = init_output.output.strip().lower()
    if "systemd" in init_str:
        init_system = "systemd"
    elif "init" in init_str:
        init_system = "sysvinit"
    elif "upstart" in init_str:
        init_system = "upstart"
    elif "openrc" in init_str:
        init_system = "openrc"
    else:
        init_system = "unknown"

    # ---- 步骤 4: 解析 os-release 内容 ----
    # os-release 是 KEY=VALUE 格式的文本文件，逐行解析
    id_val = "generic"
    id_like = ""
    name = "Linux"
    version = ""
    pretty_name = "Generic Linux"

    for line in os_release_content.split("\n"):
        line = line.strip()
        if line.startswith("ID=") and not line.startswith("ID_LIKE="):
            id_val = line[3:].strip('"').strip("'").lower()
        elif line.startswith("ID_LIKE="):
            id_like = line[8:].strip('"').strip("'").lower()
        elif line.startswith("NAME="):
            name = line[5:].strip('"').strip("'")
        elif line.startswith("VERSION_ID="):
            version = line[11:].strip('"').strip("'")
        elif line.startswith("PRETTY_NAME="):
            pretty_name = line[12:].strip('"').strip("'")

    # ---- 步骤 5: 发行版标准化映射 ----
    # 将各种发行版的 ID 统一为内部标准标识符
    system_type = id_val
    # 已知的 Linux 发行版直接使用其 ID
    if id_val in (
        "kylin",
        "uos",
        "uniontech",
        "deepin",
        "openeuler",
        "anolis",
        "ubuntu",
        "debian",
        "centos",
        "rhel",
        "fedora",
        "arch",
        "alpine",
    ):
        system_type = id_val
    elif id_val in ("opensuse", "suse"):
        system_type = "opensuse"
    elif id_like:
        # 根据 ID_LIKE 字段推测发行版家族
        if "ubuntu" in id_like:
            system_type = "ubuntu"
        elif "debian" in id_like:
            system_type = "debian"
        elif "rhel" in id_like or "fedora" in id_like:
            combined = f"{id_val} {id_like} {name} {pretty_name}".lower()
            if "centos" in combined:
                system_type = "centos"
            elif "fedora" in combined:
                system_type = "fedora"
            else:
                system_type = "rhel"
        elif "arch" in id_like:
            system_type = "arch"
        elif "suse" in id_like:
            system_type = "opensuse"
        else:
            system_type = "generic"
    else:
        system_type = "generic"

    return {
        "type": system_type,
        "name": name,
        "version": version,
        "prettyName": pretty_name,
        "packageManager": package_manager,
        "initSystem": init_system,
    }


# ============================================================
# SFTP 文件操作端点 (SFTP File Operations)
# ============================================================
# 提供基于 SFTP 协议的远程文件管理功能，所有端点都在已建立 SSH 连接的基础上运行。
# 每个端点内部都通过 _wrap_ssh_transport 包装，统一处理连接断开、权限拒绝等异常。
# 依赖：SSHManager 中的 SFTP 方法族（list / read / write / upload / download /
#       compress / extract / chmod / get_details）

@router.post("/sftp/list-files")
async def sftp_list_files(path: str):
    """
    列出远程服务器上指定目录的文件和子目录。

    前端使用场景：文件管理器页面的目录树和文件列表渲染。

    依赖：SSHManager.list_sftp_files

    数据流：
        POST /api/v1/sftp/list-files (body: path="/etc")
            ──► _wrap_ssh_transport(SSHManager.list_sftp_files)
                ──► SFTP listdir 命令
                    ──► 返回 [FileInfo, ...]（文件名、大小、权限、修改时间等）
    """
    async def _go():
        ssh = get_ssh_manager()
        return await ssh.list_sftp_files(path)

    files = await _wrap_ssh_transport(_go)
    return [f.model_dump(mode="json") for f in files]


@router.post("/sftp/read-file")
async def sftp_read_file(path: str, max_bytes: Optional[int] = None):
    """
    读取远程服务器上的文本文件内容。

    前端使用场景：
    - 文件管理器中双击文本文件打开查看/编辑
    - AI Agent 读取配置文件内容进行分析

    参数:
        path: 远程文件绝对路径
        max_bytes: 可选，最大读取字节数，用于限制大文件的读取量以防内存溢出

    依赖：SSHManager.read_sftp_file

    数据流：
        POST /api/v1/sftp/read-file (body: path="/etc/ssh/sshd_config")
            ──► _wrap_ssh_transport(SSHManager.read_sftp_file)
                ──► SFTP 读取二进制内容
                    ──► UTF-8 解码
                        ──► 如果指定了 max_bytes 则截断
                            ──► 返回 {"content": "..."}
    """
    async def _go():
        ssh = get_ssh_manager()
        return await ssh.read_sftp_file(path)

    content = await _wrap_ssh_transport(_go)
    text = content.decode("utf-8", errors="replace")
    if max_bytes and len(text) > max_bytes:
        text = text[:max_bytes]
    return {"content": text}


@router.post("/sftp/write-file")
async def sftp_write_file(req: SftpWriteRequest):
    """
    向远程服务器写入文本文件（覆盖模式）。

    前端使用场景：文件管理器的文本编辑器 "保存" 按钮。

    依赖：SSHManager.write_sftp_file

    数据流：
        POST /api/v1/sftp/write-file { path, content }
            ──► content.encode("utf-8")
                ──► _wrap_ssh_transport(SSHManager.write_sftp_file)
                    ──► SFTP 写入远程文件
                        ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.write_sftp_file(req.path, req.content.encode("utf-8"))

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/upload")
async def sftp_upload(req: SftpUploadRequest):
    """
    上传本地文件到远程服务器。

    前端使用场景：文件管理器的 "上传" 按钮（需先通过 /dialog/open 选择本地文件，
    再调用此端点上传）。

    依赖：SSHManager.upload_file

    数据流：
        POST /api/v1/sftp/upload { local_path, remote_path }
            ──► _wrap_ssh_transport(SSHManager.upload_file)
                ──► 从本地路径读取文件并通过 SFTP 传输到远程
                    ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.upload_file(req.local_path, req.remote_path)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/upload-direct")
async def sftp_upload_direct(
    file: UploadFile = File(...),
    remote_path: str = Form(...),
):
    """
    直接上传文件（接收浏览器 multipart/form-data 文件流，无需临时文件中转）。

    这是 Web 部署环境下的主要上传方式。相比 /sftp/upload 的优势：
    不需要先调用 /sftp/save-temp-file 保存到本地再上传，减少了 I/O 开销。

    前端使用场景：Web 前端的拖拽上传或文件选择上传。

    依赖：SSHManager.upload_file、Python 临时文件机制

    数据流：
        POST multipart/form-data (file + remote_path)
            ──► 将上传的字节流写入系统临时文件（后缀与原文件一致）
                ──► SSHManager.upload_file(tmp_path, remote_path)
                    ──► SFTP 传输
                        ──► 清理临时文件（finally 块保证一定执行）
                            ──► 返回 {"success": true}

    错误处理：
        - 文件上传中断 → HTTP 500
        - 远程路径权限不足 → HTTP 403（含友好中文提示 "请检查目录权限"）
        - 临时文件清理失败的 OSError 被静默忽略
    """
    import shutil

    tmp_path = None
    try:
        # 将上传的文件保存到临时位置
        filename = file.filename or "upload"
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        logger.info(f"上传文件: 本地={tmp_path}, 远程={remote_path}, 原始文件名={filename}")

        async def _go():
            ssh = get_ssh_manager()
            await ssh.upload_file(tmp_path, remote_path)

        try:
            await _wrap_ssh_transport(_go)
        except HTTPException as e:
            # SFTP 权限/路径错误 → 返回友好信息
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            if "Permission denied" in detail:
                raise HTTPException(status_code=403, detail=f"远程服务器拒绝写入: {remote_path}，请检查目录权限") from e
            raise

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}") from e
    finally:
        # 清理临时文件
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return {"success": True}


@router.post("/sftp/download")
async def sftp_download(req: SftpDownloadRequest):
    """
    从远程服务器下载文件到本地。

    前端使用场景：文件管理器右键菜单 "下载" 选项。

    依赖：SSHManager.download_file

    数据流：
        POST /api/v1/sftp/download { remote_path, local_path }
            ──► _wrap_ssh_transport(SSHManager.download_file)
                ──► SFTP 从远程读取文件并写入本地路径
                    ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.download_file(req.remote_path, req.local_path)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/create-directory")
async def sftp_create_directory(remote_path: str):
    """
    在远程服务器上创建目录（含递归创建父目录）。

    前端使用场景：文件管理器的 "新建文件夹" 按钮。

    依赖：SSHManager.create_directory

    数据流：
        POST /api/v1/sftp/create-directory (body: remote_path="/var/log/myapp")
            ──► _wrap_ssh_transport(SSHManager.create_directory)
                ──► SFTP mkdir -p
                    ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.create_directory(remote_path)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/compress")
async def sftp_compress(req: SftpCompressRequest):
    """
    压缩远程服务器上的文件/目录。

    前端使用场景：文件管理器右键菜单 "压缩" 选项。

    依赖：SSHManager.compress_file

    数据流：
        POST /api/v1/sftp/compress { source_path, target_path, format }
            ──► _wrap_ssh_transport(SSHManager.compress_file)
                ──► 通过 SSH 执行 tar / zip 命令
                    ──► 压缩包生成在 target_path
                        ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.compress_file(req.source_path, req.target_path, req.format)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/extract")
async def sftp_extract(req: SftpExtractRequest):
    """
    解压远程服务器上的压缩包。

    前端使用场景：文件管理器右键菜单 "解压" 选项。

    依赖：SSHManager.extract_file

    数据流：
        POST /api/v1/sftp/extract { archive_path, target_dir, overwrite }
            ──► _wrap_ssh_transport(SSHManager.extract_file)
                ──► 通过 SSH 执行 tar / unzip 命令解压到 target_dir
                    ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.extract_file(req.archive_path, req.target_dir)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/chmod")
async def sftp_chmod(req: SftpChmodRequest):
    """
    修改远程文件/目录的 Unix 权限位。

    前端使用场景：文件管理器的文件属性面板中的 "权限" 设置。

    依赖：SSHManager.chmod_sftp

    数据流：
        POST /api/v1/sftp/chmod { path: "/opt/app/script.sh", mode: 0o755 }
            ──► _wrap_ssh_transport(SSHManager.chmod_sftp)
                ──► SFTP chmod 命令
                    ──► 返回 {"success": true}
    """
    async def _go():
        ssh = get_ssh_manager()
        await ssh.chmod_sftp(req.path, req.mode)

    await _wrap_ssh_transport(_go)
    return {"success": True}


@router.post("/sftp/get-file-details")
async def sftp_get_file_details(path: str):
    """
    获取远程文件/目录的详细属性信息。

    前端使用场景：文件管理器的文件属性面板。

    返回信息包括：大小、所有者、权限位、修改/访问时间、MIME 类型、
    是否为符号链接等。

    依赖：SSHManager.get_file_details

    数据流：
        POST /api/v1/sftp/get-file-details (body: path="/etc/passwd")
            ──► _wrap_ssh_transport(SSHManager.get_file_details)
                ──► SFTP stat + file 命令
                    ──► 返回 FileDetails 模型序列化结果
    """
    async def _go():
        ssh = get_ssh_manager()
        return await ssh.get_file_details(path)

    details = await _wrap_ssh_transport(_go)
    return details.model_dump(mode="json")


@router.post("/sftp/save-temp-file")
async def save_temp_file(req: SaveTempFileRequest):
    """
    将 Base64 编码的内容保存为系统临时文件，返回临时文件路径。

    前端使用场景：在非 Web 部署环境下，前端将文件内容 Base64 编码后通过此端点
    保存为临时文件，再用 /sftp/upload 上传。（Web 部署环境建议使用 /sftp/upload-direct）

    依赖：Python base64 / tempfile 标准库

    数据流：
        POST /api/v1/sftp/save-temp-file { file_name, data: "base64string" }
            ──► base64.b64decode(data)
                ──► 写入 tempfile.gettempdir() / file_name
                    ──► 返回 {"path": "/tmp/xxx/filename"}
    """
    import base64

    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, req.file_name)
    data = base64.b64decode(req.data)
    with open(temp_path, "wb") as f:
        f.write(data)
    return {"path": temp_path}


# ============================================================
# 文件安全分析端点 (File Security Analysis)
# ============================================================
# 对远程服务器上的文件执行安全分析，包括哈希计算、字符串提取、
# ELF 二进制解析、病毒特征扫描等。分析动作由 action 参数指定。
# 依赖：app.services.file_analysis

@router.post("/file-analysis")
async def sftp_file_analysis_endpoint(req: FileAnalysisRequest):
    """
    对远程文件执行安全分析（标准模式）。

    前端使用场景：
    - 文件管理器右键菜单 "安全分析"
    - 安全检测模块中针对特定文件的深入分析

    依赖：file_analysis.sftp_file_analysis

    数据流：
        POST /api/v1/file-analysis { path, action }
            ──► _wrap_ssh_transport(file_analysis.sftp_file_analysis)
                ──► 根据 action 执行对应的分析算法
                    ──► 返回分析结果字典
    """
    async def _go():
        ssh = get_ssh_manager()
        return await file_analysis.sftp_file_analysis(ssh, req.path, req.action)

    result = await _wrap_ssh_transport(_go)
    return result


@router.post("/file-analysis/independent")
async def sftp_file_analysis_independent_endpoint(req: FileAnalysisRequest):
    """
    对远程文件执行独立安全分析（不依赖当前 SSH 会话缓存的独立通道）。

    前端使用场景：需要独立于当前会话执行分析的场景，例如对大型文件的分析。

    依赖：file_analysis.sftp_file_analysis_independent

    数据流：同 /file-analysis，但底层使用独立的 SSH 分析通道。
    """
    async def _go():
        ssh = get_ssh_manager()
        return await file_analysis.sftp_file_analysis_independent(ssh, req.path, req.action)

    result = await _wrap_ssh_transport(_go)
    return result


# ============================================================
# Bash 环境 & 命令补全端点 (Bash Environment & Command Completion)
# ============================================================
# 提供终端智能感知功能，包括远程 Bash 环境信息获取和 Tab 补全建议。

@router.get("/bash/environment-info")
async def get_bash_environment_info():
    """
    获取远程服务器的 Bash 环境信息。

    前端使用场景：
    - 终端页面初始化时读取远程 Shell 环境（PATH、别名、函数列表等）
    - 命令补全功能的前置依赖，了解可用的命令和路径

    依赖：SSHManager.get_bash_environment_info

    数据流：
        GET /api/v1/bash/environment-info
            ──► SSH 连接中执行 env / alias 等诊断命令
                ──► 返回 { path, aliases, functions, ... }
    """
    ssh = get_ssh_manager()
    result = await ssh.get_bash_environment_info()
    return result.model_dump()


@router.post("/command/completion")
async def get_command_completion(input: str):
    """
    获取命令 Tab 补全建议列表。

    前端使用场景：终端输入时按 Tab 键，发送已输入的前缀获取补全候选。

    依赖：SSHManager.get_command_completion

    数据流：
        POST /api/v1/command/completion (body: "ls /et")
            ──► SSH 发送 compgen / complete 命令到远程
                ──► 返回 { completions: ["/etc/", "/etc/..."] }
    """
    ssh = get_ssh_manager()
    result = await ssh.get_command_completion(input)
    return result.model_dump()


# ============================================================
# 安全检测命令端点 - 低层检测 (Security Detection - Low Level)
# ============================================================
# 以下端点均为底层原子安全检测命令，每个端点对应一种特定的安全扫描。
# 所有端点都带有 endpoint_metadata 标记，提示前端这些接口仅供 Agent
# 内部调用或调试使用，不应直接在 UI 上暴露为独立按钮。

# 依赖：app.services.detection_manager 中的各检测函数

@router.post("/detect/port-scan")
async def detect_port_scan():
    """
    端口扫描检测 - 检查远程服务器上异常的开放端口。

    检测内容：通过 netstat / ss 获取当前监听端口列表，
    与系统默认端口白名单对比，标记可疑端口。

    前端使用场景：安全检测模块的 "端口扫描" 功能项。
    """
    result = (await detection_manager.detect_port_scan(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/user-audit")
async def detect_user_audit():
    """
    用户审计检测 - 检查异常用户账户。

    检测内容：读取 /etc/passwd 和 /etc/shadow，检查：
    - UID 0 的非 root 用户（提权风险）
    - 无密码或空密码账户
    - 最近创建的可疑账户
    - 可登录的 system 账户

    前端使用场景：安全检测模块的 "用户审计" 功能项。
    """
    result = (await detection_manager.detect_user_audit(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/backdoor")
async def detect_backdoor():
    """
    后门检测 - 检查常见的后门程序特征。

    检测内容：
    - crontab 中的可疑定时任务
    - /etc/rc.local 中的可疑启动项
    - 隐藏进程（进程名以 . 开头）
    - 常见后门进程名匹配
    - SSH authorized_keys 中的未知密钥

    前端使用场景：安全检测模块的 "后门检测" 功能项。
    """
    result = (await detection_manager.detect_backdoor(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/process-analysis")
async def detect_process_analysis():
    """
    进程分析检测 - 检查运行中的可疑进程。

    检测内容：
    - CPU/内存占用异常的进程
    - 从 /tmp 等临时目录启动的进程
    - 隐藏进程（/proc 与 ps 不一致）
    - 无父进程的孤儿进程

    前端使用场景：安全检测模块的 "进程分析" 功能项。
    """
    result = (
        await detection_manager.detect_process_analysis(get_ssh_manager())
    ).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/file-permission")
async def detect_file_permission():
    """
    文件权限检测 - 检查关键系统文件的权限配置。

    检测内容：
    - /etc/passwd、/etc/shadow 的权限
    - /etc/sudoers 的权限
    - SUID/SGID 文件的审计
    - 全局可写目录检查

    前端使用场景：安全检测模块的 "文件权限" 功能项。
    """
    result = (
        await detection_manager.detect_file_permission(get_ssh_manager())
    ).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/ssh-audit")
async def detect_ssh_audit():
    """
    SSH 配置审计 - 检查 SSH 服务的安全配置。

    检测内容：
    - PermitRootLogin 是否禁用
    - PasswordAuthentication 是否安全
    - 是否使用了非标准端口
    - Protocol 版本是否为 2
    - 是否启用公钥认证

    前端使用场景：安全检测模块的 "SSH 审计" 功能项。
    """
    result = (await detection_manager.detect_ssh_audit(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/log-analysis")
async def detect_log_analysis():
    """
    日志安全分析 - 扫描系统日志中的异常事件。

    检测内容：
    - 暴力破解尝试（/var/log/auth.log 中的多次失败登录）
    - sudo 提权记录
    - 异常时段的登录活动
    - 服务崩溃记录

    前端使用场景：安全检测模块的 "日志分析" 功能项。
    """
    result = (await detection_manager.detect_log_analysis(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/firewall-check")
async def detect_firewall_check():
    """
    防火墙配置检测 - 检查系统防火墙规则。

    检测内容：
    - iptables/nftables 规则列表
    - 默认策略是否为 DROP
    - 是否开放了不必要的端口
    - firewalld/ufw 状态检查

    前端使用场景：安全检测模块的 "防火墙检查" 功能项。
    """
    result = (
        await detection_manager.detect_firewall_check(get_ssh_manager())
    ).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/cpu-test")
async def detect_cpu_test():
    """
    CPU 性能测试 - 通过 sysbench 或 dd 命令评估远程服务器 CPU 性能。

    前端使用场景：仪表盘的 "性能测试" 功能中的 CPU 测试项。

    注意：此端点的 category 为 "performance" 而非 "detection"，
    前端应根据此字段区分安全检测与性能测试。
    """
    result = (await detection_manager.detect_cpu_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/memory-test")
async def detect_memory_test():
    """
    内存性能测试 - 评估远程服务器内存读写速度和带宽。

    前端使用场景：仪表盘的 "性能测试" 功能中的内存测试项。
    """
    result = (await detection_manager.detect_memory_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/disk-test")
async def detect_disk_test():
    """
    磁盘 I/O 性能测试 - 评估远程服务器磁盘读写速度。

    前端使用场景：仪表盘的 "性能测试" 功能中的磁盘测试项。
    """
    result = (await detection_manager.detect_disk_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/network-test")
async def detect_network_test():
    """
    网络性能测试 - 评估远程服务器网络延迟与带宽。

    前端使用场景：仪表盘的 "性能测试" 功能中的网络测试项。
    """
    result = (await detection_manager.detect_network_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


# ============================================================
# 基线检测命令端点 (Security Baseline Detection)
# ============================================================
# 以下端点用于检查 Linux 系统是否满足安全基线要求。
# 每个端点对应一条或多条等保/安全基线的检查项。
# 依赖：app.services.detection_manager 中的各基线检查函数

@router.post("/detect/password-policy")
async def detect_password_policy():
    """
    密码策略基线检测 - 检查系统密码复杂度要求。

    检测内容：
    - /etc/login.defs 中的 PASS_MIN_LEN 等配置
    - /etc/pam.d/common-password 中的 pam_pwquality 参数
    - 密码最短长度、复杂度要求（字母/数字/特殊字符）
    - 密码有效期和过期提醒时间

    前端使用场景：基线检查页面的 "密码策略" 检查项。
    """
    result = (
        await detection_manager.detect_password_policy(get_ssh_manager())
    ).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "baseline",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/sudo-config")
async def detect_sudo_config():
    """
    sudo 配置基线检测 - 检查 sudoers 安全配置。

    检测内容：
    - /etc/sudoers 语法正确性
    - NOPASSWD 标签的使用（是否存在无密码提权）
    - sudo 命令日志记录（log_input/log_output）
    - sudo 使用时间戳超时设置

    前端使用场景：基线检查页面的 "sudo 配置" 检查项。
    """
    result = (await detection_manager.detect_sudo_config(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "baseline",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/pam-config")
async def detect_pam_config():
    """
    PAM 认证模块配置基线检测 - 检查 PAM 安全策略。

    检测内容：
    - /etc/pam.d/common-auth 中的认证模块链
    - pam_tally2 或 pam_faillock 的登录失败锁定配置
    - pam_limits 资源限制
    - pam_umask 默认权限掩码

    前端使用场景：基线检查页面的 "PAM 配置" 检查项。
    """
    result = (await detection_manager.detect_pam_config(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "baseline",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result


@router.post("/detect/account-lockout")
async def detect_account_lockout():
    """
    账户锁定策略基线检测 - 检查登录失败后的账户锁定机制。

    检测内容：多次登录失败后是否自动锁定账户、锁定时间和解锁方式。

    前端使用场景：基线检查页面的 "账户锁定" 检查项。
    """
    return (
        await detection_manager.detect_account_lockout(get_ssh_manager())
    ).model_dump()


@router.post("/detect/selinux-status")
async def detect_selinux_status():
    """
    SELinux/AppArmor 状态基线检测 - 检查强制访问控制是否启用。

    检测内容：SELinux 当前的 enforcing/permissive/disabled 状态，
    以及 AppArmor 的启用状态。

    前端使用场景：基线检查页面的 "SELinux 状态" 检查项。
    """
    return (
        await detection_manager.detect_selinux_status(get_ssh_manager())
    ).model_dump()


@router.post("/detect/kernel-params")
async def detect_kernel_params():
    """
    内核参数基线检测 - 检查系统内核安全参数。

    检测内容：
    - net.ipv4.tcp_syncookies（SYN Cookie 防御）
    - net.ipv4.ip_forward（IP 转发是否关闭）
    - net.ipv4.conf.all.accept_source_route（源路由安全）
    - kernel.randomize_va_space（ASLR 是否开启）

    前端使用场景：基线检查页面的 "内核参数" 检查项。
    """
    return (
        await detection_manager.detect_kernel_params(get_ssh_manager())
    ).model_dump()


@router.post("/detect/system-updates")
async def detect_system_updates():
    """
    系统更新状态基线检测 - 检查安全补丁是否及时安装。

    检测内容：待安装的安全更新数量、最近一次更新时间和更新源配置。

    前端使用场景：基线检查页面的 "系统更新" 检查项。
    """
    return (
        await detection_manager.detect_system_updates(get_ssh_manager())
    ).model_dump()


@router.post("/detect/unnecessary-services")
async def detect_unnecessary_services():
    """
    非必要服务基线检测 - 检查是否存在不必要的网络服务。

    检测内容：扫描已启用的 systemd 服务，标记如 telnet、rsh、
    finger 等不安全或不必要的服务。

    前端使用场景：基线检查页面的 "非必要服务" 检查项。
    """
    return (
        await detection_manager.detect_unnecessary_services(get_ssh_manager())
    ).model_dump()


@router.post("/detect/auto-start-services")
async def detect_auto_start_services():
    """
    自启动服务基线检测 - 检查系统开机自启动的服务项。

    检测内容：列出所有 enabled 状态的 systemd 服务，标记可能的安全风险。

    前端使用场景：基线检查页面的 "自启动服务" 检查项。
    """
    return (
        await detection_manager.detect_auto_start_services(get_ssh_manager())
    ).model_dump()


@router.post("/detect/audit-config")
async def detect_audit_config():
    """
    auditd 审计配置基线检测 - 检查 Linux 审计子系统配置。

    检测内容：auditd 服务状态、审计规则和审计日志设置。

    前端使用场景：基线检查页面的 "审计配置" 检查项。
    """
    return (await detection_manager.detect_audit_config(get_ssh_manager())).model_dump()


@router.post("/detect/history-audit")
async def detect_history_audit():
    """
    历史命令审计基线检测 - 检查 Shell 历史记录的安全配置。

    检测内容：HISTSIZE、HISTFILE 设置，历史记录是否包含时间戳，
    以及是否存在历史记录被禁用的风险。

    前端使用场景：基线检查页面的 "历史审计" 检查项。
    """
    return (
        await detection_manager.detect_history_audit(get_ssh_manager())
    ).model_dump()


@router.post("/detect/ntp-config")
async def detect_ntp_config():
    """
    NTP 时间同步基线检测 - 检查系统时间同步服务状态。

    检测内容：NTP/chrony 服务是否运行、时间源配置和时钟偏差。

    前端使用场景：基线检查页面的 "NTP 配置" 检查项。
    """
    return (await detection_manager.detect_ntp_config(get_ssh_manager())).model_dump()


@router.post("/detect/dns-config")
async def detect_dns_config():
    """
    DNS 配置基线检测 - 检查系统 DNS 解析器配置。

    检测内容：/etc/resolv.conf 中的 DNS 服务器列表，是否存在不安全的解析器。

    前端使用场景：基线检查页面的 "DNS 配置" 检查项。
    """
    return (await detection_manager.detect_dns_config(get_ssh_manager())).model_dump()


# ============================================================
# SSH 终端管理端点 (SSH Terminal Management)
# ============================================================
# 管理交互式 PTY 终端会话的生命周期，支持多终端标签页。
# 每个终端会话由前端生成的 terminal_id 唯一标识。
# 依赖：SSHManager 的终端会话方法族

@router.post("/ssh/terminal/create")
async def ssh_create_terminal_session(req: CreateTerminalSessionRequest):
    """
    在远程服务器上创建一个交互式 PTY 终端会话。

    前端使用场景：终端页面打开新标签页时。

    依赖：SSHManager.create_terminal_session

    数据流：
        POST /api/v1/ssh/terminal/create { terminal_id, cols, rows }
            ──► SSHManager.create_terminal_session()
                ──► 通过 SSH 通道分配 PTY（伪终端）
                    ──► 将 PTY 尺寸 (cols x rows) 发送给远程 Shell
                        ──► 返回 {"terminal_id": "xxx"}
                        后续通过 /ssh/terminal/send-input 和 /ssh/terminal/read-output
                        与该终端会话交互

    错误处理：
        - 无活动 SSH 连接 → HTTP 400
        - PTY 分配失败 → HTTP 400
    """
    ssh = get_ssh_manager()
    try:
        result = await ssh.create_terminal_session(req.terminal_id, req.cols, req.rows)
        return {"terminal_id": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ssh/terminal/close")
async def ssh_close_terminal_session(terminal_id: str):
    """
    关闭指定的终端会话。

    前端使用场景：终端页面关闭标签页时。

    依赖：SSHManager.close_terminal_session

    数据流：
        POST /api/v1/ssh/terminal/close (body: terminal_id)
            ──► SSHManager 关闭 PTY 并清理会话资源
                ──► 返回 {"success": true}
    """
    ssh = get_ssh_manager()
    await ssh.close_terminal_session(terminal_id)
    return {"success": True}


@router.post("/ssh/terminal/close-all")
async def ssh_close_all_terminal_sessions():
    """
    关闭所有活动的终端会话。

    前端使用场景：SSH 连接断开时清理所有终端标签页。

    依赖：SSHManager.close_all_terminal_sessions
    """
    ssh = get_ssh_manager()
    await ssh.close_all_terminal_sessions()
    return {"success": True}


@router.post("/ssh/terminal/send-input")
async def ssh_send_input(req: SendTerminalInputRequest):
    """
    向终端会话发送键盘输入（支持 ANSI 转义序列）。

    前端使用场景：用户在终端中键入字符时，每个按键（包括 Ctrl+C、
    方向键等特殊按键）都会通过此端点发送到远程 PTY。

    依赖：SSHManager.send_terminal_input

    数据流：
        POST /api/v1/ssh/terminal/send-input { terminal_id, data }
            ──► data.encode("utf-8")
                ──► SSHManager 通过 PTY 输入通道发送字节流
                    ──► 返回 {"success": true}
    """
    ssh = get_ssh_manager()
    await ssh.send_terminal_input(req.terminal_id, req.data.encode("utf-8"))
    return {"success": True}


@router.post("/ssh/terminal/read-output")
async def ssh_read_terminal_output(terminal_id: str):
    """
    读取终端会话的最新输出内容（增量读取，非阻塞）。

    前端使用场景：前端以一定频率轮询此端点获取终端输出，
    并在 xterm.js 上渲染。

    依赖：SSHManager.read_terminal_output

    数据流：
        POST /api/v1/ssh/terminal/read-output (body: terminal_id)
            ──► SSHManager 从 PTY 输出缓冲区读取增量数据
                ──► UTF-8 解码（错误字符用替换字符）
                    ──► 返回 {"data": "..."}
    """
    ssh = get_ssh_manager()
    data = await ssh.read_terminal_output(terminal_id)
    return {"data": data.decode("utf-8", errors="replace")}


@router.post("/ssh/terminal/get-completion")
async def ssh_get_completion(input: str):
    """
    在终端上下文中获取当前输入的命令补全建议。

    前端使用场景：终端页面按 Tab 键时调用的补全逻辑。

    依赖：SSHManager.get_command_completion

    数据流：同 /command/completion，但在终端会话上下文中执行。
    """
    ssh = get_ssh_manager()
    result = await ssh.get_command_completion(input)
    return result.model_dump()


# ============================================================
# 日志分析端点 (Log Analysis)
# ============================================================
# 提供对远程服务器系统日志和安全日志的读取、搜索和分析功能。
# 依赖：app.services.log_analysis

@router.post("/log/read-system")
async def read_system_log(req: ReadSystemLogRequest):
    """
    读取远程服务器上的系统日志文件（支持分页和过滤）。

    前端使用场景：日志分析页面的 "系统日志" 标签页。

    依赖：log_analysis.read_system_log

    数据流：
        POST /api/v1/log/read-system { log_path, page, page_size, filter, date_filter }
            ──► log_analysis.read_system_log()
                ──► 通过 SSH 执行 tail/head/grep 组合命令
                    ──► 返回分页后的日志行列表和总数
    """
    ssh = get_ssh_manager()
    result = await log_analysis.read_system_log(
        ssh, req.log_path, req.page, req.page_size, req.filter, req.date_filter
    )
    return result.model_dump()


@router.post("/log/read-journalctl")
async def read_journalctl_log(req: ReadJournalctlLogRequest):
    """
    通过 journalctl 读取 systemd 日志（支持服务单元和事件范围过滤）。

    前端使用场景：日志分析页面的 "systemd 日志" 标签页。

    依赖：log_analysis.read_journalctl_log

    数据流：
        POST /api/v1/log/read-journalctl { page, page_size, unit, filter, since, until }
            ──► log_analysis.read_journalctl_log()
                ──► 通过 SSH 执行 journalctl 命令组合
                    ──► 返回分页后的日志条目列表
    """
    ssh = get_ssh_manager()
    result = await log_analysis.read_journalctl_log(
        ssh, req.page, req.page_size, req.unit, req.filter, req.since, req.until
    )
    return result.model_dump()


@router.get("/log/list-files")
async def list_log_files():
    """
    列出远程服务器上可读取的日志文件。

    前端使用场景：日志分析页面左侧的 "日志文件列表" 导航树。

    依赖：log_analysis.list_log_files

    数据流：
        GET /api/v1/log/list-files
            ──► 扫描 /var/log 等常见日志目录
                ──► 返回 [LogFileInfo, ...]（文件名、路径、大小、修改时间）
    """
    ssh = get_ssh_manager()
    files = await log_analysis.list_log_files(ssh)
    return [f.model_dump() for f in files]


@router.post("/log/file-info")
async def get_log_file_info(log_path: str):
    """
    获取指定日志文件的元数据信息。

    前端使用场景：点击日志文件列表中的某个文件时，右侧展示文件基本信息和统计。

    依赖：log_analysis.get_log_file_info

    数据流：
        POST /api/v1/log/file-info (body: log_path="/var/log/auth.log")
            ──► SSH 执行 wc / stat / head / tail 等统计命令
                ──► 返回 { size, lines, first_line, last_line, ... }
    """
    ssh = get_ssh_manager()
    info = await log_analysis.get_log_file_info(ssh, log_path)
    return info.model_dump()


# ============================================================
# AI 代理辅助函数与端点 (AI Proxy)
# ============================================================
# 将前端的 AI API 请求通过 Python 后端代理转发，主要目的：
# 1. 规避浏览器的 CORS 跨域限制（AI API 通常不允许浏览器直接调用）
# 2. 避免 API Key 暴露在前端 JavaScript 上下文中
# 3. 统一管理请求超时和错误处理
# 支持流式（SSE, Server-Sent Events）和非流式两种响应模式。

def _do_ai_proxy_post(
    url: str, headers: Dict[str, str], body: Dict[str, Any], timeout_seconds: int
) -> Dict[str, Any]:
    """
    同步执行 AI API 的非流式 POST 请求（在独立线程中运行）。

    此函数是 /ai/chat-proxy 非流式模式的后端核心实现。
    使用 Python 标准库 urllib（而非 aiohttp/httpx）以减少外部依赖。

    参数:
        url: 上游 AI API 的完整 URL（如 https://api.openai.com/v1/chat/completions）
        headers: 转发给上游的 HTTP 请求头（含 Authorization 等）
        body: 请求体字典（会被 JSON 序列化）
        timeout_seconds: 超时时间（秒），至少为 5 秒

    返回:
        上游 API 返回的 JSON 解析结果字典

    安全措施:
        - 仅透传不含换行符的基础文本头，防止 HTTP 头注入攻击
        - 空 key 或非字符串 key 的 header 会被跳过

    数据流（在 asyncio.to_thread 中执行）:
        构建 urllib.request.Request
            ──► 设置 Content-Type: application/json
                ──► 逐条添加转发的 headers
                    ──► urllib.request.urlopen() POST 请求
                        ──► 读取响应体 → UTF-8 解码 → JSON 解析
                            ──► 返回解析后的字典
    """
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    # 透传前端提供的自定义 headers（如 Authorization, X-API-Key 等）
    for k, v in headers.items():
        if not k or not isinstance(k, str):
            continue
        # 仅透传基础文本头，避免注入异常头
        if "\n" in k or "\r" in k:
            continue
        req.add_header(k, str(v))

    with urllib.request.urlopen(req, timeout=max(5, timeout_seconds)) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _do_ai_proxy_stream(
    url: str, headers: Dict[str, str], body: Dict[str, Any], timeout_seconds: int
):
    """
    同步执行 AI API 的流式（SSE）POST 请求，返回原始 HTTP 响应对象。

    与 _do_ai_proxy_post 的区别：
    - 额外设置 Accept: text/event-stream 头
    - 不读取和解析响应体，而是将原始 HTTPResponse 对象返回给调用方
      由调用方通过 StreamingResponse 逐步 yield 数据块

    参数: 同 _do_ai_proxy_post

    返回:
        urllib HTTPResponse 对象，由调用方的 stream_generator 逐步读取
    """
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")  # SSE 必需
    for k, v in headers.items():
        if not k or not isinstance(k, str):
            continue
        if "\n" in k or "\r" in k:
            continue
        req.add_header(k, str(v))

    # 使用 urlopen 而不是 context manager，因为调用方负责关闭
    resp = urllib.request.urlopen(req, timeout=max(5, timeout_seconds))
    return resp


@router.post("/ai/chat-proxy")
async def ai_chat_proxy(req: AIProxyRequest):
    """
    AI 聊天请求后端代理——整个 AI 功能的核心入口。

    前端使用场景：AI 对话页面发送的所有聊天消息都经过此端点转发。

    支持两种模式：
        1. 非流式（stream=false）：等待 AI 完整响应后一次性返回 JSON
        2. 流式（stream=true）：通过 SSE (Server-Sent Events) 逐步推送每个 token

    依赖：Python 标准库 urllib（无第三方 HTTP 客户端依赖）

    数据流（流式模式）:
        POST /api/v1/ai/chat-proxy { url, headers, body: { stream: true }, timeout_seconds }
            ──► asyncio.to_thread(_do_ai_proxy_stream) 在独立线程中发起请求
                ──► 返回 StreamingResponse (media_type="text/event-stream")
                    前端通过 EventSource API 逐 token 接收

    数据流（非流式模式）:
        同上，但调用 _do_ai_proxy_post，等待完整响应后返回 {"ok": true, "data": {...}}

    错误处理：
        - urllib.error.HTTPError（上游 API 返回错误）→ HTTP 502，附带上游状态码和错误体
        - urllib.error.URLError（无法连接上游）→ HTTP 502，附带连接失败原因
        - 其他异常 → HTTP 500

    StreamingResponse 的安全头：
        - Cache-Control: no-cache（禁止浏览器缓存 SSE 数据）
        - Connection: keep-alive（保持长连接）
        - X-Accel-Buffering: no（禁用 nginx 代理缓冲，确保流式传输实时性）
    """
    # 从请求体中读取 stream 标志判断是否为流式请求
    is_stream = req.body.get("stream", False)

    if is_stream:
        # ---- 流式模式 (SSE) ----
        try:
            resp = await asyncio.to_thread(
                _do_ai_proxy_stream,
                req.url,
                req.headers,
                req.body,
                req.timeout_seconds,
            )
        except urllib.error.HTTPError as e:
            # 上游 API 返回了 HTTP 错误（如 401 未授权、429 限流）
            try:
                err_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_text = str(e)
            raise HTTPException(
                status_code=502, detail=f"上游 AI API 错误：{e.code} - {err_text}"
            ) from e
        except urllib.error.URLError as e:
            # 网络不通或 DNS 解析失败
            raise HTTPException(
                status_code=502, detail=f"无法连接上游 AI API: {e.reason}"
            ) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 代理请求失败：{e}") from e

        def stream_generator():
            """
            SSE 数据块生成器。

            从上游 HTTP 响应中每次读取 4096 字节，yield 给 StreamingResponse。
            前端通过 EventSource.onmessage 接收每个 chunk。
            finally 块确保响应对象被正确关闭，防止连接泄漏。
            """
            try:
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    yield chunk
            finally:
                resp.close()

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 nginx 代理缓冲
            },
        )

    # ---- 非流式模式 ----
    try:
        data = await asyncio.to_thread(
            _do_ai_proxy_post,
            req.url,
            req.headers,
            req.body,
            req.timeout_seconds,
        )
        return {"ok": True, "data": data}
    except urllib.error.HTTPError as e:
        try:
            err_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_text = str(e)
        raise HTTPException(
            status_code=502, detail=f"上游 AI API 错误：{e.code} - {err_text}"
        ) from e
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=502, detail=f"无法连接上游 AI API: {e.reason}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 代理请求失败：{e}") from e


# ============================================================
# 加密 & 设备信息端点 (Crypto & Device Info)
# ============================================================
# 提供 RSA 公钥分发和设备唯一标识获取功能。
# 这些端点在应用启动时由前端调用，用于建立安全通信通道和设备认证。

@router.get("/crypto/rsa-public-key")
async def get_rsa_key():
    """
    获取本地 RSA 公钥（PEM 格式）。

    前端使用场景：
    - 登录/注册时前端用此公钥加密敏感数据
    - AI API Key 等敏感配置的本地加密存储
    - 前端与后端之间的敏感参数加密通信

    依赖：app.utils.crypto.get_rsa_public_key

    数据流：
        GET /api/v1/crypto/rsa-public-key
            ──► 如果密钥对不存在则自动生成（2048 位 RSA）
                ──► 返回 {"public_key": "-----BEGIN PUBLIC KEY-----\n..."}
    """
    return {"public_key": get_rsa_public_key()}


@router.get("/device/uuid")
async def get_device_uuid_endpoint():
    """
    获取当前设备的唯一标识符（UUID）。

    前端使用场景：
    - 设备注册与许可验证
    - 加密密钥派生（结合设备 UUID 生成与设备绑定的密钥）
    - 远程连接管理中的设备身份标识

    依赖：app.services.device_info.get_device_uuid

    数据流：
        GET /api/v1/device/uuid
            ──► 基于硬件信息（MAC 地址/主板序列号/机器 ID 等）
                生成稳定的设备指纹 UUID
                ──► 返回 DeviceUUID 模型序列化结果
    """
    info = get_device_uuid()
    return info.model_dump()
