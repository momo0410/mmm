# 新功能文档索引

> 本文档收录了系统升级后新增的功能模块，所有功能默认未启用，后续可按需启用。

## 功能模块清单

| 序号 | 模块 | 文档 | 状态 |
|------|------|------|------|
| 1 | 审计日志持久化 | [audit-log.md](./audit-log.md) | 待启用 |
| 2 | RBAC权限系统 | [rbac.md](./rbac.md) | 待启用 |
| 3 | 自动回滚引擎 | [rollback-engine.md](./rollback-engine.md) | 待启用 |
| 4 | 自适应规划器 | [adaptive-planner.md](./adaptive-planner.md) | 待启用 |
| 5 | Skill Spec v2 | [skill-spec-v2.md](./skill-spec-v2.md) | 待启用 |
| 6 | 前端DAG可视化 | [frontend-dag.md](./frontend-dag.md) | 待启用 |
| 7 | CI/CD Benchmark | [benchmark-gate.md](./benchmark-gate.md) | 待启用 |

## 启用指南

详细启用步骤请参考：[enable-guide.md](./enable-guide.md)

## 架构变更

```
安全自动化平台 (Before)
├── Planner
├── Executor
├── Skills
├── Tools
├── Research
└── Reporting

安全自治平台 (After)
├── Planner
│   ├── RuleBasedPlanner
│   ├── LLMPlanner
│   └── AdaptivePlanner  [NEW]
├── Executor
│   ├── 权限检查 [NEW]
│   └── 执行安全
├── Skills
│   ├── Spec v1
│   └── Spec v2 [NEW]
├── Tools
├── Research
├── Reporting
│   └── 审计日志记录 [NEW]
├── AuditStore [NEW]
├── RBACManager [NEW]
└── RollbackEngine [NEW]
```

*文档生成时间：2026-04-22*
