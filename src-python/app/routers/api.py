from __future__ import annotations
import json
import os
import tempfile
import time
import asyncio
import logging
logger = logging.getLogger(__name__)
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar
import asyncssh
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
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
router = APIRouter(prefix="/api/v1", tags=["lovelyres"])
T = TypeVar("T")
async def _wrap_ssh_transport(factory: Callable[[], Awaitable[T]]) -> T:
    try:
        return await factory()
    except ConnectionError as e:
        msg = str(e) or "没有活动的 SSH 连接，请先在应用中连接 SSH 后再使用 SFTP。"
        raise HTTPException(status_code=400, detail=msg) from e
    except asyncssh.Error as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
_ssh_manager: Optional[SSHManager] = None
"""SSH 实时连接管理器单例，持有当前活动的 SSH/PTY 连接和 SFTP 会话。"""
_ssh_connection_manager: Optional[SSHConnectionManager] = None
"""SSH 连接配置管理器单例，负责连接配置的加密存储、加载、删除等持久化操作。"""
_window_manager: Optional[WindowManager] = None
"""桌面窗口管理器单例，支持最小化、最大化、关闭及开发者工具等窗口操作。"""
_app_settings: Optional[AppSettings] = None
"""应用设置单例（主题、语言、快捷键等），启动时从本地配置文件加载。"""
def init_state():
    global _ssh_manager, _ssh_connection_manager, _window_manager, _app_settings
    _ssh_manager = SSHManager()
    _ssh_connection_manager = SSHConnectionManager()
    _window_manager = WindowManager()
    _app_settings = load_settings()
    print("LovelyRes Python 后端初始化完成")
def get_ssh_manager() -> SSHManager:
    if _ssh_manager is None:
        raise HTTPException(status_code=500, detail="SSH管理器未初始化")
    return _ssh_manager
def get_connection_manager() -> SSHConnectionManager:
    if _ssh_connection_manager is None:
        raise HTTPException(status_code=500, detail="SSH连接管理器未初始化")
    return _ssh_connection_manager
class ConnectDirectRequest(BaseModel):
    host: str
    """目标服务器 IP 或域名"""
    port: int = 22
    """SSH 端口，默认 22"""
    username: str
    """登录用户名"""
    password: str
    """登录密码（明文传输，建议前端使用加密密码端点）"""
class ConnectWithAuthRequest(BaseModel):
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
    command: str
    """要执行的 Shell 命令"""
    username: Optional[str] = None
    """以指定用户身份执行（可选），底层使用 sudo -u 实现"""
class SftpWriteRequest(BaseModel):
    path: str
    """远程文件绝对路径"""
    content: str
    """要写入的文本内容（UTF-8 编码后写入）"""
class SftpCompressRequest(BaseModel):
    source_path: str
    """要压缩的源文件/目录路径"""
    target_path: str
    """压缩后的目标文件路径（含文件名，如 /tmp/backup.tar.gz）"""
    format: str = "tar.gz"
    """压缩格式，当前支持 tar.gz / zip"""
class SftpExtractRequest(BaseModel):
    archive_path: str
    """远程压缩包路径"""
    target_dir: str
    """解压目标目录"""
    overwrite: bool = True
    """是否覆盖已存在的文件，默认 True"""
class SftpUploadRequest(BaseModel):
    local_path: str
    """本地文件绝对路径"""
    remote_path: str
    """远程目标路径"""
class SftpDownloadRequest(BaseModel):
    remote_path: str
    """远程文件路径"""
    local_path: str
    """本地保存路径"""
class SftpChmodRequest(BaseModel):
    path: str
    """远程文件/目录路径"""
    mode: int
    """权限模式（八进制，如 0o755 对应十进制 493）"""
class SaveTempFileRequest(BaseModel):
    file_name: str
    """文件名"""
    data: str
    """Base64 编码的文件内容"""
class DockerActionRequest(BaseModel):
    container_id: str
    """Docker 容器 ID 或名称"""
    action: str
    """操作类型：start / stop / restart / pause / unpause / remove"""
class DockerLogsOptions(BaseModel):
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
    container_id: str
    """Docker 容器 ID 或名称"""
    options: Optional[DockerLogsOptions] = None
    """日志查看选项，为 None 时使用默认选项"""
