# Skill Spec v2

## 概述

Skill Spec v2 是技能规范的升级版本，在 v1 的基础上增加了条件分支、循环控制和并行执行等高级控制流能力。

## 文件位置

- **核心实现**: `src-python/app/services/agent/skills/specs_v2.py`

## v1 vs v2 对比

| 特性 | v1 | v2 |
|------|----|----|
| 顺序执行 | ✅ | ✅ |
| 依赖关系 | ✅ | ✅ |
| 条件分支 | ❌ | ✅ |
| 循环控制 | ❌ | ✅ |
| 并行执行 | ❌ | ✅ |
| 错误处理 | ❌ | ✅ |
| 重试机制 | ❌ | ✅ |
| 超时控制 | ❌ | ✅ |
| 变量定义 | ❌ | ✅ |

## 新增控制流

### 1. 条件分支 (Conditional)

```json
{
  "id": "step-check-condition",
  "name": "检查服务状态",
  "description": "检查目标服务是否运行",
  "control_flow": "conditional",
  "branches": [
    {
      "branch_name": "service_running",
      "condition": {
        "variable": "service_status",
        "operator": "equals",
        "value": "running"
      },
      "steps": [
        {"name": "记录运行状态", "tool_name": "execute_command", "parameters": {"command": "echo 'Service is running'"}}
      ]
    },
    {
      "branch_name": "service_stopped",
      "condition": {
        "variable": "service_status",
        "operator": "equals",
        "value": "stopped"
      },
      "steps": [
        {"name": "启动服务", "tool_name": "execute_command", "parameters": {"command": "systemctl start nginx"}}
      ]
    }
  ]
}
```

### 2. 循环控制 (Loop)

```json
{
  "id": "step-check-ports",
  "name": "批量检查端口",
  "description": "遍历端口列表并检查",
  "control_flow": "loop",
  "loop": {
    "variable": "port",
    "collection": "port_list",
    "max_iterations": 100,
    "until_condition": {
      "variable": "port_found",
      "operator": "equals",
      "value": true
    },
    "steps": [
      {"name": "检查端口", "tool_name": "execute_command", "parameters": {"command": "nc -z localhost {{port}}"}}
    ]
  }
}
```

### 3. 并行执行 (Parallel)

```json
{
  "id": "step-parallel-checks",
  "name": "并行安全检查",
  "description": "并行执行多个检查任务",
  "control_flow": "parallel",
  "parallel": {
    "max_concurrency": 5,
    "steps": [
      {"name": "检查SSH配置", "tool_name": "detect_ssh"},
      {"name": "检查防火墙", "tool_name": "detect_firewall"},
      {"name": "检查端口", "tool_name": "detect_port_scan"}
    ]
  }
}
```

## 条件运算符

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `equals` | 等于 | `{"variable": "status", "operator": "equals", "value": "running"}` |
| `not_equals` | 不等于 | `{"variable": "status", "operator": "not_equals", "value": "stopped"}` |
| `greater_than` | 大于 | `{"variable": "port_count", "operator": "greater_than", "value": 5}` |
| `less_than` | 小于 | `{"variable": "cpu_usage", "operator": "less_than", "value": 80}` |
| `contains` | 包含 | `{"variable": "open_ports", "operator": "contains", "value": 22}` |
| `regex_match` | 正则匹配 | `{"variable": "log_line", "operator": "regex_match", "value": "ERROR.*timeout"}` |

## 错误处理策略

| 策略 | 说明 |
|------|------|
| `fail_fast` | 遇到错误立即终止（默认） |
| `continue` | 忽略错误继续执行 |
| `retry` | 重试指定次数 |

## 代码使用

### 创建 v2 规范

```python
from app.services.agent.skills.specs_v2 import (
    SkillSpecV2,
    SkillStepSpecV2,
    StepCondition,
    ConditionalBranch,
    LoopConfig,
    ParallelGroup,
    ControlFlowType,
    ComparisonOperator,
)

# 带条件分支的步骤
step = SkillStepSpecV2(
    id="step-conditional",
    name="条件执行",
    description="根据条件选择执行路径",
    control_flow=ControlFlowType.CONDITIONAL,
    branches=[
        ConditionalBranch(
            branch_name="branch_a",
            condition=StepCondition(
                variable="condition_a",
                operator=ComparisonOperator.EQUALS,
                value=True,
            ),
            steps=[
                SkillStepSpecV2(
                    id="nested-step-a",
                    name="执行A",
                    description="执行分支A",
                    tool_name="execute_command",
                    parameters={"command": "echo A"},
                )
            ],
        )
    ],
)

# 创建 v2 技能规范
spec = SkillSpecV2(
    name="conditional_skill",
    version="2.0.0",
    description="条件分支技能示例",
    category="investigation",
    steps=[step],
)
```

### v1 升级到 v2

```python
from app.services.agent.skills.specs_v2 import upgrade_v1_to_v2

v1_payload = {
    "name": "old_skill",
    "version": "1.0.0",
    "description": "旧技能",
    "category": "investigation",
    "steps": [
        {"name": "检查", "description": "检查系统", "tool_name": "execute_command"}
    ],
}

v2_spec = upgrade_v1_to_v2(v1_payload)
print(v2_spec.schema_version)  # skill-spec/v2
```

### 获取所有步骤ID

```python
step_ids = spec.get_all_step_ids()
# 包括嵌套步骤的所有ID
```

## 启用步骤

1. **当前状态**: v2 规范已定义，但执行器尚未支持控制流
2. **后续启用时**:
   - 修改执行器以识别 `control_flow` 字段
   - 实现条件评估逻辑
   - 实现循环执行逻辑
   - 实现并行执行逻辑
3. **兼容性**: v2 规范完全向后兼容 v1，未使用控制流的步骤与 v1 行为一致

*文档生成时间：2026-04-22*
