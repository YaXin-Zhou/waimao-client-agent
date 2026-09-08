# 开发信审核边界

## 状态流转

```text
PENDING_REVIEW <----> REVISION_REQUIRED
       |                    |
       v                    v
   APPROVED             APPROVED
       |
       └── 后续阶段才允许进入发送前安全检查

PENDING_REVIEW / REVISION_REQUIRED ──> REJECTED
```

## 业务规则

- 草稿必须有清洗后的收件邮箱才能生成。
- 草稿必须保留背调证据 URL，便于人工核验。
- 审核人不能为空；退回修改和拒绝必须填写理由。
- 已批准或已拒绝的草稿不能被重复审核，避免状态被无意覆盖。
- `APPROVED` 只表示内容审核通过，不表示已经发送。
- 本阶段没有邮箱发送适配器，也不会触发外部邮件副作用。
