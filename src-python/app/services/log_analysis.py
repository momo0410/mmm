# ================================================================================
# 远程日志分析子系统 (Log Analysis Subsystem)
# ================================================================================
#
# 文件: app/services/log_analysis.py
# 从 Rust log_analysis.rs 迁移到 Python。
#
# ================================================================================
# 子系统整体架构
# ================================================================================
#
# 本模块是 LovelyRes 的**远程日志分析引擎**，负责通过 SSH 连接读取远程主机上的
# 系统日志文件和 systemd journald 日志，并进行结构化解析、关键词高亮和分页处理。
#
# 在整个后端架构中的位置：
#
#   ┌────────────────────────────────────────────────────────────┐
#   │  app/routers/api.py  (FastAPI 路由层)                      │
#   │  对外暴露 4 个日志相关 API 端点                            │
#   │  POST /api/v1/log/read-system      读取系统日志文件        │
#   │  POST /api/v1/log/read-journalctl  读取 journalctl 日志    │
#   │  GET  /api/v1/log/list-files       列出服务器日志文件      │
#   │  POST /api/v1/log/file-info        获取日志文件元数据      │
#   └──────────────┬─────────────────────────────────────────────┘
#                  │ 导入调用
#   ┌──────────────▼─────────────────────────────────────────────┐
#   │  app/services/log_analysis.py  (本文件 — 日志分析引擎)     │
#   │  ┌───────────────────────────────────────────────────────┐ │
#   │  │ 公开 API 函数（被路由层调用）                         │ │
#   │  │  · read_system_log()       系统日志文件读取           │ │
#   │  │  · read_journalctl_log()   journalctl 日志读取        │ │
#   │  │  · list_log_files()        日志文件列表扫描           │ │
#   │  │  · get_log_file_info()     日志文件元数据查询         │ │
#   │  ├───────────────────────────────────────────────────────┤ │
#   │  │ 命令生成函数（组装 SSH 命令字符串）                   │ │
#   │  │  · _generate_log_read_command()      日志文件读取命令 │ │
#   │  │  · _generate_journalctl_command()     journalctl 命令 │ │
#   │  │  · _generate_list_log_files_command() 文件列表扫描命令│ │
#   │  │  · _generate_log_file_info_command()  文件信息查询命令│ │
#   │  ├───────────────────────────────────────────────────────┤ │
#   │  │ 日志解析函数（将原始文本转为结构化数据）              │ │
#   │  │  · _parse_log_line()           解析普通日志行         │ │
#   │  │  · _parse_journalctl_json_line() 解析 journalctl JSON │ │
#   │  ├───────────────────────────────────────────────────────┤ │
#   │  │ 辅助函数                                                │ │
#   │  │  · _build_date_grep_pattern()   日期过滤器构建         │ │
#   │  │  · _paginate_and_return()      内存中分页              │ │
#   │  └───────────────────────────────────────────────────────┘ │
#   └──────────────┬─────────────────────────────────────────────┘
#                  │ 依赖
#   ┌──────────────▼─────────────────────────────────────────────┐
#   │  app/services/ssh_manager.py  (SSH 连接管理)               │
#   │  · manager.is_connected()     检查连接状态                 │
#   │  · manager.execute_command()  执行远程命令并返回输出       │
#   └──────────────┬─────────────────────────────────────────────┘
#                  │ 依赖
#   ┌──────────────▼─────────────────────────────────────────────┐
#   │  app/models/types.py  (数据契约层)                         │
#   │  · LogAnalysisEntry    单条日志的结构化表示                │
#   │  · LogAnalysisOutput   一次日志分析的完整输出              │
#   │  · LogFileInfo         日志文件的元数据描述                │
#   └────────────────────────────────────────────────────────────┘
#
# ================================================================================
# 数据流总览
# ================================================================================
#
#   前端请求 (HTTP)
#       │
#       ▼
#   FastAPI 路由 (api.py)
#       │ 调用 log_analysis.xxx()
#       ▼
#   本模块公开函数 (read_system_log / read_journalctl_log / ...)
#       │ 1. 调用 _generate_xxx_command() 拼接 SSH 命令字符串
#       │ 2. 调用 ssh_manager.execute_command(cmd) 远程执行
#       │ 3. 调用 _parse_xxx() 解析原始输出为 LogAnalysisEntry 列表
#       │ 4. 调用 _paginate_and_return() 进行内存分页
#       │ 5. 返回 LogAnalysisOutput 给路由层
#       ▼
#   路由层将结果序列化为 JSON 返回前端
#
# ================================================================================
# 支持两种日志来源
# ================================================================================
#
# 1. 传统日志文件 (Plain Log Files)
#    路径示例: /var/log/auth.log, /var/log/syslog, /var/log/kern.log 等
#    读取方式: cat + grep + tail/head 组合管道命令
#    解析方式: _parse_log_line() — 正则提取 syslog 优先级和时间戳
#    过滤方式: grep -E (日期正则) + grep -i (关键词)
#
# 2. systemd Journal (systemd-journald 二进制日志)
#    读取方式: journalctl -o json (输出 JSON 格式)
#    解析方式: 4 层回退式 JSON 解析 (见下方详细说明)
#    过滤方式: journalctl 内置 --since/--until/--grep 参数
#
# ================================================================================
# 依赖链详解
# ================================================================================
#
# 上游 (谁调用本模块):
#   · app.routers.api
#       - POST /api/v1/log/read-system      → read_system_log()
#       - POST /api/v1/log/read-journalctl   → read_journalctl_log()
#       - GET  /api/v1/log/list-files        → list_log_files()
#       - POST /api/v1/log/file-info         → get_log_file_info()
#
# 下游 (本模块依赖谁):
#   · app.models.types
#       - LogAnalysisEntry  — 单条日志条目 (line, level, highlighted, timestamp)
#       - LogAnalysisOutput — 日志分析结果 (total_count, highlighted_count, entries)
#       - LogFileInfo       — 日志文件信息 (path, name, size, modified, readable)
#   · app.services.ssh_manager
#       - SSHManager.is_connected()           — 检查 SSH 连接是否活跃
#       - SSHManager.execute_command(cmd)     — 通过 SSH 执行远程命令，返回 TerminalOutput
#   · json (Python 标准库) — JSON 解析
#   · re  (Python 标准库) — 正则表达式
#   · typing (Python 标准库) — 类型标注
#
# ================================================================================

"""日志分析模块 - 从 Rust log_analysis.rs 迁移"""

import json
import re
from typing import Any, Dict, List, Optional

from app.models.types import LogAnalysisEntry, LogAnalysisOutput, LogFileInfo
from app.services.ssh_manager import SSHManager