class DockerExecRequest(BaseModel):
    container_id: str
    """Docker 容器 ID 或名称"""
    command: str
    """要在容器内执行的命令"""
    shell: str = "sh"
    """使用的 Shell 类型，默认 sh（也可用 bash）"""
class DockerWriteFileRequest(BaseModel):
    container_id: str
    """Docker 容器 ID 或名称"""
    path: str
    """容器内的目标文件路径"""
    content: str
    """要写入的文本内容"""
class DockerCopyRequest(BaseModel):
    container_id: str
    """Docker 容器 ID 或名称"""
    direction: str
    """复制方向：to_container（本地→容器）/ from_container（容器→本地）"""
    source: str
    """源路径"""
    target: str
    """目标路径"""
class CreateTerminalSessionRequest(BaseModel):
    terminal_id: str
    """终端会话的唯一标识（由前端生成 UUID）"""
    cols: int = 80
    """终端列数（每行字符数），默认 80"""
    rows: int = 24
    """终端行数，默认 24"""
class SendTerminalInputRequest(BaseModel):
    terminal_id: str
    """目标终端会话 ID"""
    data: str
    """要发送的输入数据（键盘按键、控制序列等）"""
class SetThemeRequest(BaseModel):
    theme: str
    """主题名称，如 "light" / "dark"，由前端主题管理器定义"""
class SaveSettingsRequest(BaseModel):
    settings: Dict[str, Any]
    """设置键值对字典，会通过 AppSettings.model_validate 校验"""
class WriteSettingsFileRequest(BaseModel):
    content: str
    """配置文件的原始文本内容"""
class EncryptPasswordRequest(BaseModel):
    password: str
    """明文密码"""
class DecryptPasswordRequest(BaseModel):
    encrypted_password: str
    """已加密的密码字符串"""
class ReadSystemLogRequest(BaseModel):
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
    path: str
    """远程服务器上的文件绝对路径"""
    action: Optional[str] = None
    """可选的分析动作（如 md5 / sha256 / strings / elf 等），
       为 None 时执行完整分析"""
class DialogFilterRequest(BaseModel):
    name: Optional[str] = None
    """过滤器显示名称（如 "文本文件"）"""
    extensions: List[str] = Field(default_factory=list)
    """文件扩展名列表（如 [".txt", ".md"]）"""
class OpenDialogRequest(BaseModel):
    multiple: bool = False
    """是否允许多选文件，默认 False"""
    directory: bool = False
    """是否选择目录（directory=True 时忽略 multiple 参数），默认 False"""
    filters: List[DialogFilterRequest] = Field(default_factory=list)
    """文件类型过滤器列表"""
    default_path: Optional[str] = None
    """对话框打开时的默认路径"""
class SaveDialogRequest(BaseModel):
    filters: List[DialogFilterRequest] = Field(default_factory=list)
    """文件类型过滤器列表"""
    default_path: Optional[str] = None
    """对话框打开时的默认路径和默认文件名"""
def _run_native_dialog(kind: str, options: Dict[str, Any]) -> Any:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("当前环境不支持本机文件对话框") from exc
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.update()
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
    if not filetypes:
        filetypes = [("所有文件", "*.*")]
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
    dialog_kwargs: Dict[str, Any] = {"parent": root}
    if initialdir:
        dialog_kwargs["initialdir"] = initialdir
    if initialfile:
        dialog_kwargs["initialfile"] = initialfile
    if kind != "open_directory":
        dialog_kwargs["filetypes"] = filetypes
    try:
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
        root.destroy()
    if kind == "open_files":
        return list(result) if result else []
    return result or None
@router.post("/window/minimize")
async def minimize_window():
    return {"event": "window-minimize"}
@router.post("/window/toggle-maximize")
async def toggle_maximize():
    return {"event": "window-toggle-maximize"}
@router.post("/window/close")
async def close_window():
    return {"event": "window-close"}
@router.post("/window/open-devtools")
async def open_devtools():
    return {"event": "window-open-devtools"}
