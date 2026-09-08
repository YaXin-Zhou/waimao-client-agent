# Interfaces

HTTP API、后台任务入口和命令行入口。入口层负责协议转换，不承载核心业务规则。
# Interfaces

本地 HTTP API 适配器，供前端读取任务、客户档案、背调报告和开发信审核状态。

## 运行

```bash
python scripts/serve_api.py
```

默认监听 `127.0.0.1:8001`，可通过 `WAIMAO_API_PORT` 修改端口。

## 当前接口

- `GET /api/health`
- `GET /api/tasks/{task_id}/leads`
- `GET /api/tasks/{task_id}/leads/{domain}`
- `GET /api/drafts/{draft_id}`
- `POST /api/drafts/{draft_id}/approve`
- `POST /api/drafts/{draft_id}/request-revision`
- `POST /api/drafts/{draft_id}/reject`

接口只返回数据库已有数据；找不到客户、草稿或任务时返回明确错误，不生成替代数据。
