"""
设置管理模块 — 从 Rust settings.rs 迁移

本模块是 lovelyres 应用的设置子系统核心，负责管理所有持久化配置。
设置数据以 JSON 格式存储在平台特定的应用数据目录中：

- Windows: %APPDATA%\\lovelyres\\settings.json
         （通常为 C:\\Users\\<用户名>\\AppData\\Roaming\\lovelyres\\）
- macOS:   ~/Library/Application Support/lovelyres/settings.json
- Linux:   ~/.local/share/lovelyres/settings.json

备份文件存放在同一目录下，命名格式为 settings_backup_YYYYMMDD_HHMMSS.json。

主要组件说明：
  1. Pydantic 模型层（AppSettings 及其子模型）：
     - 定义所有配置项的类型、默认值和约束
     - 使用 pydantic 自动进行序列化/反序列化（model_validate_json / model_dump_json）
     - 前端通过 Tauri 命令调用 load_settings / save_settings 读写配置

  2. 持久化函数层：
     - load_settings()  — 从磁盘加载 JSON 并反序列化为 AppSettings 对象
     - save_settings()  — 将 AppSettings 对象序列化为 JSON 并写入磁盘
     - backup_settings() — 创建带时间戳的备份文件
     - restore_settings() — 从指定备份文件恢复设置
     - reset_settings() — 恢复出厂默认设置
     - validate_settings() — 对设置值进行合法性校验

  3. AI 模型配置层次：
     - AIPrimaryModelSettings   — 主模型配置（AI 聊天和 Agent 共享的默认模型）
     - AISettings               — AI 设置根模型，包含主模型配置和向后兼容的 providers 字段
     - AgentModelSettings       — Agent 各角色（路由、规划、分析、判定、执行、摘要）的模型配置
     - AgentSettings            — Agent 总体设置，聚合所有角色模型和规划器/安全策略

  4. Agent 安全策略：
     - AgentPlannerSettings         — 规划器行为：是否启用 LLM 规划、是否允许规则回退、可观测性开关
     - AgentExecutionSafetySettings — 执行安全策略：危险操作策略（plan_only / allow_approved）、dry_run、自动审批
"""

import json
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# ==================== 设置模型 ====================
# 以下 Pydantic 模型定义了应用的所有可配置项。
# 每个模型对应设置界面的一个子面板，最终聚合到 AppSettings 根模型中。


class NotificationSettings(BaseModel):
    """通知设置 — 控制应用内各类通知的开关

    由前端通知设置面板读写，影响事件流和 toast 通知的触发行为。
    字段:
        enabled           — 总开关，关闭后所有通知静默
        connection_status — 连接状态变更通知（SSH 连接/断开）
        command_completion — 命令执行完成通知
        error_alerts      — 错误告警通知
    """

    enabled: bool = True
    connection_status: bool = True
    command_completion: bool = False
    error_alerts: bool = True


class SecuritySettings(BaseModel):
    """安全设置 — 密码存储、会话超时和操作确认策略

    由前端安全设置面板读写，影响密码管理器和 SSH 会话生命周期。
    字段:
        save_passwords       — 是否保存密码到本地（默认关闭，安全优先）
        session_timeout      — 会话超时时间（毫秒），默认 86400000ms = 24 小时
        require_confirmation — 是否要求高危操作二次确认
    """

    save_passwords: bool = False
    session_timeout: int = 86400000  # 24小时（毫秒）
    require_confirmation: bool = False


class UISettings(BaseModel):
    """UI 设置 — 界面布局和视觉偏好

    由前端外观设置面板读写，影响终端窗口布局和渲染行为。
    字段:
        sidebar_width      — 侧边栏宽度（像素），默认 280
        show_status_bar     — 是否显示状态栏，Windows 默认隐藏（菜单栏本身即含状态），其他平台默认显示
        compact_mode        — 紧凑模式，减少内边距和间距
        animations_enabled  — 是否启用过渡动画
    """

    sidebar_width: int = 280
    show_status_bar: bool = False if platform.system() == "Windows" else True
    compact_mode: bool = False
    animations_enabled: bool = True


class SSHSettings(BaseModel):
    """SSH 设置 — SSH 连接的底层参数

    由前端 SSH 连接设置面板读写，影响所有 SSH 会话的底层协议行为。
    字段:
        keep_alive_interval — 保活心跳间隔（毫秒），默认 30000ms（30 秒）
        connection_timeout   — 连接超时（毫秒），0 表示不设限
        max_retries          — 连接失败最大重试次数，默认 3
    """

    keep_alive_interval: int = 30000
    connection_timeout: int = 0
    max_retries: int = 3


