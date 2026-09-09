# 真实数据核验记录

## 核验时间

2026-09-09

## 核验范围

- 本地 API：`http://127.0.0.1:8001`
- 本地 SQLite：`data/runtime/acquisition.db`
- 搜索方式：Google 可见浏览器结果导入
- 任务：`真实官网合格客户链路 smoke`
- 候选上限：5 家
- 合格目标：1 家
- 邮件动作：未发送

## 核验规则

一条客户记录只有同时满足以下条件，才可进入合格客户列表：

1. 官网 URL 可访问；
2. 公司名称和官网来源保持关联；
3. 公开邮箱来自官网首页、联系页或官网明确链接的公开页面；
4. 邮箱格式有效，不是图片文件名、占位地址或明显系统地址；
5. 每条邮箱保留来源 URL 和页面摘录；
6. 未能确认的字段不补猜测，显示为未知或待复核。

## 实际结果

| 官网 | 可访问 | 公开邮箱数 | 来源证据数 | 数据质量 | 最终状态 |
|---|---:|---:|---:|---|---|
| `eu.ecoflow.com` | 是 | 5 | 23 | complete | 配额外候选 |
| `iallpowers.eu` | 是 | 6 | 9 | complete | 配额外候选 |
| `solarzone.be` | 是 | 1 | 2 | complete | 配额外候选 |
| `eu.aferiy.com` | 是 | 3 | 13 | complete | 配额外候选 |
| `elmag.eu` | 是 | 1 | 5 | complete | 合格客户 |

汇总：

- 候选客户：5 家；
- 官网可访问：5/5；
- 数据质量为 `complete`：5/5；
- 公开邮箱：16 个；
- 邮箱均通过格式、占位地址和来源证据检查；
- 最终合格客户：1 家；
- 配额外候选：4 家；
- 因数据不足造成的缺口：0 家。

“最终合格客户”为 1 家是任务配额造成的，不代表其余 4 家没有邮箱。若需要一次输出 5 家，可把任务的“合格客户目标”改为 5，系统会重新按评分和规则选择。

## 发现并修复的问题

真实页面核验时发现，部分电商页面会把图片资源名中的 `@2x.png`、`@2x.svg` 误识别为邮箱，页面还可能包含 `contoso@example.com` 等示例地址。现已在领域清洗层和官网采集层同时过滤：

- 图片、图标等非邮箱文件扩展名；
- `example.com`、`domain.com`、`contoso.com` 等占位域名；
- `noreply`、`no-reply` 系统地址；
- 单条联系人复查与批量搜索使用同一套多页抓取和清洗逻辑。

修复后已重新抓取上述 5 个官网，脏数据不再出现在结果中。

## 当前限制

- Google 静态 HTTP 请求可能返回 JavaScript/Consent 页面；系统会明确报错，不会把空结果伪装成搜索成功。当前真实批次通过可见浏览器结果导入；
- 官网没有公开邮箱、需要登录、验证码或完全由 JavaScript 渲染时，系统不能保证拿到邮箱；
- “公开邮箱存在”不等于邮箱一定有人使用，正式发送仍需人工审核；
- 公司规模、成立时间、决策人等字段只有在公开来源明确出现时才会填充。

## 复现命令

```powershell
pytest -q
ruff check src/application/acquisition_service.py src/domain/lead.py src/infrastructure/website_fetcher.py tests/unit/test_website_fetcher.py tests/integration/test_acquisition_service.py
Invoke-RestMethod http://127.0.0.1:8001/api/ready
```

