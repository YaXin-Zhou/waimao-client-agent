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

## 配置

复制 `config/.env.example` 为 `config/.env`，只在本机填写真实 API 和邮箱配置。`config/.env` 不得提交 Git。

## 运行检查

```powershell
Invoke-RestMethod http://127.0.0.1:8002/api/ready
```

返回 `status=ready` 后，才开始搜索或背调。真实客户资料、来源证据、筛选结果和邮件草稿保存在 `data/runtime/acquisition.db`。

浏览器搜索默认复用 `HTTPS_PROXY`；如需为浏览器指定不同代理，可在 `config/.env` 增加 `SEARCH_BROWSER_PROXY` 覆盖默认值。修改后需要重启本地 API 进程才能生效。

官网核验默认使用 4 个受控并发 worker；可在 `config/.env` 设置 `WEBSITE_FETCH_WORKERS` 调整。每个站点仍受单站超时和页面数量上限约束，失败站点不会补造资料。

默认搜索源为 Google 静态请求和无界面 Chrome fallback。Bing 适配器目前属于实验性可选来源，
默认关闭；只有经过一轮真实相关性抽检后，才建议在 `config/.env` 中设置
`SEARCH_BING_ENABLED=true`。

## Google Consent 页面处理

点击“开始搜索客户”后，系统先自动发送静态请求；若 Google 返回 JavaScript/Consent 页面，会自动尝试以无界面 Chrome 读取公开可见结果，不弹出窗口、不模拟人工点击。若 Google 对自动化会话返回 Consent、验证码或异常流量页，系统会明确提示失败，不生成空客户或猜测数据。此时才使用“导入浏览器结果”作为人工兜底；导入后系统会自动抓取官网及相关联系页、过滤占位邮箱、保存来源并重新筛选。

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
