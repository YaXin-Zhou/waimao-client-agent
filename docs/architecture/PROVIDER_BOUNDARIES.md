# 外部提供商边界

## 目标

外部搜索、网页、AI 和邮箱服务都通过适配器接入，领域层和应用层只依赖稳定接口。更换服务商、使用 Fake 数据或处理服务失败时，不修改客户清洗和评分规则。

## 当前接口

`SearchProvider.search(criteria) -> list[LeadRecord]`

搜索提供商只负责返回原始潜客记录，不负责清洗、去重、评分或决定是否发送邮件。

当前实现：`src/infrastructure/google_search_provider.py` 可处理静态 HTML；
`src/infrastructure/browser_search_provider.py` 接收浏览器读取的可见结果，适用于
Google 返回 JavaScript 页面时的真实搜索流程。两者都保存查询来源，不从域名推测邮箱。

本地 API 默认还配置 `FallbackSearchProvider`，按顺序尝试 Bing、Google、Yahoo、
DuckDuckGo、Brave 和 Mojeek 六个公开搜索源；单个来源明确失败、为空或被验证页拦截时，
自动尝试下一个来源。六个来源全部失败后，才调用 `PlaywrightSearchProvider` 作为浏览器兜底。
浏览器适配器通过导航和 DOM/重定向读取可见结果，不绕过 Consent、验证码或异常流量页面。

本机真实验证表明，Google 无浏览器会话的静态请求可能返回仅含 `enablejs` 的页面，
此时 `GoogleSearchProvider` 必须明确失败，不能返回空客户池或虚构结果。使用浏览器
获得可见结果后，通过统一的 `POST /api/tasks/{task_id}/discover/import` 入口导入，仍然经过同一
套清洗、去重、评分和来源保存流程。

搜索结果页仅作为候选发现来源保留；产品匹配、证据质量和 AI 背调引用只使用官网或其他
公开业务页面。研究工作流会主动排除 Google/Bing 结果页，避免把搜索引擎摘要当成企业事实。

## 责任分配

| 层 | 负责内容 |
|---|---|
| SearchProvider | 根据目标条件返回原始搜索结果 |
| ApplicationService | 调度搜索、清洗、评分和保存 |
| Domain | 定义清洗规则、评分规则和状态约束 |
| Repository | 保存任务和评估结果 |
| AcquisitionExecutionService | 编排任务状态、搜索调用、评估结果和失败恢复 |
| WebsiteFetcher | 官网访问、原始文本、公开邮箱和来源证据 |
| Future AI Adapter | 背调、评分信号、开发信和回复分类建议 |

## 外部适配器必须提供的行为

- 明确输入和输出结构；
- 不把服务商异常伪装成空结果；
- 返回来源、时间和原始内容的可追溯标识；
- 支持超时、重试和取消；
- 能被 Fake 实现替换；
- 不接收领域层对象之外的隐式全局配置。

## 真实搜索适配器检查结果

1. 搜索结果和来源证据模型已定义；
2. JavaScript/同意页、网络失败、超时和空结果均有明确失败边界；
3. 任务每日数量来自 `daily_limit`，静态搜索每次查询数量由 `SEARCH_RESULTS_PER_QUERY` 配置；
4. 六个搜索源均有独立适配器，新增的 DuckDuckGo、Brave、Mojeek 有契约测试；
5. 已完成一次有限真实浏览器搜索，并将 ELMAG 结果写入本地 smoke 任务；正式客户验收仍按范围暂不执行。

## 获客任务执行契约

`AcquisitionExecutionService.execute` 的一次执行遵循：

```text
draft/failed/paused → ready → running → completed
                                      ↘ failed
```

- 搜索提供商成功返回后，统一交给 `AcquisitionService.discover_and_assess`；
- 评估结果写入客户评估仓储后，任务才进入 `completed`；
- 搜索、清洗或评分抛出异常时，任务进入 `failed` 并保留当前状态；
- `failed` 可再次执行，`completed` 禁止重复执行；
- 任务执行器不负责发送邮件，邮件仍必须经过人工审核边界。