@router.post("/dialog/open")
async def open_dialog(req: OpenDialogRequest):
    kind = (
        "open_directory"
        if req.directory
        else "open_files"
        if req.multiple
        else "open_file"
    )
    try:
        path = await asyncio.to_thread(
            _run_native_dialog,
            kind,
            req.model_dump(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"打开文件对话框失败: {exc}"
        ) from exc
    return {"path": path if path else None}
@router.post("/dialog/save")
async def save_dialog(req: SaveDialogRequest):
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
@router.get("/theme/settings")
async def get_theme():
    current_theme = _app_settings.theme if _app_settings else "light"
    return get_theme_settings(current_theme)
@router.post("/theme/set")
async def set_current_theme(req: SetThemeRequest):
    global _app_settings
    if _app_settings:
        _app_settings.theme = req.theme
        save_settings(_app_settings)
    return {"event": "theme-changed", "theme": req.theme}
@router.get("/settings")
async def get_app_settings():
    global _app_settings
    if _app_settings is None:
        _app_settings = load_settings()
    return _app_settings.model_dump()
@router.post("/settings/save")
async def save_app_settings(req: SaveSettingsRequest):
    global _app_settings
    try:
        _app_settings = AppSettings.model_validate(req.settings)
        save_settings(_app_settings)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.get("/settings/file")
async def read_settings():
    return {"content": read_settings_file()}
@router.post("/settings/file/write")
async def write_settings(req: WriteSettingsFileRequest):
    write_settings_file(req.content)
    return {"success": True}
@router.get("/system/fonts")
async def get_fonts():
    return {"fonts": get_system_fonts()}
@router.get("/ssh/connections")
async def load_ssh_connections():
    manager = get_connection_manager()
    connections = manager.load_connections()
    return [c.model_dump(mode="json") for c in connections]
@router.post("/ssh/connections/save")
async def save_ssh_connections(connections: List[SSHConnection]):
    manager = get_connection_manager()
    manager.save_connections(connections)
    return {"success": True}
@router.post("/ssh/encrypt-password")
async def encrypt_password(req: EncryptPasswordRequest):
    manager = get_connection_manager()
    return {"encrypted": manager.encrypt_password(req.password)}
@router.post("/ssh/decrypt-password")
async def decrypt_password(req: DecryptPasswordRequest):
    manager = get_connection_manager()
    return {"decrypted": manager.decrypt_password(req.encrypted_password)}
@router.post("/ssh/connect")
async def ssh_connect_with_auth(req: ConnectWithAuthRequest):
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
    ssh = get_ssh_manager()
    result = await ssh.execute_command(req.command)
    return result.model_dump(mode="json")
@router.post("/ssh/disconnect")
async def ssh_disconnect():
    ssh = get_ssh_manager()
    await ssh.disconnect()
    return {"success": True}
@router.post("/ssh/connect-direct")
async def ssh_connect_direct(req: ConnectDirectRequest):
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
    ssh = get_ssh_manager()
    await ssh.disconnect()
    return {"success": True}
@router.post("/ssh/execute-command-direct")
async def ssh_execute_command_direct(req: ExecuteCommandRequest):
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command_as_user(req.command, req.username)
    return result.model_dump(mode="json")
@router.post("/ssh/execute-dashboard-command")
async def ssh_execute_dashboard_command(req: ExecuteCommandRequest):
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")
@router.post("/ssh/execute-emergency-command")
async def ssh_execute_emergency_command(req: ExecuteCommandRequest):
    ssh = get_ssh_manager()
    if req.username:
        result = await ssh.execute_dashboard_command_as_user(req.command, req.username)
    else:
        result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")
@router.post("/ssh/execute-detection-command")
async def execute_detection_command(req: ExecuteCommandRequest):
    ssh = get_ssh_manager()
    result = await ssh.execute_dashboard_command(req.command)
    return result.model_dump(mode="json")
@router.get("/ssh/connection-status")
async def ssh_get_connection_status():
    ssh = get_ssh_manager()
    status = await ssh.get_connection_status()
    return status.model_dump(mode="json") if status else None
@router.post("/ssh/test-performance")
async def test_ssh_performance():
    ssh = get_ssh_manager()
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
    ssh = get_ssh_manager()
    if not ssh.is_connected():
        raise HTTPException(status_code=400, detail="没有活动的 SSH 连接")
    os_release_cmd = "cat /etc/os-release 2>/dev/null || cat /etc/lsb-release 2>/dev/null || echo 'ID=generic'"
    os_release_output = await ssh.execute_dashboard_command(os_release_cmd)
    os_release_content = os_release_output.output
    pkg_mgr_cmd = "which apt 2>/dev/null && echo 'apt' || which yum 2>/dev/null && echo 'yum' || which dnf 2>/dev/null && echo 'dnf' || which pacman 2>/dev/null && echo 'pacman' || which zypper 2>/dev/null && echo 'zypper' || which apk 2>/dev/null && echo 'apk' || echo 'unknown'"
    pkg_mgr_output = await ssh.execute_dashboard_command(pkg_mgr_cmd)
    package_manager = pkg_mgr_output.output.strip().split("\n")[-1].strip()
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
    system_type = id_val
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
@router.post("/sftp/list-files")
async def sftp_list_files(path: str):
    async def _go():
        ssh = get_ssh_manager()
        return await ssh.list_sftp_files(path)
    files = await _wrap_ssh_transport(_go)
    return [f.model_dump(mode="json") for f in files]
@router.post("/sftp/read-file")
async def sftp_read_file(path: str, max_bytes: Optional[int] = None):
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
    async def _go():
        ssh = get_ssh_manager()
        await ssh.write_sftp_file(req.path, req.content.encode("utf-8"))
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/upload")
async def sftp_upload(req: SftpUploadRequest):
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
    import shutil
    tmp_path = None
    try:
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
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return {"success": True}
@router.post("/sftp/download")
async def sftp_download(req: SftpDownloadRequest):
    async def _go():
        ssh = get_ssh_manager()
        await ssh.download_file(req.remote_path, req.local_path)
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/create-directory")
async def sftp_create_directory(remote_path: str):
    async def _go():
        ssh = get_ssh_manager()
        await ssh.create_directory(remote_path)
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/compress")
async def sftp_compress(req: SftpCompressRequest):
    async def _go():
        ssh = get_ssh_manager()
        await ssh.compress_file(req.source_path, req.target_path, req.format)
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/extract")
async def sftp_extract(req: SftpExtractRequest):
    async def _go():
        ssh = get_ssh_manager()
        await ssh.extract_file(req.archive_path, req.target_dir)
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/chmod")
async def sftp_chmod(req: SftpChmodRequest):
    async def _go():
        ssh = get_ssh_manager()
        await ssh.chmod_sftp(req.path, req.mode)
    await _wrap_ssh_transport(_go)
    return {"success": True}
@router.post("/sftp/get-file-details")
async def sftp_get_file_details(path: str):
    async def _go():
        ssh = get_ssh_manager()
        return await ssh.get_file_details(path)
    details = await _wrap_ssh_transport(_go)
    return details.model_dump(mode="json")
@router.post("/sftp/save-temp-file")
async def save_temp_file(req: SaveTempFileRequest):
    import base64
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, req.file_name)
    data = base64.b64decode(req.data)
    with open(temp_path, "wb") as f:
        f.write(data)
    return {"path": temp_path}
