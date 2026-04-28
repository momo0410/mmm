"""
安全检测管理器 — 从 Rust detection_manager.rs 迁移

=============================================================================
模块概述
=============================================================================

本模块是 LovelyRes 安全检测系统的核心，负责通过 SSH 远程执行各类安全基线检查命令，
并将结果封装为 Pydantic 模型返回给上层 API 路由。

检测体系分为三大类：

1. 【安全检测】(Security Detection) — 主动发现安全威胁与配置缺陷：
   - 端口扫描 (detect_port_scan)           — 识别目标主机上所有 LISTEN 端口及对应服务
   - 用户权限审计 (detect_user_audit)      — 检查 /etc/passwd 中的 root 用户、普通用户、空密码用户
   - 后门检测 (detect_backdoor)            — 排查可疑 crontab 计划任务、自启动项、SSH 授权密钥
   - 进程分析 (detect_process_analysis)    — 分析 CPU/内存占用高的进程及可疑进程（nc/socat/cryptominer 等）
   - 文件权限检测 (detect_file_permission) — 扫描 SUID 文件及 /etc/shadow、/etc/passwd 等敏感文件的权限问题
   - SSH 安全审计 (detect_ssh_audit)       — 审计 sshd_config 中的 PermitRootLogin、PasswordAuthentication、Port
   - 日志分析 (detect_log_analysis)        — 分析 /var/log/auth.log 中的失败登录尝试（暴力破解检测）
   - 防火墙检查 (detect_firewall_check)    — 检查 iptables / ufw / firewalld 三种防火墙的运行状态

2. 【性能检测】(Performance Test) — 采集主机硬件资源信息：
   - CPU 测试 (detect_cpu_test)            — 获取 CPU 型号、频率、top 负载信息
   - 内存测试 (detect_memory_test)         — 获取内存总量、已用、空闲（free -h）
   - 磁盘测试 (detect_disk_test)           — 获取各分区挂载及使用情况（df -h）
   - 网络测试 (detect_network_test)        — 获取网络接口配置（ip addr 或 ifconfig）

3. 【基线检测】(Baseline Detection) — 对照安全基线标准检查系统配置合规性：
   - 密码策略检查 (detect_password_policy)           — 检查 /etc/login.defs 中的密码有效期、最小长度等
   - Sudo 权限审计 (detect_sudo_config)              — 检查 sudo -l 中的 NOPASSWD 及 ALL 授权
   - PAM 配置检查 (detect_pam_config)                — 检查 /etc/pam.d 中的认证模块配置
   - 账号锁定策略 (detect_account_lockout)           — 检查是否启用了 pam_faillock / pam_tally 防暴力破解
   - SELinux/AppArmor 状态 (detect_selinux_status)   — 检查 SELinux 是否处于 enforcing 模式
   - 内核参数检查 (detect_kernel_params)             — 检查 ip_forward、rp_filter、exec-shield 等安全参数
   - 系统补丁状态 (detect_system_updates)            — 检查可更新的软件包列表
   - 不必要服务检查 (detect_unnecessary_services)    — 检查当前运行的服务列表
   - 自启动服务审计 (detect_auto_start_services)     — 检查启用自启动的服务单元
   - 审计配置检查 (detect_audit_config)              — 检查 auditd 服务状态及审计规则
   - 历史命令审计 (detect_history_audit)             — 检查 ~/.bash_history 最近命令
   - NTP 配置检查 (detect_ntp_config)                — 检查时间同步配置
   - DNS 配置检查 (detect_dns_config)                — 检查 /etc/resolv.conf DNS 解析器配置

=============================================================================
运行机制
=============================================================================

1. 每个检测函数接收一个 SSHManager 实例（封装了 asyncssh 连接），通过
   manager.execute_command(cmd) 在远程主机上执行 shell 命令，返回 TerminalOutput 对象。
2. 命令都附加了 "2>/dev/null || true" 等容错后缀，确保缺乏权限或文件不存在时不会
   抛出异常中断检测流程。
3. 检测结果统一包含 risk_level 字段（"low" / "medium" / "high"）用于前端展示风险等级。
4. 所有函数均为 async，通过 FastAPI 路由在 asyncio 事件循环中异步调度执行。
5. 本模块通过 app.routers.api 中的 POST 路由暴露给外部；每个函数对应一个
   /detect/* 端点，metadata 标注为 "low-level" 仅供内部 Agent 调用。

=============================================================================
"""

import re
from typing import Any, Dict, List, Optional

from app.models.types import (
    BackdoorScanResult,
    CpuTestResult,
    DiskTestResult,
    FilePermissionResult,
    FirewallCheckResult,
    GenericDetectionResult,
    LogAnalysisResult,
    MemoryTestResult,
    NetworkTestResult,
    PortScanResult,
    ProcessAnalysisResult,
    SSHAuditResult,
    UserAuditResult,
)
from app.services.ssh_manager import SSHManager


def _extract_port_from_netstat(line: str) -> Optional[int]:
    """
    从 netstat / ss 输出的单行中提取端口号。

    匹配模式为 ":PORT" 格式（如 "0.0.0.0:22" 中的 22），
    返回该行最后一个匹配的端口号。若无法匹配则返回 None。

    由 detect_port_scan 调用，用于解析 LISTEN 行的本地端口。
    """
    matches = re.findall(r':(\d+)', line)
    if matches:
        return int(matches[-1])
    return None