# ================================================================================
# 风险关键词匹配系统 (Risk/Highlight Keyword Matching)
# ================================================================================
#
# HIGHLIGHT_KEYWORDS 列表定义了需要在前端高亮标红的风险关键词。
# 当一条日志行的内容（转为小写后）包含列表中的任意一个关键词时，
# 该日志条目的 highlighted 字段将被置为 True，前端据此以醒目的红色/橙色显示该行。
#
# 关键词选择原则：
#   · 安全事件类: breach, attack, intrusion, exploit, malware, vulnerability
#     对应入侵迹象和漏洞利用，一旦出现可能需要应急响应。
#   · 认证失败类: denied, refused, unauthorized
#     常用于检测暴力破解、越权访问等攻击行为。
#   · 系统故障类: error, fail, critical, alert, emergency, warning
#     对应系统日志中的标准严重级别，涵盖从警告到紧急的所有异常状态。
#
# 匹配方式: 大小写不敏感 (通过 line.lower() 与 keyword 做子串判断)。
# 例如日志行 "Mar 15 10:23:45 server sshd[1234]: Failed password for root"
# 因包含 "fail" (Failed) 和 "error" (无) 会被高亮。
#
# 维护提示: 如需增加新关键词，直接在列表末尾追加即可，
# 所有使用 HIGHLIGHT_KEYWORDS 的地方会自动生效。

HIGHLIGHT_KEYWORDS = [
    "error", "fail", "denied", "refused", "invalid", "unauthorized",
    "critical", "alert", "emergency", "warning", "attack", "breach",
    "malware", "intrusion", "exploit", "vulnerability",
]

# ================================================================================
# Journalctl PRIORITY 数字到级别的映射表
# ================================================================================
#
# systemd journal 使用 syslog 兼容的优先级数字 (0-7)，定义在 RFC 5424 中。
# journalctl -o json 输出的 JSON 对象中，PRIORITY 字段为字符串形式的数字。
# 本映射表将数字转换为前端统一的日志级别字符串：
#
#   systemd 优先级       数字  映射级别    含义
#   ─────────────────    ──    ────────   ──────────────────────
#   LOG_EMERG            0     "error"    系统不可用
#   LOG_ALERT            1     "error"    必须立即采取措施
#   LOG_CRIT             2     "error"    临界条件
#   LOG_ERR              3     "error"    错误条件
#   LOG_WARNING          4     "warning"  警告条件
#   LOG_NOTICE           5     "info"     正常但重要的事件
#   LOG_INFO             6     "info"     信息性消息
#   LOG_DEBUG            7     "info"     调试级别消息
#
# 注意: 优先级 0-3 (紧急到错误) 统一映射为 "error" 级别，
# 优先级 4 映射为 "warning"，优先级 5-7 (通知到调试) 映射为 "info"。
# 这样使日志在前端呈现为 error/warning/info 三个级别，简洁直观。

JOURNALCTL_PRIORITY_MAP = {
    "0": "error",       # emerg — 系统不可用，最严重
    "1": "error",       # alert — 必须立即响应
    "2": "error",       # crit  — 临界条件
    "3": "error",       # err   — 一般错误
    "4": "warning",     # warning — 警告
    "5": "info",        # notice — 通知（重要但非异常）
    "6": "info",        # info  — 信息
    "7": "info",        # debug — 调试（前端不区分 debug 与 info)
}

# ================================================================================
# 常见日志文件映射表 (Common Log Files Registry)
# ================================================================================
#
# 此字典维护了一份远程主机上常见日志文件的标准路径及其中文描述。
# 用于两个场景：
#   1. list_log_files() 中：当 SSH 的 find/stat 命令未能扫描到某些常见日志时
#      （例如文件权限不足、目录结构特殊），这些文件会作为**后备选项**
#      追加到返回列表中，但 readable 字段标记为 False 表示需要验证。
#   2. 前端展示时：通过中文描述让用户快速理解每个日志文件的用途。
#
# 支持的服务:
#   · 系统级: auth.log, syslog, kern.log, dmesg, secure, messages
#   · Web 服务: nginx, apache2
#   · 数据库: mysql, postgresql
#
# 维护提示: 如需支持新服务的日志路径，在此字典中添加条目即可，
# 无需修改其他代码。路径必须是标准 Linux 系统上的常见位置。

COMMON_LOG_FILES: Dict[str, str] = {
    "/var/log/auth.log": "认证日志",
    "/var/log/syslog": "系统日志",
    "/var/log/kern.log": "内核日志",
    "/var/log/dmesg": "启动日志",
    "/var/log/secure": "安全日志",
    "/var/log/messages": "消息日志",
    "/var/log/nginx/access.log": "Nginx访问日志",
    "/var/log/nginx/error.log": "Nginx错误日志",
    "/var/log/apache2/access.log": "Apache访问日志",
    "/var/log/apache2/error.log": "Apache错误日志",
    "/var/log/mysql/error.log": "MySQL错误日志",
    "/var/log/postgresql/postgresql.log": "PostgreSQL日志",
}


# ================================================================================
# _parse_journalctl_json_line(line) — 解析 journalctl JSON 单行
# ================================================================================
#
# 将 journalctl -o json 输出的单行 JSON 字符串解析为 LogAnalysisEntry 结构体。
#
# 被调用方: read_journalctl_log() 中的 4 种 JSON 解析方法均会调用本函数
#           对每个解析出的 JSON 对象做最终字段提取。
#
# 解析逻辑:
#   1. 预处理: 移除 json-seq 格式的 \x1e (Record Separator) 前缀字符。
#      如果 sed 管道未能处理该字符，这里做兜底清理。
#   2. JSON 反序列化: 将字符串解析为 Python dict。
#      如果解析失败 (非 JSON 或格式损坏)，返回 None。
#   3. 字段提取:
#       - MESSAGE:  日志正文 (核心内容)
#       - PRIORITY: systemd 优先级数字，默认 "6" (info)
#       - __REALTIME_TIMESTAMP 或 _SOURCE_REALTIME_TIMESTAMP: 日志时间戳
#   4. 级别映射: 通过 JOURNALCTL_PRIORITY_MAP 将数字优先级转为级别字符串。
#   5. 高亮检测: 将 MESSAGE 转为小写后，与 HIGHLIGHT_KEYWORDS 交叉匹配。
#
# 参数:
#   line: journalctl 输出的单行字符串，应为 JSON 格式
#
# 返回:
#   解析成功返回 LogAnalysisEntry，失败返回 None

