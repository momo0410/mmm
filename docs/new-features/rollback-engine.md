# 自动回滚引擎

## 概述

自动回滚引擎用于撤销 Agent 执行的变更操作（mutation），支持回滚预览和回滚执行两种模式，确保所有变更操作都是可逆的。

## 文件位置

- **核心实现**: `src-python/app/services/agent/rollback_engine.py`
- **API路由**: `src-python/app/routers/api.py`（底部回滚引擎段）
- **单元测试**: `src-python/tests/agent/unit/test_rollback_engine.py`（10项测试）

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    变更操作执行                               │
│                      ↓                                      │
│            审计日志记录 (mutation=true)                      │
│                      ↓                                      │
│            RollbackEngine (回滚引擎)                         │
│                      ↓                                      │
│        回滚命令生成 → 规则匹配/预览提取                       │
│                      ↓                                      │
│        回滚执行 → 工具调用/状态记录                           │
└─────────────────────────────────────────────────────────────┘

回滚规则:
  1. 服务控制: systemctl start → systemctl stop
  2. 文件写入: write → restore from backup
  3. 配置补丁: patch → restore original
  4. 用户管理: useradd → userdel
```

## API端点

### 1. 预览回滚操作

```
POST /api/v1/rollback/preview
```

**请求体**:
```json
{
  "task_id": "task-xxx",
  "mode": "preview",
  "step_ids": []
}
```

**响应**:
```json
{
  "rollback_id": "rb-uuid",
  "task_id": "task-xxx",
  "status": "completed",
  "steps": [
    {
      "step_id": "step-1",
      "step_number": 1,
      "status": "pending",
      "rollback_command": {
        "command": "systemctl stop nginx",
        "description": "停止服务 nginx",
        "parameters": {},
        "timeout_seconds": 30
      },
      "result": "预览：将执行回滚命令 systemctl stop nginx"
    }
  ],
  "started_at": 1714000000.0,
  "completed_at": 1714000000.1,
  "total_duration_ms": 100,
  "error": null
}
```

### 2. 执行回滚操作

```
POST /api/v1/rollback/execute
```

**请求体**:
```json
{
  "task_id": "task-xxx",
  "mode": "execute"
}
```

**响应**: 同预览模式，但 `status` 为 `completed`/`failed`/`partially_completed`

### 3. 获取回滚历史

```
GET /api/v1/rollback/history/{task_id}
```

### 4. 获取特定回滚结果

```
GET /api/v1/rollback/result/{rollback_id}
```

## 回滚规则

### 内置回滚规则

| 规则名称 | 匹配条件 | 回滚动作 |
|---------|---------|---------|
| 服务控制 | `systemctl start X` | `systemctl stop X` |
| 服务控制 | `systemctl stop X` | `systemctl start X` |
| 服务控制 | `systemctl restart X` | `systemctl restart X` |
| 文件写入 | `file_write` 工具 | `cp backup_path file_path` |
| 配置补丁 | `config_patch` 工具 | `cp backup_path file_path` |
| 用户管理 | `useradd X` | `userdel -r X` |
| 用户管理 | `userdel X` | `useradd X` |

### 优先级

1. **回滚预览**：如果步骤有 `rollback_preview.commands`，直接使用
2. **规则匹配**：按上述规则自动回滚命令
3. **手动提示**：如果有 `expected_side_effects`，提示手动处理
4. **无法回滚**：返回 `null`，表示无法自动生成回滚命令

## 代码使用

### 基础使用

```python
from app.services.agent.rollback_engine import (
    get_rollback_engine,
    RollbackMode,
    RollbackStatus,
)

engine = get_rollback_engine()

# 获取变更操作步骤
step_executions = [
    {
        "step_id": "step-1",
        "step_number": 1,
        "tool_name": "execute_command",
        "parameters": {"command": "systemctl start nginx"},
        "is_mutation": True,
        "status": "completed",
    }
]

# 预览回滚
preview = await engine.preview_rollback("task-xxx", step_executions)
for step in preview.steps:
    print(f"回滚命令: {step.rollback_command.command}")

# 执行回滚
result = await engine.execute_rollback("task-xxx", step_executions)
print(f"回滚状态: {result.status}")
```

### 生成回滚命令

```python
# 手动生成回滚命令
step_exec = {
    "step_id": "step-1",
    "parameters": {"command": "systemctl start nginx"},
    "is_mutation": True,
    "status": "completed",
}
cmd = engine._generate_rollback_command(step_exec)
print(cmd.command)  # systemctl stop nginx
```

### 回滚历史查询

```python
# 获取任务的回滚历史
history = engine.get_rollback_history("task-xxx")

# 获取特定回滚结果
result = engine.get_rollback_result("rb-uuid")
```

## 前端交互流程

```
用户执行任务
    ↓
任务包含变更操作 (mutation=true)
    ↓
前端显示"预览回滚"按钮
    ↓
调用 POST /rollback/preview
    ↓
展示回滚预览：
  - 回滚命令列表
  - 预期副作用
  - 回滚说明
    ↓
用户确认回滚
    ↓
调用 POST /rollback/execute
    ↓
展示回滚结果：
  - 成功/失败状态
  - 回滚耗时
  - 错误信息（如有）
```

## 回滚状态

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行（预览模式） |
| `running` | 正在执行 |
| `completed` | 全部成功 |
| `failed` | 全部失败 |
| `partially_completed` | 部分成功 |

## 启用步骤

1. **无需额外配置**，回滚引擎已全局可用
2. 任务执行后，通过 API 查询变更操作并调用回滚
3. 前端添加"预览回滚"和"确认回滚"按钮

## 注意事项

- 回滚依赖步骤执行时产生的 `rollback_preview` 或 `backup_path`
- 部分操作无法自动回滚，需要手动处理
- 回滚引擎仅回滚 `is_mutation=true` 且 `status=completed` 的步骤
- 回滚顺序与执行顺序相反（后执行的先回滚）

## 测试

```bash
cd src-python
pytest tests/agent/unit/test_rollback_engine.py -v
```

预期输出：`10 passed`

*文档生成时间：2026-04-22*
