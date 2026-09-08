# Interfaces

HTTP API、后台任务入口和命令行入口。入口层负责协议转换，不承载核心业务规则。
# Interfaces

本地 HTTP API 适配器，供前端读取任务、客户档案、背调报告和开发信审核状态，也接收外部搜索适配器的标准化结果。

## 运行

```bash
python scripts/serve_api.py
```

默认监听 `127.0.0.1:8001`，可通过 `WAIMAO_API_PORT` 修改端口。

## 当前接口

- `GET /api/health`
- `GET /api/tasks`
- `POST /api/tasks`：按表单提交任务名称和 `criteria`，创建并持久化草稿任务
- `GET /api/tasks/{task_id}/leads`
- `GET /api/tasks/{task_id}/leads/{domain}`
- `POST /api/tasks/{task_id}/assess`：提交 `records`、`weights` 和 `signals_by_domain`，执行清洗、评分并持久化
- `GET /api/drafts/{draft_id}`
- `POST /api/drafts/{draft_id}/approve`
- `POST /api/drafts/{draft_id}/request-revision`
- `POST /api/drafts/{draft_id}/reject`

接口只返回数据库已有数据；找不到客户、草稿或任务时返回明确错误，不生成替代数据。

评估接口的评分项由请求配置，不在接口中硬编码。例如：

```json
{
  "records": [{
    "company_name": "Example GmbH",
    "website": "https://example.com",
    "email": "sales@example.com",
    "country": "DE",
    "source_url": "https://example.com/contact",
    "source_excerpt": "Contact and distribution information"
  }],
  "weights": {"product_fit": 40, "country_fit": 30},
  "signals_by_domain": {
    "example.com": {"product_fit": 35, "country_fit": 30}
  }
}
```
