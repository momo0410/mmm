# 新功能启用指南

## 概述

本文档提供本轮升级后7个新功能的详细启用步骤。所有功能默认**已实现但未启用**，可按需逐步启用。

## 启用优先级

```
Phase 1 (立即可用)
├── 1. 审计日志持久化
├── 2. 回滚引擎
└── 3. RBAC权限系统（基础）

Phase 2 (需要配置)
├── 4. 自适应规划器
└── 5. 前端DAG可视化

Phase 3 (需要开发)
├── 6. Skill Spec v2执行器支持
└── 7. CI/CD Benchmark触发
```

---

## 1. 审计日志持久化

**状态**: ✅ 已启用（自动）

**说明**: 审计日志在任务执行时自动记录，无需额外配置。

**验证方法**:

```bash
# 执行一个Agent任务后，查看审计日志
sqlite3 src-python/data/audit_log.db "SELECT COUNT(*) FROM audit_events;"

# 查看最近的事件
sqlite3 src-python/data/audit_log.db \
  "SELECT event_type, task_id, timestamp FROM audit_events ORDER BY timestamp DESC LIMIT 5;"
```

**API测试**:

```bash
# 列出所有任务
curl http://localhost:8000/api/v1/audit/tasks

# 获取任务详情
curl http://localhost:8000/api/v1/audit/tasks/{task_id}

# 高级查询
curl -X POST http://localhost:8000/api/v1/audit/query \
  -H "Content-Type: application/json" \
  -d '{"event_type": "tool_execution", "limit": 10}'
```

**无需修改任何代码**。

---

## 2. 回滚引擎

**状态**: ✅ 已启用（自动）

**说明**: 回滚引擎已全局可用，通过API调用。

**启用步骤**:

1. 执行包含变更操作的任务
2. 调用预览API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/rollback/preview \
     -H "Content-Type: application/json" \
     -d '{"task_id": "xxx"}'
   ```
3. 确认后执行回滚:
   ```bash
   curl -X POST http://localhost:8000/api/v1/rollback/execute \
     -H "Content-Type: application/json" \
     -d '{"task_id": "xxx"}'
   ```

**前端集成**（待实现）:
- 在任务详情页添加"预览回滚"按钮
- 显示回滚预览结果
- 用户确认后调用执行API

---

## 3. RBAC权限系统

**状态**: ✅ 已启用（基础），⚠️ 用户管理待实现

**说明**: RBAC已集成到Executor，但需要创建用户才能生效。

### 最小启用步骤

1. **创建初始用户**:

```python
# 在 src-python/app/main.py 或初始化脚本中
from app.services.agent.rbac import get_rbac_manager

rbac = get_rbac_manager()

# 创建管理员
admin = rbac.create_user("admin", "default", roles=["system_admin"])
print(f"Admin user_id: {admin.id}")

# 创建普通用户
user = rbac.create_user("operator1", "default", roles=["operator"])
print(f"Operator user_id: {user.id}")
```

2. **在请求中传入 user_id**:

```json
{
  "task": "检查SSH安全",
  "context": {
    "user_id": "用户ID",
    "execution_mode": "host_runtime"
  }
}
```

3. **验证**:
   - 如果用户有权限，任务正常执行
   - 如果用户无权限，返回错误: `"权限不足：用户 xxx 无权执行工具 yyy"`

### 完整启用步骤（推荐）

1. 实现用户管理API（参考 [rbac.md](./rbac.md) 的API设计）
2. 实现前端用户管理界面
3. 实现用户登录和user_id获取
4. 在所有AgentRequest中自动传入user_id

### 当前行为

- **如果请求中没有user_id**: 跳过权限检查，正常执行
- **如果有user_id但无角色**: 权限检查失败，任务被拒绝
- **如果有user_id且有角色**: 根据角色权限决定是否允许执行

---

## 4. 自适应规划器

**状态**: ⚠️ 已实现，待集成

**说明**: 自适应规划器已实现，但Orchestrator尚未使用。

### 启用步骤

1. **修改 Orchestrator**:

在 `src-python/app/services/agent/orchestrator.py` 的 `__init__` 方法中：

```python
from .adaptive_planner import AdaptivePlanner, AdaptivePlannerConfig

