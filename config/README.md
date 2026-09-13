# 配置目录

放置环境变量模板、非敏感默认配置和配置字段说明。

真实邮箱密码、模型密钥和生产地址只通过本机或部署环境注入，不提交到仓库。

配置步骤请看：[AI API 配置说明](../docs/runbooks/AI_API_CONFIG.md)。

搜索源按顺序自动尝试 Bing、Google、Yahoo、DuckDuckGo、Brave、Mojeek，全部失败后再使用浏览器兜底。
Tavily 仍保留为可选 API，但当前本机配置可以通过 `SEARCH_TAVILY_ENABLED=false` 禁用，不影响六个浏览器源。
浏览器兜底默认无界面运行；遇到验证码时会临时打开可见窗口，用户完成验证后自动继续，超时则结束本轮搜索。
密钥只保存在本机，不要提交 Git。

启用 `DEEPSEEK_SEARCH_EXPANSION_ENABLED=true` 后，首次使用一组搜索条件时，
DeepSeek 会生成少量英文同义词和采购意图词，结果会在本地缓存；模型不可用时自动使用内置关键词，
不会影响 Tavily 搜索。`DEEPSEEK_SEARCH_EXPANSION_LIMIT` 建议保持 8，避免查询数量过大。
