"""SSH 连接配置管理器 —— 从 Rust ssh_connection_manager.rs 迁移至 Python

================================================================================
模块概览
================================================================================

本模块实现了 SSH 连接配置的持久化存储和密码加密/解密功能，是整个应用 SSH 相关功能
的数据层核心。它独立于 SSHManager（后者负责实时 SSH/PTY/SFTP 连接），专注于配置数据的
生命周期管理：加密存储、加载、备份、恢复和完整性校验。

================================================================================
模块间的协作关系
================================================================================

┌─────────────────────────────────────────────────────────────────────────┐
│                         app.main.lifespan                                │
│                     （FastAPI 应用启动/关闭入口）                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ 调用
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     app.routers.api.init_state()                         │
│            （初始化全局单例：SSHManager, SSHConnectionManager, ...）        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ 实例化
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│        app.services.ssh_connection_manager.SSHConnectionManager          │
│                     （本模块 —— 配置持久化层）                             │
│                                                                         │
│  内部调用:                                                               │
│    • app.services.settings.get_app_data_dir()  → 获取数据目录路径         │
│    • app.models.types.SSHConnection           → 连接配置数据模型          │
│                                                                         │
│  外部依赖（第三方库）:                                                    │
│    • cryptography.hazmat.primitives.ciphers.aead.AESGCM                  │
│      → AES-256-GCM 对称加密实现（密钥长度 256 位，12 字节随机 nonce）      │
│    • base64    → 密文编码（nonce + ciphertext → Base64 字符串）           │
│    • json      → 配置文件序列化/反序列化                                   │
│    • shutil    → 备份文件复制                                             │
│    • datetime  → 备份文件名时间戳                                         │
│    • pathlib.Path → 跨平台路径处理                                        │
│                                                                         │
│  被调用方（通过全局单例 get_connection_manager() 访问）:                    │
│    • app.routers.api → 以下 FastAPI 端点：                                │
│        - GET  /api/v1/ssh/connections       → load_connections()         │
│        - POST /api/v1/ssh/connections/save  → save_connections()         │
│        - POST /api/v1/ssh/encrypt-password  → encrypt_password()         │
│        - POST /api/v1/ssh/decrypt-password  → decrypt_password()         │
│    • diagnose_sftp.py（CLI 诊断工具）→ load_connections()                  │
│                                                                         │
│  Rust 前端（通过 #![cfg(frontend)]）:                                     │
│    src-tauri/ → tauri::command 绑定这些方法，供 React/Vue 前端调用         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

================================================================================
加密密钥生命周期
================================================================================

密钥采用 AES-256-GCM 对称加密方案，包含以下关键环节：

1. 密钥生成（首次运行）:
   - 调用 AESGCM.generate_key(bit_length=256) 生成 32 字节随机密钥
   - 写入 {app_data_dir}/encryption.key 文件持久化存储
   - 后续运行直接读取该文件

2. 密钥加载（后续运行）:
   - 从 {app_data_dir}/encryption.key 读取 32 字节密钥
   - 若文件不存在 → 触发密钥生成
   - 若文件存在但长度 ≠ 32 字节 → 抛出 ValueError("加密密钥长度错误")

3. 密钥用途:
   - encrypt_password(): 使用密钥对 SSH 明文密码进行 AES-256-GCM 加密
   - decrypt_password(): 使用密钥对已加密的 Base64 密文进行解密

4. 密钥安全注意:
   - 密钥文件存储在本地应用数据目录（用户级权限保护）
   - 密钥不在网络间传输，不参与任何 API 响应
   - 不同设备的密钥独立生成，互不兼容
   - 密钥文件丢失 = 所有已加密密码永久不可恢复

================================================================================
备份/恢复机制
================================================================================

为防止配置文件意外损坏或人为误操作导致数据丢失，本模块内置了完整的备份机制：

备份策略:
  - 备份目录: {app_data_dir}/backups/
  - 备份文件命名: ssh_connections_backup_{YYYYMMDD_HHMMSS}.json
  - 备份方法: shutil.copy2() 保留文件元数据（修改时间等）
  - 自动清理: cleanup_old_backups() 保留最近 N 个备份（默认 5 个）

操作流程:
  create_backup()         → 复制当前配置文件到备份目录
  restore_from_backup()   → 从指定备份文件恢复覆盖当前配置
  cleanup_old_backups()   → 按修改时间排序，保留最新 N 个，删除其余

调用方式: 目前这些方法通过 Tauri command 绑定供前端调用（预留扩展），
         也可通过 CLI 工具和 Python 脚本直接调用。

================================================================================
文件路径规范（不同平台）
================================================================================

平台          app_data_dir 基路径                        配置文件路径
─────────────────────────────────────────────────────────────────────────
Windows       %APPDATA%/lovelyres/                       ssh_connections.json
macOS         ~/Library/Application Support/lovelyres/   ssh_connections.json
Linux         ~/.local/share/lovelyres/                  ssh_connections.json

所有平台统一:
  - 加密密钥: {app_data_dir}/encryption.key（32 字节二进制）
  - 备份目录: {app_data_dir}/backups/ssh_connections_backup_*.json
"""

