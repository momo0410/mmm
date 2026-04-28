"""
系统字体获取模块 —— 跨平台字体发现与列表构建。

=== 字体发现策略（3 级回退） ===

第 1 级（Windows 专用）：从注册表读取系统已安装字体列表
    → 调用 get_fonts_from_registry()，解析 Windows 注册表键值
第 2 级（全平台）：遍历操作系统字体目录中的 .ttf / .otf / .ttc 文件
    → 调用 get_fonts_from_directory()，扫描各平台标准字体路径
第 3 级（兜底方案）：返回硬编码的常用字体列表
    → 调用 get_default_fonts()，涵盖中文字体、英文字体、等宽字体、设计字体

=== 调用关系 ===

该模块由 API 端点 GET /api/v1/system/fonts 调用（定义于 app/routers/ 下），
前端字体选择器组件通过此接口获取可用字体列表，供用户在下拉框中选字。

该模块是从 Rust 版 lib.rs 中字体获取逻辑迁移而来的 Python 实现。
"""

import os
import platform
import subprocess
from typing import List


def get_default_fonts() -> List[str]:
    """
    返回硬编码的默认字体列表 —— 三层回退策略的第 3 级兜底方案。

    当注册表查询失败（非 Windows 系统或无权限）且字体目录扫描无果时，
    使用此列表作为最终回退，确保前端字体选择器至少显示可用的字体选项。

    字体涵盖：
        - "系统默认"：占位选项，表示不指定字体，由浏览器/系统决定
        - 中文宋/黑/楷/仿宋等常见 Windows 中文字体及对应英文名称
        - macOS 苹方、冬青黑体等 macOS 中文字体
        - Noto / Source Han 思源系列开源中文字体
        - Arial / Times New Roman / Calibri 等标准英文字体
        - Consolas / JetBrains Mono / Fira Code 等程序员等宽字体
        - Helvetica / Roboto / Open Sans 等国际通用设计字体

    Returns:
        List[str]: 字体名称字符串列表，已包含 "系统默认" 作为第一项。
    """
    return [
        "系统默认",
        # Windows 中文字体
        "Microsoft YaHei", "Microsoft YaHei UI", "微软雅黑",
        "SimSun", "宋体", "SimHei", "黑体", "KaiTi", "楷体",
        "FangSong", "仿宋", "Microsoft JhengHei", "微软正黑体",
        "DengXian", "等线", "YouYuan", "幼圆", "LiSu", "隶书",
        "STXihei", "华文细黑", "STKaiti", "华文楷体",
        "STSong", "华文宋体", "STFangsong", "华文仿宋",
        # macOS 中文字体
        "PingFang SC", "苹方", "Hiragino Sans GB", "冬青黑体简体中文",
        # 开源中文字体
        "Noto Sans CJK SC", "思源黑体", "Source Han Sans SC",
        "Noto Serif CJK SC", "思源宋体", "Source Han Serif SC",
        # Windows 英文字体
        "Arial", "Times New Roman", "Calibri", "Segoe UI",
        "Tahoma", "Verdana", "Georgia", "Trebuchet MS",
        "Comic Sans MS", "Impact", "Lucida Console", "Palatino Linotype",
        # 等宽字体
        "Consolas", "Courier New", "JetBrains Mono", "Fira Code",
        "Source Code Pro", "Monaco", "Menlo", "Inconsolata",
        "Roboto Mono", "Ubuntu Mono",
        # 设计字体
        "Helvetica", "Helvetica Neue", "San Francisco",
        "Roboto", "Open Sans", "Lato", "Montserrat", "Poppins",
    ]


def get_fonts_from_directory() -> List[str]:
    """
    从操作系统字体目录扫描已安装字体 —— 三层回退策略的第 2 级。

    根据当前操作系统选择对应的标准字体目录路径：
        - Windows: C:\\Windows\\Fonts、C:\\Windows\\System32\\Fonts
        - macOS:   /Library/Fonts、/System/Library/Fonts、~/Library/Fonts
        - Linux:   /usr/share/fonts、/usr/local/share/fonts、~/.fonts

    扫描 .ttf（TrueType）、.otf（OpenType）、.ttc（TrueType Collection）文件，
    提取文件名（去除扩展名、下划线和连字符）作为字体名称。

    注意：此方法只获取已安装到系统字体目录的字体文件名称，不会解析字体元数据，
    因此字体名称可能与实际字体族名不完全一致。

    返回值已排序。

    Returns:
        List[str]: 从字体目录中发现的字体名称列表，第一项为 "系统默认"。
    """
    fonts = ["系统默认"]

    if platform.system() == "Windows":
        font_dirs = ["C:\\Windows\\Fonts", "C:\\Windows\\System32\\Fonts"]
    elif platform.system() == "Darwin":
        font_dirs = ["/Library/Fonts", "/System/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:
        font_dirs = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]

    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for filename in os.listdir(font_dir):
            if filename.endswith((".ttf", ".otf", ".ttc")):
                font_name = filename.replace(".ttf", "").replace(".otf", "").replace(".ttc", "")
                font_name = font_name.replace("_", " ").replace("-", " ")
                if font_name and font_name not in fonts:
                    fonts.append(font_name)

    fonts.sort()
    return fonts


