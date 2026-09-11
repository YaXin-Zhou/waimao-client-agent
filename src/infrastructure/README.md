# Infrastructure

数据库、搜索、网页、AI、阿里邮箱和任务队列等外部系统的适配器。

`tavily_search_provider.py` 使用 Tavily 的 JSON Search API 作为首选搜索来源：每次请求
只使用基础搜索和有限结果，不调用答案生成或原始全文，返回的官网候选仍会进入统一的
公司名称、国家、行业、产品和公开邮箱核验流程。Tavily 不可用时由
`fallback_search_provider.py` 继续尝试其他来源；它不会绕过验证码，也不会伪造客户资料。

`google_search_provider.py` 是当前 Google HTML 搜索适配器：只返回公开官网链接和
来源标识，不猜测邮箱。网络失败或 Google 返回 JavaScript/同意页时会抛出明确的
`SearchProviderError`，不会伪装成空结果；此时应切换浏览器适配器。

`browser_search_provider.py` 接收浏览器控制器读取到的可见结果，负责转换为统一的
`LeadRecord`。它不会自行点击页面，也不会从公司域名推测邮箱。

`playwright_search_provider.py` 是本地自动 fallback：默认以无界面 Chrome 导航并读取
Google 可见结果，通过请求解析 Google 重定向，不模拟人工点击。遇到 Consent、验证码或
异常流量页面时明确失败；`fallback_search_provider.py` 会在来源返回候选不足时继续尝试
其他已启用来源，合并并按官网域名去重。

`bing_search_provider.py` 是可选的第二自动来源：只有静态 Google 和无界面浏览器都明确失败、
且 `SEARCH_BING_ENABLED=true` 时才调用。由于不同地区的 Bing 结果相关性需要真实样本验证，
默认关闭；开启后结果仍进入同一套官网、邮箱、评分和证据流程。