def _identify_service(port: int) -> str:
    """
    根据端口号识别常见服务名称。

    内置 22 个常用端口与服务的映射表（21=ftp, 22=ssh, 80=http, 443=https,
    3306=mysql, 5432=postgresql, 6379=redis, 27017=mongodb 等），
    未匹配的端口返回 "unknown"。

    由 detect_port_scan 调用，用于给每个 LISTEN 端口标注服务类型。
    """
    services = {
        20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
        53: "dns", 80: "http", 110: "pop3", 143: "imap", 443: "https",
        465: "smtps", 587: "submission", 993: "imaps", 995: "pop3s",
        1433: "mssql", 1521: "oracle", 3306: "mysql", 3389: "rdp",
        5432: "postgresql", 5900: "vnc", 6379: "redis", 8080: "http-proxy",
        8443: "https-alt", 9200: "elasticsearch", 27017: "mongodb",
    }
    return services.get(port, "unknown")


# ==================== 安全检测函数 ====================

async def detect_port_scan(manager: SSHManager) -> PortScanResult:
    """
    端口安全扫描 — 识别目标主机上所有处于 LISTEN 状态的 TCP 端口及对应服务。

    SSH 命令：
        (netstat -tlnp 2>/dev/null | grep LISTEN || ss -tlnp 2>/dev/null | grep LISTEN) || true
        优先使用 netstat（较旧的发行版支持更好），失败则回退到 ss。

    解析逻辑：
        逐行过滤 "LISTEN" 关键字 → 用 _extract_port_from_netstat 提取端口号 →
        用 _identify_service 识别服务名 → 按端口号去重排序。

    风险评估：
        无内置风险分级（PortScanResult 未设置 risk_level 字段），
        仅返回原始端口数据供上层分析。

    Pydantic 返回类型：app.models.types.PortScanResult
        - open_ports: List[dict]  每个元素含 port, service, state 字段
        - total_open: int         开放端口总数

    API 端点：POST /detect/port-scan (分类: detection)
    """
    cmd = "(netstat -tlnp 2>/dev/null | grep LISTEN || ss -tlnp 2>/dev/null | grep LISTEN) || true"
    output = await manager.execute_command(cmd)

    open_ports = []
    for line in output.output.split("\n"):
        if "LISTEN" in line:
            port = _extract_port_from_netstat(line)
            if port:
                service = _identify_service(port)
                open_ports.append({"port": port, "service": service, "state": "LISTEN"})

    # 去重（同一端口可能在不同地址上 LISTEN）
    seen = set()
    unique_ports = []
    for p in open_ports:
        if p["port"] not in seen:
            seen.add(p["port"])
            unique_ports.append(p)
    unique_ports.sort(key=lambda x: x["port"])

    return PortScanResult(open_ports=unique_ports, total_open=len(unique_ports))


async def detect_user_audit(manager: SSHManager) -> UserAuditResult:
    """
    用户权限审计 — 检查 /etc/passwd 中的特权用户、普通用户及空密码用户。

    SSH 命令（共2条）：
        1. cat /etc/passwd
           读取所有本地用户账号信息。
        2. sudo cat /etc/shadow 2>/dev/null | grep -E '^[^:]+::' | cut -d: -f1
           提取空密码用户列表（shadow 中第二个字段为空即密码为空）。

    解析逻辑：
        - 解析 /etc/passwd 的 7 个冒号分隔字段，提取 username/uid/gid/shell/home。
        - uid == 0 的用户归入 root_users（超级用户）。
        - 1000 <= uid < 60000 的用户归入 recent_users（普通用户），最多保留前5个。
        - 从 /etc/shadow 独立提取 empty_password_users 列表。

    风险评估：
        - root 用户数 > 1  → risk_level = "high"  （存在多个超级用户，权限管理混乱）
        - root 用户数 ≤ 1  → risk_level = "low"

    Pydantic 返回类型：app.models.types.UserAuditResult
        - users: List[dict]         root_users + recent_users[:5]
        - risk_users: List[dict]    所有 uid=0 的 root 用户
        - risk_level: str           "high" / "low"
        - details: str              含 root 用户数和空密码用户数的摘要

    API 端点：POST /detect/user-audit (分类: detection)
    """
    passwd_output = await manager.execute_command("cat /etc/passwd")

    root_users = []
    recent_users = []
    for line in passwd_output.output.split("\n"):
        parts = line.split(":")
        if len(parts) >= 7:
            username = parts[0]
            uid = int(parts[2]) if parts[2].isdigit() else 9999
            gid = int(parts[3]) if parts[3].isdigit() else 9999
            home = parts[5]
            shell = parts[6]

            user_info = {"username": username, "uid": uid, "gid": gid, "shell": shell, "home": home}
            if uid == 0:
                root_users.append(user_info)
            if 1000 <= uid < 60000:
                recent_users.append(user_info)

    # 检查空密码用户 — 通过 shadow 文件中第二个字段为空的行判定
    shadow_cmd = "sudo cat /etc/shadow 2>/dev/null | grep -E '^[^:]+::' | cut -d: -f1"
    shadow_output = await manager.execute_command(shadow_cmd)
    empty_password_users = [l.strip() for l in shadow_output.output.split("\n") if l.strip()]

    return UserAuditResult(
        users=root_users + recent_users[:5],
        risk_users=root_users,
        risk_level="high" if len(root_users) > 1 else "low",
        details=f"发现 {len(root_users)} 个root用户, {len(empty_password_users)} 个空密码用户",
    )