class AIPrimaryModelSettings(BaseModel):
    """主模型配置 — AI 聊天和 Agent 共享的默认模型

    这是整个 AI 子系统的"默认模型"配置，被 AISettings 持有。
    所有 AI 功能和 Agent 角色在没有单独配置模型时，都会回退到此处定义的模型。

    字段:
        provider — 模型提供商标识，如 "openai"、"anthropic"、"deepseek" 等
        model    — 模型名称，如 "gpt-4o-mini"、"claude-3.5-sonnet" 等
        api_key  — API 密钥（可选，未设置时尝试从旧版 providers 字段补充）
        base_url — API 端点地址（可选，未设置时使用 provider 默认地址）

    关键方法:
        to_agent_model_settings() — 将主模型配置转换为 AgentModelSettings 格式，
                                    供 Agent 各角色模型消费。转换时 base_url 提供默认值
                                    "https://api.openai.com/v1"。
    """

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def to_agent_model_settings(self) -> "AgentModelSettings":
        """转换为 AgentModelSettings 格式（供 Agent 消费）

        将主模型配置的字段映射为 Agent 模型期望的字段名（provider -> provider, model -> model_name）。
        如果 base_url 未设置，使用 OpenAI 默认端点作为后备。
        """
        return AgentModelSettings(
            provider=self.provider,
            model_name=self.model,
            api_key=self.api_key,
            base_url=self.base_url or "https://api.openai.com/v1",
        )


class AISettings(BaseModel):
    """AI 设置 — 统一管理主模型配置

    这是 AI 子系统的根设置节点，包含：
      - primary_model: 新版统一主模型配置（AIPrimaryModelSettings）
      - providers / currentProvider: 旧版向后兼容字段

    配置解析层次（由 get_effective_primary_model 实现）：
      1. 如果 primary_model 已含 api_key → 直接使用
      2. 否则，尝试从 providers[currentProvider] 中读取 api_key 等字段来补充
      3. 都没有 → 返回原始 primary_model（无 API key，后端会使用环境变量或内置默认值）

    向后兼容说明：
      providers 和 currentProvider 是早期版本的配置格式，前端设置页面仍可能写入这些字段。
      新版代码应优先使用 primary_model。当 primary_model 缺少 api_key 时，
      get_effective_primary_model() 会回退读取 providers 以确保已保存的 API key 不丢失。
    """

    primary_model: AIPrimaryModelSettings = Field(default_factory=AIPrimaryModelSettings)

    # 向后兼容：保留 providers/currentProvider（前端设置页面使用）
    # providers 格式示例: { "openai": { "provider": "openai", "model": "gpt-4", "apiKey": "sk-...", "baseUrl": "..." } }
    providers: Optional[Dict[str, Any]] = None
    currentProvider: Optional[str] = None

    def get_effective_primary_model(self) -> AIPrimaryModelSettings:
        """获取有效的 primary_model：如果 primary_model 缺少 api_key，
        尝试从 providers[currentProvider] 中补充

        这是一个兼容性方法，确保从旧版设置格式迁移的用户不会丢失 API 密钥。
        返回的 AIPrimaryModelSettings 对象始终保证 provider 和 model 字段非空。
        """
        pm = self.primary_model
        if pm.api_key:
            return pm

        # 尝试从旧版 providers 字典中读取对应 provider 的配置
        if self.providers and self.currentProvider:
            provider_cfg = self.providers.get(self.currentProvider, {})
            if isinstance(provider_cfg, dict):
                return AIPrimaryModelSettings(
                    provider=provider_cfg.get("provider", pm.provider)
                    or pm.provider,
                    model=provider_cfg.get("model", pm.model) or pm.model,
                    api_key=provider_cfg.get("apiKey") or provider_cfg.get("api_key"),
                    base_url=provider_cfg.get("baseUrl") or provider_cfg.get("base_url"),
                )
        return pm


class AgentModelSettings(BaseModel):
    """Agent 模型配置 — 单个 Agent 角色的 LLM 模型参数

    Agent 系统中不同角色（路由、规划、分析、判定、执行、摘要）各自持有一个
    AgentModelSettings 实例，允许为每个角色精确控制模型行为和资源消耗。

    字段:
        provider       — 模型提供商标识
        model_name     — 模型名称
        api_key        — API 密钥
        base_url       — API 端点地址，默认 OpenAI
        temperature    — 生成温度（0-2），越高越随机，默认 0.7
        max_tokens     — 单次调用最大生成 token 数，默认 4096
        timeout        — API 调用超时（秒），默认 60
        fallback_model — 备选模型名称，主模型不可用时回退到此模型
    """

    provider: str = "openai"
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    fallback_model: Optional[str] = None


