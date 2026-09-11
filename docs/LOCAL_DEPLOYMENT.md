# 本地运行说明

当前交付形态为本机内部使用，不需要云端数据库或部署服务器。

## 运行组件

```text
浏览器
  │
  ├── http://127.0.0.1:5174/     React + Vite 工作台
  │
  └── http://127.0.0.1:8002/     Python 本地 API
                                  │
                                  └── data/runtime/acquisition.db
```

## 启动

在项目根目录打开两个 PowerShell 窗口：

```powershell
python -B -u scripts/serve_api.py
```

```powershell
npm run dev
```

然后访问 `http://127.0.0.1:5174/`。

## 当前测试入口

开发和真实搜索测试只使用 `5174`。`5175` 是历史打包版 EXE 的独立运行入口，
它使用打包目录内的另一份 SQLite 数据库，不会自动读取项目根目录的数据。
同时打开两个入口会看到不同的客户数量，不能用来互相对比。

```text
源代码测试：5174 → API 8002 → 项目根目录/data/runtime/acquisition.db
旧版 EXE：  5175 → 打包目录内置 API → 打包目录内置数据库
```

## 配置

复制 `config/.env.example` 为 `config/.env`，只在本机填写真实 API 和邮箱配置。`config/.env` 不得提交 Git。

## 运行检查

```powershell
Invoke-RestMethod http://127.0.0.1:8002/api/ready
```

返回 `status=ready` 后，才开始搜索或背调。真实客户资料、来源证据、筛选结果和邮件草稿保存在 `data/runtime/acquisition.db`。

浏览器搜索默认复用 `HTTPS_PROXY`；如需为浏览器指定不同代理，可在 `config/.env` 增加 `SEARCH_BROWSER_PROXY` 覆盖默认值。修改后需要重启本地 API 进程才能生效。

官网核验默认使用 4 个受控并发 worker；可在 `config/.env` 设置 `WEBSITE_FETCH_WORKERS` 调整。每个站点仍受单站超时和页面数量上限约束，失败站点不会补造资料。

默认先使用原有的 Yahoo、Bing、Google 静态请求和本机浏览器搜索链路；如果这些来源失败，
且配置了 `TAVILY_API_KEY`，再使用 Tavily 基础搜索作为后备。设置
`SEARCH_TAVILY_PRIMARY=true` 才会将 Tavily 提升为第一来源。Brave 默认关闭。客户日常只需点击一次“搜索可发送客户”，
不需要选择搜索源；所有来源都必须经过国家、官网和公开邮箱核验，异常或无关结果不会进入
可发送客户。

## Google Consent 页面处理

点击“搜索可发送客户”后，系统先自动尝试多个静态搜索源；全部失败或结果不足时，再自动启动受控 Chrome/Edge 浏览器读取公开可见结果，不点击广告、不绕过验证码。若浏览器遇到 Consent、验证码或异常流量页，系统会停止自动搜索，不生成空客户或猜测数据。此时才使用“浏览器补充搜索”作为人工兜底；导入后系统会自动抓取官网及相关联系页、过滤占位邮箱、保存来源并重新筛选。

JSON 最少包含 `title`（或 `company_name`）、`website`，推荐同时保留 `excerpt` 和 `source_url`：

```json
[
  {
    "title": "公开搜索结果中的公司名称",
    "website": "https://company.example",
    "excerpt": "Google 可见摘要",
    "source_url": "https://www.google.com/search?q=..."
  }
]
```

## 当前边界

- 搜索和官网采集使用外部公开网页；结果必须经过清洗、证据保存和合格筛选。
- Tavily 只负责发现候选官网，国家、行业、产品和公开邮箱仍由本机核验流程确认；候选数不等于合格客户数。
- 邮件发送仍由人工审核和发送安全策略控制。
- 当前不是公网生产部署，不包含 HTTPS、多人权限和云端数据库。
