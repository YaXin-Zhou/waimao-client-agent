# 本地 API 适配说明

本 Skill 的业务执行目标是客户电脑上的 `http://127.0.0.1:8001`。

推荐由 `scripts/workbuddy_cli.py` 作为唯一调用入口，不在 Skill 中拼接 HTTP 请求。

## 查询类

```text
GET  /api/ready
GET  /api/tasks
GET  /api/tasks/{task_id}/leads
GET  /api/tasks/{task_id}/leads/{domain}
GET  /api/tasks/{task_id}/leads/{domain}/audit-events
GET  /api/tasks/{task_id}/mail-threads
GET  /api/tasks/{task_id}/reply-analyses
```

## 任务类

```text
POST /api/tasks
POST /api/tasks/{task_id}/discover
POST /api/tasks/{task_id}/discover/import
POST /api/tasks/{task_id}/leads/{domain}/research
POST /api/tasks/{task_id}/leads/{domain}/contacts/discover
POST /api/tasks/{task_id}/leads/{domain}/draft
PATCH /api/tasks/{task_id}/leads/{domain}/research-fields/{field_key}
PATCH /api/tasks/{task_id}/criteria
POST /api/tasks/{task_id}/mailbox/sync
POST /api/tasks/{task_id}/reply-analyses/run
```

字段复核只允许人工确认后写回；确认状态必须有已保存的来源证据。对应 CLI 命令：

```text
python scripts/workbuddy_cli.py review-field <task_id> <domain> <field_key> --value "..."
```

公开邮箱采集只解析官网页面中出现的 `mailto` 或可见邮箱，并保存页面 URL 和上下文摘录：

```text
python scripts/workbuddy_cli.py discover-contacts <task_id> <domain>
```

浏览器搜索结果导入必须声明 `source_mode=browser`，并提交每条结果的 `website`、
`source_url` 和可见摘要 `source_excerpt`。对应 CLI 命令：

```text
python scripts/workbuddy_cli.py import-search <task_id> browser-results.json
```

## 邮件发送

发送必须先经过审核和发送前检查，并由用户在 WorkBuddy 对话中明确确认。Skill 不得默认调用发送接口。