class AgentPlannerSettings(BaseModel):
    """Agent Planner 配置 — 控制任务规划器的行为和 LLM 依赖策略

    规划器（Planner）是 Agent 的"大脑"，负责将用户指令分解为可执行的任务步骤。
    此配置控制规划器是否使用 LLM、是否允许降级回退、以及是否记录调用详情。

    字段:
        enable_llm_planner   — 是否启用 LLM 驱动的规划器（默认 True）
        max_skills_per_task  — 每个任务最多使用的技能数，默认 3

        require_llm           — 强制要求 LLM 模式（stric 模式，默认 True）
                                设为 True 时：无适配器或 LLM 调用失败直接报错，不会回退到规则系统
                                设为 False 时：允许在 LLM 不可用时尝试规则规划器

        allow_rule_fallback   — 是否允许回退到规则规划器（默认 False）
                                当 require_llm=True 时此字段无效（因为不允许任何回退）
                                仅当 require_llm=False 时此字段生效

        llm_observability     — 是否记录 LLM 调用详情到 planner runtime info（默认 True）
                                用于调试和性能分析，记录每次 LLM 规划的输入/输出/token 消耗
    """

    enable_llm_planner: bool = True  # 默认启用 LLM planner
    max_skills_per_task: int = 3
    
    # LLM 驱动与可观测性配置
    require_llm: bool = Field(
        default=True,  # 默认强制要求 LLM（strict 模式）
        description="是否强制要求 LLM（无 adapter 或调用失败时直接报错，不回退）",
    )
    allow_rule_fallback: bool = Field(
        default=False,  # 默认不允许回退（strict 模式）
        description="是否允许回退到规则规划器（require_llm=True 时无效）",
    )
    llm_observability: bool = Field(
        default=True,
        description="是否记录 LLM 调用详情（planner runtime info）",
    )


class AgentExecutionSafetySettings(BaseModel):
    """Agent 执行安全策略 — 控制 Agent 执行任务时的安全护栏

    此配置决定 Agent 在面临可能产生副作用的操作时的行为：
      - 是否仅生成计划而不执行
      - 是否默认使用 dry-run 模式
      - 是否需要人工审批

    这些安全策略在 Agent 运行时被强制执行，不可由 LLM 自身绕过。

    字段:
        dangerous_execution_policy — 危险操作执行策略（默认 "plan_only"）：
                                       "plan_only"       — 仅生成计划，不执行任何操作
                                       "allow_approved"  — 经审批后可执行
        dry_run                   — 默认是否以 dry-run 模式运行（默认 False）
        auto_approve              — 是否默认自动审批所有操作（默认 False，安全优先）
    """

    dangerous_execution_policy: str = Field(
        default="plan_only",
        description="Dangerous execution policy: plan_only / allow_approved",
    )
    dry_run: bool = Field(
        default=False,
        description="Default dry-run flag for agent execution.",
    )
    auto_approve: bool = Field(
        default=False,
        description="Whether approvals are auto-granted by default.",
    )


