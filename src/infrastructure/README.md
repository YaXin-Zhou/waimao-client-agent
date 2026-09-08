# Infrastructure

数据库、搜索、网页、AI、阿里邮箱和任务队列等外部系统的适配器。

`google_search_provider.py` 是当前 Google HTML 搜索适配器：只返回公开官网链接和
来源标识，不猜测邮箱。网络失败或 Google 返回 JavaScript/同意页时会抛出明确的
`SearchProviderError`，不会伪装成空结果；此时应切换浏览器适配器。
