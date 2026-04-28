# 审计日志持久化

## 概述

审计日志持久化模块将所有 Agent 执行事件记录到 SQLite 数据库，支持历史查询、审计追踪和数据分析。

## 文件位置

- **核心实现**: `src-python/app/services/agent/audit_store.py`
- **数据库文件**: `src-python/data/audit_log.db`（运行时自动创建）
- **API路由**: `src-python/app/routers/api.py`（底部审计日志查询段）

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentOrchestrator                         │
│                      ↓ 集成点                               │
│              AuditLogger (审计日志记录器)                    │
│                      ↓                                      │
│              AuditStore (SQLite存储)                         │
│                      ↓                                      │
│          data/audit_log.db (审计日志数据库)                  │
└─────────────────────────────────────────────────────────────┘
```

## 数据模型

### AuditRecord（审计记录）

```python
{
    "event_id": "uuid",              # 事件唯一ID
    "event_type": "task_start",      # 事件类型
    "task_id": "uuid",               # 所属任务ID
    "step_id": "uuid",               # 步骤ID（可选）
    "step_number": 1,                # 步骤序号（可选）
    "skill_name": "ssh_audit",       # 技能名称（可选）
    "tool_name": "detect_ssh",       # 工具名称（可选）
    "risk_level": "high",            # 风险等级（可选）
    "is_mutation": false,            # 是否变更操作
    "status": "completed",           # 执行状态
    "duration_ms": 1234,             # 耗时（毫秒）
    "error": null,                   # 错误信息（可选）
    "user_id": "user-123",           # 用户ID（可选）
    "execution_mode": "host_runtime", # 执行模式
    "timestamp": 1714000000.0,       # 时间戳
    "details": {...}                 # 详细信息（JSON）
}
```

### 事件类型清单

| 事件类型 | 说明 | 记录时机 |
|---------|------|---------|
| `task_start` | 任务开始 | Orchestrator.run() 入口 |
| `task_end` | 任务结束 | Orchestrator.run() 出口 |
| `step_start` | 步骤开始 | Executor 执行步骤前 |
| `step_end` | 步骤结束 | Executor 执行步骤后 |
| `skill_invocation` | 技能调用 | 技能被调用时 |
| `tool_execution` | 工具执行 | 工具被执行时 |
| `policy_evaluation` | 策略评估 | PolicyGuard 评估后 |
| `approval_request` | 审批请求 | 需要审批时 |
| `approval_response` | 审批响应 | 审批结果返回时 |
| `budget_exceeded` | 预算超限 | 预算耗尽时 |
| `error_occurred` | 错误发生 | 异常捕获时 |
| `rollback_initiated` | 回滚开始 | 回滚启动时 |
| `rollback_completed` | 回滚完成 | 回滚完成后 |

## API端点

### 1. 列出所有任务

```
GET /api/v1/audit/tasks
```

**响应**:
```json
{
  "tasks": [
    {
      "task_id": "uuid",
      "start_time": 1714000000.0,
      "end_time": 1714000100.0,
      "event_count": 25,
      "execution_mode": "host_runtime"
    }
  ]
}
```

### 2. 获取任务审计详情

```
GET /api/v1/audit/tasks/{task_id}
GET /api/v1/audit/tasks/{task_id}?event_type=step_end
```

**响应**:
```json
{
  "task_id": "uuid",
  "summary": {
    "total_events": 25,
    "total_steps": 5,
    "completed_steps": 4,
    "failed_steps": 1,
    "mutation_steps": 2,
    "high_risk_steps": 1,
    "avg_duration_ms": 234.5,
    "total_duration_ms": 1172,
    "start_time_iso": "2026-04-22T10:00:00+00:00",
    "end_time_iso": "2026-04-22T10:01:40+00:00",
    "duration_seconds": 100.0
  },
  "events": [...]
}
```

### 3. 获取任务执行时间线

```
GET /api/v1/audit/tasks/{task_id}/timeline
```

### 4. 获取变更操作审计

```
GET /api/v1/audit/tasks/{task_id}/mutations
```

### 5. 高级审计查询

```
POST /api/v1/audit/query
```

**请求体**:
```json
{
  "event_type": "tool_execution",
  "skill_name": "ssh_audit",
  "risk_level": "high",
  "is_mutation": true,
  "status": "completed",
  "start_time": 1714000000.0,
  "end_time": 1714100000.0,
  "limit": 100,
  "offset": 0
}
```

### 6. 获取错误事件

```
GET /api/v1/audit/errors
GET /api/v1/audit/errors?task_id=xxx&limit=50
```

### 7. 清理旧审计日志

```
DELETE /api/v1/audit/cleanup?max_age_days=90
```

## 代码集成点

### Orchestrator 集成

在 `orchestrator.py` 的 `run()` 方法中：

```python
# 任务开始时记录
self.audit_logger = AuditLogger(user_id=request.context.get("user_id"))
self.audit_logger.log_task_start(
    task_id=request.id,
    task=request.task,
    execution_mode=request.context.get("execution_mode"),
    skills=request.skills,
)

# 任务结束时记录
self.audit_logger.log_task_end(
    task_id=request.id,
    status=task_status,
    duration_ms=task_duration_ms,
)
```

### 手动记录审计事件

```python
from app.services.agent.audit_store import AuditLogger, AuditRecord, AuditEventType

# 创建审计日志记录器
logger = AuditLogger(user_id="user-123")

# 记录步骤开始
logger.log_step_start(
    task_id="task-001",
    step_id="step-001",
    step_number=1,
    skill_name="ssh_audit",
    tool_name="detect_ssh",
    risk_level="low",
    is_mutation=False,
)

# 记录步骤结束
logger.log_step_end(
    task_id="task-001",
    step_id="step-001",
    step_number=1,
    status="completed",
    duration_ms=1234,
)

# 记录策略评估
logger.log_policy_evaluation(
    task_id="task-001",
    step_id="step-001",
    decision="allowed",
    risk_level="low",
    reason="低风险只读操作",
)
```

## 数据库查询示例

```bash
# 查看表结构
sqlite3 src-python/data/audit_log.db ".schema audit_events"

# 查看最近10条记录
sqlite3 src-python/data/audit_log.db \
  "SELECT event_type, task_id, timestamp FROM audit_events ORDER BY timestamp DESC LIMIT 10;"

# 统计任务数量
sqlite3 src-python/data/audit_log.db \
  "SELECT COUNT(DISTINCT task_id) FROM audit_events;"

# 查看错误事件
sqlite3 src-python/data/audit_log.db \
  "SELECT task_id, step_id, error FROM audit_events WHERE error IS NOT NULL;"

# 清理90天前的数据
sqlite3 src-python/data/audit_log.db \
  "DELETE FROM audit_events WHERE timestamp < strftime('%s', 'now', '-90 days');"
```

## 启用步骤

1. **无需额外配置**，审计日志在任务执行时自动记录
2. 确保 `data/` 目录存在（运行时自动创建）
3. 数据库路径可通过 `AuditStore(db_path="custom/path/audit.db")` 自定义

## 测试

```bash
cd src-python
pytest tests/agent/unit/test_rbac.py -v
```

*文档生成时间：2026-04-22*