async def detect_backdoor(manager: SSHManager) -> BackdoorScanResult:
    """
    后门检测 — 排查目标主机上可疑的持久化机制（计划任务、自启动项、SSH 授权密钥）。

    SSH 命令（共3条）：
        1. (crontab -l; sudo crontab -l; cat /etc/crontab) |
           grep -v '^#' | grep -v '^$' | grep -E '(curl|wget|nc|bash|sh|python)'
           提取所有用户 crontab 及系统 crontab 中包含网络下载或脚本执行的可疑条目。
        2. find /etc/init.d /etc/systemd/system /etc/rc*.d -type f 2>/dev/null | head -20
           列出自启动目录中的文件（限制前20条以免输出过多）。
        3. find /home /root -name authorized_keys 2>/dev/null |
           xargs cat 2>/dev/null | grep -v '^#' | grep -v '^$' | head -5
           列出所有 SSH 授权密钥（截断到前60字符），检测是否有非授权访问入口。

    风险评估：
        - 发现可疑 crontab 条目 → risk_level = "high"  （存在后门/持久化恶意脚本）
        - 无可疑条目           → risk_level = "low"

    Pydantic 返回类型：app.models.types.BackdoorScanResult
        - suspicious_files: List[dict]  cron + autostart 条目合并
        - risk_level: str               "high" / "low"
        - details: str                  摘要信息

    API 端点：POST /detect/backdoor (分类: detection)
    """
    # 检查可疑的计划任务 — 过滤含有外部网络连接或脚本解释器的 crontab 条目
    cron_cmd = (
        "(crontab -l 2>/dev/null; sudo crontab -l 2>/dev/null; cat /etc/crontab 2>/dev/null) | "
        "grep -v '^#' | grep -v '^$' | grep -E '(curl|wget|nc|bash|sh|python)'"
    )
    cron_output = await manager.execute_command(cron_cmd)
    suspicious_cron = [l.strip() for l in cron_output.output.split("\n") if l.strip()]

    # 检查可疑的启动项 — 遍历 init.d / systemd 系统 / rc*.d 目录
    autostart_cmd = "find /etc/init.d /etc/systemd/system /etc/rc*.d -type f 2>/dev/null | head -20"
    autostart_output = await manager.execute_command(autostart_cmd)
    suspicious_autostart = [l.strip() for l in autostart_output.output.split("\n") if l.strip()][:10]

    # 检查 SSH authorized_keys — 发现是否有未授权的公钥登录入口
    ssh_keys_cmd = (
        "find /home /root -name authorized_keys 2>/dev/null | "
        "xargs cat 2>/dev/null | grep -v '^#' | grep -v '^$' | head -5"
    )
    keys_output = await manager.execute_command(ssh_keys_cmd)
    suspicious_ssh_keys = [l.strip()[:60] + "..." for l in keys_output.output.split("\n") if l.strip()]

    return BackdoorScanResult(
        suspicious_files=[{"path": x} for x in (suspicious_cron + suspicious_autostart)],
        risk_level="high" if suspicious_cron else "low",
        details=f"发现 {len(suspicious_cron)} 个可疑cron任务, {len(suspicious_autostart)} 个启动项",
    )


async def detect_process_analysis(manager: SSHManager) -> ProcessAnalysisResult:
    """
    进程分析 — 识别高资源消耗进程及可疑恶意进程。

    SSH 命令：
        ps aux --sort=-%cpu | head -50
        按 CPU 占用率降序排列，取前 50 行（含标题行），以获取资源消耗最大的进程。

    解析逻辑：
        - 跳过标题行（第一行），对后续行按空白分割成 11 个字段。
        - 提取 user / pid / cpu% / mem% / command 五个关键字段。
        - cpu > 50% 或 mem > 50% → 归入 high_resource_processes。
        - command 中包含 nc/ncat/socat/cryptominer/xmrig → 归入 suspicious_processes。
          这些关键词对应反弹 shell 工具和加密挖矿程序。

    风险评估：
        - 存在可疑进程 → risk_level = "high"  （可能有反弹 shell 或挖矿程序）
        - 无可疑进程   → risk_level = "low"

    Pydantic 返回类型：app.models.types.ProcessAnalysisResult
        - processes: List[dict]             高资源进程 + 可疑进程合并
        - suspicious_processes: List[dict]  仅可疑进程子集
        - risk_level: str                   "high" / "low"
        - details: str                      含可疑进程数与高资源进程数

    API 端点：POST /detect/process-analysis (分类: detection)
    """
    cmd = "ps aux --sort=-%cpu | head -50"
    output = await manager.execute_command(cmd)

    suspicious_processes = []
    high_resource_processes = []
    for line in output.output.split("\n")[1:]:  # 跳过标题行
        parts = line.split(None, 10)
        if len(parts) >= 11:
            proc = {
                "user": parts[0], "pid": int(parts[1]) if parts[1].isdigit() else 0,
                "cpu": float(parts[2]) if parts[2] else 0,
                "mem": float(parts[3]) if parts[3] else 0,
                "command": parts[10],
            }
            if proc["cpu"] > 50 or proc["mem"] > 50:
                high_resource_processes.append(proc)
            # 检测可疑进程 — 匹配反弹shell工具和挖矿程序的常见文件名
            suspicious_keywords = ["nc", "ncat", "socat", "cryptominer", "xmrig"]
            if any(kw in proc["command"].lower() for kw in suspicious_keywords):
                suspicious_processes.append(proc)

    return ProcessAnalysisResult(
        processes=high_resource_processes + suspicious_processes,
        suspicious_processes=suspicious_processes,
        risk_level="high" if suspicious_processes else "low",
        details=f"发现 {len(suspicious_processes)} 个可疑进程, {len(high_resource_processes)} 个高资源进程",
    )


