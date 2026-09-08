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
- `POST /api/tasks`：按表单提交任务名称、`criteria` 和可选的 `sender_profile`，创建并持久化草稿任务
- `POST /api/tasks/{task_id}/transition`：按领域状态机推进任务，并记录操作者和原因
- `GET /api/tasks/{task_id}/audit-events`：读取任务状态变更记录
- `POST /api/tasks/{task_id}/sender-profile`：更新已有任务的发件人资料，供下一版开发信使用
- `GET /api/tasks/{task_id}/leads`
- `GET /api/tasks/{task_id}/leads/{domain}`
- `POST /api/tasks/{task_id}/leads/{domain}/transition`：按客户状态机推进状态并记录审计
- `GET /api/tasks/{task_id}/leads/{domain}/audit-events`：读取客户状态变更记录
- `GET /api/tasks/{task_id}/follow-up-tasks`：读取来信分析生成的人工跟进待办
- `PATCH /api/tasks/{task_id}/follow-up-tasks/{follow_up_id}`：更新人工跟进待办状态
- `POST /api/mailbox/test`：只验证阿里 IMAP 登录和只读打开，不读取邮件
- `POST /api/tasks/{task_id}/assess`：提交 `records`、`weights` 和 `signals_by_domain`，执行清洗、评分并持久化
- `POST /api/tasks/{task_id}/leads/{domain}/draft`：仅在真实邮箱和真实背调存在时调用 DeepSeek 生成待审核草稿，不发送邮件
- `GET /api/drafts/{draft_id}`
- `GET /api/drafts/{draft_id}/audit-events`：读取草稿审核状态变更记录
- `POST /api/drafts/{draft_id}/send-check`：只做发送前安全检查，不发送邮件
- `POST /api/drafts/{draft_id}/send`：仅在批准、人工确认和内容快照一致后调用 SMTP
- `GET /api/drafts/{draft_id}/send-attempts`：读取发送尝试审计记录
- `POST /api/drafts/{draft_id}/translate`：调用非大模型机器翻译生成中文阅读预览，不覆盖原始英文草稿
- `POST /api/drafts/{draft_id}/approve`
- `POST /api/drafts/{draft_id}/request-revision`
- `POST /api/drafts/{draft_id}/reject`

接口只返回数据库已有数据；找不到客户、草稿或任务时返回明确错误，不生成替代数据。
发送预检可接收 `contacted_recently`、`attachments`（文件名和字节数）、`max_attachments`、单文件/总大小和允许扩展名配置；预检只检查元数据，不读取或发送附件内容。
开发信生成接口只生成待审核草稿，不执行发送；发送联调不属于当前阶段验收范围。

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
