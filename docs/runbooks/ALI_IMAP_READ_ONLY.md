# 阿里邮箱只读接入

## 目标

本阶段只读取阿里企业邮箱收件箱，建立邮件记录和线程关联，不提供 SMTP 发送能力。

## 配置

在本机 `config/.env` 填写以下字段，不要提交该文件：

```text
ALI_IMAP_HOST=imap.qiye.aliyun.com
ALI_IMAP_PORT=993
ALI_IMAP_USERNAME=你的邮箱地址
ALI_IMAP_PASSWORD=你的邮箱密码或应用专用密码
ALI_IMAP_MAILBOX=INBOX
```

密码不会写入 SQLite、日志或前端接口。`GET /api/mailbox/status` 只返回是否已配置，不返回用户名和密码。

## 只读验证

1. 启动 API。
2. 查看邮箱状态：`GET /api/mailbox/status`。
3. 对指定获客任务调用 `POST /api/tasks/{task_id}/mailbox/sync`。
4. 查看线程：`GET /api/tasks/{task_id}/mail-threads`。

同步会按 `Message-ID` 去重；来自某个客户主域名的邮件会关联到该客户；主题会去除 `Re:`、`Fw:` 前缀生成线程键；`mailer-daemon`、`postmaster` 和常见退信主题会标记为退信。

当前明确不支持：SMTP、自动回复、自动发送、附件入库和正式邮箱客户验收。接入前应使用专用测试邮箱，并由人工确认阿里邮箱后台已开启 IMAP 和必要的安全策略。

SMTP 配置字段仅记录在 `config/.env.example` 作为后续阶段模板；当前不要填写或启用。发送接口即使实现，也必须再次提交人工确认的收件人、主题和正文快照。
