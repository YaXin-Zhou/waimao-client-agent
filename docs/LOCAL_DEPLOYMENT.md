# 本地运行说明

当前交付形态为本机内部使用，不需要云端数据库或部署服务器。

## 运行组件

```text
浏览器
  │
  ├── http://127.0.0.1:5174/     React + Vite 工作台
  │
  └── http://127.0.0.1:8001/     Python 本地 API
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

## 配置

复制 `config/.env.example` 为 `config/.env`，只在本机填写真实 API 和邮箱配置。`config/.env` 不得提交 Git。

## 运行检查

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/ready
```

返回 `status=ready` 后，才开始搜索或背调。真实客户资料、来源证据、筛选结果和邮件草稿保存在 `data/runtime/acquisition.db`。

浏览器搜索默认复用 `HTTPS_PROXY`；如需为浏览器指定不同代理，可在 `config/.env` 增加 `SEARCH_BROWSER_PROXY` 覆盖默认值。浏览器搜索默认使用可见窗口，这样遇到 Google 验证时，人工验证和后续结果读取使用同一个会话。若明确需要无界面运行，可将 `SEARCH_BROWSER_HEADLESS=true`，但验证交互将不再适合人工处理。修改后需要重启本地 API 进程才能生效。

官网核验默认使用 4 个受控并发 worker；可在 `config/.env` 设置 `WEBSITE_FETCH_WORKERS` 调整。每个站点仍受单站超时和页面数量上限约束，失败站点不会补造资料。

默认搜索链为 Bing、Google、Yahoo、DuckDuckGo、Brave、Mojeek 六个来源，按顺序自动尝试；
客户不需要选择搜索源；可通过 `SEARCH_*_ENABLED` 在维护配置中关闭某个来源。

浏览器搜索默认以可见窗口运行。若检测到 Consent、验证码或异常流量页面，系统会在当前窗口
等待用户手动完成验证；验证页面消失后自动继续读取搜索结果。系统不会代替用户解验证码，也不会绕过验证。
等待上限由 `SEARCH_BROWSER_CHALLENGE_TIMEOUT_SECONDS` 控制，默认 180 秒。

## Google Consent 页面处理

点击“开始搜索客户”后，系统按配置的搜索链路读取公开结果；浏览器搜索使用可见窗口，若 Google 返回
Consent、验证码或异常流量页，系统会等待用户手动完成验证，再继续读取当前页面结果。系统不会代替用户解验证码，
也不会绕过验证；无法通过时不会生成空客户或猜测数据。

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
- 邮件发送仍由人工审核和发送安全策略控制。
- 当前不是公网生产部署，不包含 HTTPS、多人权限和云端数据库。
