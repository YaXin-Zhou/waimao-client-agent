# 外部提供商边界

## 目标

外部搜索、网页、AI 和邮箱服务都通过适配器接入，领域层和应用层只依赖稳定接口。更换服务商、使用 Fake 数据或处理服务失败时，不修改客户清洗和评分规则。

## 当前接口

`SearchProvider.search(criteria) -> list[LeadRecord]`

搜索提供商只负责返回原始潜客记录，不负责清洗、去重、评分或决定是否发送邮件。

当前实现：`src/infrastructure/google_search_provider.py` 可处理静态 HTML；
`src/infrastructure/browser_search_provider.py` 接收浏览器读取的可见结果，适用于
Google 返回 JavaScript 页面时的真实搜索流程。两者都保存查询来源，不从域名推测邮箱。

## 责任分配

| 层 | 负责内容 |
|---|---|
| SearchProvider | 根据目标条件返回原始搜索结果 |
| ApplicationService | 调度搜索、清洗、评分和保存 |
| Domain | 定义清洗规则、评分规则和状态约束 |
| Repository | 保存任务和评估结果 |
| Future Web Adapter | 官网访问、原始文本和来源证据 |
| Future AI Adapter | 背调、评分信号、开发信和回复分类建议 |

## 外部适配器必须提供的行为

- 明确输入和输出结构；
- 不把服务商异常伪装成空结果；
- 返回来源、时间和原始内容的可追溯标识；
- 支持超时、重试和取消；
- 能被 Fake 实现替换；
- 不接收领域层对象之外的隐式全局配置。

## 下一步进入真实搜索前的检查

1. 定义搜索结果和来源证据模型；
2. 定义访问失败、验证码、超时和空结果状态；
3. 定义任务重试上限和人工暂停点；
4. 为真实适配器建立契约测试；
5. 用有限真实样例做一次端到端验收。