async def detect_file_permission(manager: SSHManager) -> FilePermissionResult:
    """
    文件权限检测 — 扫描 SUID 特权文件和敏感系统文件的权限问题。

    SSH 命令（共2条）：
        1. find / -perm -4000 -type f 2>/dev/null | head -30
           扫描系统所有 SUID 文件（权限位 4000），限制前 30 个。
           SUID 文件允许普通用户以文件所有者（通常是 root）身份执行，存在提权风险。
        2. ls -la /etc/shadow /etc/passwd /etc/ssh/sshd_config 2>/dev/null |
           grep -E '(world|other)'
           检查三个核心敏感文件是否对 "world" 或 "other" 有异常读写权限。

    风险评估：
        - SUID 文件数 > 20  → risk_level = "medium"  （SUID 文件异常多，需审查）
        - SUID 文件数 ≤ 20  → risk_level = "low"

    Pydantic 返回类型：app.models.types.FilePermissionResult
        - risky_files: List[dict]  SUID 文件 + 敏感文件权限问题合并
        - risk_level: str          "medium" / "low"
        - details: str             含 SUID 文件数及权限问题数

    API 端点：POST /detect/file-permission (分类: detection)
    """
    # SUID 文件扫描 — 任何设置了 setuid 位的可执行文件都有潜在提权风险
    suid_cmd = "find / -perm -4000 -type f 2>/dev/null | head -30"
    suid_output = await manager.execute_command(suid_cmd)
    suid_files = [l.strip() for l in suid_output.output.split("\n") if l.strip()]

    # 敏感文件权限问题 — 检查 /etc/shadow、/etc/passwd、sshd_config 是否被普通用户可读
    sensitive_cmd = (
        "ls -la /etc/shadow /etc/passwd /etc/ssh/sshd_config 2>/dev/null | "
        "grep -E '(world|other)'"
    )
    sensitive_output = await manager.execute_command(sensitive_cmd)
    sensitive_issues = [l.strip() for l in sensitive_output.output.split("\n") if l.strip()]

    return FilePermissionResult(
        risky_files=[{"path": x} for x in (suid_files + sensitive_issues)],
        risk_level="medium" if len(suid_files) > 20 else "low",
        details=f"发现 {len(suid_files)} 个SUID文件, {len(sensitive_issues)} 个权限问题",
    )


async def detect_ssh_audit(manager: SSHManager) -> SSHAuditResult:
    """
    SSH 安全审计 — 检查 sshd_config 中的关键安全配置项。

    SSH 命令：
        cat /etc/ssh/sshd_config 2>/dev/null
        读取 SSH 服务配置文件全文，容错处理（文件不存在或不可读时静默失败）。

    审计项（三项检查，基于配置文本大小写不敏感匹配）：
        1. PermitRootLogin — 是否允许 root 直接 SSH 登录。
           判定逻辑：显式配置 "permitrootlogin yes" 或未配置（默认允许）。
        2. PasswordAuthentication — 是否允许密码认证（vs 仅允许密钥认证）。
           判定逻辑：显式配置 "passwordauthentication yes" 或未出现在配置中。
        3. Port — 是否使用默认 22 端口。
           判定逻辑：显式配置 "port 22" 或未出现 "port" 行。

    风险评估：
        - 问题数 ≥ 2 → risk_level = "high"   （多项不安全配置）
        - 问题数 = 1 → risk_level = "medium"
        - 问题数 = 0 → risk_level = "low"    （SSH 配置安全）

    Pydantic 返回类型：app.models.types.SSHAuditResult
        - config_issues: List[dict]  每项为一个 {"issue": "问题描述"} 字典
        - risk_level: str            "high" / "medium" / "low"
        - details: str               以逗号分隔的问题列表，或"SSH配置安全"

    API 端点：POST /detect/ssh-audit (分类: detection)
    """
    cmd = "cat /etc/ssh/sshd_config 2>/dev/null"
    output = await manager.execute_command(cmd)

    config = output.output.lower()
    # 检查是否允许 root 登录：显式 yes 或未明确禁止（默认即允许）
    permit_root_login = "permitrootlogin yes" in config or "permitrootlogin without-password" not in config and "permitrootlogin no" not in config
    # 检查是否允许密码认证：显式 yes 或未配置（默认允许）
    password_auth = "passwordauthentication yes" in config or "passwordauthentication" not in config
    # 检查是否使用默认 SSH 端口
    default_port = "port 22" in config or "port " not in config

    issues = []
    if permit_root_login:
        issues.append("允许root登录")
    if password_auth:
        issues.append("允许密码认证")
    if default_port:
        issues.append("使用默认SSH端口(22)")

    return SSHAuditResult(
        config_issues=[{"issue": i} for i in issues],
        risk_level="high" if len(issues) >= 2 else "medium" if issues else "low",
        details=", ".join(issues) if issues else "SSH配置安全",
    )


async def detect_log_analysis(manager: SSHManager) -> LogAnalysisResult:
    """
    日志分析 — 检测 SSH 认证失败日志以发现暴力破解攻击迹象。

    SSH 命令（二选一回退）：
        优先：grep -i 'failed|error|invalid' /var/log/auth.log 2>/dev/null | tail -20
        回退：journalctl -u sshd --since '1 hour ago' 2>/dev/null | grep -i 'failed' | tail -20
        先尝试读取传统 syslog 格式的 auth.log，若不存在则通过 journalctl 查询 sshd 日志。

    分析逻辑：
        - 逐行提取最近 20 条包含 "failed" / "error" / "invalid" 的认证日志条目。
        - 统计其中含 "failed" 的行数作为暴力破解尝试次数（brute_force_count）。

    风险评估：
        - failed > 10  → risk_level = "high"   （疑似暴力破解攻击进行中）
        - failed > 3   → risk_level = "medium"  （少量失败尝试）
        - failed ≤ 3   → risk_level = "low"     （正常水平）

    Pydantic 返回类型：app.models.types.LogAnalysisResult
        - entries: List[dict]   每项为 {"line": "日志原文"}
        - risk_level: str       "high" / "medium" / "low"
        - details: str          含失败登录尝试次数

    API 端点：POST /detect/log-analysis (分类: detection)
    """
    cmd = (
        "grep -i 'failed\\|error\\|invalid' /var/log/auth.log 2>/dev/null | tail -20 || "
        "journalctl -u sshd --since '1 hour ago' 2>/dev/null | grep -i 'failed' | tail -20"
    )
    output = await manager.execute_command(cmd)

    entries = [l.strip() for l in output.output.split("\n") if l.strip()]
    brute_force_count = len([e for e in entries if "failed" in e.lower()])

    return LogAnalysisResult(
        entries=[{"line": e} for e in entries],
        risk_level="high" if brute_force_count > 10 else "medium" if brute_force_count > 3 else "low",
        details=f"发现 {brute_force_count} 次失败登录尝试",
    )