def _parse_journalctl_json_line(line: str) -> Optional[LogAnalysisEntry]:
    """解析 journalctl JSON 格式输出，提取正确的 PRIORITY"""

    # 移除 json-seq 的 \x1e 分隔符（如果 sed 未能处理）
    if line.startswith('\x1e'):
        line = line[1:]

    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    # 提取日志消息正文
    message = data.get("MESSAGE", "")
    # 提取 systemd 优先级数字，默认 "6" (info)
    priority = data.get("PRIORITY", "6")
    # 提取时间戳：优先使用高精度实时时间戳，回退到源时间戳
    timestamp = data.get("__REALTIME_TIMESTAMP", "") or data.get("_SOURCE_REALTIME_TIMESTAMP", "")

    # 将数字优先级 (如 "3") 映射为级别字符串 (如 "error")
    level = JOURNALCTL_PRIORITY_MAP.get(str(priority), "info")

    # 关键词高亮检测：消息正文转为小写后逐一匹配 HIGHLIGHT_KEYWORDS
    line_lower = message.lower()
    highlighted = any(kw in line_lower for kw in HIGHLIGHT_KEYWORDS)

    return LogAnalysisEntry(line=message, level=level, highlighted=highlighted, timestamp=timestamp)


# ================================================================================
# _parse_log_line(line) — 解析普通日志文件行
# ================================================================================
#
# 将传统日志文件 (如 /var/log/auth.log, /var/log/syslog) 的文本行
# 解析为 LogAnalysisEntry 结构体。与 _parse_journalctl_json_line 不同，
# 本函数处理的是纯文本格式的 syslog 风格日志。
#
# 被调用方: read_system_log() — 对 grep/head/tail 管道输出的每一行调用本函数。
#
# 解析逻辑分三步:
#
# 第一步: 关键词高亮检测
#   将整行转为小写后，检查是否包含 HIGHLIGHT_KEYWORDS 中的任一关键词。
#   此检测对所有日志行执行，不依赖后续的级别解析结果。
#
# 第二步: 日志级别识别 (两种回退策略)
#   策略 A — syslog 优先级标记 <N>:
#     检查行首是否有 <数字> 格式的优先级标记 (如 "<3>Failed password")。
#     这是 RFC 5424 定义的 syslog 优先级格式。数字由 Facility * 8 + Severity 组成，
#     其中低 3 位 (数字 & 0x07) 为严重级别，映射到 JOURNALCTL_PRIORITY_MAP。
#   策略 B — 关键词回退 (当行首没有 <N> 标记时):
#     检查整行 (小写) 是否包含 "error/critical/emergency/alert" → level = "error"
#     检查整行 (小写) 是否包含 "warning/warn" → level = "warning"
#     都不匹配则保持默认 level = "info"
#
# 第三步: 时间戳提取 (两种格式)
#   Syslog 格式: "Mon DD HH:MM:SS" (如 "Mar 15 10:23:45")
#     · 正则: ^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})
#     · 3 字母月份 + 1-2 位日期 + 时间 (时:分:秒)
#   ISO 格式:   "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DDTHH:MM:SS"
#     · 正则: ^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})
#     · 标准 ISO 8601 日期时间
#   以上两种格式均从行首开始匹配 (^ 锚定)。
#
# 参数:
#   line: 原始日志文件中的一行文本
#
# 返回:
#   LogAnalysisEntry 实例，即使无法提取级别和时间戳也会返回带默认值的结构