# 原代码:
# self.planner = create_planner(planner_config)

# 修改为:
base_planner = create_planner(planner_config)
self.planner = AdaptivePlanner(
    base_planner,
    AdaptivePlannerConfig(
        min_success_rate=0.7,
        max_skills_per_task=5,
    )
)
```

2. **在任务完成后记录反馈**:

在 `orchestrator.py` 的 `run()` 方法末尾：

```python
from .adaptive_planner import ExecutionFeedback

# 在 return final_report 之前
if hasattr(self, 'planner') and isinstance(self.planner, AdaptivePlanner):
    for step_exec in getattr(execution_result, 'step_executions', []):
        feedback = ExecutionFeedback(
            task_id=request.id,
            skill_name=getattr(step_exec, 'skill_id', '') or getattr(step_exec, 'tool_name', ''),
            success=getattr(step_exec, 'status') == 'completed',
            duration_ms=getattr(step_exec, 'duration_ms', 0),
        )
        self.planner.record_execution_feedback(feedback)
```

3. **（可选）持久化统计数据**:

```python
import pickle

# 保存
with open("data/adaptive_planner_stats.pkl", "wb") as f:
    pickle.dump(self.planner._scorer._stats, f)

# 加载（在Orchestrator初始化时）
try:
    with open("data/adaptive_planner_stats.pkl", "rb") as f:
        self.planner._scorer._stats = pickle.load(f)
except FileNotFoundError:
    pass
```

### 验证方法

```python
# 执行多个任务后，查看性能报告
report = orchestrator.planner.get_performance_report()
print(report)
```

---

## 5. 前端DAG可视化

**状态**: ⚠️ 已实现，待集成

**说明**: 前端组件已实现，但未集成到主UI。

### 启用步骤

1. **在导航配置中添加入口**:

修改 `src/modules/ui/navigationConfig.ts`:

```typescript
export const navigationItems = [
  // ... 现有导航项
  {
    id: 'audit-log',
    label: '审计日志',
    icon: '📋',
    page: 'audit-log'
  }
];
```

2. **在渲染器中注册页面**:

修改 `src/modules/ui/modernUIRenderer.ts`:

```typescript
import { dashboard } from '../modules/ui/executionDashboard';

// 在页面渲染逻辑中添加
case 'audit-log':
  dashboard.init(container);
  break;
```

3. **在AI指挥台中添加回滚入口**:

修改 `src/modules/ai/aiCommandCenterRendererV2.ts`:

```typescript
// 在任务完成后显示回滚按钮
if (result.has_mutations) {
  const rollbackBtn = document.createElement('button');
  rollbackBtn.textContent = '预览回滚';
  rollbackBtn.onclick = () => {
    window.location.href = `#/audit-log?task=${result.task_id}`;
  };
  actionsContainer.appendChild(rollbackBtn);
}
```

### 替代方案（快速集成）

如果不想修改现有UI，可以创建独立页面：

```html
<!-- audit-log.html -->
<!DOCTYPE html>
<html>
<head>
  <title>审计日志</title>
  <script src="modules/ui/executionDashboard.js"></script>
</head>
<body>
  <div id="dashboard"></div>
  <script>
    dashboard.init(document.getElementById('dashboard'));
  </script>
</body>
</html>
```

---

## 6. Skill Spec v2

**状态**: ⚠️ 规范已定义，执行器待支持

**说明**: v2规范已实现，但执行器尚未支持控制流（条件分支、循环、并行）。

### 当前兼容性

- v2规范完全向后兼容v1
- 未使用控制流的步骤与v1行为一致
- 可以开始使用v2格式定义技能

### 后续启用步骤

1. **修改执行器识别控制流**:

在 `executor.py` 中添加控制流处理逻辑：

```python
async def execute_step(self, step, context):
    if step.control_flow == ControlFlowType.CONDITIONAL:
        return await self._execute_conditional(step, context)
    elif step.control_flow == ControlFlowType.LOOP:
        return await self._execute-loop(step, context)
    elif step.control_flow == ControlFlowType.PARALLEL:
        return await self._execute-parallel(step, context)
    else:
        # 原有逻辑
        return await self._execute-normal(step, context)
