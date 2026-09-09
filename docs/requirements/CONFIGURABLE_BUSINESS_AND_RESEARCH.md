# 配置化业务与背调字段

## 目标

系统不把客户所在行业、主营服务或背调项目写死在代码中。客户在创建获客任务时，可以自行维护业务目录、关键词和需要核实的字段；后续搜索、背调、评分和导出都读取这份配置。

## 配置模型

### 业务目录 `business_offerings`

每项业务包含：

- `name`：展示名称
- `key`：稳定的 `snake_case` 标识
- `description`：给研究流程的业务说明
- `keywords`：用于搜索和匹配的关键词

### 背调字段 `research_fields`

每项字段包含：

- `name`、`key`、`description`、`keywords`
- `type`：`text`、`number`、`boolean` 或 `select`
- `required`：是否要求输出该字段
- `evidence_required`：是否必须附来源
- `human_review`：是否进入人工复核
- `options`：选择型字段的允许值

## 真实性规则

关键词只是发现信号，不是事实。字段结果必须带 `status`、`confidence`、`sources` 和 `checked_at`。无法从当前来源确认时输出 `unknown` 和空来源；多个来源冲突时输出 `conflicting`，不能用模型猜测补齐。

## 已完成边界

当前版本已完成领域模型、任务 API 接收、SQLite 持久化、研究提示词动态生成、配置业务相关性评分信号、研究结果 API 返回和 CSV 动态列导出，并兼容没有配置新字段的历史任务。

下一阶段实现前端“业务目录 / 背调字段”配置窗口和字段结果展示；再下一阶段接入多来源采集器，使每个字段能积累多条来源证据。邮件发送仍保持人工确认和每日 30 封默认上限。