async def detect_firewall_check(manager: SSHManager) -> FirewallCheckResult:
    """
    防火墙检查 — 检测目标主机防火墙的运行状态（支持 iptables、ufw、firewalld 三种）。

    SSH 命令（共3条，并行执行）：
        1. sudo iptables -L -n 2>/dev/null | head -20
           查看 iptables 规则列表，输出超过 50 字节视为有规则配置。
        2. sudo ufw status 2>/dev/null
           查看 Ubuntu/Debian 默认防火墙 ufw 的运行状态。
        3. sudo firewall-cmd --state 2>/dev/null
           查看 RHEL/CentOS/Fedora 默认防火墙 firewalld 的运行状态。

    判定逻辑：
        - ufw 输出含 "active"  → 防火墙激活
        - firewalld 输出含 "running" → 防火墙激活
        - iptables 输出长度 > 50 字节 → 防火墙激活（有规则）
        三种任一条满足即认为 firewall_active = True。

    风险评估：
        - 防火墙未激活 → risk_level = "high"  （主机直接暴露，安全风险极高）
        - 防火墙已激活 → risk_level = "low"

    Pydantic 返回类型：app.models.types.FirewallCheckResult
        - status: str          "active" / "inactive"
        - rules: List[dict]    前 10 条 iptables 规则
        - risk_level: str      "high" / "low"
        - details: str         "防火墙已启用" 或 "防火墙未启用"

    API 端点：POST /detect/firewall-check (分类: detection)
    """
    # 检查 iptables 规则 — Linux 内核级防火墙框架
    iptables_cmd = "sudo iptables -L -n 2>/dev/null | head -20"
    iptables_output = await manager.execute_command(iptables_cmd)

    # 检查 ufw 状态 — Ubuntu 上的 iptables 前端简化工具
    ufw_cmd = "sudo ufw status 2>/dev/null"
    ufw_output = await manager.execute_command(ufw_cmd)

    # 检查 firewalld 状态 — RHEL/CentOS 7+ 的默认防火墙服务
    firewalld_cmd = "sudo firewall-cmd --state 2>/dev/null"
    firewalld_output = await manager.execute_command(firewalld_cmd)

    # 三种防火墙中任一种处于活跃状态即认定防火墙已启用
    firewall_active = (
        "active" in ufw_output.output.lower()
        or "running" in firewalld_output.output.lower()
        or len(iptables_output.output.strip()) > 50
    )

    rules = [l.strip() for l in iptables_output.output.split("\n") if l.strip()][:10]

    return FirewallCheckResult(
        status="active" if firewall_active else "inactive",
        rules=[{"rule": r} for r in rules],
        risk_level="high" if not firewall_active else "low",
        details="防火墙已启用" if firewall_active else "防火墙未启用",
    )


# ==================== 性能检测函数 ====================

async def detect_cpu_test(manager: SSHManager) -> CpuTestResult:
    """
    CPU 测试 — 获取远程主机的 CPU 型号、频率及当前负载信息。

    SSH 命令：
        lscpu | grep -E '^(CPU\\(s\\)|Model name|CPU MHz)' && echo '---' && top -bn1 | head -5
        1. lscpu 获取 CPU 核心数（CPU(s)）、型号名称（Model name）、主频（CPU MHz）。
        2. 以 "---" 分隔后运行 top -bn1（非交互模式单次采样）获取 1/5/15 分钟平均负载。

    风险评估：
        无风险分级（CPU 信息属于性能监控数据，非安全检测项）。

    Pydantic 返回类型：app.models.types.CpuTestResult
        - cpu_info: str    lscpu 输出（CPU 硬件信息）
        - cpu_usage: float 固定为 0.0（当前未做进一步解析）
        - details: str     完整命令输出的原始文本

    API 端点：POST /detect/cpu-test (分类: performance)
    """
    cmd = "lscpu | grep -E '^(CPU\\(s\\)|Model name|CPU MHz)' && echo '---' && top -bn1 | head -5"
    output = await manager.execute_command(cmd)
    return CpuTestResult(cpu_info=output.output, cpu_usage=0.0, details=output.output)


async def detect_memory_test(manager: SSHManager) -> MemoryTestResult:
    """
    内存测试 — 获取远程主机的内存总量、已用、空闲信息。

    SSH 命令：
        free -h
        以人类可读格式（-h）显示内存和交换分区使用情况。

    解析逻辑：
        - 按换行分割输出，取第 2 行（Mem 行）。
        - 以空白分割后取 parts[1]=total, parts[2]=used, parts[3]=free。
        - 若 free 输出行数不足 2 行（异常情况），各字段回退为 "N/A"。

    风险评估：
        无风险分级（内存信息属于性能监控数据，非安全检测项）。

    Pydantic 返回类型：app.models.types.MemoryTestResult
        - total: str         总内存（如 "7.6Gi"）
        - used: str          已用内存
        - free: str          空闲内存
        - usage_percent: float 固定为 0.0（当前未做百分比计算）
        - details: str       free -h 完整输出

    API 端点：POST /detect/memory-test (分类: performance)
    """
    cmd = "free -h"
    output = await manager.execute_command(cmd)
    lines = output.output.strip().split("\n")
    total = used = free = "N/A"
    usage_percent = 0.0
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 4:
            total, used, free = parts[1], parts[2], parts[3]
    return MemoryTestResult(total=total, used=used, free=free, usage_percent=usage_percent, details=output.output)


