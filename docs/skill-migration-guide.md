# Skill Migration Guide

## 目标

本指南用于把现有 Python class skill 逐步迁移到声明式 `Skill Spec v1`，同时保持：

- API 路由兼容
- skill 名称兼容
- planner / orchestrator / executor 兼容
- legacy skill 可回退

本仓库当前采用“渐进迁移”策略，而不是一次性迁移全部 builtin skill。

## 当前迁移策略

默认 `SkillRegistry` 的组装顺序是：

1. 先注册所有 legacy Python builtin skill
2. 再从 `skills/` 目录加载声明式 spec
3. 同名 spec 覆盖同名 legacy skill

因此迁移一个 skill 的最低成本做法是：

- 保留旧 Python class
- 新增同名 spec 文件
- 用测试确保声明式版本和旧版本行为一致

如果 spec 有问题，移除 spec 文件后，系统会自然回退到 legacy 实现。

## 迁移步骤

### 1. 盘点 skill 元数据

从 legacy skill 中提取：

- `name`
- `description`
- `category`
- `parameters`
- `required_context_keys`
- `output_template`
- `steps` 或 `build_steps()` 逻辑

### 2. 判断是否适合先迁移

优先迁移：

- 固定步骤 skill
- 参数分支较少的 skill
- 不依赖复杂 Python 逻辑分支的 skill

暂缓迁移：

- 大量条件分支
- 强依赖 Python 对象拼装步骤
- 需要复杂后处理的 skill

### 3. 新建 spec 文件

在仓库根目录对应位置新增：

- builtin skill: `skills/builtin/<skill-name>.json`
- generated skill: `skills/generated/<skill-name>--<version>--<id>.json`
- experimental skill: `skills/experimental/<skill-name>.json`

建议保留以下字段：

```json
{
  "schema_version": "skill-spec/v1",
  "name": "skill_name",
  "version": "1.0.0",
  "description": "Skill description",
  "category": "investigation",
  "status": "active",
  "source": "builtin",
  "parameters": [],
  "steps": [],
  "required_context_keys": [],
  "output_template": "",
  "legacy_compatibility": {
    "python_class": "app.services.agent.skills.some_skill.SomeSkill"
  }
}
```

### 4. 把 legacy steps 翻译为 declarative steps

固定步骤 skill 可以直接把 `steps` 原样迁移到 JSON。  
如果原 skill 的 `build_steps()` 只是返回 `self.steps`，这是最适合的第一批迁移对象。

如果 skill 只使用模板参数替换，也可以迁移，因为当前 runtime declarative skill 已支持：

- `{{ args.xxx }}`
- `{{ context.xxx }}`
- `{{ context.xxx.yyy }}` 嵌套路径

### 5. 保持 skill name 不变

迁移样例必须保持 `name` 与 legacy skill 相同。  
这样 planner、orchestrator、前端 UI、调用方都不用改。

### 6. 增加测试

至少补两类测试：

- validator / loader 测试
  - schema 合法
  - 目录来源合法
  - draft/generated 不自动加载
- registry 集成测试
  - 声明式 skill 被默认 registry 加载
  - 未迁移的 legacy skill 仍存在

### 7. 验证默认 registry 行为

迁移完成后，应验证：

- `registry.get("<skill-name>")` 返回声明式 skill
- `registry.get("<other-legacy-skill>")` 仍返回 legacy Python skill
- `list_skills()` 中能看到 `version/status/source`

## Generated Skill 特殊说明

generated skill 的迁移规则与 builtin 不同：

- 默认落到 `skills/generated`
- 默认 `status=draft`
- 默认不自动加载进默认 registry
- 需要显式批准后切到 `active`

这条规则是为了避免 AI 生成 skill 在未经审核时直接变成长期启用能力。

注意：

- 当前单次请求内的 runtime auto-register 行为仍保留，用于不打断现有 orchestrator 自适应链路
- 但持久化到目录的 generated skill 会以 `draft` 形式落盘

## 已完成的迁移样例

当前仓库已提供两个 builtin skill 的声明式迁移样例：

- [capability_check.json](D:/项目/new-lovely/skills/builtin/capability_check.json)
- [remediation_verification.json](D:/项目/new-lovely/skills/builtin/remediation_verification.json)

这两个样例的共同特点：

- 步骤固定
- 依赖少
- 与 legacy 实现容易对齐

## 推荐的后续迁移顺序

建议下一批优先迁移：

1. `incident_timeline`
2. `web_target_probe`
3. `capability_check` 同类的固定步骤审计 skill

建议最后迁移：

1. `host_triage`
2. `log_investigation`
3. `ssh_audit`
4. 其他含较多参数分支和动态步骤拼装的 skill

## 回滚方式

如果某个声明式迁移出现问题，最小回滚方式是：

1. 删除或停用对应 spec 文件
2. 保留 legacy Python class skill
3. 默认 registry 会自动退回 legacy 实现

这也是本次平台升级选择“同名覆盖”而不是“直接删除旧 skill”的原因。
