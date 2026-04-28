# 自适应规划器

## 概述

自适应规划器（AdaptivePlanner）根据历史执行反馈动态调整技能选择策略，通过评分系统优化任务规划质量。

## 文件位置

- **核心实现**: `src-python/app/services/agent/adaptive_planner.py`

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    AdaptivePlanner                           │
│                                                              │
│  BasePlanner ──→ plan() ──→ _adapt_plan() ──→ 优化后的Plan  │
│                      ↑                    ↓                  │
│                      │              SkillScorer              │
│                      │                    ↓                  │
│               执行反馈记录      成功率/性能/时效性评分         │
└─────────────────────────────────────────────────────────────┘

评分公式:
  total_score = 0.5 * success_rate
              + 0.3 * performance_score
              + 0.2 * recency_score

降级规则:
  - success_rate < 70%  → score × 0.5
  - failure_count >= 3  → score × 0.3
```

## 核心组件

### SkillScorer（技能评分器）

```python
from app.services.agent.adaptive_planner import SkillScorer, AdaptivePlannerConfig

config = AdaptivePlannerConfig(
    min_success_rate=0.7,        # 最低成功率阈值
    max_failure_threshold=3,     # 最大失败次数
    performance_weight=0.3,      # 性能权重
    success_rate_weight=0.5,     # 成功率权重
    recency_weight=0.2,          # 时效性权重
    lookback_window_seconds=3600, # 回溯窗口（1小时）
    max_skills_per_task=5,       # 每个任务最大技能数
)

scorer = SkillScorer(config)
```

### 评分维度

| 维度 | 计算方式 | 权重 |
|------|---------|------|
| 成功率 | `success_count / total_invocations` | 50% |
| 性能 | `1 - (avg_duration_ms / 10000)` | 30% |
| 时效性 | `1 - (recency / lookback_window)` | 20% |

## 代码使用

### 创建自适应规划器

```python
from app.services.agent.adaptive_planner import AdaptivePlanner, AdaptivePlannerConfig
from app.services.agent.planner import RuleBasedPlanner, PlannerConfig

# 创建基础规划器
base_planner = RuleBasedPlanner(PlannerConfig())

# 创建自适应规划器
adaptive_planner = AdaptivePlanner(
    base_planner=base_planner,
    config=AdaptivePlannerConfig(
        min_success_rate=0.7,
        max_skills_per_task=5,
    )
)
```

### 记录执行反馈

```python
from app.services.agent.adaptive_planner import ExecutionFeedback

feedback = ExecutionFeedback(
    task_id="task-001",
    skill_name="ssh_audit",
    success=True,
    duration_ms=1234,
    context={"execution_mode": "host_runtime"},
)

adaptive_planner.record_execution_feedback(feedback)
```

### 记录任务完成

```python
adaptive_planner.record_task_completion(
    request=request,
    plan=plan,
    execution_result={"status": "completed"},
)
```

### 自适应规划

```python
plan = await adaptive_planner.plan(request, skills, context)
# plan.steps 会根据历史反馈自动调整和排序
```

### 获取性能报告

```python
report = adaptive_planner.get_performance_report()
print(report)
# {
#   "total_skills_tracked": 10,
#   "skills": {
#     "ssh_audit": {
#       "total_invocations": 50,
#       "success_rate": 0.96,
#       "avg_duration_ms": 1234.5,
#       "failure_count": 2,
#       "top_errors": {"permission_denied": 1}
#     }
#   }
# }
```

### 重置统计数据

```python
adaptive_planner.reset_stats()
```

## 启用步骤

1. **替换 Orchestrator 中的规划器**:
   ```python
   from app.services.agent.adaptive_planner import AdaptivePlanner
   
   # 在 Orchestrator.__init__ 中
   base_planner = create_planner(planner_config)
   self.planner = AdaptivePlanner(base_planner)
   ```

2. **在任务完成后记录反馈**:
   ```python
   # 在 Orchestrator.run() 末尾
   for step_execution in result.step_executions:
       feedback = ExecutionFeedback(
           task_id=request.id,
           skill_name=step_execution.skill_id,
           success=step_execution.status == "completed",
           duration_ms=step_execution.duration_ms,
           error_type=extract_error_type(step_execution.error),
       )
       self.planner.record_execution_feedback(feedback)
   ```

3. **（可选）定期保存/加载统计数据**:
   ```python
   import pickle
   
   # 保存
   with open("adaptive_planner_stats.pkl", "wb") as f:
       pickle.dump(adaptive_planner._scorer._stats, f)
   
   # 加载
   with open("adaptive_planner_stats.pkl", "rb") as f:
       adaptive_planner._scorer._stats = pickle.load(f)
   ```

## 降级策略

| 条件 | 操作 |
|------|------|
| 成功率 < 70% | 评分减半 |
| 失败次数 >= 3 | 评分降至 30% |
| 无历史记录 | 默认评分 0.5 |
| 超过最大技能数 | 按评分截断 |

## 注意事项

- 自适应规划器是包装器，不替换基础规划器
- 初始阶段无历史数据时，退化为普通规划器
- 统计数据默认保存在内存中，重启后丢失
- 建议定期保存统计数据，实现跨会话学习

*文档生成时间：2026-04-22*