async def detect_disk_test(manager: SSHManager) -> DiskTestResult:
    """
    磁盘测试 — 获取远程主机各分区的挂载信息及使用率。

    SSH 命令：
        df -h
        以人类可读格式显示所有文件系统的磁盘空间使用情况。

    解析逻辑：
        - 跳过标题行（第 1 行），对后续每行按空白分割成 ≥6 个字段。
        - 提取 filesystem/size/used/avail/use%/mount 六个字段组成磁盘字典。

    风险评估：
        无风险分级（磁盘信息属于性能监控数据，非安全检测项）。

    Pydantic 返回类型：app.models.types.DiskTestResult
        - disks: List[dict]   每个元素含 filesystem, size, used, avail, use%, mount
        - details: str        df -h 完整输出

    API 端点：POST /detect/disk-test (分类: performance)
    """
    cmd = "df -h"
    output = await manager.execute_command(cmd)
    disks = []
    for line in output.output.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 6:
            disks.append({"filesystem": parts[0], "size": parts[1], "used": parts[2], "avail": parts[3], "use%": parts[4], "mount": parts[5]})
    return DiskTestResult(disks=disks, details=output.output)


async def detect_network_test(manager: SSHManager) -> NetworkTestResult:
    """
    网络测试 — 获取远程主机的网络接口配置信息。

    SSH 命令：
        ip addr show 2>/dev/null || ifconfig 2>/dev/null
        优先使用现代 iproute2 工具的 ip addr show，若不支持则回退到传统 ifconfig。

    解析逻辑：
        不做详细解析，将整个命令输出作为单条 info 存入 interfaces 列表。

    风险评估：
        无风险分级（网络信息属于性能监控数据，非安全检测项）。

    Pydantic 返回类型：app.models.types.NetworkTestResult
        - interfaces: List[dict]   含一条 {"info": "原始输出"} 记录
        - connections: List[dict]  空列表（当前未做连接状态解析）
        - details: str             原始命令输出

    API 端点：POST /detect/network-test (分类: performance)
    """
    cmd = "ip addr show 2>/dev/null || ifconfig 2>/dev/null"
    output = await manager.execute_command(cmd)
    return NetworkTestResult(interfaces=[{"info": output.output}], connections=[], details=output.output)


# ==================== 基线检测函数（基于通用模板） ====================

async def _generic_detection(
    manager: SSHManager,
    title: str,
    cmd: str,
    items_are_issues: bool = True,
) -> GenericDetectionResult:
    """
    通用基线检测模板 — 执行一条 SSH 命令并将输出行转为检测条目。

    参数：
        manager: SSHManager 实例，提供远程命令执行能力。
        title: 检测项标题（如 "密码策略检查"）。
        cmd: 在远程主机上执行的 shell 命令。
        items_are_issues: 输出行是否代表"问题"（True=发现的每一项都是问题；False=发现的每一项都是配置信息）。

    风险评估逻辑（与 items_are_issues 关联）：
        - items_are_issues = True 时（输出行 = 问题项）：
            问题数 > 5   → risk_level = "high",   status = "fail"
            问题数 > 0   → risk_level = "medium", status = "fail"
            问题数 = 0   → risk_level = "low",    status = "pass"
        - items_are_issues = False 时（输出行 = 期望配置项）：
            有输出项       → risk_level = "low",    status = "pass"
            无输出项       → risk_level = "medium", status = "fail"

    Pydantic 返回类型：app.models.types.GenericDetectionResult
        - title: str         检测项名称
        - status: str        "pass" / "fail"
        - items: List[dict]  每项为 {"line": "输出行内容"}
        - risk_level: str    "high" / "medium" / "low"
        - details: str       摘要描述字符串

    使用方式：
        所有基线检测函数（detect_password_policy、detect_sudo_config 等）
        均通过本模板函数执行命令并生成标准化结果，避免重复代码。
    """
    output = await manager.execute_command(cmd)
    items = [l.strip() for l in output.output.split("\n") if l.strip()]
    if items_are_issues:
        risk_level = "high" if len(items) > 5 else "medium" if items else "low"
        status = "fail" if items else "pass"
        details = f"发现 {len(items)} 个问题"
    else:
        status = "pass" if items else "fail"
        risk_level = "low" if items else "medium"
        details = f"已获取 {len(items)} 条配置信息" if items else "未获取到有效配置"
    return GenericDetectionResult(
        title=title, status=status, items=[{"line": i} for i in items],
        risk_level=risk_level, details=details,
    )


async def detect_password_policy(manager: SSHManager) -> GenericDetectionResult:
    """
    密码策略检查 — 检查 /etc/login.defs 中配置的密码安全策略参数。

    SSH 命令：
        grep -v '^#' /etc/login.defs 2>/dev/null | grep -E '(PASS_MAX_DAYS|PASS_MIN_DAYS|PASS_MIN_LEN|PASS_WARN_AGE)'
        过滤注释行后提取四个关键密码策略参数：最大有效期、最小修改间隔、最小长度、过期警告天数。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - 缺少某些密码策略配置 → 找到的参数越多表示安全越好
        - 实际行为：缺少这些参数视为问题项，缺少越多风险越高

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/password-policy (分类: baseline)
    """
    cmd = "grep -v '^#' /etc/login.defs 2>/dev/null | grep -E '(PASS_MAX_DAYS|PASS_MIN_DAYS|PASS_MIN_LEN|PASS_WARN_AGE)'"
    return await _generic_detection(manager, "密码策略检查", cmd)


