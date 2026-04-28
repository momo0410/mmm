"""
=====================================================
文件安全分析模块 (File Security Analysis Module)
=====================================================
通过 SSH 连接对远程 Linux 主机上的文件执行多层次安全分析。
从 Rust file_analysis.rs 迁移至 Python 实现。

=====================================================
模块概述
=====================================================
支持两种分析模式：

1. 完整分析 (Full Analysis)
   - 收集文件元数据（类型、大小、权限、所有者、时间戳）
   - 计算三种密码学哈希（MD5 / SHA-1 / SHA-256）
   - 检测特殊权限位（SUID / SGID / 全局可写 / 隐藏文件）
   - 扫描文件内容中的可疑模式（eval / exec / system / subprocess 等）
   - 综合评估风险等级（low / medium / high）
   - 返回类型：FileAnalysisResult 模型（Pydantic BaseModel）

2. 独立分析 (Independent Analysis)
   - 支持 30+ 种预定义的分析动作 (action)，按需执行单一命令
   - 涵盖：哈希计算、签名识别、权限查看、MIME 类型、ELF 头解析、
     字符串提取、hex-dump、动态库依赖、进程关联、包归属、
     安全检测（webshell / backdoor / crypto-mining / reverse-shell）等
   - 返回类型：通用字典 {"action", "file_path", "result", "exit_code", "timestamp"}

=====================================================
数据模型
=====================================================
FileAnalysisResult (app.models.types.py, Pydantic BaseModel):
  - path: str                    文件路径
  - file_type: str                文件类型（如 "regular file"）
  - size: int                    文件大小（字节）
  - permissions: str              权限八进制字符串（如 "755"）
  - owner: str                    文件所有者
  - group: str                    文件所属用户组
  - hash_md5: Optional[str]       MD5 哈希值
  - hash_sha1: Optional[str]      SHA-1 哈希值
  - hash_sha256: Optional[str]    SHA-256 哈希值
  - modified: Optional[str]       最后修改时间（ISO 8601 格式）
  - created: Optional[str]        创建时间（ISO 8601 格式）
  - accessed: Optional[str]       最后访问时间（ISO 8601 格式）
  - is_suid: bool                 是否设置了 SUID 位（安全风险标记）
  - is_sgid: bool                 是否设置了 SGID 位（安全风险标记）
  - is_world_writable: bool       是否全局可写（安全风险标记）
  - is_hidden: bool               是否隐藏文件（以 . 开头）
  - risk_indicators: List[str]    风险指标列表（中文描述）
  - risk_level: str               风险等级（low / medium / high）
  - details: str                  分析详情摘要

=====================================================
风险等级判定规则
=====================================================
  - low:     无任何风险指标
  - medium:  1~2 个风险指标
  - high:    3 个及以上风险指标

风险指标分为两类：

  A. 文件属性类（无需读取文件内容，由权限位直接判定）：
     - SUID 位已设置    (chmod u+s，执行时以文件所有者权限运行)
     - SGID 位已设置    (chmod g+s，执行时以文件所属组权限运行)
     - 全局可写         (chmod o+w，任何用户均可修改文件)
     - 隐藏文件         (文件名以 . 开头，常见于隐蔽恶意文件)

  B. 文件内容类（仅对 < 1MB 的文件扫描前 1MB 内容）：
     - 使用 eval()      (代码注入风险)
     - 使用 exec()      (代码注入风险)
     - 使用 system()    (命令注入风险)
     - 使用 os.system   (命令注入风险)
     - 使用 subprocess  (子进程调用风险)
     - 危险 rm -rf 命令  (破坏性操作)
     - 危险 chmod 777   (权限过度开放)
     - 访问 /etc/passwd  (敏感文件读取)
     - 访问 /etc/shadow  (敏感文件读取)

=====================================================
SSH 命令清单
=====================================================
完整分析模式执行的远程命令：
  1. stat -c "%F|%s|%a|%U|%G|%W|%Y|%X" <path>
     -> 获取文件类型、大小（字节）、权限（八进制）、所有者、组、创建/修改/访问时间

  2. md5sum <path> && sha1sum <path> && sha256sum <path>
     -> 依次计算 MD5、SHA-1、SHA-256 三种哈希值

  3. head -c 1048576 <path>
     -> 读取文件前 1MB 内容，用于可疑模式正则匹配（仅对小于 1MB 的文件执行）

独立分析模式支持的 30+ 种 action 及其命令：
  - hash:           md5sum + sha1sum + sha256sum
  - signature:      file -b（文件签名/类型识别）
  - permissions:    ls -lh + stat 权限和所有者信息
  - timestamps:     stat 完整时间戳信息
  - inode:          stat inode、硬链接数、设备号、大小
  - mime-type:      file -b --mime-type（MIME 类型）
  - file-size:      du -h + ls -lh（磁盘占用和逻辑大小）
  - strings:        strings -n 8 | head -100（提取可打印字符串）
  - hex-dump:       xxd | head -50（十六进制转储）
  - line-count:     wc -l（行数统计）
  - archive-list:   tar -tzf 或 unzip -l（归档文件内容列表）
  - elf-header:     readelf -h（ELF 二进制文件头解析）
  - processes:      lsof 或 fuser（查看哪些进程正在使用该文件）
  - package-owner:  dpkg -S 或 rpm -qf（查找文件所属软件包）
  - hard-links:     find / -samefile（查找同 inode 的硬链接）
  - process-maps:   grep /proc/*/maps（查看进程内存映射）
  - xattr:          getfattr -d 或 xattr -l（扩展属性）
  - capabilities:   getcap（Linux capabilities 能力集）
  - selinux-context: ls -Z（SELinux 安全上下文）
  - dynamic-deps:   ldd（动态链接库依赖关系）
  - config-references: grep -r /etc/ | head -20（配置文件中的引用）
  - symlink-analysis: ls -l + readlink -f（符号链接分析）
  - suspicious-path: 检查路径是否位于 /tmp、/dev/shm、/var/tmp 等可疑目录
  - hidden-file:     检查文件名是否以 . 开头（隐藏文件）
  - suid-sgid:       find -perm /6000（SUID/SGID 位检测）
  - webshell:        grep 检测 eval/base64_decode/system/exec/shell_exec/passthru（webshell 特征检测）
  - backdoor:        grep 检测 nc -e、/bin/bash、/bin/sh -i 等后门特征（后门检测）
  - crypto-mining:   grep 检测 xmrig/stratum/cryptonight/monero 挖矿特征（挖矿程序检测）
  - reverse-shell:   grep 检测反弹 shell 特征（bash -i、/dev/tcp/ 等反弹shell检测）

=====================================================
依赖关系
=====================================================
  - app.services.ssh_manager.SSHManager  -> 提供 SSH 远程命令执行能力
  - app.models.types.FileAnalysisResult  -> 完整分析返回的 Pydantic 数据模型

=====================================================
被调用的 API 端点
=====================================================
  POST /api/v1/file-analysis
  sftp_file_analysis:
    -> app.routers.api: sftp_file_analysis_endpoint (第 2016 行)
       前端场景：文件管理器右键菜单 "安全分析"
       数据流：前端 -> _wrap_ssh_transport() -> sftp_file_analysis()
           -> 有 action -> _execute_independent_analysis() -> 返回字典
           -> 无 action -> _execute_full_analysis() -> FileAnalysisResult.model_dump()

  POST /api/v1/file-analysis/independent
  sftp_file_analysis_independent:
    -> app.routers.api: sftp_file_analysis_independent_endpoint (第 2041 行)
       前端场景：需要独立于当前 SSH 会话执行分析的场景
       数据流：前端 -> _wrap_ssh_transport() -> sftp_file_analysis_independent()
           -> sftp_file_analysis() -> 与上述流程相同
           （本函数仅是 sftp_file_analysis 的别名，用于语义区分）
"""

