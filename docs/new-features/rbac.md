# RBAC 权限系统

## 概述

RBAC（Role-Based Access Control）多租户权限系统，提供细粒度的资源级权限控制，支持角色定义、用户管理、多租户隔离和权限检查。

## 文件位置

- **核心实现**: `src-python/app/services/agent/rbac.py`
- **Executor集成**: `src-python/app/services/agent/executor.py`（execute_step方法中）
- **单元测试**: `src-python/tests/agent/unit/test_rbac.py`（18项测试）

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Executor.execute_step()                   │
│                      ↓ 权限检查点                            │
│              RBACManager (权限管理器)                        │
│                      ↓                                      │
│          User → Roles → Permissions (权限链)                 │
└─────────────────────────────────────────────────────────────┘

角色层次:
  Viewer (只读)
    ↓
  Operator (可执行)
    ↓
  Analyst (高级分析)
    ↓
  Engineer (配置修改)
    ↓
  Security Admin (审批管理)
    ↓
  System Admin (全部权限)
```

## 角色定义

### 预定义角色

| 角色 | 代码 | 权限范围 |
|------|------|---------|
| Viewer | `viewer` | 只读：查看任务、报告、审计日志 |
| Operator | `operator` | 执行：创建任务、执行技能/工具 |
| Analyst | `analyst` | 分析：Operator + 创建报告、查看审计 |
| Engineer | `engineer` | 工程：Analyst + 修改配置、创建技能 |
| Security Admin | `security_admin` | 安全：Engineer + 审批、删除、系统配置 |
| System Admin | `system_admin` | 全部：所有资源的所有操作 |

### 权限维度

**资源类型** (`ResourceType`):
- `skill` - 技能
- `tool` - 工具
- `task` - 任务
- `plan` - 计划
- `report` - 报告
- `approval` - 审批
- `audit_log` - 审计日志
- `system_config` - 系统配置
- `user` - 用户
- `role` - 角色

**操作类型** (`PermissionAction`):
- `read` - 读取
- `execute` - 执行
- `create` - 创建
- `update` - 更新
- `delete` - 删除
- `approve` - 审批
- `admin` - 管理

## API设计

### 权限检查接口（待实现）

```
GET /api/v1/rbac/users          # 列出用户
POST /api/v1/rbac/users         # 创建用户
GET /api/v1/rbac/users/{id}     # 获取用户
PUT /api/v1/rbac/users/{id}/roles  # 分配角色
DELETE /api/v1/rbac/users/{id}/roles # 撤销角色

GET /api/v1/rbac/roles          # 列出角色
POST /api/v1/rbac/roles         # 创建自定义角色
GET /api/v1/rbac/roles/{name}/permissions # 获取角色权限
PUT /api/v1/rbac/roles/{name}/permissions # 修改角色权限

POST /api/v1/rbac/check         # 检查权限
{
  "user_id": "xxx",
  "resource_type": "skill",
  "action": "execute",
  "resource_id": "ssh_audit"
}
```

## 代码使用

### 初始化

```python
from app.services.agent.rbac import (
    get_rbac_manager,
    RBACManager,
    RoleName,
    Permission,
    PermissionAction,
    ResourceType,
)

# 获取全局RBAC管理器
rbac = get_rbac_manager()
```

### 创建用户

```python
# 创建用户并分配角色
user = rbac.create_user(
    username="zhangsan",
    tenant_id="company-a",
    roles=["operator", "analyst"]  # 可分配多个角色
)
print(f"User ID: {user.id}")
```

### 权限检查

```python
# 检查单个权限
if rbac.check_permission(user_id, "skill", "execute", "ssh_audit"):
    print("有权执行技能")
else:
    print("无权执行技能")

# 批量检查权限
permissions = [
    {"resource_type": "skill", "action": "execute"},
    {"resource_type": "tool", "action": "execute"},
]
if rbac.check_permissions(user_id, permissions):
    print("拥有所有必要权限")
```

### 便捷检查方法

```python
# 检查技能执行权限
rbac.enforce_skill_execution(user_id, "ssh_audit")

# 检查工具执行权限
rbac.enforce_tool_execution(user_id, "execute_command")

# 检查任务创建权限
rbac.enforce_task_create(user_id)

# 检查审批权限
rbac.enforce_approval(user_id)
```

### 配置持久化

```python
# 保存配置到文件
rbac.save_config("/path/to/rbac_config.json")

# 从文件加载配置
rbac.load_config("/path/to/rbac_config.json")
```

### 创建自定义角色

```python
from app.services.agent.rbac import Permission, PermissionAction, ResourceType

permissions = [
    Permission(ResourceType.SKILL, PermissionAction.READ),
    Permission(ResourceType.SKILL, PermissionAction.EXECUTE),
    Permission(ResourceType.TOOL, PermissionAction.READ),
]

role = rbac.create_role(
    name="custom_viewer",
    description="自定义只读角色",
    permissions=permissions
)
```

## Executor集成

在 `executor.py` 的 `execute_step()` 方法中，自动进行权限检查：

```python
async def execute_step(self, step, context):
    user_id = context.get("user_id")
    if user_id and step.tool_name:
        rbac = get_rbac_manager()
        if not rbac.enforce_tool_execution(user_id, step.tool_name):
            execution.status = ExecutionStatus.FAILED
            execution.error = f"权限不足：用户 {user_id} 无权执行工具 {step.tool_name}"
            return self._mark_finished(execution)
    
    # ... 正常执行逻辑
```

## 多租户隔离

```python
# 创建租户用户
user1 = rbac.create_user("user1", "tenant_a")
user2 = rbac.create_user("user2", "tenant_b")

# 获取租户下的所有用户
tenant_a_users = rbac.list_tenant_users("tenant_a")
tenant_b_users = rbac.list_tenant_users("tenant_b")
```

## 请求集成

在 `AgentRequest.context` 中传入 `user_id`：

```json
{
  "task": "检查SSH安全",
  "context": {
    "user_id": "user-123",
    "execution_mode": "host_runtime"
  }
}
```

## 启用步骤

1. **创建用户和角色配置**:
   ```python
   from app.services.agent.rbac import get_rbac_manager
   
   rbac = get_rbac_manager()
   
   # 创建管理员用户
   admin = rbac.create_user("admin", "default", roles=["system_admin"])
   
   # 创建普通用户
   user = rbac.create_user("operator1", "default", roles=["operator"])
   
   # 保存配置
   rbac.save_config("src-python/data/rbac_config.json")
   ```

2. **在请求中传入 user_id**:
   - 前端登录获取 user_id
   - AgentRequest.context.user_id = user_id

3. **（可选）实现用户管理API**:
   - 参考"API设计"章节
   - 提供前端用户管理界面

## 测试

```bash
cd src-python
pytest tests/agent/unit/test_rbac.py -v
```

预期输出：`18 passed`

*文档生成时间：2026-04-22*