class AgentSettings(BaseModel):
    """Agent 设置 — Agent 子系统的根配置节点

    聚合 Agent 所有子配置：功能开关、多模型角色分配、规划器策略、执行安全策略。

    Agent 的多模型架构包含 6 个角色，每个角色可使用不同的模型：
      - router_model     (路由)  — 将用户请求分发到合适的处理流程，默认 gpt-4
      - planner_model    (规划)  — 分解任务为可执行步骤，默认 gpt-4
      - analyst_model    (分析)  — 分析执行结果和上下文，默认 gpt-3.5-turbo
      - judge_model      (判定)  — 判定任务是否完成、结果是否符合预期，默认 gpt-4
      - executor_model   (执行)  — 生成具体执行代码/命令，默认 gpt-3.5-turbo
      - summarizer_model (摘要)  — 汇总多步结果生成最终回复，默认 gpt-3.5-turbo

    字段:
        enabled              — Agent 功能总开关
        skills_enabled       — 技能系统开关
        mcp_enabled          — MCP（模型上下文协议）开关
        multi_model_enabled  — 多模型模式开关（启用后方可为各角色分配不同模型）
        planner              — 规划器行为配置（AgentPlannerSettings）
        execution_safety     — 执行安全策略配置（AgentExecutionSafetySettings）
        router_model         — 路由角色模型配置
        planner_model        — 规划角色模型配置
        analyst_model        — 分析角色模型配置
        judge_model          — 判定角色模型配置
        executor_model       — 执行角色模型配置
        summarizer_model     — 摘要角色模型配置

    向后兼容说明:
        构造函数中存在旧版字段名兼容逻辑：
        - planner_model_role → planner_model（旧版字段名映射）
        - summarizer_model   → analyst_model（旧版语义：summarizer 现在由 analyst 角色承担）
    """

    enabled: bool = True
    skills_enabled: bool = True
    mcp_enabled: bool = False
    multi_model_enabled: bool = False
    planner: AgentPlannerSettings = Field(default_factory=AgentPlannerSettings)
    execution_safety: AgentExecutionSafetySettings = Field(
        default_factory=AgentExecutionSafetySettings
    )
    router_model: AgentModelSettings = Field(
        default_factory=lambda: AgentModelSettings(model_name="gpt-4")
    )
    planner_model: AgentModelSettings = Field(default_factory=AgentModelSettings)
    analyst_model: AgentModelSettings = Field(
        default_factory=lambda: AgentModelSettings(model_name="gpt-3.5-turbo")
    )
    judge_model: AgentModelSettings = Field(
        default_factory=lambda: AgentModelSettings(model_name="gpt-4")
    )
    executor_model: AgentModelSettings = Field(
        default_factory=lambda: AgentModelSettings(model_name="gpt-3.5-turbo")
    )
    summarizer_model: AgentModelSettings = Field(
        default_factory=lambda: AgentModelSettings(model_name="gpt-3.5-turbo")
    )

    def __init__(self, **data):
        """AgentSettings 构造函数 — 包含旧版字段名向后兼容逻辑

        处理两种情况：
          1. planner_model_role 旧字段 → 自动赋值给 planner_model
          2. summarizer_model 被定义但 analyst_model 未定义 → 将 summarizer_model 复制到 analyst_model
             （早期版本 summarizer 角色独立，后合并到 analyst 角色中）
        """
        super().__init__(**data)
        if getattr(self, "planner_model_role", None) and not getattr(
            self, "planner_model", None
        ):
            self.planner_model = self.planner_model_role
        if getattr(self, "summarizer_model", None) and not getattr(
            self, "analyst_model", None
        ):
            self.analyst_model = self.summarizer_model


