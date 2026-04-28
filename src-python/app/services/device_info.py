"""
设备信息采集模块 —— 从 Rust device_info.rs 迁移至 Python 实现。

设备标识机制：
  本模块负责采集本地设备的唯一标识信息（UUID、设备类型、设备名称），
  根据不同操作系统采用平台特定的系统命令或配置文件进行提取。

  识别策略（跨平台）：
  - 通过 platform.system() 判断当前操作系统（Windows / Darwin / Linux）。
  - 使用 subprocess 调用系统级命令获取硬件/系统 UUID。
  - 对不支持的平台回退为 "unknown"。

  安全考量：
  - 所有 subprocess 调用均设置了 timeout（5~10 秒），防止子进程挂起导致调用方阻塞。
  - Windows 平台创建子进程时使用 CREATE_NO_WINDOW 标志，避免弹出控制台窗口。
  - 所有外部命令调用和文件读取均包裹在 try/except 中，任何异常都会走降级路径，
    确保不会因单个采集步骤失败而抛出未处理异常。
  - 未对外发送任何网络请求，仅在本地读取系统信息。
"""

import platform
import subprocess
from typing import Optional

from app.models.types import DeviceInfo


# ============================================================================
# 平台特定 UUID 获取函数
# 每个函数针对一种操作系统，内含多级回退链，最终保底返回 "unknown"。
# ============================================================================


def _get_windows_uuid() -> str:
    """
    获取 Windows 设备 UUID。

    实现方式：
      通过 PowerShell 调用 WMI 查询 Win32_ComputerSystemProduct 类的 UUID 属性。
      执行命令：
        powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"

    回退链：
      1. 尝试执行 PowerShell 命令获取 UUID。
      2. 命令执行成功且输出非空 → 返回 UUID。
      3. 任何异常（命令不存在、权限不足、超时等）→ 返回 "unknown"。

    安全措施：
      - timeout=10 秒，防止 PowerShell 挂起。
      - CREATE_NO_WINDOW 标志避免弹出终端窗口。
    """
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_macos_uuid() -> str:
    """
    获取 macOS 设备 UUID。

    实现方式：
      通过 ioreg 命令查询 IOPlatformExpertDevice 注册表节点，
      从输出中解析 IOPlatformUUID 字段的值。
      执行命令：
        ioreg -rd1 -c IOPlatformExpertDevice

    解析逻辑：
      对输出的每一行检查是否包含 "IOPlatformUUID" 字符串，
      若包含则按双引号分割字符串并取第 4 段（索引 3）作为 UUID 值。
      示例行格式：  "IOPlatformUUID" = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"

    回退链：
      1. 执行 ioreg 命令。
      2. 逐行解析输出，查找 IOPlatformUUID 字段。
      3. 任何异常（命令不存在、解析失败、超时等）→ 返回 "unknown"。

    安全措施：
      - timeout=10 秒，防止 ioreg 挂起。
    """
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return parts[3]
    except Exception:
        pass
    return "unknown"