async def detect_sudo_config(manager: SSHManager) -> GenericDetectionResult:
    """
    Sudo 配置审计 — 检查当前用户是否拥有无密码 sudo 或全权限 sudo 授权。

    SSH 命令：
        sudo -l 2>/dev/null | grep -E '(NOPASSWD|ALL)'
        列出当前用户 sudo 权限中涉及免密码（NOPASSWD）或全部命令（ALL）的条目。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - 发现 NOPASSWD 或 ALL 授权条目 → 视为安全配置问题，条目越多风险越高。
        - 无此类授权 → status = "pass", risk_level = "low"。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/sudo-config (分类: baseline)
    """
    cmd = "sudo -l 2>/dev/null | grep -E '(NOPASSWD|ALL)'"
    return await _generic_detection(manager, "Sudo 配置审计", cmd)


async def detect_pam_config(manager: SSHManager) -> GenericDetectionResult:
    """
    PAM 配置检查 — 读取 /etc/pam.d/common-auth 和 /etc/pam.d/sshd 的有效配置行。

    SSH 命令：
        grep -v '^#' /etc/pam.d/common-auth /etc/pam.d/sshd 2>/dev/null | grep -v '^$'
        去除注释行和空行后提取 PAM 认证模块配置（可插拔认证模块）。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=False）：
        - 有 PAM 配置行 → status = "pass", risk_level = "low"（配置存在即为合规）。
        - 无 PAM 配置行 → status = "fail", risk_level = "medium"（缺少 PAM 配置有风险）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/pam-config (分类: baseline)
    """
    cmd = "grep -v '^#' /etc/pam.d/common-auth /etc/pam.d/sshd 2>/dev/null | grep -v '^$'"
    return await _generic_detection(manager, "PAM 配置检查", cmd, items_are_issues=False)


async def detect_account_lockout(manager: SSHManager) -> GenericDetectionResult:
    """
    账号锁定策略检查 — 检查 PAM 是否配置了登录失败锁定机制（防暴力破解）。

    SSH 命令：
        grep -v '^#' /etc/pam.d/common-auth 2>/dev/null | grep -i 'pam_faillock\|pam_tally'
        在 PAM 认证配置中搜索 pam_faillock 或 pam_tally 模块（常见的账号锁定实现）。

    风险评估：
        - 有锁定策略配置 → status = "pass", risk_level = "low"。
        - 未配置锁定策略 → status = "fail", risk_level = "high"（无暴力破解防护）。
        注意：此函数不使用 _generic_detection 模板，而是自行构造结果以明确区分
        配置存在/缺失两种状态。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/account-lockout (分类: baseline)
    """
    cmd = "grep -v '^#' /etc/pam.d/common-auth 2>/dev/null | grep -i 'pam_faillock\\|pam_tally'"
    output = await manager.execute_command(cmd)
    items = [l.strip() for l in output.output.split("\n") if l.strip()]
    return GenericDetectionResult(
        title="账号锁定策略检查", status="pass" if items else "fail",
        items=[{"line": i} for i in items] if items else [{"line": "未配置账号锁定策略"}],
        risk_level="low" if items else "high", details="已配置" if items else "未配置账号锁定策略",
    )


async def detect_selinux_status(manager: SSHManager) -> GenericDetectionResult:
    """
    SELinux/AppArmor 状态检查 — 检查强制访问控制（MAC）安全模块是否启用。

    SSH 命令：
        getenforce 2>/dev/null || echo 'Not installed'
        优先调用 SELinux 的 getenforce 获取运行模式（Enforcing/Permissive/Disabled），
        若 SELinux 未安装则输出 "Not installed"。

    风险评估：
        - Enforcing（强制模式）→ status = "pass", risk_level = "low"。
        - 其他状态（Permissive/Disabled/Not installed）→ status = "fail", risk_level = "medium"。
        注意：Permissive 模式下 SELinux 只记录违规但不阻止，仍被视为不安全。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/selinux-status (分类: baseline)
    """
    cmd = "getenforce 2>/dev/null || echo 'Not installed'"
    output = await manager.execute_command(cmd)
    status_val = output.output.strip().lower()
    return GenericDetectionResult(
        title="SELinux/AppArmor 状态检查",
        status="pass" if "enforcing" in status_val else "fail",
        items=[{"status": status_val}],
        risk_level="low" if "enforcing" in status_val else "medium",
        details=f"SELinux状态: {status_val}",
    )


async def detect_kernel_params(manager: SSHManager) -> GenericDetectionResult:
    """
    内核参数检查 — 检查 Linux 内核中与安全相关的 sysctl 参数。

    SSH 命令：
        sysctl -a 2>/dev/null | grep -E '(net.ipv4.ip_forward|net.ipv4.conf.all.rp_filter|kernel.exec-shield)' | head -10
        检查三个关键安全内核参数：
        - net.ipv4.ip_forward    — IP 转发（应关闭，防止主机充当路由器）。
        - net.ipv4.conf.all.rp_filter — 反向路径过滤（应开启，防 IP 欺骗攻击）。
        - kernel.exec-shield     — 执行屏蔽/地址空间随机化（应开启）。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=False）：
        - 有内核参数输出 → status = "pass"（参数存在即可读取）。
        - 无输出         → status = "fail"（无法读取内核参数，可能没有安全配置）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/kernel-params (分类: baseline)
    """
    cmd = "sysctl -a 2>/dev/null | grep -E '(net.ipv4.ip_forward|net.ipv4.conf.all.rp_filter|kernel.exec-shield)' | head -10"
    return await _generic_detection(manager, "内核参数检查", cmd, items_are_issues=False)