class AppSettings(BaseModel):
    """应用设置根模型 — 所有设置的顶层聚合

    这是整个设置系统的根节点，由 load_settings() 反序列化，由 save_settings() 序列化。
    前端通过 Tauri 命令 IPC 与此对象交互（读取、修改、保存）。

    字段分组:
        【通用】
        theme              — 主题：light / dark / sakura
        language           — 界面语言：zh-CN / en-US
        auto_connect       — 启动时是否自动连接上次的 SSH 会话
        auto_save_interval — 自动保存间隔（毫秒）

        【终端】
        terminal_font       — 终端字体（CSS font-family 格式）
        terminal_font_size  — 终端字体大小（px）
        max_log_lines       — 终端日志最大缓存行数
        default_ssh_port    — SSH 连接默认端口

        【子配置组】— 各对应一个前端设置面板
        notifications — 通知设置（NotificationSettings）
        security      — 安全设置（SecuritySettings）
        ui            — UI 布局设置（UISettings）
        ssh           — SSH 连接设置（SSHSettings）
        ai            — AI 模型设置（AISettings，Optional，旧版用户可能无此字段）
        agent         — Agent 设置（AgentSettings，默认自动创建）
    """

    theme: str = "light"
    language: str = "zh-CN"
    auto_connect: bool = False
    default_ssh_port: int = 22
    terminal_font: str = "Monaco, Consolas, monospace"
    terminal_font_size: int = 14
    max_log_lines: int = 1000
    auto_save_interval: int = 30000
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    ui: UISettings = Field(default_factory=UISettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    ai: Optional[AISettings] = None
    agent: Optional[AgentSettings] = Field(default_factory=AgentSettings)


# ==================== 设置管理 ====================
# 以下函数负责设置文件的路径解析、读写、备份/恢复、重置和校验。
# 所有文件操作都通过 Path 对象进行，确保跨平台兼容性。


def get_app_data_dir() -> Path:
    """获取应用数据目录（平台相关）

    根据操作系统返回 lovelyres 的应用数据目录路径，不存在则自动创建。

    路径规则:
        Windows — %APPDATA%/lovelyres/
        macOS   — ~/Library/Application Support/lovelyres/
        Linux   — ~/.local/share/lovelyres/

    返回: 平台对应的 Path 对象，目录已确保存在
    """
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"

    app_data_dir = base / "lovelyres"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir


def get_settings_file_path() -> Path:
    """获取设置文件路径

    返回 settings.json 的完整路径（位于 get_app_data_dir() 目录下）。
    注意：此函数只返回路径，不检查文件是否存在。

    返回: <app_data_dir>/settings.json 的 Path 对象
    """
    return get_app_data_dir() / "settings.json"


def load_settings() -> AppSettings:
    """加载应用设置

    从磁盘读取 settings.json 并反序列化为 AppSettings 对象。

    工作流程:
        1. 获取设置文件路径（get_settings_file_path()）
        2. 检查文件是否存在
        3. 如果不存在 → 打印提示，返回默认 AppSettings
        4. 如果存在 → 读取 JSON 内容，使用 Pydantic 的 model_validate_json 解析
        5. 解析失败 → 打印错误，返回默认 AppSettings（优雅降级，不崩溃）

    Pydantic 自动处理类型转换和默认值填充：
        - JSON 中缺失的字段使用模型定义的默认值
        - 类型不匹配的字段会触发 ValidationError（被捕获后回退到默认值）
        - 多余字段会被忽略

    返回: AppSettings 对象（总是有效，不会抛出异常）
    """
    settings_file = get_settings_file_path()

    if not settings_file.exists():
        print("设置文件不存在，返回默认设置")
        return AppSettings()

    try:
        content = settings_file.read_text(encoding="utf-8")
        settings = AppSettings.model_validate_json(content)
        print("成功加载应用设置")
        return settings
    except Exception as e:
        print(f"解析设置文件失败: {e}，返回默认设置")
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """保存应用设置

    将 AppSettings 对象序列化为 JSON 并写入磁盘文件 settings.json。

    工作流程:
        1. 获取设置文件路径（get_settings_file_path()）
        2. 使用 Pydantic 的 model_dump_json(indent=2) 生成格式化 JSON
           - indent=2: 2 空格缩进，确保文件人类可读
           - model_dump_json 自动排除 Optional 值为 None 的字段
        3. 以 UTF-8 编码写入文件（覆盖已有内容）

    参数:
        settings: 要保存的 AppSettings 对象

    注意: 此函数不进行校验，调用方应在调用前确保 settings 对象合法。
           如需校验，请先调用 validate_settings()。
    """
    settings_file = get_settings_file_path()
    content = settings.model_dump_json(indent=2)
    settings_file.write_text(content, encoding="utf-8")
    print("成功保存应用设置")


def reset_settings() -> None:
    """重置设置到默认值

    创建一个全新的 AppSettings() 对象（所有字段使用模型定义的默认值）
    并保存到磁盘，覆盖当前设置文件。

    效果等同于"恢复出厂设置"：所有自定义配置丢失，恢复到安装时的初始状态。
    """
    save_settings(AppSettings())


def backup_settings() -> Path:
    """备份当前设置

    读取当前设置文件内容，以带时间戳的文件名在同目录下创建备份。

    备份文件命名格式: settings_backup_YYYYMMDD_HHMMSS.json
    时间戳使用 UTC 时间。

    工作流程:
        1. 调用 load_settings() 获取当前设置
        2. 生成时间戳字符串（格式: "20260428_143025"）
        3. 在 app_data_dir 下创建备份文件
        4. 序列化当前设置并写入备份文件

    返回: 备份文件的 Path 对象（可用于后续 restore_settings() 调用）
    """
    settings = load_settings()
    app_data_dir = get_app_data_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = app_data_dir / f"settings_backup_{timestamp}.json"
    content = settings.model_dump_json(indent=2)
    backup_file.write_text(content, encoding="utf-8")
    print(f"设置已备份到: {backup_file}")
    return backup_file


def restore_settings(backup_file: Path) -> None:
    """从备份恢复设置

    从指定的备份文件读取 JSON 内容，反序列化后覆盖当前设置文件。

    工作流程:
        1. 检查备份文件是否存在（不存在则抛出 FileNotFoundError）
        2. 读取备份文件内容
        3. 使用 Pydantic 解析为 AppSettings（解析失败会向上抛出异常）
        4. 调用 save_settings() 将解析结果覆盖写入 settings.json

    参数:
        backup_file: 备份文件的完整路径（通常由 backup_settings() 返回）

    异常:
        FileNotFoundError — 备份文件不存在
        ValidationError   — 备份文件内容格式不合法（Pydantic 解析失败）
    """
    if not backup_file.exists():
        raise FileNotFoundError("备份文件不存在")

    content = backup_file.read_text(encoding="utf-8")
    settings = AppSettings.model_validate_json(content)
    save_settings(settings)
    print(f"设置已从备份恢复: {backup_file}")


def validate_settings(settings: AppSettings) -> None:
    """验证设置格式，不合法则抛出 ValueError

    对 AppSettings 中所有关键字段进行业务逻辑校验，确保值在合理范围内。
    此校验独立于 Pydantic 的类型校验（Pydantic 只检查类型，不检查业务约束）。

    校验规则（按字段）:
        theme                 — 必须是 "light" / "dark" / "sakura" 之一
        language              — 必须是 "zh-CN" / "en-US" 之一
        default_ssh_port      — 范围 1-65535
        terminal_font_size    — 范围 8-72（像素）
        max_log_lines         — 范围 1-100000
        auto_save_interval    — 范围 1000-3600000 毫秒（1 秒 ~ 1 小时）
        security.session_timeout — 范围 60000-86400000 毫秒（1 分钟 ~ 24 小时）
        ui.sidebar_width      — 范围 200-800（像素）
        ssh.keep_alive_interval — 范围 5000-300000 毫秒（5 秒 ~ 5 分钟）
        ssh.connection_timeout  — 范围 1000-600000 毫秒（1 秒 ~ 10 分钟）
        ssh.max_retries        — 范围 1-10

    异常:
        ValueError — 任一字段值超出合法范围，消息指明具体字段

    调用时机:
        前端在保存设置前应调用此函数进行预校验，避免写入无效配置。
    """
    if settings.theme not in ("light", "dark", "sakura"):
        raise ValueError("无效的主题设置")
    if settings.language not in ("zh-CN", "en-US"):
        raise ValueError("无效的语言设置")
    if not (0 < settings.default_ssh_port <= 65535):
        raise ValueError("无效的SSH端口设置")
    if not (8 <= settings.terminal_font_size <= 72):
        raise ValueError("无效的终端字体大小设置")
    if not (0 < settings.max_log_lines <= 100000):
        raise ValueError("无效的最大日志行数设置")
    if not (1000 <= settings.auto_save_interval <= 3600000):
        raise ValueError("无效的自动保存间隔设置")
    if not (60000 <= settings.security.session_timeout <= 86400000):
        raise ValueError("无效的会话超时设置")
    if not (200 <= settings.ui.sidebar_width <= 800):
        raise ValueError("无效的侧边栏宽度设置")
    if not (5000 <= settings.ssh.keep_alive_interval <= 300000):
        raise ValueError("无效的SSH保活间隔设置")
    if not (1000 <= settings.ssh.connection_timeout <= 600000):
        raise ValueError("无效的SSH连接超时设置")
    if not (0 < settings.ssh.max_retries <= 10):
        raise ValueError("无效的SSH最大重试次数设置")


def read_settings_file() -> str:
    """读取设置文件原始内容（字符串形式）

    直接读取 settings.json 的原始文本内容，不做解析和校验。
    用于需要原始 JSON 字符串的场景（如前端直接展示或透传给 Rust 侧）。

    如果文件不存在，返回空字符串 ""（不抛出异常）。

    返回: settings.json 的 UTF-8 文本内容，或空字符串
    """
    settings_file = get_settings_file_path()
    if settings_file.exists():
        return settings_file.read_text(encoding="utf-8")
    return ""


def write_settings_file(content: str) -> None:
    """写入设置文件原始内容（字符串形式）

    直接将字符串写入 settings.json，不经过 Pydantic 序列化。
    用于接收前端或外部系统提供的 JSON 字符串并直接持久化。

    参数:
        content: 要写入的 JSON 字符串

    注意: 此函数不做任何校验或格式化，调用方需确保 content 是合法的 JSON 且符合 AppSettings 结构。
           如需带校验的写入，请使用 save_settings() + validate_settings()。
    """
    settings_file = get_settings_file_path()
    settings_file.write_text(content, encoding="utf-8")