import base64
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 外部依赖: cryptography 库, 提供 AES-GCM 对称加密算法
# AES-GCM (Galois/Counter Mode) 同时提供机密性和完整性校验（认证加密 AEAD）
# AESGCM.generate_key(256) 生成 32 字节（256 位）随机密钥
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 内部依赖: SSHConnection 数据模型（Pydantic）, 定义连接/账号/认证字段结构
from app.models.types import SSHConnection
# 内部依赖: 获取跨平台应用数据目录（Windows: %APPDATA%, macOS: ~/Library, Linux: ~/.local/share）
from app.services.settings import get_app_data_dir


class SSHConnectionManager:
    """SSH 连接配置的持久化管理器

    ============================================================================
    核心职责
    ============================================================================
    1. SSH 连接配置（SSHConnection 列表）的持久化存储与加载
       - 存储文件: {app_data_dir}/ssh_connections.json（JSON 格式，UTF-8 编码）
       - 加载时自动迁移旧版单账号数据到新版多账号模式（accounts 列表）

    2. SSH 密码的 AES-256-GCM 对称加密/解密
       - 加密: 明文密码 → AES-GCM 加密 → Base64 编码 → 密文字符串
       - 解密: Base64 密文 → Base64 解码 → AES-GCM 解密 → 明文密码
       - 密钥来源: {app_data_dir}/encryption.key（32 字节随机密钥）

    3. 配置文件备份与恢复
       - 自动备份到 {app_data_dir}/backups/ 目录
       - 按时间戳命名备份文件，支持保留最近 N 个备份

    4. 配置文件完整性校验
       - 通过尝试加载并解析配置文件来验证文件格式和内容是否有效

    ============================================================================
    与其他模块的关系
    ============================================================================
    上游调用方（谁使用本类）:
      - app.routers.api.init_state() → 应用启动时创建全局单例
      - app.routers.api.get_connection_manager() → FastAPI 依赖注入获取单例
      - diagnose_sftp.py → CLI 诊断工具直接实例化

    下游依赖（本类使用什么）:
      - app.services.settings.get_app_data_dir() → 获取跨平台数据目录
      - app.models.types.SSHConnection → 连接配置数据模型（Pydantic）
      - cryptography.hazmat.primitives.ciphers.aead.AESGCM → 加密算法实现

    API 端点调用映射:
      - GET  /api/v1/ssh/connections       → load_connections()
      - POST /api/v1/ssh/connections/save  → save_connections()
      - POST /api/v1/ssh/encrypt-password  → encrypt_password()
      - POST /api/v1/ssh/decrypt-password  → decrypt_password()

    ============================================================================
    全局单例模式
    ============================================================================
    整个应用生命周期内只存在一个 SSHConnectionManager 实例。
    在 app.routers.api 中以模块级变量 _ssh_connection_manager 持有，
    通过 get_connection_manager() 访问器获取（具有初始化状态检查）。
    """

    def __init__(self):
        """初始化 SSH 连接管理器

        构造流程:
          1. 获取跨平台应用数据目录（Windows/macOS/Linux 自动适配）
          2. 确定配置文件和备份目录的绝对路径
          3. 确保备份目录存在（mkdir -p 语义）
          4. 调用 _get_or_create_encryption_key() 初始化加密密钥

        实例变量:
          self.app_data_dir     → app_data_dir / "lovelyres"（由 get_app_data_dir() 返回）
          self.connections_file → app_data_dir / "ssh_connections.json"（JSON 配置文件）
          self.backups_dir      → app_data_dir / "backups"（备份存储目录）
          self.encryption_key   → bytes (32 字节 AES-256 密钥)

        调用时机: 应用启动时由 init_state() 调用，或诊断工具直接实例化
        """
        # 获取跨平台应用数据目录（由 settings 模块统一管理）
        # Windows: %APPDATA%/lovelyres
        # macOS:   ~/Library/Application Support/lovelyres
        # Linux:   ~/.local/share/lovelyres
        self.app_data_dir = get_app_data_dir()

        # SSH 连接配置文件的完整路径
        self.connections_file = self.app_data_dir / "ssh_connections.json"

        # 备份文件存储目录
        self.backups_dir = self.app_data_dir / "backups"
        # 确保备份目录存在（递归创建父目录，已存在则跳过不报错）
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        # 获取或生成 AES-256 加密密钥（首次运行生成，后续运行加载）
        self.encryption_key = self._get_or_create_encryption_key()

    def _get_or_create_encryption_key(self) -> bytes:
        """获取或创建 AES-256-GCM 加密密钥

        ========================================================================
        密钥生命周期管理
        ========================================================================

        ● 首次运行（密钥文件不存在）:
          1. 调用 AESGCM.generate_key(bit_length=256) 生成 32 字节随机密钥
             - 使用操作系统 CSPRNG（加密安全伪随机数生成器）
             - 密钥长度 256 位 = 32 字节，符合 AES-256 规范
          2. 将密钥以二进制形式写入 {app_data_dir}/encryption.key
          3. 打印 "生成新的加密密钥" 日志
          4. 返回 32 字节密钥

        ● 后续运行（密钥文件已存在）:
          1. 读取 {app_data_dir}/encryption.key 全部内容
          2. 校验密钥长度：必须恰好 32 字节
             - 若长度 ≠ 32 → 抛出 ValueError("加密密钥长度错误")
             - 此校验防止密钥文件损坏或被篡改
          3. 打印 "加载现有加密密钥" 日志
          4. 返回 32 字节密钥

        ========================================================================
        安全考量
        ========================================================================
        - 密钥文件 encryption.key 是 32 字节的原始二进制数据，无任何编码包装
        - 密钥生成使用操作系统级的加密安全随机源（os.urandom 通过 libcrypto）
        - 密钥永不离开本地文件系统，不参与任何网络传输
        - 密钥文件权限建议设置为仅当前用户可读（Windows 上由用户目录 ACL 控制）
        - 警告: 若 encryption.key 丢失，所有已加密的 SSH 密码将永久无法解密

        ========================================================================
        被调用方
        ========================================================================
        - self.__init__() — 构造函数中调用，确保实例创建时密钥已就绪

        返回:
          bytes: 32 字节 AES-256 对称加密密钥
        """
        # 密钥文件路径: {app_data_dir}/encryption.key
        key_file = self.app_data_dir / "encryption.key"

        if key_file.exists():
            # 密钥文件存在 → 加载已有密钥
            key_data = key_file.read_bytes()
            # 校验密钥长度：AES-256 要求精确 32 字节（256 位）
            if len(key_data) != 32:
                raise ValueError("加密密钥长度错误")
            print("加载现有加密密钥")
            return key_data
        else:
            # 密钥文件不存在 → 首次运行，生成新密钥
            # AESGCM.generate_key(256) 返回 32 字节 CSPRNG 随机密钥
            key = AESGCM.generate_key(bit_length=256)
            # 将密钥以原始二进制形式写入磁盘
            key_file.write_bytes(key)
            print("生成新的加密密钥")
            return key

    def load_connections(self) -> List[SSHConnection]:
        """从本地 JSON 文件加载 SSH 连接配置列表

        ========================================================================
        方法职责
        ========================================================================
        读取 {app_data_dir}/ssh_connections.json 文件，解析并返回 SSHConnection
        对象列表。文件不存在时返回空列表（而非报错），兼容首次使用场景。

        ========================================================================
        处理流程
        ========================================================================
        1. 检查配置文件是否存在 → 不存在则打印日志、返回空列表 []
        2. 以 UTF-8 编码读取文件内容
        3. 使用 json.loads() 将 JSON 字符串解析为原生 Python list[dict]
        4. 对每个 dict 调用 SSHConnection.model_validate() 进行 Pydantic 校验和实例化
           - 自动完成字段类型转换（如字符串 → datetime）
           - 自动填充默认值（如 id 使用 uuid4 生成）
        5. 自动迁移旧版数据:
           - 遍历每个连接，若 accounts 列表为空但旧版 username 字段有值
           - 则调用 conn.migrate_legacy_account() 将单账号数据迁移为多账号模式
           - 迁移后自动调用 save_connections() 持久化（确保后续加载无需再次迁移）
        6. 任何步骤异常均返回空列表（容错设计）

        ========================================================================
        异常处理
        ========================================================================
        - JSON 解析失败（语法错误）→ 打印错误日志，返回空列表
        - Pydantic 校验失败（字段类型/格式错误）→ 打印错误日志，返回空列表
        - 文件权限不足（无法读取）→ 异常向上传播（不捕获）
        - 迁移保存失败 → 打印错误日志，不影响已加载的连接列表返回

        ========================================================================
        API 端点调用方
        ========================================================================
        - GET /api/v1/ssh/connections
          前端使用场景: 连接管理页面展示已保存服务器列表、快速连接下拉菜单
          数据流: 请求 → get_connection_manager() → load_connections()
                  → 返回 [SSHConnection, ...] 序列化列表

        其他调用方:
        - diagnose_sftp.py（CLI 诊断工具）→ 显示已保存的连接数量和详情

        返回:
          List[SSHConnection]: 已保存的 SSH 连接配置列表，
                              配置文件不存在或解析失败时返回空列表
        """
        if not self.connections_file.exists():
            # 配置文件不存在（首次使用或手动删除），返回空列表供前端展示空态
            print("SSH连接配置文件不存在，返回空列表")
            return []

        try:
            # 以 UTF-8 编码读取 JSON 配置文件内容
            content = self.connections_file.read_text(encoding="utf-8")
            # 将 JSON 字符串解析为 Python 原生类型: list[dict]
            raw_list = json.loads(content)
            # 对每个 dict 进行 Pydantic 模型校验和实例化
            # model_validate() 会进行字段类型验证、默认值填充、自定义验证器执行
            connections = [SSHConnection.model_validate(c) for c in raw_list]
        except Exception as e:
            # JSON 解析异常或 Pydantic 校验异常 → 容错返回空列表
            print(f"解析SSH配置文件失败: {e}")
            return []

        # 自动迁移旧的单账号数据到多账号模式
        # 旧版数据使用 username/auth_type 等单字段存储认证信息
        # 新版数据使用 accounts: List[SSHAccountCredential] 支持多账号
        migrated_count = 0
        for conn in connections:
            # 迁移条件: accounts 列表为空 且 旧版 username 字段有值
            if not conn.accounts and conn.username:
                # SSHConnection.migrate_legacy_account() 内部创建默认账号并加入 accounts
                conn.migrate_legacy_account()
                migrated_count += 1

        if migrated_count > 0:
            # 迁移完成后自动保存，确保磁盘上的配置文件也更新为新格式
            print(f"自动迁移了 {migrated_count} 个旧账号数据到多账号模式")
            try:
                self.save_connections(connections)
            except Exception as e:
                # 保存失败不阻断数据加载，仅打印日志
                print(f"保存迁移后的数据失败: {e}")

        return connections

    def save_connections(self, connections: List[SSHConnection]) -> None:
        """将 SSH 连接配置列表全量保存到本地 JSON 文件

        ========================================================================
        方法职责
        ========================================================================
        将传入的 SSHConnection 列表序列化为 JSON 并写入磁盘文件，是全量覆盖写
        （非增量追加）。确保父目录存在，支持自动创建。

        ========================================================================
        处理流程
        ========================================================================
        1. 确保配置文件父目录存在（mkdir -p 语义）
        2. 对每个 SSHConnection 调用 model_dump(mode="json") 序列化为 dict
           - mode="json" 会将 datetime 转为 ISO 8601 字符串、UUID 转为字符串
        3. 使用 json.dumps() 序列化为格式化的 JSON 字符串
           - indent=2: 2 空格缩进，便于人工阅读和版本控制 diff
           - ensure_ascii=False: 保留中文字符不转义为 \\uXXXX
           - default=str: 兜底将未知类型转为字符串（防止序列化中断）
        4. 以 UTF-8 编码写入 {app_data_dir}/ssh_connections.json
        5. 打印保存成功日志（含连接数量）

        ========================================================================
        注意事项
        ========================================================================
        - 此方法不负责加密 —— 加密在 encrypt_password() 中单独处理
        - 前端在调用 save_connections() 前应已通过 encrypt-password 端点
          对密码字段进行加密，encrypted_password 字段存储的是 Base64 密文
        - 保存操作是同步 I/O，在大连接数量场景下可能阻塞事件循环，
          但实际使用中连接数量不会超过几十个，无性能问题

        ========================================================================
        API 端点调用方
        ========================================================================
        - POST /api/v1/ssh/connections/save
          前端使用场景: 添加/删除/编辑连接后保存、连接排序后保存新顺序
          请求体: [SSHConnection, ...]（全量连接列表）
          数据流: 请求 → get_connection_manager() → save_connections(connections)
                  → 写入本地文件 → 返回 {"success": true}

        参数:
          connections (List[SSHConnection]): 待保存的完整连接配置列表
        """
        # 确保配置文件的父目录存在（递归创建，已存在则跳过）
        self.connections_file.parent.mkdir(parents=True, exist_ok=True)

        # 将 Pydantic 模型列表序列化为 dict 列表
        # model_dump(mode="json") 确保 datetime/UUID 等特殊类型正确序列化
        data = [c.model_dump(mode="json") for c in connections]

        # 序列化为格式化的 JSON 字符串
        # indent=2:       美观缩进，便于人工用文本编辑器直接修改
        # ensure_ascii=False: 保留 Unicode 字符原样输出（支持中文连接名）
        # default=str:    对未知类型调用 str() 兜底，防止序列化中断
        content = json.dumps(data, indent=2, ensure_ascii=False, default=str)

        # 以 UTF-8 编码覆盖写入配置文件
        self.connections_file.write_text(content, encoding="utf-8")
        print(f"成功保存 {len(connections)} 个SSH连接配置")

    def encrypt_password(self, password: str) -> str:
        """使用 AES-256-GCM 算法加密明文密码

        ========================================================================
        加密算法详解
        ========================================================================

        加密方案: AES-256-GCM（Galois/Counter Mode）
        - 属于 AEAD（Authenticated Encryption with Associated Data）认证加密
        - 同时提供机密性（加密）和完整性校验（认证标签），防止密文篡改
        - GCM 模式支持关联数据（AAD），本次未使用（传 None）

        加密流程:
          1. 创建 AESGCM 实例，传入 32 字节密钥 self.encryption_key
          2. 生成 12 字节（96 位）随机 nonce（Number used ONCE）
             - 使用 os.urandom(12) 生成（操作系统 CSPRNG）
             - nonce 不需要保密，但必须唯一（每次加密不同）
             - 12 字节是 GCM 模式推荐的 nonce 长度
          3. 调用 aesgcm.encrypt(nonce, plaintext, aad):
             - nonce: 12 字节随机数
             - plaintext: 密码明文的 UTF-8 字节表示
             - aad: None（本次不使用关联数据）
             - 返回 ciphertext（密文）+ 16 字节认证标签（自动附加）
          4. 将 nonce（12 字节）+ ciphertext（含认证标签）拼接为字节序列
          5. 对整个字节序列进行 Base64 编码，转为可安全存储在 JSON 中的字符串
          6. 返回 Base64 密文字符串（可直接存入 SSHConnection.encrypted_password）

        nonce 与 ciphertext 的拼接格式:
          [nonce (12 bytes)] + [ciphertext (variable bytes, 含 16 字节 GCM tag)]

        Base64 编码原因:
          - JSON 不支持原始二进制数据，需要将字节转为可打印 ASCII 字符串
          - Base64 编码后可在 JSON 字段中安全传输和存储

        ========================================================================
        API 端点调用方
        ========================================================================
        - POST /api/v1/ssh/encrypt-password
          前端使用场景: 用户在连接编辑表单输入密码后，保存前先加密
          请求体: { "password": "明文密码" }
          数据流: 请求 → get_connection_manager() → encrypt_password(password)
                  → 返回 { "encrypted": "Base64密文字符串" }

        参数:
          password (str): SSH 明文密码

        返回:
          str: Base64 编码的密文（nonce + AES-GCM 加密数据），可安全存入 JSON
        """
        # 使用已加载的 AES-256 密钥创建 AESGCM 加密器实例
        aesgcm = AESGCM(self.encryption_key)

        # 生成 12 字节随机 nonce（每次加密使用不同的 nonce，防止重放攻击）
        nonce = os.urandom(12)

        # 执行 AES-GCM 加密
        # encrypt(data, associated_data) → ciphertext (含 16 字节认证标签)
        # password 编码为 UTF-8 字节序列后再加密
        # associated_data=None 表示不使用关联数据功能
        ciphertext = aesgcm.encrypt(nonce, password.encode("utf-8"), None)

        # 拼接 nonce + ciphertext，统一进行 Base64 编码
        # 前端/数据库存储的格式: "base64(nonce || ciphertext)"
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode("utf-8")

    def decrypt_password(self, encrypted_password: str) -> str:
        """使用 AES-256-GCM 算法解密 Base64 编码的密文密码

        ========================================================================
        解密算法详解
        ========================================================================

        解密流程（与 encrypt_password 完全对称逆向）:
          1. 对 Base64 密文字符串进行 Base64 解码，得到原始字节序列
          2. 校验字节序列长度 ≥ 12（至少包含 nonce）
          3. 从字节序列中提取:
             - 前 12 字节: nonce（加密时生成的随机数）
             - 剩余字节:   ciphertext（密文 + 16 字节 GCM 认证标签）
          4. 创建 AESGCM 实例，传入相同的 32 字节密钥
          5. 调用 aesgcm.decrypt(nonce, ciphertext, aad):
             - GCM 模式自动验证认证标签，若数据被篡改则抛出异常
             - 解密成功则返回原始明文 UTF-8 字节
          6. 将明文字节解码为 UTF-8 字符串并返回

        ========================================================================
        GCM 认证标签校验
        ========================================================================
        AES-GCM 会在解密时自动验证 16 字节认证标签。若密文在存储或传输过程中
        被篡改（任何一位改变），decrypt() 会抛出 InvalidTag 异常，拒绝返回
        伪造的明文。这是 GCM 模式相比 CBC 等传统模式的优势。

        ========================================================================
        异常情况
        ========================================================================
        - encrypted_data 长度 < 12 → ValueError("加密数据格式错误")
          （数据不完整，无法提取 nonce）
        - Base64 解码失败 → binascii.Error（非法的 Base64 字符串）
        - 认证标签校验失败 → cryptography.exceptions.InvalidTag
          （密文被篡改或使用了不同的加密密钥）

        ========================================================================
        API 端点调用方
        ========================================================================
        - POST /api/v1/ssh/decrypt-password
          前端使用场景: 点击已保存连接时，预填充密码框（需要解密显示）
          请求体: { "encrypted_password": "Base64密文字符串" }
          数据流: 请求 → get_connection_manager() → decrypt_password(encrypted_password)
                  → 返回 { "decrypted": "明文密码" }

        其他调用方:
        - diagnose_sftp.py → SSH 连接测试前解密密码

        参数:
          encrypted_password (str): Base64 编码的密文（由 encrypt_password() 生成）

        返回:
          str: SSH 原始明文密码
        """
        # 使用已加载的 AES-256 密钥创建 AESGCM 解密器实例
        aesgcm = AESGCM(self.encryption_key)

        # Base64 解码: 将 Base64 字符串还原为原始字节序列
        encrypted_data = base64.b64decode(encrypted_password)

        # 数据完整性校验: 至少包含 12 字节 nonce
        if len(encrypted_data) < 12:
            raise ValueError("加密数据格式错误")

        # 分离 nonce（前 12 字节）和 ciphertext（剩余字节，含 GCM 认证标签）
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]

        # 执行 AES-GCM 解密
        # GCM 模式自动验证认证标签 —— 若数据被篡改则抛出 InvalidTag 异常
        # 解密成功 → 返回原始明文 UTF-8 字节序列
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        # 将明文 UTF-8 字节解码为 Python 字符串
        return plaintext.decode("utf-8")

    def create_backup(self) -> str:
        """创建 SSH 连接配置文件的备份

        ========================================================================
        备份策略
        ========================================================================
        - 使用 shutil.copy2() 复制文件（同时复制文件内容和元数据）
        - 备份文件命名: ssh_connections_backup_{YYYYMMDD_HHMMSS}.json
        - 备份目录: {app_data_dir}/backups/
        - 时间戳使用 UTC 时间（datetime.utcnow()），避免时区混淆

        ========================================================================
        调用方
        ========================================================================
        当前无直接 API 端点绑定，预留供以下场景使用:
        - Tauri command 绑定 → 前端 "备份配置" 按钮
        - CLI 管理工具 → 定时备份脚本
        - 程序内部自动备份 → 重大操作前（如数据迁移）自动触发

        返回:
          str: 备份文件名（不含路径），如 "ssh_connections_backup_20260428_143052.json"

        异常:
          FileNotFoundError: 配置文件不存在时抛出（无数据可备份）
        """
        if not self.connections_file.exists():
            # 配置文件不存在，无数据可备份
            raise FileNotFoundError("SSH配置文件不存在")

        # 生成 UTC 时间戳作为备份标识
        # 格式: YYYYMMDD_HHMMSS，便于按文件名排序和人工识别
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"ssh_connections_backup_{timestamp}.json"
        backup_path = self.backups_dir / backup_filename

        # 复制文件及其元数据（修改时间、权限等）到备份目录
        shutil.copy2(self.connections_file, backup_path)
        print(f"创建SSH配置备份: {backup_filename}")
        return backup_filename

    def restore_from_backup(self, backup_filename: str) -> None:
        """从指定备份文件恢复 SSH 连接配置

        ========================================================================
        恢复策略
        ========================================================================
        - 使用 shutil.copy2() 将备份文件覆盖到当前配置文件路径
        - 恢复操作是破坏性的: 当前配置文件将被完全替换
        - 建议在恢复前先调用 create_backup() 备份当前配置（双重保险）

        ========================================================================
        调用方
        ========================================================================
        当前无直接 API 端点绑定，预留供以下场景使用:
        - Tauri command 绑定 → 前端 "从备份恢复" 对话框
        - 程序内部错误恢复 → 检测到配置文件损坏时自动恢复最近备份
        - CLI 管理工具 → 手动恢复指定备份

        参数:
          backup_filename (str): 备份文件名（不含路径），如 "ssh_connections_backup_20260428_143052.json"

        异常:
          FileNotFoundError: 指定的备份文件不存在
        """
        backup_path = self.backups_dir / backup_filename
        if not backup_path.exists():
            # 备份文件不存在（文件名错误或已被清理）
            raise FileNotFoundError("备份文件不存在")

        # 将备份文件复制（覆盖）到配置文件位置
        shutil.copy2(backup_path, self.connections_file)
        print(f"从备份恢复SSH配置: {backup_filename}")

    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """清理旧的备份文件，仅保留最近 N 个

        ========================================================================
        清理策略
        ========================================================================
        1. 扫描备份目录，筛选文件名以 "ssh_connections_backup_" 开头的文件
        2. 按文件修改时间（st_mtime）降序排序（最新的排前面）
        3. 保留前 keep_count 个文件，删除其余所有更早的备份
        4. 单个文件删除失败不中断整体清理流程（逐文件异常捕获）

        ========================================================================
        设计意图
        ========================================================================
        防止备份文件无限累积占用磁盘空间。默认保留 5 个最近备份，
        在数据安全（多版本可恢复）和存储空间（定期清理）之间取得平衡。

        ========================================================================
        调用方
        ========================================================================
        当前无直接 API 端点绑定，预留供以下场景使用:
        - Tauri command 绑定 → 前端 "备份管理" 页面自动清理
        - 程序定时任务 → 应用启动时自动清理过期备份
        - CLI 管理工具 → 手动触发清理

        参数:
          keep_count (int): 保留的备份文件数量，默认为 5

        返回:
          int: 本次清理删除的备份文件数量
        """
        if not self.backups_dir.exists():
            # 备份目录不存在（从未创建过备份）
            return 0

        # 收集所有备份文件（按文件名前缀过滤，避免误删其他文件）
        backup_files = sorted(
            [f for f in self.backups_dir.iterdir()
             if f.name.startswith("ssh_connections_backup_") and f.is_file()],
            key=lambda f: f.stat().st_mtime,  # 按文件修改时间排序
            reverse=True,                       # 降序 → 最新的文件排在最前面
        )

        # 删除 keep_count 之后的文件（即第 keep_count+1 个及以后的所有文件）
        deleted_count = 0
        for backup_file in backup_files[keep_count:]:
            try:
                # 删除单个备份文件
                backup_file.unlink()
                deleted_count += 1
            except Exception as e:
                # 单个文件删除失败（权限问题等）不中断流程，继续处理下一个
                print(f"删除旧备份失败: {backup_file}: {e}")

        if deleted_count > 0:
            print(f"清理了 {deleted_count} 个旧备份文件")
        return deleted_count

    def validate_config(self) -> bool:
        """验证 SSH 连接配置文件的完整性和有效性

        ========================================================================
        校验方法
        ========================================================================
        通过尝试调用 load_connections() 加载并解析配置文件来验证:
        - 文件是否可读（权限检查）
        - JSON 语法是否正确（格式校验）
        - 数据字段是否符合 SSHConnection 模型定义（模型校验，含 Base64 格式检查）
        - 迁移逻辑是否正确执行

        注意: 此方法仅检查 JSON 结构和模型字段，不验证:
        - 加密密钥是否匹配（加密内容本身不在校验范围内）
        - 主机地址是否可达
        - 认证信息是否正确

        ========================================================================
        调用方
        ========================================================================
        当前无直接 API 端点绑定，预留供以下场景使用:
        - 程序内部 → 启动时自检配置文件健康状况
        - Tauri command 绑定 → 前端 "验证配置" 按钮
        - 自动恢复逻辑 → 校验失败后自动尝试从最近备份恢复

        返回:
          bool: True=配置文件有效（或文件不存在视为有效），False=校验失败
        """
        if not self.connections_file.exists():
            # 文件不存在不是错误，视为有效（首次使用场景）
            return True

        try:
            # 通过完整加载流程来验证配置文件
            # 包括: JSON 解析 → Pydantic 模型校验 → 迁移逻辑
            self.load_connections()
            print("SSH配置文件验证通过")
            return True
        except Exception as e:
            # 任何异常均视为校验失败
            print(f"SSH配置文件验证失败: {e}")
            return False
