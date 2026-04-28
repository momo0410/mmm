# CI/CD Benchmark 回归测试

## 概述

自动化性能基准测试工作流，在代码提交或PR时自动运行，检测性能回归问题。

## 文件位置

- **工作流定义**: `.github/workflows/benchmark-gate.yml`
- **测试用例**: `src-python/tests/agent/test_benchmark_runner.py`

## 工作流设计

```
触发条件:
  ├── push到main分支
  ├── PR到main分支
  └── 定时任务（每周一凌晨2点）
       ↓
  jobs:
  ├── benchmark-regression     # 执行基准测试
  ├── benchmark-threshold-check # 检查性能阈值
  └── benchmark-report          # 生成测试报告
```

## 测试用例清单

| 测试名称 | 测试内容 | 阈值 |
|---------|---------|------|
| `test_orchestrator_basic` | 编排器基本流程 | 5000ms |
| `test_planner_rule_based` | 规则规划器性能 | 1000ms |
| `test_executor_sequential` | 执行器顺序执行 | 3000ms |
| `test_skill_registry_loading` | 技能注册表加载 | 500ms |
| `test_audit_store_performance` | 审计存储读写 | 1000ms |
| `test_metrics_registry_performance` | 指标注册表性能 | 500ms |

## 输出产物

### 1. Benchmark结果JSON

```json
{
  "benchmarks": [
    {
      "name": "test_orchestrator_basic",
      "stats": {
        "mean": 1234.5,
        "stddev": 45.6,
        "min": 1100.0,
        "max": 1300.0,
        "runs": 5
      }
    }
  ]
}
```

### 2. GitHub PR评论

当检测到性能回归时，自动在PR中添加评论：

```markdown
## Benchmark Summary
Run completed at: 2026-04-22

| Benchmark | Mean (ms) | Stddev (ms) |
|-----------|-----------|-------------|
| test_orchestrator_basic | 1234.50 | 45.60 |
| test_planner_rule_based | 890.20 | 30.10 |
```

## 阈值配置

在 `benchmark-gate.yml` 的 `benchmark-threshold-check` job 中配置：

```yaml
THRESHOLDS = {
    'test_orchestrator_basic': 5000,  # ms
    'test_planner_rule_based': 1000,
    'test_executor_sequential': 3000,
}
```

## 缓存机制

### 基准线缓存

```yaml
# 保存基准线（仅main分支）
- name: Store new baseline (on main branch)
  if: github.ref == 'refs/heads/main'
  uses: actions/cache/save@v4
  with:
    path: src-python/benchmark-baseline.json
    key: benchmark-baseline-${{ runner.os }}-${{ github.sha }}
```

### 结果缓存

```yaml
# 下载基准线
- name: Download baseline benchmark (if exists)
  uses: actions/cache/restore@v4
  with:
    path: src-python/benchmark-baseline.json
    key: benchmark-baseline-${{ runner.os }}
```

## 本地运行

```bash
cd src-python

# 安装依赖
pip install pytest pytest-asyncio pytest-benchmark

# 运行基准测试
pytest tests/agent/test_benchmark_runner.py -v --benchmark-only

# 生成JSON报告
pytest tests/agent/test_benchmark_runner.py -v --benchmark-only --json=benchmark-results.json
```

## 启用步骤

1. **当前状态**: GitHub Actions工作流已定义，但需要触发条件
2. **后续启用时**:
   - 确保 `pytest-benchmark` 已安装
   - 推送代码到main分支或创建PR
   - 查看Actions页面运行结果
3. **配置建议**:
   - 在GitHub仓库设置中启用Actions
   - 根据需要调整阈值配置

## 故障排查

### 问题1: 工作流未触发

**解决**:
1. 检查GitHub Actions是否启用
2. 确认分支名称匹配触发条件
3. 查看 `.github/workflows/benchmark-gate.yml` 语法是否正确

### 问题2: 基准测试失败

**解决**:
1. 检查依赖是否安装: `pip install pytest-benchmark`
2. 确认测试环境配置正确
3. 查看测试日志定位问题

*文档生成时间：2026-04-22*