import re
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.models.types import FileAnalysisResult
from app.services.ssh_manager import SSHManager


async def sftp_file_analysis(manager: SSHManager, path: str, action: Optional[str] = None) -> Dict[str, Any]:
    """
    远程文件安全分析（统一入口函数）
    ============================================
    根据 action 参数决定执行完整分析还是独立分析：

    1. 如果指定了 action 参数 -> 执行独立分析（30+ 种预设命令）
       返回通用字典：{"action", "file_path", "result", "exit_code", "timestamp"}

    2. 如果 action 为 None -> 执行完整分析
       返回 FileAnalysisResult 模型的字典形式，包含文件元数据、哈希值、
       权限标记、风险指标和风险等级等完整信息。

    调用方：POST /api/v1/file-analysis (app.routers.api: sftp_file_analysis_endpoint)

    Args:
        manager: SSH 管理器实例，用于执行远程命令。
                 必须先建立连接（manager.is_connected() == True），
                 否则抛出 ConnectionError。
        path:    远程主机上的目标文件绝对路径。
        action:  可选的独立分析动作名称（如 "hash", "webshell", "elf-header" 等）。
                 如果为 None，则执行完整分析流程。

    Returns:
        Dict[str, Any]:
          - 完整分析时：FileAnalysisResult 模型序列化后的字典
          - 独立分析时：{"action", "file_path", "result", "exit_code", "timestamp"}

    Raises:
        ConnectionError: 如果没有活动的 SSH 连接
        ValueError:      如果 action 不在预定义的命令列表中
    """
    # 检查 SSH 连接状态，未连接则拒绝执行分析
    if not manager.is_connected():
        raise ConnectionError("没有活动的 SSH 连接")

    # 根据是否传入 action 参数，分流到不同的分析逻辑
    if action:
        # ── 独立分析模式：执行单一预设命令 ──
        return await _execute_independent_analysis(manager, path, action)

    # ── 完整分析模式：收集文件所有安全相关信息 ──
    return await _execute_full_analysis(manager, path)


