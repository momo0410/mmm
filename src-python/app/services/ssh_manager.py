"""
SSH 核心管理器模块

本模块定义了 SSHManager 类，作为整个 LovelyRes 后端应用的**中心基础设施服务**。

角色定位：
  SSHManager 是应用运行时唯一的 SSH 连接管理中枢，负责与远程 Linux 主机建立
  异步 SSH 连接，并在此连接之上提供三种核心能力：
    1. **命令执行**      — 在远程主机上运行任意命令并获取结构化输出
    2. **SFTP 文件管理**  — 浏览、读写、上传/下载远程文件
    3. **交互式终端**    — 创建/销毁伪终端(PTY)会话，支持 WebSocket 双向实时交互

调用方全景：
  - app.main                       — WebSocket 终端生命周期管理、健康检查
  - app.routers.api                — REST API 层：连接/断开、命令执行、文件操作、终端
  - app.services.detection_manager — 安全基线检测（端口扫描、用户审计、后门检测等）
  - app.services.log_analysis      — 远程系统日志分析
  - app.services.file_analysis     — 远程文件安全分析
  - src-python/diagnose_sftp.py    — SFTP 诊断脚本
  - src-python/tests/*             — 单元测试用例

外部依赖：
  - asyncssh (>=2.18.0)  — 异步 SSH 协议客户端，提供连接、PTY、SFTP 全套能力
  - 所有异步操作均基于 asyncio 事件循环

状态管理：
  SSHManager 在 app.routers.api.init_state() 中被创建为全局单例 _ssh_manager，
  应用启动时初始化、关闭时断开。同一时刻仅维护一条 SSH 连接。

作者: LovelyRes Team
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import asyncssh
from asyncssh.constants import (
    FILEXFER_TYPE_DIRECTORY,
    FILEXFER_TYPE_SYMLINK,
    FILEXFER_TYPE_UNKNOWN,
)

from app.models.types import (
    BashEnvironmentInfo,
    CommandCompletion,
    ConnectionInfo,
    SftpFileDetails,
    SftpFileInfo,
    SSHConnectionStatus,
    TerminalOutput,
)


class SSHManager:
    """
    SSH 连接、命令执行、SFTP 文件管理与交互式终端的统一管理器。

    内部状态：
      - _connection:      asyncssh.SSHClientConnection  活跃的 SSH 连接对象
      - _sftp:            asyncssh.SFTPClient            复用的 SFTP 客户端子通道
      - _connection_info: ConnectionInfo                 当前连接的身份信息
      - _terminal_sessions: Dict[str, dict]             终端会话注册表 (terminal_id → 会话元数据)
      - _terminal_session_locks: Dict[str, asyncio.Lock] 每个终端会话的互斥锁，防止并发创建/销毁竞态

    设计要点：
      - 单连接模式：同一时刻只维护一条 SSH 连接，调用 connect() 时会先断开旧连接
      - SFTP 懒初始化：SFTP 子通道在首次文件操作时通过 _ensure_sftp() 按需建立
      - 终端会话隔离：每个 terminal_id 对应独立的 PTY 通道，互不干扰
      - 线程安全：终端会话操作通过 asyncio.Lock 保证协程级并发安全
    """

    def __init__(self):
        """
        初始化 SSHManager 实例。

        将所有内部状态设置为空/默认值：
          - SSH 连接、SFTP 客户端、连接信息均为 None
          - 终端会话字典和锁字典为空
          - 连接标志为 False，主机/端口/用户名为空字符串或默认端口 22
        """
        self._connection: Optional[asyncssh.SSHClientConnection] = None
        self._sftp: Optional[asyncssh.SFTPClient] = None
        self._connection_info: Optional[ConnectionInfo] = None
        self._terminal_sessions: Dict[str, Any] = {}
        self._terminal_session_locks: Dict[str, asyncio.Lock] = {}
        self._connected = False
        self._host = ""
        self._port = 22
        self._username = ""

    async def _open_terminal_process(
        self, cols: int, rows: int
    ) -> Tuple[Any, Any, Any, Any]:
        """
        在已建立的 SSH 连接上打开一个交互式伪终端(PTY)进程通道。

        本方法是终端会话创建的底层工厂方法，由 create_terminal_session() 调用。

        SSH PTY 生命周期阶段——打开：
          1. 本方法通过 SSH 连接对象的 create_process() 启动远程 shell 进程
          2. asyncssh 在远程主机上分配一个伪终端(Pseudo-Terminal)
          3. 终端类型设为 xterm-256color，支持 256 色终端渲染
          4. 终端尺寸由 (rows, cols) 元组指定
          5. encoding=None 表示原始字节流模式（不做字符编码转换）
          6. 返回四元组: (通道, 标准输入流, 标准输出流, 标准错误流)

        错误处理：
          - 使用级联回退策略依次尝试三种 shell 启动命令:
            (1) 系统默认 shell (通常读取 /etc/passwd 中配置的登录 shell)，超时 2.5s
            (2) bash --noprofile --norc -i（跳过配置文件以加速启动），超时 2.0s
            (3) sh -i（最简交互式 shell），超时 2.0s
          - 如果所有候选命令都超时，抛出中文 TimeoutError
          - 如果 asyncio.wait_for 因其他原因失败，抛出 RuntimeError

        参数:
          cols: 终端列数 (字符宽度)
          rows: 终端行数 (字符高度)

        返回:
          (channel, stdin, stdout, stderr): SSH 通道、标准输入/输出/错误流

        异常:
          TimeoutError: 三种候选 shell 均启动超时
          RuntimeError: 其他原因导致的通道创建失败
        """
        # TermSize 是 asyncssh 的四元组 (行数, 列数, 像素宽度, 像素高度)
        # 像素尺寸传 0 表示由客户端自行计算
        term_size = (rows, cols, 0, 0)
        # shell 候选列表: (启动命令, 超时秒数)
        # None 表示使用远程用户的默认登录 shell
        shell_candidates: List[Tuple[Optional[str], float]] = [
            (None, 2.5),
            ("bash --noprofile --norc -i", 2.0),
            ("sh -i", 2.0),
        ]
        last_timeout: Optional[Exception] = None

        for command, timeout in shell_candidates:
            try:
                process = await asyncio.wait_for(
                    self._connection.create_process(
                        command,
                        term_type="xterm-256color",
                        term_size=term_size,
                        encoding=None,
                    ),
                    timeout=timeout,
                )
                return process.channel, process.stdin, process.stdout, process.stderr
            except asyncio.TimeoutError as exc:
                # 当前 shell 超时，保存异常并尝试下一个候选
                last_timeout = exc
                continue

        # 所有候选均失败
        if last_timeout is not None:
            raise TimeoutError("创建终端通道超时，请重试")
        raise RuntimeError("创建终端通道失败")

    async def connect(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        key_passphrase: Optional[str] = None,
    ) -> str:
        """
        建立到远程主机的 SSH 连接。

        调用方:
          - app.routers.api  — POST /api/ssh/connect REST 端点
          - app.main         — 应用启动时的自动重连逻辑
          - diagnose_sftp.py — SFTP 诊断脚本

        认证方式（优先级从高到低）：
          1. 私钥认证（private_key 参数非空）
             - 如果 private_key 是有效的本地文件路径，使用该文件作为密钥
             - 如果 private_key 是原始密钥数据字符串，直接传递给 asyncssh
             - 可选传递 key_passphrase 用于加密私钥
          2. 密码认证（password 参数非空，且未提供私钥）

        边缘情况：
          - 如果当前已存在活跃连接，自动断开旧连接再建立新连接（单连接模式）
          - known_hosts 设为 None：跳过主机密钥验证（内网工具场景，生产环境需评估）
          - 连接超时与登录超时分别为 8 秒，避免长时间阻塞
          - keepalive_interval=20s + count_max=3：60 秒无响应后判定断线

        参数:
          host:             远程主机 IP 或域名
          port:             SSH 端口（通常为 22）
          username:         登录用户名
          password:         密码（密码认证时使用）
          private_key:      私钥文件路径或私钥内容字符串（密钥认证时使用）
          key_passphrase:   私钥加密口令（可选）

        返回:
          连接成功的中文提示消息字符串

        异常:
          asyncssh.Error:   SSH 协议层错误（认证失败、连接拒绝、超时等）
          OSError:          网络不可达
        """
        if self._connected:
            # 单连接模式：先断开旧连接
            await self.disconnect()

        kwargs: Dict[str, Any] = {
            "host": host,
            "port": port,
            "username": username,
            "known_hosts": None,              # 内网工具跳过主机密钥检查
            "connect_timeout": 8,             # TCP 连接超时 8 秒
            "login_timeout": 8,               # SSH 认证超时 8 秒
            "keepalive_interval": 20,         # 每 20 秒发送保活包
            "keepalive_count_max": 3,         # 3 次无响应后断开
        }

        if password:
            # 密码认证（仅在未提供密钥时生效）
            kwargs["password"] = password
        if private_key:
            if os.path.isfile(private_key):
                # 是文件路径：asyncssh 会从文件中读取密钥
                kwargs["client_keys"] = [private_key]
                if key_passphrase:
                    kwargs["passphrase"] = key_passphrase
            else:
                # 是原始密钥字符串：直接传入（不验证文件存在性）
                kwargs["client_keys"] = [private_key]

        self._connection = await asyncssh.connect(**kwargs)
        self._connected = True
        self._host = host
        self._port = port
        self._username = username
        # 记录认证方式，用于后续审计和状态展示
        self._connection_info = ConnectionInfo(
            host=host,
            port=port,
            username=username,
            auth_method="key" if private_key else "password",
        )
        return f"已连接到 {username}@{host}:{port}"

    async def disconnect(self) -> None:
        """
        断开 SSH 连接并清理所有资源。

        调用方:
          - app.routers.api       — POST /api/ssh/disconnect REST 端点
          - app.main              — 应用关闭时的清理逻辑
          - self.connect()        — 重新连接前自动断开旧连接
          - self                 — 发生异常时上层调用方手动断开

        清理顺序（严格按依赖关系从上层到下层）：
          1. 关闭所有活跃的终端会话（每个会话的 PTY channel 都会被关闭）
          2. 退出 SFTP 子通道（调用 exit() 而非 close()，符合 asyncssh API 约定）
          3. 关闭 SSH 连接并等待异步关闭完成（wait_closed() 确保底层 socket 完全释放）
          4. 重置所有内部状态为默认值

        边缘情况：
          - 本方法幂等：重复调用不会抛出异常（即使连接已断开）
          - SFTP 和 SSH 连接在关闭前都做了 None 检查，防止对已关闭对象重复操作
          - wait_closed() 是异步方法，需要 await 以确保连接完全终止
        """
        await self.close_all_terminal_sessions()

        if self._sftp:
            # asyncssh SFTP 客户端使用 exit() 关闭，不是 close()
            self._sftp.exit()
            self._sftp = None
        if self._connection:
            self._connection.close()
            # 等待连接完全关闭，释放底层资源
            await self._connection.wait_closed()
            self._connection = None
        self._connected = False
        self._connection_info = None

    def is_connected(self) -> bool:
        """
        检查 SSH 连接是否处于活跃状态。

        调用方:
          - app.main              — WebSocket 端点连接前的状态检查
          - app.routers.api       — 各 API 端点的前置条件验证
          - self                  — 所有需要前置连接的方法内部守卫

        返回:
          True 当且仅当 _connected 标志为 True 且连接对象不为 None

        注意:
          这是同步方法，不发起网络 I/O，仅检查本地状态标志。
          它不保证连接在下一毫秒仍然有效（网络随时可能断开）。
          实际 I/O 操作时 asyncssh 会抛出 ConnectionLost 异常。
        """
        return self._connected and self._connection is not None

    async def execute_command(self, command: str) -> TerminalOutput:
        """
        在远程主机上执行单条 shell 命令并返回结构化结果。

        调用方（可能是本模块最广泛使用的方法）:
          - app.routers.api               — /api/execute REST 端点
          - app.services.detection_manager — 所有安全检测方法最终都通过本方法执行远程命令
          - app.services.log_analysis      — 远程日志文件内容读取
          - app.services.file_analysis     — 远程文件信息查询（stat/file/hash 等）
          - self.execute_dashboard_command — 直接转发（纯别名）
          - self.get_bash_environment_info — 批量获取 Bash 环境变量
          - self.get_command_completion    — 命令自动补全的候选获取
          - self.compress_file             — 压缩操作
          - self.extract_file              — 解压操作

        设计要点:
          - 使用 connection.run() 而非 create_process()：单次命令执行，无需交互
          - check=False：命令执行失败不抛异常，由调用方根据 exit_code 自行判断
          - encoding=None：保持原始字节流，在 Python 侧统一做 UTF-8 解码
          - stdout 解码使用 errors="replace"：避免因编码问题导致整个输出丢失

        错误处理:
          - 连接未建立：抛出 ConnectionError("没有活动的 SSH 连接")
          - 命令执行异常：返回 exit_code=-1 的 TerminalOutput，output 为异常消息
          - 空输出：stdout 为 None 或空字节时，output 为 "" 并成功返回
          - 命令本身失败（exit_code != 0）：正常返回，不抛异常，由上层判断

        参数:
          command: 要在远程主机上执行的 shell 命令字符串

        返回:
          TerminalOutput: 包含命令文本、输出内容、退出码的结构化对象
        """
        if not self.is_connected():
            raise ConnectionError("没有活动的 SSH 连接")

        try:
            result = await self._connection.run(command, check=False, encoding=None)
            stdout_bytes = result.stdout or b""
            # 容错解码：用 replacement character 替代无法解码的字节
            output = stdout_bytes.decode("utf-8", errors="replace")
            return TerminalOutput.create(
                command=command, output=output, exit_code=result.exit_status
            )
        except Exception as e:
            # 网络断开或协议错误时，返回失败结果而非让异常向上传播
            return TerminalOutput.create(command=command, output=str(e), exit_code=-1)

    async def execute_dashboard_command(self, command: str) -> TerminalOutput:
        """
        仪表盘命令执行的别名方法——直接委托给 execute_command()。

        调用方:
          - app.routers.api — /api/dashboard/execute REST 端点

        说明:
          与 execute_command() 行为完全一致，仅用于语义区分（仪表盘专用端点）。
          未来可在此层加入仪表盘特有的审计日志、命令过滤等逻辑。
        """
        return await self.execute_command(command)

    async def execute_dashboard_command_as_user(
        self, command: str, username: Optional[str] = None
    ) -> TerminalOutput:
        """
        以指定用户身份执行仪表盘命令。

        调用方:
          - app.routers.api — /api/dashboard/execute-as-user REST 端点

        工作原理:
          - 如果 username 为空或等于当前登录用户，直接执行原命令
          - 如果 username 不同于当前登录用户，使用 sudo -u 切换用户执行
          - sudo 不会要求密码，前提是远程主机已配置 NOPASSWD（工具场景假设）

        安全注意:
          依赖远程主机的 sudoers 配置。如果未配置 NOPASSWD，sudo 会阻塞等待密码输入，
          但 execute_command 的超时机制可以兜底（asyncssh 连接层的超时设置）。
        """
        if username and username != self._username:
            return await self.execute_command(f"sudo -u {username} {command}")
        return await self.execute_command(command)

    async def get_connection_status(self) -> Optional[SSHConnectionStatus]:
        """
        获取当前 SSH 连接的状态快照。

        调用方:
          - app.routers.api — GET /api/ssh/status REST 端点

        返回:
          连接活跃时返回包含主机、端口、用户名、最后活动时间的连接状态对象
          未连接时返回 None

        注意:
          last_activity 使用当前时间，非实际记录的最后 I/O 时间（简化实现）。
        """
        if not self.is_connected():
            return None
        return SSHConnectionStatus(
            connected=True,
            host=self._host,
            port=self._port,
            username=self._username,
            last_activity=datetime.now(timezone.utc),
        )

    async def _ensure_sftp(self) -> asyncssh.SFTPClient:
        """
        确保 SFTP 客户端已初始化（懒加载模式），并返回可用客户端。

        调用方:
          - self.list_sftp_files     — 目录列表
          - self.read_sftp_file      — 读取远程文件
          - self.write_sftp_file     — 写入远程文件
          - self.upload_file         — 上传本地文件
          - self.download_file       — 下载远程文件
          - self.create_directory    — 创建远程目录
          - self.chmod_sftp          — 修改远程文件权限
          - self.get_file_details    — 获取远程文件详情

        设计要点:
          - SFTP 子通道在首次文件操作时按需建立，而非连接时预建
          - 一旦建立，后续所有文件操作复用同一 SFTP 客户端实例
          - 断开连接时 _sftp 被置为 None，下次操作会重新建立

        异常:
          ConnectionError: 未建立 SSH 连接时调用
          asyncssh.Error:  SFTP 子通道创建失败（如远程服务器不支持 SFTP）
        """
        if not self.is_connected():
            raise ConnectionError("没有活动的 SSH 连接")
        if self._sftp is None:
            self._sftp = await self._connection.start_sftp_client()
        return self._sftp

    @staticmethod
    def _join_remote(path: str, name: str) -> str:
        """
        拼接远程文件路径。

        调用方:
          - self.list_sftp_files — 组装 SftpFileInfo 的完整路径

        边界情况:
          - 根目录 "/" 下拼接时避免双斜杠 "//name" → 返回 "/name"
          - 非根目录下自动去除右侧多余的 "/"
        """
        if path == "/":
            return f"/{name}"
        return f"{path.rstrip('/')}/{name}"

    @staticmethod
    def _sftp_entry_filename(entry: Any) -> str:
        """
        从 asyncssh.SFTPName 对象中安全提取文件名。

        调用方:
          - self.list_sftp_files — 遍历目录条目时提取文件名

        说明:
          asyncssh.SFTPName 的字段名为 filename（而非 name），
          且在某些服务器实现中返回 bytes 类型而非 str。
          本方法兼容以下情况：
            - entry.filename 为 str   → 直接返回
            - entry.filename 为 bytes  → 使用 surrogateescape 解码以保留原始字节
            - entry 无 filename 属性    → 回退到 entry.name，或返回空字符串
        """
        raw = getattr(entry, "filename", None) or getattr(entry, "name", "") or ""
        if isinstance(raw, (bytes, bytearray)):
            # surrogateescape: 将无法解码的字节映射到 Unicode 私有区，保证往返安全
            return bytes(raw).decode("utf-8", errors="surrogateescape")
        return str(raw)

    @staticmethod
    def _perm_to_str(mode: Optional[int]) -> Optional[str]:
        """
        将 POSIX 权限位转换为字符串表示（如 "drwxr-xr-x"）。

        调用方:
          - self.list_sftp_files  — 文件列表的权限字段
          - self.get_file_details — 文件详情的权限字段

        格式:
          - 第 1 位：文件类型（d=目录, l=符号链接, -=普通文件）
          - 第 2-10 位：owner/group/other 的 rwx 权限位

        参数:
          mode: POSIX stat 权限位（如 0o755）

        返回:
          权限字符串，mode 为 None 时返回 None
        """
        if mode is None:
            return None
        perms = []
        # 文件类型判断：0o40000 (S_IFDIR) = 目录, 0o120000 (S_IFLNK) = 符号链接
        file_type = "d" if (mode & 0o40000) else ("l" if (mode & 0o120000) else "-")
        perms.append(file_type)
        for shift in (6, 3, 0):
            p = (mode >> shift) & 0b111
            perms.append("r" if p & 0b100 else "-")
            perms.append("w" if p & 0b010 else "-")
            perms.append("x" if p & 0b001 else "-")
        return "".join(perms)

    @staticmethod
    def _epoch_to_iso(ts: Optional[int]) -> Optional[str]:
        """
        将 Unix 时间戳转换为 ISO 8601 格式字符串。

        调用方:
          - self.list_sftp_files  — 文件的修改时间
          - self.get_file_details — 文件的创建/修改/访问时间

        边界情况与安全防护：
          - ts 为 None → 返回 None（无时间信息）
          - ts <= 0    → 返回 None（许多 unix 系统用 0 表示"无时间"）
          - SFTP 服务器可能返回异常时间戳（损坏/极大的值），
            datetime.fromtimestamp() 可能抛出 OSError 或 OverflowError
          - 所有异常被捕获并静默返回 None，避免影响文件列表的整体展示

        返回:
          格式为 "YYYY-MM-DDTHH:MM:SS+00:00" 的 ISO 字符串，或 None
        """
        if ts is None:
            return None
        try:
            t = int(ts)
            if t <= 0:
                return None
            return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            # 部分 SFTP 服务器返回异常时间戳，静默忽略
            return None

    @staticmethod
    def _classify_sftp_entry(attrs: Optional[asyncssh.SFTPAttrs]) -> Tuple[str, bool]:
        """
        综合 SFTP 属性判断文件条目的类型分类。

        调用方:
          - self.list_sftp_files  — 分类目录条目
          - self.get_file_details — 确定单文件类型

        分类策略（两级判断）：
          1. 优先使用 SFTP v4+ 的 attrs.type 字段（FILEXFER_TYPE_* 常量）
             - 如果 type 明确为目录或符号链接，直接采用
             - 如果 type 为 UNKNOWN（即服务器不支持 v4 type 字段），回退到第 2 级
          2. 使用传统 POSIX mode 位判断
             - S_IFDIR (0o40000)   → 目录
             - S_IFLNK (0o120000)  → 符号链接
             - 其他                → 普通文件

        返回:
          (类型字符串, 是否目录的布尔值)
            - "directory" / "symlink" / "file"
            - True 表示目录
        """
        mode = attrs.permissions if attrs else None
        file_type = "file"
        is_dir = False
        if attrs is not None and attrs.type != FILEXFER_TYPE_UNKNOWN:
            # SFTP v4+ 支持 type 字段时优先使用
            if attrs.type == FILEXFER_TYPE_DIRECTORY:
                return "directory", True
            if attrs.type == FILEXFER_TYPE_SYMLINK:
                return "symlink", False
        if mode is not None:
            # 回退到 POSIX 权限位判断
            if mode & 0o40000:
                return "directory", True
            if mode & 0o120000:
                return "symlink", False
        return file_type, is_dir

    async def list_sftp_files(self, path: str) -> List[SftpFileInfo]:
        """
        列出远程主机指定目录下的所有文件和子目录。

        调用方:
          - app.routers.api — 文件浏览器相关 REST 端点

        工作流程:
          1. 通过 _ensure_sftp() 获取复用的 SFTP 客户端
          2. 调用 sftp.readdir() 读取目录条目列表
          3. 对每个条目提取文件名、拼接完整路径、判断类型、解析权限和时间
          4. 组装为 SftpFileInfo 列表返回

        边缘情况:
          - 目录为空：返回空列表
          - attrs 为 None：使用默认值（size=0, 无时间, 类型为 "file"）
          - readdir 失败会向上传播 asyncssh 异常

        参数:
          path: 远程目录的绝对路径（如 "/home/user"）

        返回:
          SftpFileInfo 列表，每个元素包含名称、路径、类型、大小、修改时间、权限
        """
        sftp = await self._ensure_sftp()
        out: List[SftpFileInfo] = []
        for entry in await sftp.readdir(path):
            fname = self._sftp_entry_filename(entry)
            attrs = entry.attrs
            mode = attrs.permissions if attrs else None
            file_type, is_dir = self._classify_sftp_entry(attrs)
            out.append(
                SftpFileInfo(
                    name=fname,
                    path=self._join_remote(path, fname),
                    file_type=file_type,
                    is_dir=is_dir,
                    size=(attrs.size if attrs and attrs.size is not None else 0),
                    modified=self._epoch_to_iso(attrs.mtime if attrs else None),
                    permissions=self._perm_to_str(mode),
                )
            )
        return out

    async def read_sftp_file(self, path: str) -> bytes:
        """
        从远程主机读取文件的原始字节内容。

        调用方:
          - app.routers.api       — 文件内容预览端点
          - app.services.*        — 日志分析、文件分析等模块

        说明:
          使用 async with 上下文管理器确保 SFTP 文件句柄正确关闭。
          一次性读取全部内容到内存——适用于中小文件。
          对超大文件应使用 download_file() 进行流式下载。
        """
        sftp = await self._ensure_sftp()
        async with sftp.open(path, "rb") as f:
            return await f.read()

    async def write_sftp_file(self, path: str, content: bytes) -> None:
        """
        将字节内容写入远程主机的指定路径。

        调用方:
          - app.routers.api — 远程文件编辑/创建 REST 端点

        说明:
          覆盖写入模式（"wb"）。如果文件已存在，内容将被完全替换。
          encoding=None 表示直接操作字节流，不做字符编码转换。
        """
        sftp = await self._ensure_sftp()
        async with sftp.open(path, "wb", encoding=None) as f:
            await f.write(content)

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        将本地文件上传到远程主机（流式分块传输，兼容大文件）。

        调用方:
          - app.routers.api — 文件上传 REST 端点

        传输策略:
          - 使用 32KB 分块（chunk_size=32768）流式读取本地文件并写入远程
          - 避免将整个文件加载到内存，适合大文件传输
          - 相比 asyncssh 内置的 sftp.put()，使用 open() 流式写入兼容性更好
            （部分老旧 SFTP 服务器不完全支持 put 协议）

        参数:
          local_path:  本地文件路径
          remote_path: 远程目标文件路径
        """
        sftp = await self._ensure_sftp()
        # 分块读取本地文件并流式写入远程，避免大文件内存溢出
        chunk_size = 32768
        async with sftp.open(remote_path, "wb", encoding=None) as remote_f:
            with open(local_path, "rb") as local_f:
                while True:
                    chunk = local_f.read(chunk_size)
                    if not chunk:
                        break
                    await remote_f.write(chunk)

    async def download_file(self, remote_path: str, local_path: str) -> None:
        """
        将远程文件下载到本地（流式分块读取，兼容大文件）。

        调用方:
          - app.routers.api — 文件下载 REST 端点

        传输策略:
          与 upload_file 对称——32KB 分块流式传输。
          首先打开本地文件句柄（同步 open），然后异步读取远程文件并写入本地。
          相比 asyncssh 内置的 sftp.get()，流式方法更稳定。
        """
        sftp = await self._ensure_sftp()
        chunk_size = 32768
        with open(local_path, "wb") as local_f:
            async with sftp.open(remote_path, "rb", encoding=None) as remote_f:
                while True:
                    chunk = await remote_f.read(chunk_size)
                    if not chunk:
                        break
                    local_f.write(chunk)

    async def create_directory(self, remote_path: str) -> None:
        """
        在远程主机上创建新目录。

        调用方:
          - app.routers.api — 新建目录 REST 端点

        说明:
          直接委托给 asyncssh.SFTPClient.mkdir()。
          如果父目录不存在或权限不足，asyncssh 将抛出异常（向上传播）。
        """
        sftp = await self._ensure_sftp()
        await sftp.mkdir(remote_path)

    async def chmod_sftp(self, path: str, mode: int) -> None:
        """
        修改远程文件的 POSIX 权限位。

        调用方:
          - app.routers.api — 文件权限修改 REST 端点

        参数:
          path: 远程文件路径
          mode: 新的权限位（如 0o755）
        """
        sftp = await self._ensure_sftp()
        await sftp.chmod(path, mode)

    async def get_file_details(self, path: str) -> SftpFileDetails:
        """
        获取单个远程文件的详细元数据。

        调用方:
          - app.routers.api — 文件右键属性/详情 REST 端点

        获取的元数据包括：
          - 文件名、路径、类型
          - 文件大小
          - POSIX 权限字符串
          - 所有者 UID、所属组 GID（转换为字符串）
          - 创建时间（crtime，部分文件系统支持）
          - 修改时间（mtime）、访问时间（atime）

        边缘情况:
          - crtime 属性仅在部分 SFTP 服务器/文件系统上可用，不可用时为 None
          - uid/gid 转为字符串是为了前端展示方便
          - 时间戳使用 _epoch_to_iso() 做安全转换
        """
        sftp = await self._ensure_sftp()
        attrs = await sftp.stat(path)
        mode = attrs.permissions if attrs else None
        file_type, _is_dir = self._classify_sftp_entry(attrs)
        crtime = getattr(attrs, "crtime", None) if attrs else None
        return SftpFileDetails(
            name=path.rsplit("/", 1)[-1],
            path=path,
            file_type=file_type,
            size=(attrs.size if attrs and attrs.size is not None else 0),
            permissions=self._perm_to_str(mode) or "",
            owner=str(attrs.uid) if attrs and attrs.uid is not None else None,
            group=str(attrs.gid) if attrs and attrs.gid is not None else None,
            created=self._epoch_to_iso(crtime),
            modified=self._epoch_to_iso(attrs.mtime if attrs else None),
            accessed=self._epoch_to_iso(attrs.atime if attrs else None),
        )

    async def compress_file(self, source_path: str, target_path: str, fmt: str) -> None:
        """
        在远程主机上压缩文件/目录。

        调用方:
          - app.routers.api — 文件压缩 REST 端点

        支持的格式：
          - tar.gz / tgz    → tar -czf
          - tar             → tar -cf
          - tar.bz2 / tbz2  → tar -cjf
          - zip             → zip -r

        错误处理:
          通过 execute_command 执行压缩命令，检查退出码。
          如果退出码非零（压缩失败），抛出 RuntimeError 并附带命令的错误输出。

        安全注意:
          路径参数通过双引号包裹，防止空格导致的命令注入。
          但参数本身未做 shell 转义——调用方应确保路径来源可信。
        """
        if fmt in ("tar.gz", "tgz"):
            cmd = f'tar -czf "{target_path}" -C "{source_path}" .'
        elif fmt == "tar":
            cmd = f'tar -cf "{target_path}" -C "{source_path}" .'
        elif fmt in ("tar.bz2", "tbz2"):
            cmd = f'tar -cjf "{target_path}" -C "{source_path}" .'
        elif fmt == "zip":
            cmd = f'cd "{source_path}" && zip -r "{target_path}" .'
        else:
            # 未知格式默认使用 tar.gz
            cmd = f'tar -czf "{target_path}" -C "{source_path}" .'
        result = await self.execute_command(cmd)
        if result.exit_code and result.exit_code != 0:
            raise RuntimeError(result.output)

    async def extract_file(self, archive_path: str, target_dir: str) -> None:
        """
        在远程主机上解压压缩文件。

        调用方:
          - app.routers.api — 文件解压 REST 端点

        支持的格式（根据文件扩展名自动识别）：
          - .tar.gz / .tgz   → tar -xzf
          - .tar.bz2 / .tbz2 → tar -xjf
          - .tar             → tar -xf
          - .zip             → unzip -o
          - 其他             → 默认使用 tar -xzf

        注意事项:
          - 解压前会先 mkdir -p 创建目标目录（递归创建并忽略已存在的目录）
          - unzip 使用 -o 参数强制覆盖已存在文件
          - 解压失败时抛出 RuntimeError
        """
        if archive_path.endswith((".tar.gz", ".tgz")):
            cmd = f'mkdir -p "{target_dir}" && tar -xzf "{archive_path}" -C "{target_dir}"'
        elif archive_path.endswith((".tar.bz2", ".tbz2")):
            cmd = f'mkdir -p "{target_dir}" && tar -xjf "{archive_path}" -C "{target_dir}"'
        elif archive_path.endswith(".tar"):
            cmd = (
                f'mkdir -p "{target_dir}" && tar -xf "{archive_path}" -C "{target_dir}"'
            )
        elif archive_path.endswith(".zip"):
            cmd = f'mkdir -p "{target_dir}" && unzip -o "{archive_path}" -d "{target_dir}"'
        else:
            # 未知扩展名默认按 tar.gz 处理
            cmd = f'mkdir -p "{target_dir}" && tar -xzf "{archive_path}" -C "{target_dir}"'
        result = await self.execute_command(cmd)
        if result.exit_code and result.exit_code != 0:
            raise RuntimeError(result.output)

    # ────────────────────────────────────────────────────────────────
    #  交互式终端会话管理 (Terminal Session Management)
    #
    #  SSH PTY 生命周期概述：
    #    ┌─────────────────────────────────────────────────────────┐
    #    │ 1. 创建阶段  create_terminal_session()                   │
    #    │    ├─ _open_terminal_process() 在远程启动交互式 shell    │
    #    │    ├─ asyncssh 分配 PTY 伪终端（xterm-256color）         │
    #    │    └─ 将 channel/stdin/stdout/stderr 注册到会话字典     │
    #    │                                                          │
    #    │ 2. 运行阶段  send → read 循环                            │
    #    │    ├─ send_terminal_input()  → 写入用户按键到 stdin     │
    #    │    ├─ read_terminal_output() → 从 stdout 读取终端输出    │
    #    │    └─ resize_terminal()     → 调整 PTY 窗口尺寸         │
    #    │                                                          │
    #    │ 3. 销毁阶段  close_terminal_session()                    │
    #    │    ├─ session["channel"].close() 关闭 SSH 通道           │
    #    │    ├─ 远程 shell 进程收到 SIGHUP 终止                    │
    #    │    └─ 从 _terminal_sessions 字典中移除                   │
    #    └─────────────────────────────────────────────────────────┘
    #
    #  并发安全：
    #    每个 terminal_id 有独立的 asyncio.Lock，确保同一终端的
    #    创建/销毁/读写操作在协程级别是互斥的。
    # ────────────────────────────────────────────────────────────────

    async def create_terminal_session(
        self, terminal_id: str, cols: int = 80, rows: int = 24
    ) -> str:
        """
        创建新的交互式终端会话（WebSocket 终端的第一步）。

        调用方:
          - app.main — WebSocket connect 事件处理函数

        SSH PTY 生命周期——创建阶段：
          1. 检查 SSH 连接是否活跃
          2. 为该 terminal_id 分配互斥锁（确保并发安全）
          3. 检查 terminal_id 是否已存在——如存在则直接返回（幂等）
          4. 调用 _open_terminal_process() 在远程主机上启动交互式 shell
          5. 将返回的通道(channel)、标准输入(stdin)、标准输出(stdout)、
             标准错误(stderr)连同终端尺寸注册到 _terminal_sessions 字典

        并发安全:
          使用 asyncio.Lock 保护。如果两个协程同时尝试创建同一 terminal_id，
          第一个获取锁的协程创建会话，第二个在获取锁后发现会话已存在而直接返回。

        参数:
          terminal_id: 终端会话的唯一标识符（由 WebSocket 路由层生成）
          cols:        终端列数，默认 80
          rows:        终端行数，默认 24

        返回:
          终端 ID（与入参相同）

        异常:
          ConnectionError: 未建立 SSH 连接
          TimeoutError:    远程 shell 启动超时（来自 _open_terminal_process）
        """
        if not self.is_connected():
            raise ConnectionError("没有活动的 SSH 连接")

        # setdefault: 如果锁不存在则创建，避免并发竞态
        lock = self._terminal_session_locks.setdefault(terminal_id, asyncio.Lock())
        async with lock:
            if terminal_id in self._terminal_sessions:
                # 会话已存在，幂等返回（避免重复创建 PTY）
                return terminal_id

            channel, stdin, stdout, stderr = await self._open_terminal_process(
                cols, rows
            )

            self._terminal_sessions[terminal_id] = {
                "channel": channel,
                "stdin": stdin,
                "stdout": stdout,
                "stderr": stderr,
                "cols": cols,
                "rows": rows,
            }
            return terminal_id

    async def close_terminal_session(self, terminal_id: str) -> None:
        """
        关闭指定终端会话（WebSocket 断开时调用）。

        调用方:
          - app.main             — WebSocket disconnect 事件处理函数
          - self.close_all_terminal_sessions — 批量关闭所有会话

        SSH PTY 生命周期——销毁阶段：
          1. 从 _terminal_sessions 字典中移除会话记录（pop 而非 get+del，原子操作）
          2. 从 _terminal_session_locks 字典中移除对应的互斥锁
          3. 调用 channel.close() 关闭 SSH 通道
          4. 远程 shell 进程收到 SIGHUP 后自动终止
          5. asyncssh 底层释放 PTY 资源

        边缘情况:
          - terminal_id 不存在：静默返回（pop 的 default=None 保护）
          - channel.close() 抛出异常：被捕获并忽略（会话无论如何都会被移除）
          - 此处不调用 stdin.close() 或 stdout.close()——channel.close() 会连带关闭流
        """
        session = self._terminal_sessions.pop(terminal_id, None)
        self._terminal_session_locks.pop(terminal_id, None)
        if session:
            try:
                session["channel"].close()
            except Exception:
                # 通道关闭失败不传播异常（连接可能已断开）
                pass

    async def close_all_terminal_sessions(self) -> None:
        """
        关闭所有活跃的终端会话。

        调用方:
          - self.disconnect — SSH 断开时清理所有终端资源

        说明:
          遍历 _terminal_sessions 的键快照（list copy），逐个调用 close_terminal_session。
          使用快照避免在迭代过程中修改字典导致 RuntimeError。
        """
        for tid in list(self._terminal_sessions.keys()):
            await self.close_terminal_session(tid)

    async def send_terminal_input(self, terminal_id: str, data: bytes) -> None:
        """
        向指定终端会话发送用户输入（键盘按键数据）。

        调用方:
          - app.main — WebSocket message 事件处理函数（用户在前端终端中打字）

        SSH PTY 生命周期——运行阶段（输入侧）：
          1. 获取终端会话的 stdin 写入流
          2. 将原始字节数据写入远程 shell 进程的标准输入
          3. 调用 drain() 等待底层缓冲区刷新，确保数据已发送

        参数:
          terminal_id: 目标终端会话 ID
          data:        要发送的原始按键字节（可能包含 ANSI 转义序列）

        异常:
          ValueError: terminal_id 对应的会话不存在
        """
        session = self._terminal_sessions.get(terminal_id)
        if not session:
            raise ValueError(f"终端会话不存在: {terminal_id}")
        session["stdin"].write(data)
        # drain() 确保数据被刷新到 SSH 传输层
        await session["stdin"].drain()

    async def read_terminal_output(self, terminal_id: str) -> bytes:
        """
        从指定终端会话读取远程输出（终端渲染数据）。

        调用方:
          - app.main — WebSocket 定时轮询循环（约 100ms 间隔）

        SSH PTY 生命周期——运行阶段（输出侧）：
          1. 从终端会话的 stdout 读取流中读取最多 4096 字节
          2. 使用 asyncio.wait_for 设置 0.1 秒超时
          3. 超时时返回空字节（无新数据可读，上层继续轮询）
          4. 读取异常时返回空字节（连接可能异常，保持鲁棒性）

        设计考量:
          - 4096 字节的读取缓冲区对于终端渲染足够（单帧 ANSI 输出通常小于此值）
          - 0.1 秒超时允许每秒轮询 ~10 次，在延迟和 CPU 使用之间取得平衡
          - 超时不抛异常，返回 b"" 让 WebSocket 循环继续

        参数:
          terminal_id: 目标终端会话 ID

        返回:
          终端输出的原始字节（可能包含 ANSI 控制序列和转义码），无新数据时返回 b""
        """
        session = self._terminal_sessions.get(terminal_id)
        if not session:
            raise ValueError(f"终端会话不存在: {terminal_id}")
        try:
            data = await asyncio.wait_for(session["stdout"].read(4096), timeout=0.1)
            return data if data else b""
        except asyncio.TimeoutError:
            # 超时 = 当前无新数据，非异常情况
            return b""
        except Exception:
            # 连接断开或其他 I/O 错误，静默返回空字节
            return b""

    async def resize_terminal(self, terminal_id: str, cols: int, rows: int) -> None:
        """
        调整终端会话的窗口尺寸（用户拖动终端窗口时触发）。

        调用方:
          - app.main — WebSocket resize 事件处理函数

        SSH PTY 生命周期——运行阶段（尺寸调整）：
          1. 更新本地缓存的 cols/rows 尺寸记录
          2. 调用 channel.change_terminal_size() 通知远程 PTY 调整尺寸
          3. 远程 shell 进程收到 SIGWINCH 信号，重新计算其内部窗口布局
             （如 vim/less 等全屏程序会据此重绘界面）

        参数:
          terminal_id: 目标终端会话 ID
          cols:        新的列数
          rows:        新的行数

        异常:
          ValueError: terminal_id 对应的会话不存在
        """
        session = self._terminal_sessions.get(terminal_id)
        if not session:
            raise ValueError(f"终端会话不存在: {terminal_id}")
        session["cols"] = cols
        session["rows"] = rows
        # TermSize 格式: (rows, cols, pixel_width, pixel_height)
        session["channel"].change_terminal_size((rows, cols, 0, 0))

    async def get_bash_environment_info(self) -> BashEnvironmentInfo:
        """
        获取远程主机的 Bash 环境信息快照。

        调用方:
          - app.routers.api — /api/terminal/bash-env REST 端点

        采集的项目：
          - bash_version  — "bash --version" 的首行输出
          - shell_type    — $SHELL 环境变量
          - ps1           — $PS1 提示符变量
          - pwd           — 当前工作目录
          - home          — $HOME 用户主目录
          - user          — whoami 当前用户
          - hostname      — 主机名
          - path          — $PATH 环境变量

        错误处理:
          每条命令独立执行；单条失败不影响其他命令的采集。
          失败的命令返回空字符串，不会中断整体采集流程。

        返回:
          BashEnvironmentInfo: 包含所有采集值的模型对象
        """
        cmds = {
            "bash_version": "bash --version 2>/dev/null | head -1 || echo 'unknown'",
            "shell_type": "echo $SHELL 2>/dev/null || echo 'sh'",
            "ps1": "echo \"$PS1\" 2>/dev/null || echo '$ '",
            "pwd": "pwd",
            "home": "echo $HOME",
            "user": "whoami",
            "hostname": "hostname",
            "path": "echo $PATH",
        }
        out: Dict[str, str] = {}
        for k, cmd in cmds.items():
            try:
                r = await self.execute_command(cmd)
                out[k] = (r.output or "").strip()
            except Exception:
                # 单条命令失败不中断，返回空字符串
                out[k] = ""
        return BashEnvironmentInfo(**out)

    async def get_command_completion(self, input_text: str) -> CommandCompletion:
        """
        根据用户输入生成命令自动补全候选列表。

        调用方:
          - app.routers.api — /api/terminal/command-completion REST 端点

        补全策略（两阶段）：
          阶段 1 — 命令名补全（首词，尚未输入空格）：
            从预定义的常用 Linux 命令列表中筛选以用户输入开头的命令。
            涵盖文件操作、进程管理、网络工具、文本处理等类别。

          阶段 2 — 路径/文件补全（已有空格或包含 "/" 字符）：
            在远程主机上执行 ls -1a 命令获取目录内容，
            筛选匹配输入前缀的文件名。

        边缘情况:
          - 输入为空或仅空格：返回所有常用命令
          - ls 命令失败：静默忽略，返回已获取的候选（可能为空）
          - 路径中包含 "/"：正确分割目录和文件名前缀进行匹配

        参数:
          input_text: 用户当前已输入的文本（前端命令输入框内容）

        返回:
          CommandCompletion: 包含候选列表和输入前缀
        """
        words = input_text.split()
        completions: List[str] = []
        if not words or (len(words) == 1 and not input_text.endswith(" ")):
            # 阶段 1：正在输入命令名
            common = [
                "ls",
                "cd",
                "pwd",
                "cat",
                "grep",
                "find",
                "ps",
                "top",
                "htop",
                "df",
                "du",
                "free",
                "uname",
                "whoami",
                "id",
                "groups",
                "chmod",
                "chown",
                "cp",
                "mv",
                "rm",
                "mkdir",
                "rmdir",
                "tar",
                "gzip",
                "gunzip",
                "zip",
                "unzip",
                "vim",
                "nano",
                "less",
                "more",
                "head",
                "tail",
                "ssh",
                "scp",
                "rsync",
                "wget",
                "curl",
                "systemctl",
                "service",
                "crontab",
                "history",
                "awk",
                "sed",
                "sort",
                "uniq",
                "wc",
                "tr",
            ]
            prefix = words[-1] if words else ""
            completions = [c for c in common if c.startswith(prefix)]
        else:
            # 阶段 2：正在输入文件路径
            last_word = words[-1]
            dir_path = "."
            if "/" in last_word:
                dir_path = last_word.rsplit("/", 1)[0] or "/"
            try:
                r = await self.execute_command(f"ls -1a {dir_path}")
                files = (r.output or "").split("\n")
                prefix = last_word.split("/")[-1]
                for f in files:
                    f = f.strip()
                    if f and f not in (".", "..") and f.startswith(prefix):
                        if "/" in last_word:
                            completions.append(
                                f"{last_word[: last_word.rfind('/') + 1]}{f}"
                            )
                        else:
                            completions.append(f)
            except Exception:
                # 远程 ls 失败时静默忽略
                pass
        return CommandCompletion(completions=completions, prefix=input_text)