def _parse_log_line(line: str) -> LogAnalysisEntry:
    """解析日志行（用于文件日志，优先解析 syslog 优先级）"""

    # 第一步: 关键词高亮检测 (大小写不敏感)
    line_lower = line.lower()
    highlighted = any(kw in line_lower for kw in HIGHLIGHT_KEYWORDS)

    # 第二步: 尝试提取 syslog 优先级标记 <N>
    # 格式: <数字> 后跟日志内容，数字由 Facility*8 + Severity 组成
    level = "info"
    priority_match = re.match(r'^<(\d+)>', line)
    if priority_match:
        # 提取优先级数字
        priority_num = int(priority_match.group(1))
        # 取低 3 位作为 severity (0=emerg, 7=debug)
        severity = priority_num & 0x07
        level = JOURNALCTL_PRIORITY_MAP.get(str(severity), "info")
    else:
        # 策略 B: 关键词回退匹配
        if any(kw in line_lower for kw in ["error", "critical", "emergency", "alert"]):
            level = "error"
        elif any(kw in line_lower for kw in ["warning", "warn"]):
            level = "warning"

    # 第三步: 尝试提取时间戳
    timestamp = None
    # 尝试匹配 Syslog 格式: Mon DD HH:MM:SS (如 "Mar 15 10:23:45")
    ts_match = re.match(r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', line)
    if ts_match:
        timestamp = ts_match.group(1)
    else:
        # 尝试匹配 ISO 格式: YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS
        ts_match = re.match(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', line)
        if ts_match:
            timestamp = ts_match.group(1)

    return LogAnalysisEntry(line=line, level=level, highlighted=highlighted, timestamp=timestamp)


# ================================================================================
# MONTH_MAP — 数字月份到英文缩写的映射表
# ================================================================================
# 用于 _build_date_grep_pattern() 将 ISO 格式的 "2026-04-22" 中的 "04"
# 转换为 syslog 格式的 "Apr"，以便同时匹配两种日期表示。

MONTH_MAP = {
    '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
    '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
    '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
}


# ================================================================================
# _build_date_grep_pattern(date_filter) — 构建日期 grep 正则模式
# ================================================================================
#
# 将前端传来的 ISO 日期字符串 (如 "2026-04-22") 转换为一个 grep -E 正则表达式，
# 使其能同时匹配日志文件中两种最常见的日期格式：
#
# 1. ISO 格式: "2026-04-22"
#    常见于 journal 输出、自定义应用日志等使用标准格式的场景。
#    模式: 2026-04-22
#
# 2. Syslog 格式 (双空格): "Apr  22"
#    常见于 auth.log、syslog、messages 等标准 syslog 文件。
#    当日期为 1-9 号时，syslog 会在月份和日期之间填充两个空格 (对齐用)。
#    模式: {月份英文缩写}  {日期数字}
#    例如 "Apr  5" (4月5日，两个空格)
#
# 3. Syslog 格式 (单空格): "Apr 22"
#    当日期为 10-31 号时，日期占两位，月份和日期之间只有一个空格。
#    模式: {月份英文缩写} {日期(补零两位数)}
#    例如 "Apr 22" (4月22日，一个空格)
#
# 构建结果示例:
#   输入: "2026-04-22"
#   输出: "(2026-04-22|Apr 22|Apr  22)"
#   — 此正则可以同时匹配 "2026-04-22"、ISO 格式、
#     "Apr 22" (单空格) 和 "Apr  22" (双空格，用于 1-9 日) 三种格式。
#
# 构建结果示例 (1-9号日期):
#   输入: "2026-04-05"
#   输出: "(2026-04-05|Apr 05|Apr  5)"
#   — 双空格匹配 "Apr  5"，单空格匹配补零的 "Apr 05"。
#
# 被调用方: _generate_log_read_command() — 在组装 cat/grep/tail 管道命令时调用。
#
# 边界情况处理:
#   · date_filter 为 None 或长度不足 10 (非标准日期) → 原样返回，不做转换
#   · 月份不在 MONTH_MAP 中 → 原样返回
#   · 日期解析异常 (ValueError, IndexError) → 原样返回
#
# 参数:
#   date_filter: 前端传来的日期字符串，期望格式为 "YYYY-MM-DD"
#
# 返回:
#   包含多种日期格式匹配的 grep 正则表达式字符串

def _build_date_grep_pattern(date_filter: str) -> str:
    """构建支持多种日志格式的日期grep模式

    支持:
    - ISO格式: 2026-04-22 (适用于journal、自定义日志)
    - Syslog格式: Apr 22 或 Apr  22 (适用于auth.log, syslog等)
    """
    if not date_filter or len(date_filter) < 10:
        return date_filter

    try:
        # 解析 YYYY-MM-DD 格式
        parts = date_filter.split('-')
        if len(parts) == 3:
            year, month, day = parts
            # 将数字月份 (如 "04") 转换为英文缩写 (如 "Apr")
            month_name = MONTH_MAP.get(month, '')

            # 构建同时匹配多种格式的正则表达式
            # 1. ISO格式: 保留原始的 "2026-04-22"
            # 2. Syslog片段: 双空格 "Apr  22" (1-9号对齐用)
            # 3. Syslog片段: 单空格 "Apr 22" (10-31号用补零格式)
            if month_name:
                # 将日期字符串转为整数（去除前导零，如 "05" → 5）
                day_int = int(day)
                # 兼容单数字和双数字日期 (Apr 5 或 Apr 05 或 Apr  5)
                pattern = f"({year}-{month}-{day}|{month_name} {day}|{month_name}  {day_int})"
                return pattern
    except (ValueError, IndexError):
        pass

    return date_filter


# ================================================================================
# _generate_log_read_command(log_path, page, page_size, filter_text, date_filter)
# — 生成传统日志文件的 SSH 读取命令
# ================================================================================
#
# 组装一个由 cat → grep (日期过滤) → grep (关键词过滤) → tail (跳过)
# → head (取行) 组成的管道命令。管道中的每一步都是可选的，顺序经过精心设计
# 以确保分页正确性。
#
# 被调用方: read_system_log()  — 生成命令后通过 SSH 执行。
#
# 命令组装逻辑 (管道顺序):
#
#   cat '/var/log/auth.log' 2>/dev/null
#     │  读取原始日志文件，2>/dev/null 抑制文件不存在时的错误输出
#     │
#     ▼  [如果指定了 date_filter]
#   grep -E '(2026-04-22|Apr 22|Apr  22)'
#     │  用正则表达式 (由 _build_date_grep_pattern 构建) 过滤特定日期的行
#     │  此步骤在关键词过滤之前执行，减少后续 grep 的输入量
#     │
#     ▼  [如果指定了 filter_text]
#   grep -i 'failed password'
#     │  大小写不敏感地过滤包含特定关键词的行
#     │  -i 标志确保 "Failed" 和 "failed" 都能匹配
#     │
#     ▼  [分页 — 始终执行]
#   tail -n +{start+1}
#     │  跳过前 (page-1)*page_size 行，实现分页的起始偏移
#     │  tail -n +N 表示从第 N 行开始输出 (第 1 行的页 +1 即 tail -n +1 输出全部)
#     │
#     ▼
#   head -n {page_size}
#     取前 page_size 行，实现分页的每页大小限制
#
# 分页公式: start = (page - 1) * page_size
#   例: page=1, page_size=100 → tail -n +1 | head -n 100 (取 1~100 行)
#   例: page=2, page_size=100 → tail -n +101 | head -n 100 (取 101~200 行)
#
# 参数:
#   log_path:   日志文件完整路径 (如 "/var/log/auth.log")
#   page:       页码 (从 1 开始)
#   page_size:  每页行数
#   filter_text: 可选的关键词过滤
#   date_filter: 可选的日期过滤 ("YYYY-MM-DD")
#
# 返回:
#   完整的 SSH 管道命令字符串

def _generate_log_read_command(
    log_path: str, page: int = 1, page_size: int = 100,
    filter_text: Optional[str] = None, date_filter: Optional[str] = None,
) -> str:
    """生成读取日志的命令"""

    # 基础 cat 命令，2>/dev/null 抑制文件不存在的错误信息
    cmd = f"cat '{log_path}' 2>/dev/null"

    # 日期过滤: 通过正则表达式匹配特定日期的日志行
    if date_filter:
        grep_pattern = _build_date_grep_pattern(date_filter)
        cmd = f"grep -E '{grep_pattern}' {cmd}"

    # 关键词过滤: 大小写不敏感地匹配用户输入的搜索文本
    if filter_text:
        cmd = f"grep -i '{filter_text}' {cmd}"

    # 分页: tail 跳过前 (page-1)*page_size 行，head 取当前页
    start = (page - 1) * page_size
    cmd = f"{cmd} | tail -n +{start + 1} | head -n {page_size}"

    return cmd


# ================================================================================
# _generate_journalctl_command(page, page_size, unit, filter_text, since, until)
# — 生成 journalctl JSON 输出命令
# ================================================================================
#
# 组装 journalctl 命令，使用 -o json 格式输出，利用 journalctl 内置的
# 过滤参数 (--since, --until, --grep, -u) 进行服务器端过滤。
#
# 被调用方: read_journalctl_log() — 生成命令后通过 SSH 执行。
#
# 命令参数说明:
#   journalctl --no-pager     禁止分页器 (默认会调用 less)，确保输出直接到 stdout
#              -o json        输出 JSON 格式，每行一个 JSON 对象
#              -n {max_lines}  限制输出总行数为 page * page_size
#                              (例如 page=2, page_size=100 → -n 200)
#                              这样确保 SSH 不会因输出过多而超时
#              -u {unit}      按 systemd 服务单元过滤 (如 "nginx.service", "sshd.service")
#              --since '{..}' 起始时间过滤 (如 "2026-04-22 00:00:00")
#              --until '{..}' 结束时间过滤
#              --grep '{..}'  journalctl 内置的关键词过滤 (比管道 grep 更高效)
#
# 分页策略: 区别于传统日志文件的 tail/head 管道分页，
# 本命令将 page * page_size 条日志全部返回，分页在 Python 端
# (_paginate_and_return) 的**内存中**完成。这样做是因为:
#   1. journalctl 输出的 JSON 对象可能是多行的，无法用简单的行号做 tail/head
#   2. JSON 解析本身就要求完整的 JSON 对象，被截断会导致解析失败
#   3. 通过 -n 限制总行数保证了 SSH 传输量可控
#
# 参数:
#   page:        页码 (从 1 开始)
#   page_size:   每页条数
#   unit:        可选的 systemd 服务单元名
#   filter_text: 可选的关键词过滤 (传递给 journalctl --grep)
#   since:       可选起始时间 ("YYYY-MM-DD HH:MM:SS")
#   until:       可选结束时间 ("YYYY-MM-DD HH:MM:SS")
#
# 返回:
#   完整的 journalctl 命令字符串

def _generate_journalctl_command(
    page: int = 1, page_size: int = 100,
    unit: Optional[str] = None, filter_text: Optional[str] = None,
    since: Optional[str] = None, until: Optional[str] = None,
) -> str:
    """生成 journalctl 命令，使用 json 输出格式，通过 -n 限制条数，分页在 Python 中处理"""

    # 核心参数: --no-pager 禁止分页器, -o json 输出 JSON 格式
    cmd_parts = ["journalctl --no-pager -o json"]

    # 限制最大读取条数为 page * page_size，防止 SSH 超时
    # 例如: page=2, page_size=100 → max_lines=200, 即 -n 200
    max_lines = page * page_size
    cmd_parts.append(f"-n {max_lines}")

    # 可选过滤参数
    if unit:
        cmd_parts.append(f"-u {unit}")
    if since:
        cmd_parts.append(f"--since '{since}'")
    if until:
        cmd_parts.append(f"--until '{until}'")
    if filter_text:
        cmd_parts.append(f"--grep '{filter_text}'")

    cmd = " ".join(cmd_parts)
    return cmd


# ================================================================================
# _generate_list_log_files_command() — 生成日志文件列表扫描命令
# ================================================================================
#
# 组装一个由 find → head → xargs → stat 组成的管道命令，
# 用于扫描远程主机 /var/log 目录下可读取的日志文件及其元数据。
#
# 被调用方: list_log_files() — 生成命令后通过 SSH 执行。
#
# 命令各部分说明:
#
#   1. find /var/log -maxdepth 2 -type f -readable
#      扫描 /var/log 目录 (最大深度 2 层) 下所有可读的常规文件。
#      -maxdepth 2: 防止深度递归导致扫描过多文件
#      -type f:     仅匹配常规文件 (排除目录、设备文件等)
#      -readable:   仅匹配当前用户有读权限的文件 (避免无权限报错)
#
#   2. 文件名匹配模式 (通过 -name 组合):
#      · '*.log'  '*.log.*'  — 标准日志文件及轮转日志
#      · 'messages' 'secure' 'auth.log' 'syslog' 'kern.log' 'dmesg'
#        — 常见系统日志文件 (无 .log 后缀)
#      · 'Xorg.*' 'boot.log' 'cron' 'faillog' 'maillog' 'spooler'
#        — 其他常见守护进程日志
#
#   3. 排除模式 (通过 ! -name 排除):
#      · lastlog  — 二进制用户最后登录记录，不可文本解析
#      · btmp     — 二进制失败登录记录 (/var/log/btmp)
#      · wtmp     — 二进制登录历史记录 (/var/log/wtmp)
#      · utmp     — 二进制当前登录用户记录 (/var/run/utmp)
#      · *.gz *.xz *.bz2 *.zst  — 压缩归档日志 (节省传输，如需分析请解压)
#
#   4. head -100
#      限制最多返回 100 个文件，防止输出过多导致 SSH 超时。
#
#   5. xargs -d '\n' stat -c '%s|%n|%Y'
#      对每个找到的文件执行 stat -c 获取元数据:
#      · %s — 文件大小 (字节)
#      · %n — 文件完整路径
#      · %Y — 最后修改时间 (Unix 时间戳，秒)
#      输出格式: 大小|路径|修改时间 (如 "12345|/var/log/auth.log|1713456789")
#      使用 xargs 替代 while read 循环，单次命令即可完成全部操作，效率更高。
#
# 返回:
#   完整的 SSH 管道命令字符串

def _generate_list_log_files_command() -> str:
    """生成列出日志文件的命令"""

    # 用 xargs 替代 while 循环，提升执行速度，避免 SSH 超时
    # -readable 确保只列出可读文件
    # 排除二进制文件（lastlog, btmp, wtmp, utmp 等）
    find_expr = (
        "/var/log -maxdepth 2 -type f -readable "
        "\\( -name '*.log' -o -name '*.log.*' -o -name 'messages' -o -name 'secure' "
        "-o -name 'auth.log' -o -name 'syslog' -o -name 'kern.log' -o -name 'dmesg' "
        "-o -name 'Xorg.*' -o -name 'boot.log' -o -name 'cron' -o -name 'faillog' "
        "-o -name 'maillog' -o -name 'spooler' \\) "
        "! -name 'lastlog' ! -name 'btmp' ! -name 'wtmp' ! -name 'utmp' "
        "! -name '*.gz' ! -name '*.xz' ! -name '*.bz2' ! -name '*.zst'"
    )
    return (
        f"find {find_expr} 2>/dev/null | "
        "head -100 | "
        "xargs -d '\n' stat -c '%s|%n|%Y' 2>/dev/null"
    )


# ================================================================================
# _generate_log_file_info_command(log_path) — 生成日志文件元数据查询命令
# ================================================================================
#
# 组装 stat 命令获取单个日志文件的元数据，如果文件不可读则返回 readable:no。
#
# 被调用方: get_log_file_info() — 生成命令后通过 SSH 执行。
#
# 命令逻辑:
#   stat -c 'size:%s|modified:%Y' '/var/log/auth.log' 2>/dev/null
#     · size:%s    — 文件大小 (字节)，如 "size:123456"
#     · modified:%Y — 最后修改时间 (Unix 时间戳)，如 "modified:1713456789"
#   || echo 'readable:no'
#     · 如果 stat 命令失败 (文件不存在或无权限)，输出 "readable:no"
#     · || 为 shell 短路操作符，当前一条命令失败 (退出码非 0) 时执行
#
# 参数:
#   log_path: 日志文件完整路径
#
# 返回:
#   完整的 SSH 命令字符串，格式如:
#     stat -c 'size:%s|modified:%Y' '/var/log/auth.log' 2>/dev/null || echo 'readable:no'

def _generate_log_file_info_command(log_path: str) -> str:
    """生成获取日志文件信息的命令"""
    return f"stat -c 'size:%s|modified:%Y' '{log_path}' 2>/dev/null || echo 'readable:no'"


# ================================================================================
# read_system_log(manager, log_path, page, page_size, filter_text, date_filter)
# — 读取远程系统日志文件 (公开 API)
# ================================================================================
#
# 通过 SSH 读取远程主机上指定路径的日志文件，支持关键词过滤、日期过滤和分页。
#
# 被调用方:
#   app.routers.api → POST /api/v1/log/read-system
#     前端使用场景: 日志分析页面的 "系统日志" 标签页。
#     请求体: { log_path, page, page_size, filter, date_filter }
#
# 处理流程:
#   1. 检查 SSH 连接状态，未连接则抛出 ConnectionError
#   2. 调用 _generate_log_read_command() 组装 cat/grep/tail/head 管道命令
#   3. 通过 SSH 执行命令，获取原始文本输出
#   4. 按换行符分割输出，逐行调用 _parse_log_line() 解析
#   5. 跳过空行和错误提示行 (如 "Log file not found", "No matching entries")
#   6. 统计高亮行数，构造 LogAnalysisOutput 返回
#
# 注意:
#   · 分页在 SSH 命令层面完成 (tail/head 管道)，非 Python 内存分页
#   · 如果命令退出码非 0 (如文件不存在)，仅打印日志不中断，返回空结果
#   · 错误提示行 ("Log file not found" 等) 被过滤不进入 entries 列表
#
# 参数:
#   manager:     SSHManager 实例 (由 api.py 通过 get_ssh_manager() 获取)
#   log_path:    日志文件路径 (如 "/var/log/auth.log")
#   page:        页码 (默认 1)
#   page_size:   每页行数 (默认 100)
#   filter_text: 关键词过滤 (如 "failed")
#   date_filter: 日期过滤 (如 "2026-04-22")
#
# 返回:
#   LogAnalysisOutput 包含 total_count, highlighted_count, entries 列表

async def read_system_log(
    manager: SSHManager,
    log_path: str,
    page: int = 1,
    page_size: int = 100,
    filter_text: Optional[str] = None,
    date_filter: Optional[str] = None,
) -> LogAnalysisOutput:
    """读取系统日志文件"""

    # 检查 SSH 连接是否活跃，未连接则拒绝执行
    if not manager.is_connected():
        raise ConnectionError("没有活动的 SSH 连接")

    # 生成并执行 cat/grep/tail/head 管道命令
    cmd = _generate_log_read_command(log_path, page, page_size, filter_text, date_filter)
    print(f"[log_analysis] 读取系统日志: {cmd}")
    output = await manager.execute_command(cmd)

    # 非零退出码仅记录日志，不中断处理 (例如 grep 无匹配时退出码为 1)
    if output.exit_code and output.exit_code != 0:
        print(f"[log_analysis] 退出码: {output.exit_code}")

    # 逐行解析，过滤空行和错误提示行
    entries = []
    for line in output.output.split("\n"):
        line = line.strip()
        if not line or "Log file not found" in line or "No matching entries" in line:
            continue
        entries.append(_parse_log_line(line))

    print(f"[log_analysis] 解析到 {len(entries)} 条日志")
    highlighted_count = sum(1 for e in entries if e.highlighted)

    return LogAnalysisOutput(
        total_count=len(entries),
        highlighted_count=highlighted_count,
        entries=entries,
    )


# ================================================================================
# read_journalctl_log(manager, page, page_size, unit, filter_text, since, until)
# — 读取 systemd journalctl 日志 (公开 API)
# ================================================================================
#
# 通过 SSH 执行 journalctl 命令获取 systemd journal 日志，支持 JSON 和
# JSON-Seq 两种输出格式的自动解析。分页在 Python 内存中完成 (非 tail/head 管道)。
#
# 被调用方:
#   app.routers.api → POST /api/v1/log/read-journalctl
#     前端使用场景: 日志分析页面的 "systemd 日志" 标签页。
#     请求体: { page, page_size, unit, filter, since, until }
#
# ================================================================================
# 4 种 JSON 解析方法 (按优先级降序回退)
# ================================================================================
#
# journalctl -o json 的输出格式依赖宿主系统的 systemd 版本和配置，
# 不同发行版/版本可能产生不同的输出格式。本函数实现 4 层回退式解析，
# 按优先级依次尝试，任意一种方法成功即返回，全部失败则输出调试信息返回空。
#
# ┌──────────────────────────────────────────────────────────────────┐
# │ 方法 1: JSON 数组解析 (最高优先级)                              │
# │                                                                    │
# │ 格式示例: [{"MESSAGE":"...","PRIORITY":"6"}, {...}, ...]          │
# │ 适用场景: 某些 systemd 版本将输出包装为完整 JSON 数组              │
# │ 实现方式: json.loads(raw_output) 一次反序列化整个数组             │
# │ 优点: 最简单直接，一次调用完成全部解析                            │
# │ 缺点: 仅在输出为有效 JSON 数组格式时生效                          │
# │ 失败条件: json.loads 抛出 JSONDecodeError 或 ValueError           │
# └──────────────┬───────────────────────────────────────────────────┘
#                │ 失败时回退
#                ▼
# ┌──────────────────────────────────────────────────────────────────┐
# │ 方法 2: JSONDecoder 流式逐对象解析 (raw_decode)                  │
# │                                                                    │
# │ 格式示例: {"MESSAGE":"..."} {"MESSAGE":"..."} {"MESSAGE":"..."}  │
# │ 适用场景: 输出为连续拼接的 JSON 对象 (无数组括号，无分隔符)        │
# │ 实现方式: 使用 json.JSONDecoder().raw_decode() 从指定位置开始     │
# │           逐对象解析。每次 raw_decode 返回 (obj, end_index)，     │
# │           下次从 end_index 继续，跳过中间的空白字符。             │
# │ 优点: 不要求输出是完整数组，兼容性最广                            │
# │ 缺点: 需要手动管理解析位置，代码较复杂                            │
# │ 失败条件: 遇到无法解析的字符 (非 JSON 对象起始)                   │
# └──────────────┬───────────────────────────────────────────────────┘
#                │ 失败时回退
#                ▼
# ┌──────────────────────────────────────────────────────────────────┐
# │ 方法 3: JSON-Seq (RFC 7464) 按 \x1e 字符分割                    │
# │                                                                    │
# │ 格式示例: \x1e{"MESSAGE":"..."}\n\x1e{"MESSAGE":"..."}\n         │
# │ 适用场景: journalctl 输出 JSON-Seq 格式 (RFC 7464)                │
# │ 说明: JSON-Seq 是一种流式 JSON 文本序列化格式，                   │
# │       每条 JSON 记录前有一个 ASCII Record Separator (\x1e, 0x1E)  │
# │       作为分隔符，记录后跟换行符 \n。                              │
# │ 实现方式: 按 \x1e 字符分割全文本，每个片段调用                    │
# │           _parse_journalctl_json_line() 解析                       │
# │ 优点: 高效、精确，是 journalctl 的原生输出格式之一                │
# │ 缺点: 仅当输出中实际包含 \x1e 字符时才尝试                        │
# │ 失败条件: 输出中没有 \x1e 字符 或 分割后的行解析失败              │
# └──────────────┬───────────────────────────────────────────────────┘
#                │ 失败时回退
#                ▼
# ┌──────────────────────────────────────────────────────────────────┐
# │ 方法 4: 按空行分割多行 JSON 对象 (最后手段)                      │
# │                                                                    │
# │ 格式示例: {"MESSAGE":"line1\\nline2","PRIORITY":"6"}              │
# │           (空行)                                                   │
# │           {"MESSAGE":"next log","PRIORITY":"5"}                   │
# │ 适用场景: 某些 journalctl 版本将每个多行 JSON 对象用空行分隔       │
# │ 实现方式: 按正则 \n\s*\n (一个或多个空行) 分割全文本，            │
# │           对每个非空块尝试 json.loads() 解码。                    │
# │ 优点: 兼容多行 JSON 对象的场景                                    │
# │ 缺点: 可能将 JSON 内部的空行误判为分隔符 (但 JSON 字符串内的      │
# │       \n 会被转义为 \\n，不会产生多个连续换行，故此场景少见)       │
# │ 失败条件: 所有块均无法解码为有效 JSON                             │
# └──────────────┬───────────────────────────────────────────────────┘
#                │ 全部失败
#                ▼
#            打印调试信息 (raw_output 前 500 字符)，返回空结果
#
# 处理流程:
#   1. 检查 SSH 连接状态，未连接则抛出 ConnectionError
#   2. 调用 _generate_journalctl_command() 组装 journalctl 命令
#   3. 通过 SSH 执行命令，获取原始文本输出
#   4. 如果输出为空或包含 "no entries"，提前返回空结果
#   5. 按上述 4 种方法依次尝试 JSON 解析
#   6. 每种方法成功后将 entries 传给 _paginate_and_return() 进行内存分页
#   7. 全部失败时打印调试信息，返回空结果

async def read_journalctl_log(
    manager: SSHManager,
    page: int = 1,
    page_size: int = 100,
    unit: Optional[str] = None,
    filter_text: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> LogAnalysisOutput:
    """读取 journalctl 日志（支持 json / json-seq 多种格式）"""

    # 检查 SSH 连接是否活跃
    if not manager.is_connected():
        raise ConnectionError("没有活动的 SSH 连接")

    # 生成并执行 journalctl 命令
    cmd = _generate_journalctl_command(page, page_size, unit, filter_text, since, until)
    output = await manager.execute_command(cmd)

    raw_output = output.output.strip()
    entries = []

    # 快速判定: 空输出或无匹配条目
    if not raw_output or "no entries" in raw_output.lower():
        return LogAnalysisOutput(total_count=0, highlighted_count=0, entries=[])

    # ========================================================================
    # 方法 1: 尝试解析为 JSON 数组 [...]
    # 适用场景: systemd v240+ 某些版本将 journalctl -o json 输出为完整数组
    # ========================================================================
    try:
        data_array = json.loads(raw_output)
        if isinstance(data_array, list):
            for item in data_array:
                parsed = _parse_journalctl_json_line(json.dumps(item))
                if parsed:
                    entries.append(parsed)
            if entries:
                print(f"[log_analysis] 方法1: 解析为 JSON 数组，共 {len(entries)} 条")
                return _paginate_and_return(entries, page, page_size)
    except (json.JSONDecodeError, ValueError):
        pass

    # ========================================================================
    # 方法 2: 使用 json.JSONDecoder 逐对象解析 (处理连续的 JSON 对象)
    # 适用场景: 输出为 {"key":"val"}{"key":"val"}... 无分隔符的连续 JSON 对象
    # 原理: raw_decode(s, idx) 从字符串 s 的 idx 位置开始解析第一个完整 JSON
    #       对象，返回 (obj, end_idx)，然后从 end_idx 继续下一个
    # ========================================================================
    try:
        decoder = json.JSONDecoder()
        pos = 0
        length = len(raw_output)
        while pos < length:
            # 跳过空白字符 (空格、制表符、换行符、回车符)
            while pos < length and raw_output[pos] in ' \t\n\r':
                pos += 1
            if pos >= length:
                break
            # raw_decode: 从 pos 位置开始解析第一个完整 JSON 对象
            obj, end = decoder.raw_decode(raw_output, pos)
            parsed = _parse_journalctl_json_line(json.dumps(obj))
            if parsed:
                entries.append(parsed)
            # 下一次从 end 位置继续
            pos = end
        if entries:
            print(f"[log_analysis] 方法2: JSONDecoder 逐对象解析，共 {len(entries)} 条")
            return _paginate_and_return(entries, page, page_size)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[log_analysis] 方法2 失败: {e}")
        pass

    # ========================================================================
    # 方法 3: 按 \x1e (json-seq 分隔符, ASCII Record Separator) 分割
    # 适用场景: journalctl 输出 JSON-Seq 格式 (RFC 7464)
    # 说明: JSON-Seq 用 \x1e 字符 + 换行作为记录分隔符
    # ========================================================================
    if '\x1e' in raw_output:
        for line in raw_output.split('\x1e'):
            line = line.strip()
            if not line:
                continue
            parsed = _parse_journalctl_json_line(line)
            if parsed:
                entries.append(parsed)
        if entries:
            print(f"[log_analysis] 方法3: json-seq 格式解析，共 {len(entries)} 条")
            return _paginate_and_return(entries, page, page_size)

    # ========================================================================
    # 方法 4: 按空行分割多行 JSON 对象 (最后手段)
    # 适用场景: 某些 journalctl 版本用空行分隔每个日志条目的 JSON 块
    # 说明: 使用正则 \n\s*\n 匹配一个或多个空行作为分隔符
    # ========================================================================
    blocks = re.split(r'\n\s*\n', raw_output)
    for block in blocks:
        block = block.strip()
        # 只处理以 { 开头的 JSON 对象块
        if not block or block.startswith('{') is False:
            continue
        try:
            obj = json.loads(block)
            parsed = _parse_journalctl_json_line(json.dumps(obj))
            if parsed:
                entries.append(parsed)
        except (json.JSONDecodeError, ValueError):
            continue
    if entries:
        print(f"[log_analysis] 方法4: 空行分割解析，共 {len(entries)} 条")
        return _paginate_and_return(entries, page, page_size)

    # 所有解析方法均失败 — 输出调试信息帮助排查问题
    print(f"[log_analysis] 所有解析方法均失败")
    print(f"[log_analysis] 原始输出前 500 字符: {raw_output[:500]}")
    return LogAnalysisOutput(total_count=0, highlighted_count=0, entries=[])


# ================================================================================
# _paginate_and_return(entries, page, page_size) — 内存分页辅助函数
# ================================================================================
#
# 对已解析的 entries 列表进行内存切片分页，返回 LogAnalysisOutput。
# 用于 journalctl 日志的读取流程: journalctl 通过 -n 参数返回了
# page * page_size 条日志的全部 JSON 数据，Python 端解析后
# 通过本函数切出当前页需要的切片。
#
# 被调用方: read_journalctl_log() — 4 种解析方法成功后均调用本函数。
#
# 分页公式:
#   start = (page - 1) * page_size    — 起始索引 (0-based)
#   end   = start + page_size         — 结束索引 (不含)
#   paginated = entries[start:end]    — 当前页的条目切片
#
# 统计说明:
#   total_count 使用原始 entries 的总长度 (而非当前页的条目数)，
#   以便前端正确显示总条数和页码导航。
#   highlighted_count 仅统计当前页的条目 (只统计可见内容)。
#
# 参数:
#   entries:   所有已解析的日志条目列表
#   page:      页码 (从 1 开始)
#   page_size: 每页条数

def _paginate_and_return(entries: list, page: int, page_size: int) -> LogAnalysisOutput:
    """对条目进行分页并返回结果"""

    total_count = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = entries[start:end]
    highlighted_count = sum(1 for e in paginated if e.highlighted)
    return LogAnalysisOutput(
        total_count=total_count,
        highlighted_count=highlighted_count,
        entries=paginated,
    )


# ================================================================================
# list_log_files(manager) — 列出远程主机可用的日志文件 (公开 API)
# ================================================================================
#
# 通过 SSH 执行 find + stat 命令扫描 /var/log 目录，
# 返回所有可读的日志文件列表。如果扫描未覆盖某些常见日志文件，
# 会从 COMMON_LOG_FILES 中补充为后备选项 (标记为 readable=False)。
#
# 被调用方:
#   app.routers.api → GET /api/v1/log/list-files
#     前端使用场景: 日志分析页面左侧的 "日志文件列表" 导航树。
#     返回: [LogFileInfo, ...] (文件名、路径、大小、修改时间)
#
# 处理流程:
#   1. 检查 SSH 连接状态
#   2. 调用 _generate_list_log_files_command() 生成 find/stat 管道命令
#   3. 通过 SSH 执行命令
#   4. 解析 stat 输出 (格式: "大小|路径|时间戳")
#   5. 从 COMMON_LOG_FILES 补充未扫描到的常见日志文件 (readable=False)
#   6. 返回 LogFileInfo 列表
#
# 性能优化:
#   · 使用 xargs 替代 while read 循环，只执行一次 SSH 命令
#   · head -100 限制最多 100 个文件，防止输出过多
#   · -maxdepth 2 限制扫描深度，避免递归到底层子目录
#
# 参数:
#   manager: SSHManager 实例
#
# 返回:
#   LogFileInfo 列表，包含扫描到的文件和后备常见日志文件

async def list_log_files(manager: SSHManager) -> List[LogFileInfo]:
    """列出可用的日志文件"""

    # 检查 SSH 连接状态
    if not manager.is_connected():
        raise ConnectionError("没有活动的 SSH 连接")

    # 执行 find + xargs + stat 管道命令
    cmd = _generate_list_log_files_command()
    print(f"[log_analysis] 执行日志文件列表命令: {cmd}")
    output = await manager.execute_command(cmd)
    print(f"[log_analysis] 命令输出 (前500字符): {output.output[:500]}")
    if output.output:
        print(f"[log_analysis] 输出行数: {len(output.output.strip().splitlines())}")
    print(f"[log_analysis] 退出码: {output.exit_code}")

    # 解析 stat 输出: 格式为 "大小|路径|时间戳"
    log_files = []
    for line in output.output.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            try:
                size = int(parts[0])
            except ValueError:
                size = 0
            path = parts[1]
            # 提取文件名 (路径中最后一个 / 之后的部分)
            name = path.rsplit("/", 1)[-1]
            modified = parts[2]
            log_files.append(LogFileInfo(path=path, name=name, size=size, modified=modified, readable=True))

    print(f"[log_analysis] 找到 {len(log_files)} 个日志文件")

    # 补充常见日志文件作为后备选项 (readable=False 表示需要验证)
    # 这些文件可能因权限、路径差异等原因未被 find 扫描到，
    # 但仍列入列表供用户选择尝试打开
    for path, name in COMMON_LOG_FILES.items():
        if not any(f.path == path for f in log_files):
            log_files.append(LogFileInfo(path=path, name=name, size=0, modified="", readable=False))

    return log_files


# ================================================================================
# get_log_file_info(manager, log_path) — 获取日志文件元数据 (公开 API)
# ================================================================================
#
# 通过 SSH 执行 stat 命令获取单个日志文件的基本元数据 (大小、修改时间)。
# 如果文件不可读 (不存在或无权限)，返回 readable=False 的 LogFileInfo。
#
# 被调用方:
#   app.routers.api → POST /api/v1/log/file-info
#     前端使用场景: 点击日志文件列表中的某个文件时，右侧展示文件基本信息和统计。
#     请求体 (或 query): log_path="/var/log/auth.log"
#
# 处理流程:
#   1. 检查 SSH 连接状态
#   2. 调用 _generate_log_file_info_command() 生成 stat 命令
#   3. 通过 SSH 执行命令
#   4. 检查输出中是否包含 "readable:no" → 文件不可读
#   5. 解析 "size:12345|modified:1713456789" 格式的元数据输出
#   6. 返回 LogFileInfo 实例
#
# 参数:
#   manager:  SSHManager 实例
#   log_path: 日志文件完整路径
#
# 返回:
#   LogFileInfo 包含路径、文件名、大小、修改时间和可读性标志

async def get_log_file_info(manager: SSHManager, log_path: str) -> LogFileInfo:
    """获取日志文件信息"""

    # 检查 SSH 连接状态
    if not manager.is_connected():
        raise ConnectionError("没有活动的 SSH 连接")

    # 执行 stat 命令获取文件元数据
    cmd = _generate_log_file_info_command(log_path)
    output = await manager.execute_command(cmd)
    name = log_path.rsplit("/", 1)[-1]

    # 文件不可读 (stat 失败回退输出 "readable:no")
    if "readable:no" in output.output:
        return LogFileInfo(path=log_path, name=name, size=0, modified="", readable=False)

    # 解析 stat 输出的元数据字段
    size = 0
    modified = ""
    for part in output.output.split("|"):
        if part.startswith("size:"):
            try:
                size = int(part[5:])
            except ValueError:
                pass
        elif part.startswith("modified:"):
            modified = part[9:]

    return LogFileInfo(path=log_path, name=name, size=size, modified=modified, readable=True)