@router.post("/file-analysis")
async def sftp_file_analysis_endpoint(req: FileAnalysisRequest):
    async def _go():
        ssh = get_ssh_manager()
        return await file_analysis.sftp_file_analysis(ssh, req.path, req.action)
    result = await _wrap_ssh_transport(_go)
    return result
@router.post("/file-analysis/independent")
async def sftp_file_analysis_independent_endpoint(req: FileAnalysisRequest):
    async def _go():
        ssh = get_ssh_manager()
        return await file_analysis.sftp_file_analysis_independent(ssh, req.path, req.action)
    result = await _wrap_ssh_transport(_go)
    return result
@router.get("/bash/environment-info")
async def get_bash_environment_info():
    ssh = get_ssh_manager()
    result = await ssh.get_bash_environment_info()
    return result.model_dump()
@router.post("/command/completion")
async def get_command_completion(input: str):
    ssh = get_ssh_manager()
    result = await ssh.get_command_completion(input)
    return result.model_dump()
@router.post("/detect/port-scan")
async def detect_port_scan():
    result = (await detection_manager.detect_port_scan(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/user-audit")
async def detect_user_audit():
    result = (await detection_manager.detect_user_audit(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/backdoor")
async def detect_backdoor():
    result = (await detection_manager.detect_backdoor(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/process-analysis")
async def detect_process_analysis():
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
    result = (await detection_manager.detect_ssh_audit(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/log-analysis")
async def detect_log_analysis():
    result = (await detection_manager.detect_log_analysis(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "detection",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/firewall-check")
async def detect_firewall_check():
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
    result = (await detection_manager.detect_cpu_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/memory-test")
async def detect_memory_test():
    result = (await detection_manager.detect_memory_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/disk-test")
async def detect_disk_test():
    result = (await detection_manager.detect_disk_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/network-test")
async def detect_network_test():
    result = (await detection_manager.detect_network_test(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "performance",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/password-policy")
async def detect_password_policy():
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
    result = (await detection_manager.detect_sudo_config(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "baseline",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/pam-config")
async def detect_pam_config():
    result = (await detection_manager.detect_pam_config(get_ssh_manager())).model_dump()
    result["endpoint_metadata"] = {
        "type": "low-level",
        "category": "baseline",
        "recommended_usage": "仅供 Agent 内部调用或调试使用",
    }
    return result
@router.post("/detect/account-lockout")
async def detect_account_lockout():
    return (
        await detection_manager.detect_account_lockout(get_ssh_manager())
    ).model_dump()
@router.post("/detect/selinux-status")
async def detect_selinux_status():
    return (
        await detection_manager.detect_selinux_status(get_ssh_manager())
    ).model_dump()
@router.post("/detect/kernel-params")
async def detect_kernel_params():
    return (
        await detection_manager.detect_kernel_params(get_ssh_manager())
    ).model_dump()
@router.post("/detect/system-updates")
async def detect_system_updates():
    return (
        await detection_manager.detect_system_updates(get_ssh_manager())
    ).model_dump()
@router.post("/detect/unnecessary-services")
async def detect_unnecessary_services():
    return (
        await detection_manager.detect_unnecessary_services(get_ssh_manager())
    ).model_dump()
@router.post("/detect/auto-start-services")
async def detect_auto_start_services():
    return (
        await detection_manager.detect_auto_start_services(get_ssh_manager())
    ).model_dump()
@router.post("/detect/audit-config")
async def detect_audit_config():
    return (await detection_manager.detect_audit_config(get_ssh_manager())).model_dump()
@router.post("/detect/history-audit")
async def detect_history_audit():
    return (
        await detection_manager.detect_history_audit(get_ssh_manager())
    ).model_dump()
@router.post("/detect/ntp-config")
async def detect_ntp_config():
    return (await detection_manager.detect_ntp_config(get_ssh_manager())).model_dump()
@router.post("/detect/dns-config")
async def detect_dns_config():
    return (await detection_manager.detect_dns_config(get_ssh_manager())).model_dump()
@router.post("/ssh/terminal/create")
async def ssh_create_terminal_session(req: CreateTerminalSessionRequest):
    ssh = get_ssh_manager()
    try:
        result = await ssh.create_terminal_session(req.terminal_id, req.cols, req.rows)
        return {"terminal_id": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.post("/ssh/terminal/close")
async def ssh_close_terminal_session(terminal_id: str):
    ssh = get_ssh_manager()
    await ssh.close_terminal_session(terminal_id)
    return {"success": True}
@router.post("/ssh/terminal/close-all")
async def ssh_close_all_terminal_sessions():
    ssh = get_ssh_manager()
    await ssh.close_all_terminal_sessions()
    return {"success": True}
@router.post("/ssh/terminal/send-input")
async def ssh_send_input(req: SendTerminalInputRequest):
    ssh = get_ssh_manager()
    await ssh.send_terminal_input(req.terminal_id, req.data.encode("utf-8"))
    return {"success": True}
@router.post("/ssh/terminal/read-output")
async def ssh_read_terminal_output(terminal_id: str):
    ssh = get_ssh_manager()
    data = await ssh.read_terminal_output(terminal_id)
    return {"data": data.decode("utf-8", errors="replace")}
@router.post("/ssh/terminal/get-completion")
async def ssh_get_completion(input: str):
    ssh = get_ssh_manager()
    result = await ssh.get_command_completion(input)
    return result.model_dump()
@router.post("/log/read-system")
async def read_system_log(req: ReadSystemLogRequest):
    ssh = get_ssh_manager()
    result = await log_analysis.read_system_log(
        ssh, req.log_path, req.page, req.page_size, req.filter, req.date_filter
    )
    return result.model_dump()
@router.post("/log/read-journalctl")
async def read_journalctl_log(req: ReadJournalctlLogRequest):
    ssh = get_ssh_manager()
    result = await log_analysis.read_journalctl_log(
        ssh, req.page, req.page_size, req.unit, req.filter, req.since, req.until
    )
    return result.model_dump()
@router.get("/log/list-files")
async def list_log_files():
    ssh = get_ssh_manager()
    files = await log_analysis.list_log_files(ssh)
    return [f.model_dump() for f in files]
@router.post("/log/file-info")
async def get_log_file_info(log_path: str):
    ssh = get_ssh_manager()
    info = await log_analysis.get_log_file_info(ssh, log_path)
    return info.model_dump()
# ==================== 渗透测试 Agent (多任务) ====================
from app.services.pentest_agent.state import State
from app.services.pentest_agent.executor import Executor
from app.services.pentest_agent.llm_client import LLMClient, set_llm_client, get_llm_client
from datetime import datetime
from uuid import uuid4

_pentest_tasks: dict[str, dict] = {}
"""所有渗透任务 {task_id: {target, state_file, start_time, task_obj, status}}"""

_PENTEST_STATE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

def _state_file(task_id: str) -> str:
    return os.path.join(_PENTEST_STATE_DIR, f"pentest_state_{task_id}.json")

def _extract_task_id_from_state_file(path: str) -> Optional[str]:
    name = os.path.basename(path)
    prefix = "pentest_state_"
    suffix = ".json"
    if not name.startswith(prefix) or not name.endswith(suffix):
        return None
    return name[len(prefix):-len(suffix)]

def _list_pentest_state_files() -> list[str]:
    if not os.path.isdir(_PENTEST_STATE_DIR):
        return []
    files = []
    for name in os.listdir(_PENTEST_STATE_DIR):
        if name.startswith("pentest_state_") and name.endswith(".json"):
            files.append(os.path.join(_PENTEST_STATE_DIR, name))
    return sorted(files, reverse=True)

def _resolve_task_state_path(task_id: str) -> Optional[str]:
    tinfo = _pentest_tasks.get(task_id)
    if tinfo and tinfo.get("state_file"):
        state_path = tinfo["state_file"]
        if os.path.exists(state_path):
            return state_path

    state_path = _state_file(task_id)
    if os.path.exists(state_path):
        return state_path
    return None

def _load_task_state(task_id: str) -> Optional[State]:
    state_path = _resolve_task_state_path(task_id)
    if not state_path or not os.path.exists(state_path):
        return None
    return State(state_path)

def _infer_task_status(task_id: str, state: Optional[State], tinfo: Optional[dict]) -> str:
    if tinfo:
        task = tinfo.get("task_obj")
        if tinfo.get("status") == "running" and task and not task.done():
            return "running"
        if tinfo.get("status"):
            return tinfo["status"]

    if state and state.data.get("phase") == "done":
        return "done"
    if state and state.data.get("actions_taken"):
        return "stopped"
    return "stopped"

def _build_history_item(task_id: str, tinfo: Optional[dict] = None) -> Optional[dict]:
    state = _load_task_state(task_id)
    state_path = _resolve_task_state_path(task_id)

    if not tinfo and not state_path:
        return None

    targets = state.data.get("targets", []) if state else []
    created_at = state.data.get("created_at") if state else None

    return {
        "task_id": task_id,
        "target": (tinfo or {}).get("target") or (targets[0] if targets else "未知目标"),
        "start_time": (tinfo or {}).get("start_time") or created_at or "",
        "status": _infer_task_status(task_id, state, tinfo),
        "phase": state.data.get("phase", "init") if state else "init",
        "findings_count": state.find_count if state else 0,
        "vuln_count": state.vuln_count if state else 0,
        "actions_count": len(state.data.get("actions_taken", [])) if state else 0,
    }

class PentestStartRequest(BaseModel):
    target: str = Field(..., description="目标 IP / 域名 / 网段")
    max_rounds: int = Field(30, ge=1, le=100, description="最大执行轮数")
    dry_run: bool = Field(False, description="不真正执行命令")
    api_key: str = Field("", description="LLM API Key")
    model: str = Field("gpt-4o-mini", description="LLM 模型")
    base_url: str = Field("https://api.openai.com/v1", description="LLM API 地址")
    provider: str = Field("openai", description="LLM 提供商: openai/deepseek/qwen/ollama")
    temperature: float = Field(0.3, ge=0, le=2, description="LLM 温度")

@router.post("/agent/pentest/start")
async def pentest_start(req: PentestStartRequest):
    # 检查是否有运行中的任务
    for tid, tinfo in _pentest_tasks.items():
        if tinfo.get("status") == "running":
            return {"success": False, "message": f"已有任务在运行中: {tid}", "task_id": tid}

    task_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    state_path = _state_file(task_id)

    client = LLMClient(
        api_key=req.api_key,
        model=req.model,
        base_url=req.base_url,
        provider=req.provider,
        temperature=req.temperature,
    )
    set_llm_client(client)

    _pentest_tasks[task_id] = {
        "target": req.target,
        "state_file": state_path,
        "start_time": str(datetime.now()),
        "status": "running",
        "task_obj": None,
    }

    async def _run_agent():
        llm = get_llm_client()
        loop = asyncio.new_event_loop()

        def llm_fn(system: str, user: str) -> str:
            return loop.run_until_complete(llm.chat(system, user))

        from app.services.pentest_agent.agent import run as agent_run

        def _blocking():
            try:
                agent_run(req.target, llm_fn, state_path, req.max_rounds, req.dry_run)
            finally:
                loop.close()

        await asyncio.to_thread(_blocking)
        _pentest_tasks[task_id]["status"] = "done"

    task = asyncio.create_task(_run_agent())
    _pentest_tasks[task_id]["task_obj"] = task
    return {"success": True, "message": "渗透任务已启动", "target": req.target, "task_id": task_id}

@router.get("/agent/pentest/status")
async def pentest_status(task_id: str):
    tinfo = _pentest_tasks.get(task_id)
    if not tinfo:
        raise HTTPException(status_code=404, detail="任务不存在")

    state = State(tinfo["state_file"])
    is_running = tinfo.get("status") == "running" and tinfo.get("task_obj") and not tinfo["task_obj"].done()
    actions = state.data["actions_taken"]
    slim_actions = []
    for a in actions[-10:]:
        slim = {k: v for k, v in a.items() if k != "full_stdout"}
        slim_actions.append(slim)
    return {
        "running": is_running,
        "phase": state.data["phase"],
        "targets": state.data["targets"],
        "findings_count": state.find_count,
        "vuln_count": state.vuln_count,
        "cred_count": len(state.data["credentials"]),
        "actions_count": len(actions),
        "actions": slim_actions,
        "task_id": task_id,
    }

@router.get("/agent/pentest/logs")
async def pentest_logs(task_id: str):
    state = _load_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "phase": state.data["phase"],
        "actions_count": len(state.data["actions_taken"]),
        "actions": state.data["actions_taken"],
        "task_id": task_id,
    }

@router.post("/agent/pentest/stop")
async def pentest_stop(task_id: str):
    tinfo = _pentest_tasks.get(task_id)
    if not tinfo:
        return {"success": False, "message": "任务不存在"}
    task = tinfo.get("task_obj")
    if task and not task.done():
        task.cancel()
        tinfo["status"] = "stopped"
        return {"success": True, "message": "已请求停止"}
    return {"success": False, "message": "没有运行中的任务"}

@router.get("/agent/state")
async def pentest_get_state(task_id: str):
    state = _load_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state.data

@router.get("/agent/report")
async def pentest_get_report(task_id: str):
    state = _load_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    report_path = state.generate_report()
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"report": content, "phase": state.data["phase"], "task_id": task_id}

@router.get("/agent/history")
async def pentest_history():
    """返回所有渗透任务历史列表"""
    items = []
    seen: set[str] = set()

    for state_path in _list_pentest_state_files():
        task_id = _extract_task_id_from_state_file(state_path)
        if not task_id or task_id in seen:
            continue
        item = _build_history_item(task_id, _pentest_tasks.get(task_id))
        if item:
            items.append(item)
            seen.add(task_id)

    for task_id, tinfo in sorted(_pentest_tasks.items(), reverse=True):
        if task_id in seen:
            continue
        item = _build_history_item(task_id, tinfo)
        if item:
            items.append(item)
            seen.add(task_id)

    items.sort(key=lambda item: item.get("start_time", ""), reverse=True)
    return {"history": items, "total": len(items)}

@router.delete("/agent/history/{task_id}")
async def pentest_delete_history(task_id: str):
    tinfo = _pentest_tasks.pop(task_id, None)
    state_path = _state_file(task_id)
    deleted = False

    if tinfo and tinfo.get("state_file"):
        state_path = tinfo["state_file"]

    try:
        os.remove(state_path)
        deleted = True
    except FileNotFoundError:
        deleted = False

    if deleted or tinfo:
        return {"success": True, "message": "已删除"}
    return {"success": False, "message": "任务不存在"}

@router.get("/crypto/rsa-public-key")
async def get_rsa_key():
    return {"public_key": get_rsa_public_key()}
@router.get("/device/uuid")
async def get_device_uuid_endpoint():
    info = get_device_uuid()
    return info.model_dump()

# ==================== Skills 管理 ====================
_SKILLS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "skills")
_KNOWLEDGE_BASE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "knowledge_base")

def _ensure_kb_dir():
    os.makedirs(_KNOWLEDGE_BASE_ROOT, exist_ok=True)

@router.get("/skills")
async def list_skills():
    """列出所有 skills（不区分分类）"""
    result = []
    for root, _dirs, files in os.walk(_SKILLS_ROOT):
        for fname in sorted(files):
            if fname.endswith(".json"):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    result.append({
                        "filename": fname,
                        "name": data.get("name", fname),
                        "description": data.get("description", ""),
                    })
                except Exception:
                    result.append({
                        "filename": fname,
                        "name": fname,
                        "description": "",
                    })
    return {"items": result}

@router.delete("/skills/{filename}")
async def delete_skill(filename: str):
    """删除指定 skill（在所有子目录中查找）"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    for root, _dirs, files in os.walk(_SKILLS_ROOT):
        if filename in files:
            fpath = os.path.join(root, filename)
            os.remove(fpath)
            return {"success": True, "message": "已删除"}
    raise HTTPException(status_code=404, detail="文件不存在")

@router.post("/skills")
async def upload_skill(file: UploadFile = File(...)):
    """上传新 skill JSON 文件（默认存到 experimental）"""
    fname = file.filename or "unknown.json"
    if not fname.endswith(".json"):
        fname += ".json"
    if ".." in fname or "/" in fname or "\\" in fname:
        raise HTTPException(status_code=400, detail="无效的文件名")
    target_dir = os.path.join(_SKILLS_ROOT, "experimental")
    os.makedirs(target_dir, exist_ok=True)
    fpath = os.path.join(target_dir, fname)
    content = await file.read()
    try:
        json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 JSON: {e}")
    with open(fpath, "wb") as f:
        f.write(content)
    return {"success": True, "message": "上传成功", "filename": fname}

# ==================== 本地知识库管理 ====================
@router.get("/knowledge-base")
async def list_knowledge_base():
    """列出本地知识库条目"""
    _ensure_kb_dir()
    result = []
    for fname in sorted(os.listdir(_KNOWLEDGE_BASE_ROOT)):
        fpath = os.path.join(_KNOWLEDGE_BASE_ROOT, fname)
        if os.path.isfile(fpath) and fname.endswith(".json"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.append({
                    "name": data.get("name", fname),
                    "filename": fname,
                    "description": data.get("description", ""),
                    "content_preview": json.dumps(data)[:200],
                })
            except Exception:
                result.append({
                    "name": fname,
                    "filename": fname,
                    "description": "",
                    "content_preview": "",
                })
    return {"items": result}

@router.delete("/knowledge-base/{filename}")
async def delete_knowledge_base(filename: str):
    """删除知识库条目"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    _ensure_kb_dir()
    fpath = os.path.join(_KNOWLEDGE_BASE_ROOT, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="文件不存在")
    os.remove(fpath)
    return {"success": True, "message": "已删除"}

class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""

@router.post("/knowledge-base")
async def create_knowledge_base(req: KnowledgeBaseCreateRequest):
    """创建知识库条目"""
    _ensure_kb_dir()
    safe_name = "".join(c for c in req.name if c.isalnum() or c in "-_ ").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    filename = f"{safe_name}.json"
    fpath = os.path.join(_KNOWLEDGE_BASE_ROOT, filename)
    data = {
        "name": req.name,
        "description": req.description,
        "content": req.content,
        "created_at": str(datetime.now()),
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"success": True, "message": "创建成功", "filename": filename}
