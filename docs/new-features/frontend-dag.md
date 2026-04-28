# 前端DAG可视化看板

## 概述

前端DAG可视化组件提供任务执行的依赖图展示、时间线可视化和交互式步骤详情查询。

## 文件位置

- **核心实现**: `src/modules/ui/executionDashboard.ts`

## 功能特性

- 任务列表展示（表格）
- DAG执行状态图（SVG渲染）
- 时间线可视化
- 风险等级着色
- 交互式步骤详情
- 审计日志查询集成

## 数据模型

### DAGNode（DAG节点）

```typescript
interface DAGNode {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked' | 'preview' | 'pending_approval';
  type: 'skill' | 'tool' | 'research' | 'plan';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  is_mutation: boolean;
  duration_ms: number;
  step_number: number;
  depends_on: string[];
  error?: string;
}
```

### DAGEdge（DAG边）

```typescript
interface DAGEdge {
  from: string;
  to: string;
  type: 'dependency' | 'data_flow';
}
```

### ExecutionTimeline（执行时间线）

```typescript
interface ExecutionTimeline {
  task_id: string;
  task: string;
  status: string;
  start_time: number;
  end_time?: number;
  total_duration_ms: number;
  nodes: DAGNode[];
  edges: DAGEdge[];
}
```

## API使用

### 执行Dashboard实例

```typescript
import { dashboard } from '../modules/ui/executionDashboard';

// 初始化
await dashboard.init(containerElement);

// 加载任务时间线
const timeline = await dashboard.loadTaskTimeline(taskId);

// 加载任务DAG
const dagData = await dashboard.loadTaskDAG(taskId);

// 列出所有任务
const tasks = await dashboard.listTasks();

// 渲染DAG图
dashboard.renderDAG(containerElement, dagData.nodes, dagData.edges);

// 渲染任务列表
dashboard.renderTaskList(containerElement, tasks);
```

## 状态着色

### 节点状态颜色

| 状态 | 颜色 | 说明 |
|------|------|------|
| `pending` | #999 (灰色) | 待执行 |
| `running` | #2196F3 (蓝色) | 正在执行 |
| `completed` | #4CAF50 (绿色) | 已完成 |
| `failed` | #F44336 (红色) | 失败 |
| `blocked` | #FF9800 (橙色) | 阻塞 |
| `preview` | #9C27B0 (紫色) | 预演模式 |
| `pending_approval` | #607D8B (蓝灰) | 等待审批 |

### 风险等级边框颜色

| 风险等级 | 颜色 |
|---------|------|
| `low` | #4CAF50 (绿色) |
| `medium` | #FFC107 (黄色) |
| `high` | #FF9800 (橙色) |
| `critical` | #F44336 (红色) |

## 集成到前端

### 1. 在导航中添加入口

修改 `src/modules/ui/navigationConfig.ts`:

```typescript
{
  id: 'audit-log',
  label: '审计日志',
  icon: '📋',
  page: 'audit-log'
}
```

### 2. 在渲染器中注册页面

修改 `src/modules/ui/modernUIRenderer.ts`:

```typescript
case 'audit-log':
  import('../modules/ui/executionDashboard').then(({ dashboard }) => {
    dashboard.init(container);
  });
  break;
```

### 3. 在AI指挥台中集成回滚

修改 `src/modules/ai/aiCommandCenterRendererV2.ts`:

```typescript
// 任务完成后显示回滚按钮
if (result.has_mutations) {
  const rollbackBtn = document.createElement('button');
  rollbackBtn.textContent = '预览回滚';
  rollbackBtn.onclick = () => showRollbackPreview(result.task_id);
  actionsContainer.appendChild(rollbackBtn);
}
```

## 扩展方向

### 1. 使用专业DAG库替换当前SVG实现

推荐使用以下库之一：

- **dagre-d3**: 专为DAG设计，支持自动布局
- **Cytoscape.js**: 强大的图可视化库
- **React Flow**: 如果迁移到React，推荐此库

### 2. 添加实时更新

```typescript
// 使用WebSocket推送执行状态更新
const ws = new WebSocket('/ws/agent/events');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  dashboard.updateNodeStatus(update.taskId, update.stepId, update.status);
};
```

### 3. 添加筛选和搜索

```typescript
// 按状态筛选
dashboard.renderDAG(container, nodes.filter(n => n.status === 'failed'), edges);

// 按风险等级筛选
dashboard.renderDAG(container, nodes.filter(n => n.risk_level === 'high'), edges);
```

## 启用步骤

1. **当前状态**: 组件已实现，但未集成到主前端
2. **后续启用时**:
   - 在导航配置中添加入口
   - 在渲染器中注册页面
   - 在AI指挥台中添加回滚入口
3. **依赖**: 需要后端审计日志API正常运行

*文档生成时间：2026-04-22*
