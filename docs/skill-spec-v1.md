# Skill Spec v1

## 目标

`Skill Spec v1` 是当前仓库的统一声明式技能描述格式，用于把 builtin、generated、experimental 三类 skill 收敛到同一套：

- 可版本化
- 可校验
- 可测试
- 可审核
- 可落盘
- 与 legacy Python class skill 兼容

本版本不替换现有执行引擎，而是把声明层统一到 spec，再复用现有 `RuntimeDeclarativeSkill`、`RuntimeSkillFactory`、`SkillRegistry`。

## 目录结构

仓库根目录新增：

```text
skills/
  builtin/
  generated/
  experimental/
```

语义：

- `skills/builtin`: 受控内建技能，默认可被 loader 自动加载
- `skills/generated`: 生成式技能落盘目录，默认 `draft`，不会自动启用
- `skills/experimental`: 实验性技能目录，默认不进入默认 registry，需显式 opt-in

## Schema 入口

代码入口：

- `app.services.agent.skills.specs.SkillSpec`
- `app.services.agent.skills.specs.SkillSpecValidator`
- `app.services.agent.skills.loader.SkillSpecLoader`

Pydantic schema 会导出 JSON Schema：

```python
from app.services.agent.skills.specs import SkillSpecValidator

schema = SkillSpecValidator.json_schema()
```

## 顶层字段

`SkillSpec` 的核心字段如下：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `schema_version` | literal | 是 | 当前固定为 `skill-spec/v1` |
| `name` | string | 是 | skill 唯一名称 |
| `version` | semver string | 是 | 版本号，如 `1.0.0` |
| `description` | string | 是 | skill 描述 |
| `category` | string | 是 | 类别，如 `investigation` |
| `status` | enum | 是 | `draft` / `active` / `disabled` / `deprecated` |
| `source` | enum | 是 | `builtin` / `generated` / `experimental` / `legacy_python` / `runtime` |
| `parameters` | list | 否 | 输入参数定义，沿用 `SkillParameter` |
| `steps` | list | 是 | 执行步骤定义 |
| `required_context_keys` | list | 否 | 运行时上下文依赖 |
| `output_template` | string | 否 | 报告模板 |
| `tags` | list | 否 | 标签 |
| `owners` | list | 否 | 维护者 |
| `legacy_compatibility` | object | 否 | legacy Python skill 对应关系 |

## Step 字段

每个 step 的字段如下：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `id` | string | 否 | 未提供时自动生成 |
| `name` | string | 是 | 步骤名称 |
| `description` | string | 是 | 步骤说明 |
| `tool_name` | string | 是 | 要调用的 tool |
| `parameters` | object | 否 | tool 参数 |
| `depends_on` | list | 否 | 依赖步骤 ID |

## 状态语义

### `draft`

- 用于新生成或待审核 skill
- 可被 loader 发现
- 默认不会自动注册进默认 `SkillRegistry`

### `active`

- 可自动加载
- builtin 和批准后的 generated skill 使用该状态

### `disabled`

- 已停用，不自动加载
- 可用于 rejected / expired generated skill

### `deprecated`

- 历史兼容保留，不建议继续使用
- 默认不自动加载

## 默认加载规则

默认 `SkillSpecLoader` 行为：

- 自动加载 `builtin` + `generated` 中 `status=active` 的 spec
- `generated` 中 `draft` spec 不自动加载
- `experimental` spec 默认不进入默认 registry

可选行为：

- `include_drafts=True`: 允许加载 `draft`
- `allow_experimental=True`: 允许加载 `experimental`

## Generated Skill 规则

生成式技能落盘时会被标准化为 `SkillSpec`：

- `source=generated`
- `status=draft`
- `version=0.1.0`（可后续递增）

这条规则用于保证：

- 生成技能先审后用
- 默认 registry 不会直接启用新生成 skill
- generated skill 可以进入版本化目录并参与审计

## Loader 闭环

当前闭环如下：

1. `SkillSpecLoader` 从仓库根目录 `skills/` 发现 JSON 文件
2. `SkillSpecValidator` 校验 schema 和目录来源是否一致
3. `SkillSpec` 转换为 runtime config
4. `RuntimeSkillFactory` 生成 `RuntimeDeclarativeSkill`
5. `SkillRegistry` 注册 skill

默认 registry 组装顺序：

1. 先注册 legacy Python builtin skills
2. 再加载声明式 spec
3. 同名 spec 覆盖同名 legacy skill

这样可以保证：

- spec 成功时，优先使用声明式 skill
- spec 缺失或校验失败时，旧 Python skill 仍可用

## 示例

当前已迁移两个 builtin skill 样例：

- [skills/builtin/capability_check.json](D:/项目/new-lovely/skills/builtin/capability_check.json)
- [skills/builtin/remediation_verification.json](D:/项目/new-lovely/skills/builtin/remediation_verification.json)

## 向后兼容

当前仍保留 legacy 通道：

- `BaseSkill` 继续是执行抽象
- legacy Python skill 默认 `source=legacy_python`
- spec loader 只覆盖已迁移的同名 skill
- 未迁移 builtin skill 不受影响

这保证了本轮升级先打通“spec -> loader -> validator -> registry”，而不是一次性重写全部 skill。