def get_fonts_from_registry() -> List[str]:
    """
    从 Windows 注册表获取系统已安装字体列表 —— 三层回退策略的第 1 级（仅 Windows）。

    在 Windows 系统中，通过执行 reg query 命令查询注册表路径：
        HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts

    该键下存储了所有已安装字体的注册表值（REG_SZ 类型），键名为字体显示名称。
    命令设置了 10 秒超时，避免在异常环境下长时间阻塞。

    解析逻辑：
        1. 按行分割命令输出
        2. 筛出包含 "REG_SZ" 的行（字体注册项）
        3. 以 "REG_SZ" 为分隔符提取键名部分
        4. 去除 "(TrueType)"、"(OpenType)" 等字体技术标注
        5. 去除 Bold / Italic / Regular / Light / Medium 等字重/样式后缀
        6. 仅保留长度大于 1 的名称

    对于非 Windows 系统，直接返回空列表。

    返回值已排序。查询失败（权限不足、注册表项不存在等）时静默返回空列表。

    Returns:
        List[str]: 从注册表解析出的字体名称列表；非 Windows 或失败时返回 []。
    """
    if platform.system() != "Windows":
        return []

    try:
        result = subprocess.run(
            ["reg", "query", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            fonts = ["系统默认"]
            for line in result.stdout.split("\n"):
                if "REG_SZ" in line and line.strip():
                    parts = line.split("REG_SZ")
                    if parts:
                        font_entry = parts[0].strip()
                        font_name = (
                            font_entry.replace(" (TrueType)", "").replace(" (OpenType)", "")
                            .replace(" Bold", "").replace(" Italic", "")
                            .replace(" Regular", "").replace(" Light", "")
                            .replace(" Medium", "").strip()
                        )
                        if font_name and font_name not in fonts and len(font_name) > 1:
                            fonts.append(font_name)
            fonts.sort()
            return fonts
    except Exception:
        pass
    return []


def get_system_fonts() -> List[str]:
    """
    获取系统字体列表 —— 三级回退策略的编排器（orchestrator）。

    该函数是模块的对外入口，按优先级依次尝试三种字体获取方式：

    === 回退流程 ===

    第 1 级 — 注册表查询（仅 Windows）：
        调用 get_fonts_from_registry() 从 Windows 注册表获取字体列表。
        如果返回结果超过 10 个字体，说明查询成功且数据有效，直接返回。
        如果不足 10 个（查询失败、无权限、或非 Windows 系统），继续下一级。

    第 2 级 — 字体目录扫描（全平台）：
        调用 get_fonts_from_directory() 扫描系统字体目录。
        如果返回结果超过 10 个字体，直接返回。
        如果不足 10 个（字体目录为空或无权限访问），继续下一级。

    第 3 级 — 硬编码默认列表（兜底）：
        调用 get_default_fonts() 返回内置的常用字体列表。
        这是最终兜底方案，确保前端总是能拿到可用的字体数据。

    === 调用方 ===

    该函数由 API 端点 GET /api/v1/system/fonts 调用，
    响应 JSON 中的字体列表直接填充前端字体选择器下拉框。

    阈值 10 的设计理由：如果注册表返回的数据过少（仅"系统默认"加零星几个），
    说明命令执行异常（如权限不足、注册表路径不存在），应跳过该结果继续下一级。

    Returns:
        List[str]: 系统可用字体名称列表，已排序，第一项为 "系统默认"。
    """
    # 方法1: 从注册表获取 (Windows)
    if platform.system() == "Windows":
        fonts = get_fonts_from_registry()
        if len(fonts) > 10:
            return fonts

    # 方法2: 从字体目录获取
    fonts = get_fonts_from_directory()
    if len(fonts) > 10:
        return fonts

    # 方法3: 使用默认字体列表
    return get_default_fonts()