async def sftp_file_analysis_independent(manager: SSHManager, path: str, action: Optional[str] = None) -> Dict[str, Any]:
    """
    独立文件分析（sftp_file_analysis 的别名函数）
    ============================================
    提供独立的调用入口，内部直接委托给 sftp_file_analysis()，行为完全一致。

    调用方：POST /api/v1/file-analysis/independent (app.routers.api: sftp_file_analysis_independent_endpoint)

    存在此函数是为了在 API 层提供语义清晰的两个端点，
    便于前端在不同使用场景下调用不同路由。

    Args:
        manager: SSH 管理器实例
        path:    远程文件绝对路径
        action:  可选的独立分析动作名称

    Returns:
        与 sftp_file_analysis() 相同的字典结构
    """
    return await sftp_file_analysis(manager, path, action)

async def _execute_full_analysis(manager: SSHManager, path: str) -> Dict[str, Any]:
    """
    执行完整文件安全分析
    ============================================
    通过 SSH 执行多步骤分析，收集文件的全面安全信息：

    1. 调用 stat 获取文件元数据
       - 文件类型 (%F)、大小 (%s)、权限 (%a)
       - 所有者 (%U)、所属组 (%G)
       - 创建时间 (%W)、修改时间 (%Y)、访问时间 (%X)

    2. 计算文件哈希 (md5sum + sha1sum + sha256sum)
       - MD5 哈希值 (128-bit)
       - SHA-1 哈希值 (160-bit)
       - SHA-256 哈希值 (256-bit)

    3. 检测特殊权限 SUID/SGID/全局可写/隐藏文件
       - SUID 位 (0o4000)：表示文件执行时以所有者权限运行（如 root 的 passwd 命令）
       - SGID 位 (0o2000)：表示文件执行时以所属组权限运行
       - 全局可写 (0o0002)：表示任何用户均可修改此文件
       - 隐藏文件：文件名以 . 开头（常见于隐蔽恶意文件）

    4. 对于小于 1MB 的文件，读取前 1MB 内容 (head -c 1048576)，用正则扫描可疑模式：
       - eval() / exec() 动态代码执行（代码注入风险）
       - system() / os.system 系统命令调用（命令注入风险）
       - subprocess 子进程调用（提权/逃逸风险）
       - rm -rf / chmod 777 危险操作（破坏性操作风险）
       - /etc/passwd / /etc/shadow 敏感文件访问（信息泄露风险）

    5. 综合风险等级判定 "high" / "medium" / "low"：
       - 无风险指标 -> low
       - 1~2 个风险指标 -> medium
       - 3 个及以上风险指标 -> high

    Args:
        manager: SSH 管理器（复用当前 SSH session）
        path:    远程文件绝对路径

    Returns:
        FileAnalysisResult.model_dump() - Pydantic 模型序列化后的字典
    """
    # ==================================================================
    # 第 1 步：调用 stat 命令获取文件元数据
    # ==================================================================
    # stat 的格式化输出 "%F|%s|%a|%U|%G|%W|%Y|%X" 含义：
    #   %F = 文件类型 (regular file / directory / symbolic link 等)
    #   %s = 总大小 (字节数)
    #   %a = 访问权限 (八进制 如 755)
    #   %U = 所有者用户名
    #   %G = 所属组名
    #   %W = 创建时间 (Unix Epoch 秒)
    #   %Y = 最后修改时间
    #   %X = 最后访问时间
    stat_cmd = f'stat -c "%F|%s|%a|%U|%G|%W|%Y|%X" "{path}" 2>/dev/null'
    stat_output = await manager.execute_command(stat_cmd)

    # 初始化默认值，当 stat 执行失败时也能返回基础结构
    file_type = "unknown"
    size = 0
    permissions = ""
    owner = ""
    group = ""
    created = ""
    modified = ""
    accessed = ""

    if stat_output.exit_code == 0:
        parts = stat_output.output.strip().split("|")
        if len(parts) >= 8:
            file_type = parts[0]
            try:
                size = int(parts[1])
            except ValueError:
                pass
            permissions = parts[2]
            owner = parts[3]
            group = parts[4]
            # 将 Unix 时间戳转换为 ISO 8601 格式的 UTC 时间字符串
            # 跳过无效时间戳 (Epoch=0 表示时间不可用)
            for i, key in [(5, "created"), (6, "modified"), (7, "accessed")]:
                try:
                    ts = int(parts[i])
                    if ts > 0:
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                        if key == "created":
                            created = dt
                        elif key == "modified":
                            modified = dt
                        else:
                            accessed = dt
                except (ValueError, IndexError):
                    pass

    # ==================================================================
    # 第 2 步：计算文件密码学哈希值
    # ==================================================================
    # 使用 Shell 的 && 串联执行三个哈希命令 (任一失败则后续不执行)
    # md5sum / sha1sum / sha256sum 输出格式: "<hash> <filename>" (空格分隔)
    hash_cmd = f'md5sum "{path}" 2>/dev/null && sha1sum "{path}" 2>/dev/null && sha256sum "{path}" 2>/dev/null'
    hash_output = await manager.execute_command(hash_cmd)

    hash_md5 = None
    hash_sha1 = None
    hash_sha256 = None
    hash_lines = hash_output.output.strip().split("\n")
    if len(hash_lines) >= 1 and hash_lines[0].strip():
        hash_md5 = hash_lines[0].split()[0] if hash_lines[0].split() else None
    if len(hash_lines) >= 2 and hash_lines[1].strip():
        hash_sha1 = hash_lines[1].split()[0] if hash_lines[1].split() else None
    if len(hash_lines) >= 3 and hash_lines[2].strip():
        hash_sha256 = hash_lines[2].split()[0] if hash_lines[2].split() else None

    # ==================================================================
    # 第 3 步：检测特殊权限位
    # ==================================================================
    # 将八进制权限字符串 (如 "4755") 转为整数，按位掩码检测：
    #   0o4000 = SUID (Set User ID)：文件将以所有者身份执行（高危，如 passwd 命令）
    #   0o2000 = SGID (Set Group ID)：文件将以所属组身份执行
    #   0o0002 = 全局可写 (Other write)：任何用户均可修改文件内容
    is_suid = False
    is_sgid = False
    is_world_writable = False
    is_hidden = path.split("/")[-1].startswith(".")

    if permissions:
        try:
            perm_int = int(permissions, 8)
            is_suid = bool(perm_int & 0o4000)
            is_sgid = bool(perm_int & 0o2000)
            is_world_writable = bool(perm_int & 0o0002)
        except ValueError:
            pass

    # ==================================================================
    # 第 4 步：收集文件属性级别的风险指标
    # ==================================================================
    # 将风险描述追加到 risk_indicators 列表中（后续作为 "details" 字段内容）
    risk_indicators = []
    if is_suid:
        risk_indicators.append("SUID位已设置")
    if is_sgid:
        risk_indicators.append("SGID位已设置")
    if is_world_writable:
        risk_indicators.append("全局可写")
    if is_hidden:
        risk_indicators.append("隐藏文件")

    # ==================================================================
    # 第 5 步：扫描文件内容中的可疑模式 (仅对小于 1MB 的文件执行)
    # ==================================================================
    # 使用 head -c 1048576 仅读取文件前 1MB (1048576 字节)
    # 通过正则表达式匹配 9 种常见的可疑代码模式
    risk_level = "low"
    if size < 1024 * 1024:  # 小于 1MB
        content_cmd = f'head -c 1048576 "{path}" 2>/dev/null'
        content_output = await manager.execute_command(content_cmd)
        content = content_output.output

        # 可疑模式正则列表: (正则表达式, 中文描述)
        suspicious_patterns = [
            (r'eval\s*\(', "使用eval()"),      # Python/PHP/JavaScript 动态代码执行
            (r'exec\s*\(', "使用exec()"),      # Python/PHP 动态执行
            (r'system\s*\(', "使用system()"),  # C/PHP/Perl 系统命令调用
            (r'os\.system', "使用os.system"),  # Python 系统命令调用
            (r'subprocess', "使用subprocess"), # Python 子进程模块
            (r'rm\s+-rf', "危险rm命令"),       # 递归强制删除 (破坏性操作)
            (r'chmod\s+777', "危险chmod"),     # 权限过度开放 (rwxrwxrwx)
            (r'/etc/passwd', "访问passwd文件"),  # 敏感系统文件读取
            (r'/etc/shadow', "访问shadow文件"),  # 敏感密码文件读取
        ]

        for pattern, desc in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                risk_indicators.append(desc)

    # 综合判定 "high" / "medium" / "low" 三级风险
    if len(risk_indicators) >= 3:
        risk_level = "high"
    elif risk_indicators:
        risk_level = "medium"

    # ==================================================================
    # 第 6 步：将结果封装为 FileAnalysisResult Pydantic 模型并序列化
    # ==================================================================
    # FileAnalysisResult 定义于 app.models.types (Pydantic BaseModel)
    # 使用 model_dump() 将模型转为字典，以便 JSON 序列化返回给前端
    return FileAnalysisResult(
        path=path,
        file_type=file_type,
        size=size,
        permissions=permissions,
        owner=owner,
        group=group,
        hash_md5=hash_md5,
        hash_sha1=hash_sha1,
        hash_sha256=hash_sha256,
        modified=modified,
        created=created,
        accessed=accessed,
        is_suid=is_suid,
        is_sgid=is_sgid,
        is_world_writable=is_world_writable,
        is_hidden=is_hidden,
        risk_indicators=risk_indicators,
        risk_level=risk_level,
        details=f"发现 {len(risk_indicators)} 个风险指标" if risk_indicators else "未发现风险",
    ).model_dump()

