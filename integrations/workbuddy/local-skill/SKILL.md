---
name: waimao-client-workflow
display_name: 外贸客户开发助手
display_name_en: Foreign Trade Client Workflow
description: 搜索、背调、评分、生成多语言开发信并整理客户资料
description_zh: 在本地外贸客户系统中执行客户搜索、官网背调、邮件草稿和回信分析
description_en: Run local customer discovery, research, multilingual drafts and reply analysis
category: business
version: 0.1.0
author: NORTHSTAR OPS
user-invocable: true
disable-model-invocation: false
---

# 外贸客户开发助手

本 Skill 连接客户电脑上的本地外贸客户系统。所有业务结果必须来自真实搜索、真实官网或真实邮箱；没有证据时标记为未知，不得编造公司规模、行业、采购意向或联系人信息。

本地调用入口是仓库中的 `scripts/workbuddy_cli.py`；先确认 `python scripts/serve_api.py` 已在客户电脑运行。

## 执行规则

1. 先确认产品、目标国家、客户类型和每日数量。
2. 调用本地 CLI 查询或创建获客任务。
3. 搜索结果只保存公开官网和公开联系地址。
4. 背调前先确认官网地址；背调结果必须保存证据 URL。
5. 邮件语言使用任务的 `auto` 策略，参考官网语言和目标市场；不确定时使用英语并要求人工确认。
6. 开发信和回复邮件只能生成草稿，不能把草稿当成已发送。
7. 真实发送必须经过人工审核、安全检查和二次确认。
8. 对验证码、429、超时、邮箱认证失败和空结果如实报告并暂停对应步骤。

## 可执行场景

### 搜索客户

```text
请使用本 Skill 搜索 {国家} 的 {客户类型}，产品是 {产品}，最多返回 {数量} 家。
```

### 官网背调

```text
请对客户 {域名} 做官网背调，只使用公开证据，并保存来源链接。
```

### 生成开发信

```text
请基于已完成背调，为客户 {域名} 生成自动判断语言的开发信草稿，并提供中文预览。
```

### 分析回信

```text
请同步本地阿里邮箱，分析真实客户来信，跳过系统通知和退信，并生成跟进草稿。
```

## 高风险动作

发送邮件不是普通查询。必须把收件人、主题、正文和语言展示给用户，等待用户明确确认后才允许调用发送接口。默认 SMTP 发送关闭。

## 输出要求

每次任务结束报告：

- 实际处理数量；
- 成功、跳过、失败数量；
- 失败原因；
- 输出文件路径；
- 是否生成草稿；
- 是否发生真实发送；
- 下一步需要人工确认的事项。