async def detect_system_updates(manager: SSHManager) -> GenericDetectionResult:
    """
    系统补丁状态检查 — 检查是否有待安装的安全更新。

    SSH 命令：
        apt list --upgradable 2>/dev/null | head -20 || yum check-update 2>/dev/null | head -20
        优先使用 Debian/Ubuntu 的 apt list --upgradable，
        失败则回退到 RHEL/CentOS 的 yum check-update。
        均限制前 20 条避免输出过长。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - 有可更新包 → 每一项为一个"问题"（未打补丁），条目越多风险越高。
        - 无可更新包 → status = "pass", risk_level = "low"（系统已是最新）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/system-updates (分类: baseline)
    """
    cmd = "apt list --upgradable 2>/dev/null | head -20 || yum check-update 2>/dev/null | head -20"
    return await _generic_detection(manager, "系统补丁状态检查", cmd)


async def detect_unnecessary_services(manager: SSHManager) -> GenericDetectionResult:
    """
    不必要服务检查 — 列出当前正在运行的所有 systemd 服务，检查是否有不必要的暴露面。

    SSH 命令：
        systemctl list-units --type=service --state=running 2>/dev/null | head -30
        只列出 type=service 且 state=running 的服务单元，限制前 30 条。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=False）：
        - 有运行服务列表 → status = "pass"（可供审计人员审视是否有不必要服务）。
        - 无法列出服务 → status = "fail"（探测失败或 systemd 不可用）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/unnecessary-services (分类: baseline)
    """
    cmd = "systemctl list-units --type=service --state=running 2>/dev/null | head -30"
    return await _generic_detection(manager, "不必要服务检查", cmd, items_are_issues=False)


async def detect_auto_start_services(manager: SSHManager) -> GenericDetectionResult:
    """
    自启动服务审计 — 列出所有启用自启动（enabled）的 systemd 服务单元。

    SSH 命令：
        systemctl list-unit-files --state=enabled 2>/dev/null | head -30
        只列出状态为 enabled 的服务单元文件，限制前 30 条。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=False）：
        - 有自启动服务列表 → status = "pass"（可审查是否有恶意自启动服务）。
        - 无法列出        → status = "fail"。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/auto-start-services (分类: baseline)
    """
    cmd = "systemctl list-unit-files --state=enabled 2>/dev/null | head -30"
    return await _generic_detection(manager, "自启动服务审计", cmd, items_are_issues=False)


async def detect_audit_config(manager: SSHManager) -> GenericDetectionResult:
    """
    审计配置检查 — 检查 auditd 审计守护进程的运行状态及当前审计规则。

    SSH 命令：
        systemctl is-active auditd 2>/dev/null && auditctl -l 2>/dev/null | head -10 || echo 'auditd not running'
        1. 先检查 auditd 服务是否 active（活跃）。
        2. 如果 active，列出前 10 条审计规则。
        3. 如果未运行，输出 "auditd not running"。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - auditd 未运行 → "auditd not running" 被视为 1 个问题项。
        - 有审计规则输出 → 被视为发现项（不影响 status）。
        注意：默认的 items_are_issues=True 意味着每条输出行都算"问题"，
        此处虽逻辑有些模糊，但核心目的是确保 auditd 处于运行状态。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/audit-config (分类: baseline)
    """
    cmd = "systemctl is-active auditd 2>/dev/null && auditctl -l 2>/dev/null | head -10 || echo 'auditd not running'"
    return await _generic_detection(manager, "审计配置检查", cmd)


async def detect_history_audit(manager: SSHManager) -> GenericDetectionResult:
    """
    历史命令审计 — 检查当前用户最近执行的 shell 命令历史。

    SSH 命令：
        cat ~/.bash_history 2>/dev/null | tail -20
        读取 Bash 历史文件中最近 20 条命令（可能包含敏感操作记录）。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - 每条历史命令都被视为一个"问题"条目（敏感操作记录）。
        - 历史命令数量 > 5 → risk_level = "high"（可能存在大量可疑操作）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/history-audit (分类: baseline)
    """
    cmd = "cat ~/.bash_history 2>/dev/null | tail -20"
    return await _generic_detection(manager, "历史命令审计", cmd)


async def detect_ntp_config(manager: SSHManager) -> GenericDetectionResult:
    """
    NTP 配置检查 — 检查系统时间同步服务的配置状态。

    SSH 命令：
        timedatectl 2>/dev/null || ntpq -p 2>/dev/null | head -5
        优先使用 systemd 的 timedatectl 获取时间同步信息（含 NTP 启用状态），
        不支持则回退到传统 ntpq -p 查看 NTP 对等节点（取前 5 行）。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=False）：
        - 有 NTP 配置信息 → status = "pass"（时间同步服务可工作）。
        - 无输出          → status = "fail", risk_level = "medium"（时间不同步影响日志审计精度）。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/ntp-config (分类: baseline)
    """
    cmd = "timedatectl 2>/dev/null || ntpq -p 2>/dev/null | head -5"
    return await _generic_detection(manager, "NTP 配置检查", cmd, items_are_issues=False)


async def detect_dns_config(manager: SSHManager) -> GenericDetectionResult:
    """
    DNS 配置检查 — 检查系统的 DNS 解析器配置。

    SSH 命令：
        cat /etc/resolv.conf 2>/dev/null
        读取 DNS 配置文件，检查 nameserver 指向是否安全可信。

    风险评估：
        使用 _generic_detection 模板（items_are_issues=True）：
        - 每行 DNS 配置都被视为一个检查项。
        - 如果配置了不受信任的 DNS 服务器或条目过多，risk_level 会相应升高。

    Pydantic 返回类型：GenericDetectionResult
    API 端点：POST /detect/dns-config (分类: baseline)
    """
    cmd = "cat /etc/resolv.conf 2>/dev/null"
    return await _generic_detection(manager, "DNS 配置检查", cmd)