```

2. **实现条件评估**:

```python
async def _execute_conditional(self, step, context):
    for branch in step.branches:
        if branch.condition.evaluate(context):
            for nested_step in branch.steps:
                await self.execute_step(nested_step, context)
            break
```

3. **实现循环执行**:

```python
async def _execute-loop(self, step, context):
    loop_config = step.loop
    for i in range(loop_config.max_iterations):
        # 设置循环变量
        context[loop_config.variable] = ...
        
        # 执行循环体
        for nested_step in loop_config.steps:
            await self.execute_step(nested_step, context)
        
        # 检查终止条件
        if loop_config.until_condition and loop_config.until_condition.evaluate(context):
            break
```

4. **实现并行执行**:

```python
async def _execute-parallel(self, step, context):
    parallel = step.parallel
    semaphore = asyncio.Semaphore(parallel.max_concurrency)
    
    async def run-step(s):
        async with semaphore:
            await self.execute_step(s, context)
    
    tasks = [run-step(s) for s in parallel.steps]
    await asyncio.gather(*tasks)
```

---

## 7. CI/CD Benchmark

**状态**: ✅ 已实现，待触发

**说明**: GitHub Actions工作流已定义，推送代码即可触发。

### 启用步骤

1. **确保GitHub Actions已启用**:
   - 进入仓库 Settings → Actions
   - 确认 "Allow all actions" 或 "Allow selected actions" 已启用

2. **推送代码到main分支或创建PR**:
   ```bash
   git push origin main
   # 或创建PR
   ```

3. **查看运行结果**:
   - 进入仓库 Actions 页面
   - 查看 "Benchmark Regression Gate" 工作流

### 本地测试

```bash
cd src-python
pip install pytest-benchmark
pytest tests/agent/test_benchmark_runner.py -v --benchmark-only
```

---

## 启用检查清单

| 功能 | 代码状态 | 配置要求 | 验证方法 | 状态 |
|------|---------|---------|---------|------|
| 审计日志 | ✅ 已集成 | 无 | 查看数据库 | 已启用 |
| 回滚引擎 | ✅ 已集成 | 无 | 调用API | 已启用 |
| RBAC权限 | ✅ 已集成 | 创建用户 | 请求中传user_id | 基础启用 |
| 自适应规划器 | ✅ 已实现 | 修改Orchestrator | 查看性能报告 | 待集成 |
| 前端DAG | ✅ 已实现 | 集成到UI | 访问审计日志页 | 待集成 |
| Skill Spec v2 | ✅ 规范已定义 | 修改Executor | 执行v2技能 | 待开发 |
| CI/CD Benchmark | ✅ 已定义 | 推送代码 | 查看Actions | 待触发 |

---

## 快速验证脚本

```bash
#!/bin/bash
# 验证新功能是否正常工作

echo "=== 验证审计日志 ==="
sqlite3 src-python/data/audit_log.db "SELECT COUNT(*) as event_count FROM audit_events;"

echo "=== 验证RBAC ==="
cd src-python
python -c "
from app.services.agent.rbac import get_rbac_manager
rbac = get_rbac_manager()
print(f'预定义角色数: {len(rbac.list_roles())}')
"

echo "=== 验证回滚引擎 ==="
python -c "
from app.services.agent.rollback_engine import get_rollback_engine
engine = get_rollback_engine()
print(f'回滚引擎已初始化')
"

echo "=== 验证自适应规划器 ==="
python -c "
from app.services.agent.adaptive_planner import AdaptivePlanner, AdaptivePlannerConfig
from app.services.agent.planner import RuleBasedPlanner, PlannerConfig
config = PlannerConfig()
base = RuleBasedPlanner(config)
planner = AdaptivePlanner(base)
print(f'自适应规划器已创建')
"

echo "=== 验证完成 ==="
```

*文档生成时间：2026-04-22*
