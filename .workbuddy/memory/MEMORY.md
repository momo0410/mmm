# 项目长期记忆

## 项目架构
- 渗透测试 Agent 系统：`src-python/app/services/pentest_agent/` 是核心
  - `agent.py` — 主循环（构建 prompt → 调 LLM → 解析计划 → 执行任务 → 更新阶段）
  - `executor.py` — 工具执行器（shell 命令、交互式会话）
  - `tool_registry.py` — 工具注册表（静态 + 动态扫描 + skill 注入）
  - `capabilities.py` — 任务能力推断
  - `llm_client.py` — OpenAI/DeepSeek/Qwen 兼容 LLM 客户端
- Skill 引擎：`src-python/app/services/skill_engine/`
  - `skill_loader.py` — 统一加载 SKILL.md + skill.json
  - `skill_matcher.py` — 关键词/服务指纹/domain 匹配，注入 prompt
  - `skill_md_parser.py` — 解析 v2.0 五段式 SKILL.md（需 PyYAML）
  - `skill_generator.py` — 自升级闭环，LLM 生成 v2.0 skill
- 联网检索（2026-06-22 新增）：`src-python/app/services/online_search/`
  - `registry.py` — OnlineSearchService 统一入口 + 预算/去重/兜底
  - `nvd_client.py` — NVD REST API v2.0（stdlib urllib，限流+重试）
  - `cache.py` — 三级缓存（L1 内存/L2 磁盘7天/L3 永久 knowledge_base）
  - `msf_module_client.py` — MSF 模块文档（离线KB + Rapid7）
  - `default_creds_client.py` — 默认密码（内置数据集 + cirt.net）

## Skill v2.0 五段式结构
SKILL.md 必须含：Principle / Detection Fingerprint / Workflow / Failure Modes / Generalization / Key Concepts
- 位于 `skills/builtin/`（手写）、`skills/exploit-skills/`（17个）、`skills/learned/`（自学习）

## 联网检索设计要点（handoff-03）
- 4 个工具：search_cve / search_exploit / lookup_msf_module / lookup_default_creds
- 工具 kind="online_search"，agent.py 拦截路由到 OnlineSearchService，不走 executor.run()
- 本地 skill 优先，联网是补充；联网结果通过自升级闭环反哺成本地 skill
- 离线 100% 可用：失败返回 error，不中断流程
- 预算：默认每次渗透 10 次联网查询，同一查询去重

## 依赖
- managed Python: `C:\Users\T1367\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 已装：pyyaml, httpx
- venv 未创建（当前用全局 site-packages）

## 文档位置
- 交接文档：`docs/handoff-00~03-*.md`
- NVD 反查脚本：`scripts/verify_skills_with_nvd.py`（--fix 模式自动修正 Principle）