async def _execute_independent_analysis(manager: SSHManager, path: str, action: str) -> Dict[str, Any]:
    """
    执行独立分析命令（30+ 种预设 action 的单一命令分析）
    ============================================
    根据 action 参数选择对应的 SSH 命令并执行。
    不进行综合风险判定，直接返回命令的原始输出。

    Args:
        manager: SSH 管理器（复用当前 SSH session）
        path:    远程文件绝对路径
        action:  独立分析动作名称，支持以下 30+ 种 action：

         文件基本信息类：
          - hash           : MD5 + SHA-1 + SHA-256 三种哈希值
          - signature      : file -b 文件签名/类型识别
          - permissions    : ls -lh + stat 权限和所有者信息
          - timestamps     : stat 完整时间戳信息
          - inode          : stat 获取 inode/硬链接数/设备号/大小
          - mime-type      : MIME 媒体类型检测
          - file-size      : du -h + ls -lh 磁盘占用和逻辑大小

         内容分析类：
          - strings        : strings 提取可打印字符串 (前 100 行)
          - hex-dump       : xxd 十六进制转储 (前 50 行)
          - line-count     : wc -l 行数统计
          - archive-list   : 归档文件内容列表 (tar/unzip 通用)

         二进制分析类：
          - elf-header     : ELF 二进制文件头解析 (readelf -h)
          - dynamic-deps   : 动态链接库依赖关系 (ldd)

         系统关联类：
          - processes      : 哪些进程正在使用该文件 (lsof/fuser)
          - package-owner  : 文件所属软件包 (dpkg -S / rpm -qf)
          - hard-links     : 查找同 inode 的硬链接 (find -samefile)
          - process-maps   : 进程内存映射中的引用 (/proc/*/maps)
          - config-references: 配置文件中的引用 (grep /etc/)

         属性与安全类：
          - xattr          : 扩展属性 (getfattr/xattr)
          - capabilities   : Linux capabilities 能力集 (getcap)
          - selinux-context: SELinux 安全上下文 (ls -Z)
          - symlink-analysis: 符号链接分析 (readlink -f)

         安全检测类：
          - suspicious-path: 可疑路径检测 (/tmp /dev/shm 等)
          - hidden-file    : 隐藏文件检测 (以 . 开头)
          - suid-sgid      : SUID/SGID 位检测 (find -perm /6000)
          - webshell       : Webshell 特征检测 (grep 匹配常见 webshell 函数)
          - backdoor       : 后门程序检测 (grep 匹配常见后门特征)
          - crypto-mining  : 挖矿程序检测 (grep 匹配挖矿软件特征)
          - reverse-shell  : 反弹 Shell 检测 (grep 匹配反弹 shell 特征)

    Returns:
        {
            "action": action,
            "file_path": path,
            "result": 命令成功时返回标准输出，失败时返回错误信息,
            "exit_code": result.exit_code,
            "timestamp": datetime.now(tz=timezone.utc).isoformat()
        }

        注意：独立分析不返回 FileAnalysisResult 模型，
        每个 action 的结果结构独立，由前端负责解析展示。

    Raises:
        ValueError: 如果 action 不在预定义的 commands 字典中
    """
    # ==================================================================
    # 根据 action 映射到对应的 SSH 命令
    # ==================================================================
    # 30+ 种预设命令，涵盖文件分析的各个维度
    # 安全检测类命令 (webshell 等) 使用 grep 正则匹配可疑特征
    # 二进制分析类 (strings, hex-dump 等) 限制输出行数防止数据过大
    # 所有命令通过 2>/dev/null 抑制错误输出，避免干扰
    commands = {
        'hash': f'md5sum "{path}" 2>/dev/null && sha1sum "{path}" 2>/dev/null && sha256sum "{path}" 2>/dev/null',
        'signature': f'file -b "{path}"',
        'permissions': f'ls -lh "{path}" && stat -c \'%A %a %U:%G\' "{path}"',
        'timestamps': f'stat "{path}"',
        'inode': f'stat -c \'Inode: %i\\nLinks: %h\\nDevice: %d\\nSize: %s bytes\' "{path}"',
        'mime-type': f'file -b --mime-type "{path}"',
        'file-size': f'du -h "{path}" && ls -lh "{path}"',
        'strings': f'strings -n 8 "{path}" 2>/dev/null | head -100',
        'hex-dump': f'xxd "{path}" 2>/dev/null | head -50',
        'line-count': f'wc -l "{path}"',
        'archive-list': f'tar -tzf "{path}" 2>/dev/null || unzip -l "{path}" 2>/dev/null',
        'elf-header': f'readelf -h "{path}" 2>/dev/null',
        'processes': f'lsof "{path}" 2>/dev/null || fuser -v "{path}" 2>/dev/null',
        'package-owner': f'dpkg -S "{path}" 2>/dev/null || rpm -qf "{path}" 2>/dev/null',
        'hard-links': f'find / -samefile "{path}" 2>/dev/null',
        'process-maps': f'grep "{path}" /proc/*/maps 2>/dev/null',
        'xattr': f'getfattr -d "{path}" 2>/dev/null || xattr -l "{path}" 2>/dev/null',
        'capabilities': f'getcap "{path}" 2>/dev/null',
        'selinux-context': f'ls -Z "{path}" 2>/dev/null',
        'dynamic-deps': f'ldd "{path}" 2>/dev/null',
        'config-references': f'grep -r "{path}" /etc/ 2>/dev/null | head -20',
        'symlink-analysis': f'ls -l "{path}" && readlink -f "{path}" 2>/dev/null',
        'suspicious-path': f'echo "{path}" | grep -E \'(/tmp/|/dev/shm/|/var/tmp/|\\.\\.)\'',
        'hidden-file': f'basename "{path}" | grep \'^\\.\'',
        'suid-sgid': f'find "{path}" -perm /6000 -ls 2>/dev/null',
        'webshell': f'grep -E \'(eval|base64_decode|system|exec|shell_exec|passthru)\' "{path}" 2>/dev/null',
        'backdoor': f'grep -E \'(nc -e|/bin/bash|/bin/sh.*-i)\' "{path}" 2>/dev/null',
        'crypto-mining': f'grep -E \'(xmrig|stratum|cryptonight|monero)\' "{path}" 2>/dev/null',
        'reverse-shell': f'grep -E \'(bash -i|sh -i|nc.*-e|/dev/tcp/)\' "{path}" 2>/dev/null'
    }

    # 查找 action 对应的命令，未找到则抛出 ValueError
    cmd = commands.get(action)
    if not cmd:
        raise ValueError(f"未知的分析动作: {action}")

    # 通过 SSH 执行命令并获取结果
    result = await manager.execute_command(cmd)

    # 构建并返回统一格式的分析结果字典
    return {
        "action": action,
        "file_path": path,
        "result": result.output if result.exit_code == 0 else f"命令执行失败: {result.error}",
        "exit_code": result.exit_code,
        "timestamp": datetime.now(tz=timezone.utc).isoformat()
    }