def _get_linux_uuid() -> str:
    """
    获取 Linux 设备 UUID。

    实现方式（多级回退链，按优先级依次尝试）：
      1. 读取 /etc/machine-id —— systemd 系统生成的唯一机器 ID（优先使用）。
      2. 读取 /var/lib/dbus/machine-id —— D-Bus 守护进程缓存的机器 ID（次选）。
      3. 执行 dmidecode -s system-uuid —— 从 DMI/SMBIOS 表中读取硬件 UUID
         （需要 root 权限，普通用户可能无权限执行）。
      4. 以上全部失败 → 返回 "unknown"。

    安全措施：
      - dmidecode 子进程设置了 timeout=10 秒。
      - 文件读取和子进程调用均异常安全，不会中断上层调用。
        （无 root 权限时 dmidecode 通常会返回非零退出码并被捕获）
    """
    # 尝试从 /etc/machine-id 读取（systemd 机器 ID，最可靠的用户态标识）
    try:
        with open("/etc/machine-id") as f:
            return f.read().strip()
    except Exception:
        pass

    # 尝试从 /var/lib/dbus/machine-id 读取（D-Bus 机器 ID，非 systemd 系统备选）
    try:
        with open("/var/lib/dbus/machine-id") as f:
            return f.read().strip()
    except Exception:
        pass

    # 尝试使用 dmidecode 读取硬件 UUID（需要 root 权限）
    try:
        result = subprocess.run(
            ["dmidecode", "-s", "system-uuid"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return "unknown"


# ============================================================================
# 设备类型与名称获取函数
# ============================================================================


def _get_device_type() -> str:
    """
    获取设备操作系统类型字符串。

    通过 platform.system() 判断操作系统：
      Windows  → "windows"
      Darwin   → "macos"
      Linux    → "linux"
      其他     → "unknown"
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    return "unknown"


def _get_device_name() -> str:
    """
    获取设备主机名（人类可读的设备名称）。

    各平台实现方式：
      Windows：
        - 执行 hostname 命令获取主机名。
        - 使用 CREATE_NO_WINDOW 标志避免弹出终端窗口。
        - timeout=5 秒。
      macOS：
        - 执行 scutil --get ComputerName 获取系统偏好设置中的计算机名。
        - timeout=5 秒。
      Linux：
        - 优先读取 /etc/hostname 文件（静态主机名）。
        - 文件不存在时执行 hostname 命令作为备选。
        - timeout=5 秒。

    保底回退：
      - 所有平台方法失败后，使用 platform.node() 获取网络节点名。
      - platform.node() 也失败时返回 "Unknown Device"。
    """
    system = platform.system().lower()
    if system == "windows":
        try:
            result = subprocess.run(
                ["hostname"], capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
    elif system == "darwin":
        try:
            result = subprocess.run(
                ["scutil", "--get", "ComputerName"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
    elif system == "linux":
        try:
            with open("/etc/hostname") as f:
                return f.read().strip()
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["hostname"], capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return platform.node() or "Unknown Device"


# ============================================================================
# 主入口函数
# ============================================================================


def get_device_uuid() -> DeviceInfo:
    """
    获取当前设备的完整标识信息，返回 DeviceInfo 结构体。

    调用链路：
      此函数由 API 路由层调用，对应接口：
        GET /api/v1/device/uuid
      （客户端通过该接口获取设备 UUID 以进行设备注册/识别）

    调度逻辑（按操作系统分发）：
      1. 通过 platform.system().lower() 判断当前操作系统。
      2. Windows   → 调用 _get_windows_uuid()，使用 PowerShell + WMI 查询。
      3. Darwin    → 调用 _get_macos_uuid()，使用 ioreg 查询 I/O Kit 注册表。
      4. Linux     → 调用 _get_linux_uuid()，多级回退链获取机器 ID。
      5. 其他系统 → 直接赋值为 "unknown"（不支持的平台）。
      6. 同时通过 _get_device_type() 获取设备类型字符串。
      7. 同时通过 _get_device_name() 获取主机名。
      8. 将所有信息封装为 DeviceInfo 对象返回。

    安全考量：
      - 所有 subprocess 调用均在各自函数内设置了超时和异常捕获，
        本函数仅做分发，不会额外引入安全风险。
      - 返回的 UUID 为客户端本地标识，不涉及任何远程通信。
    """
    system = platform.system().lower()

    if system == "windows":
        device_uuid = _get_windows_uuid()
    elif system == "darwin":
        device_uuid = _get_macos_uuid()
    elif system == "linux":
        device_uuid = _get_linux_uuid()
    else:
        device_uuid = "unknown"

    return DeviceInfo(
        device_uuid=device_uuid,
        device_type=_get_device_type(),
        device_name=_get_device_name(),
    )
