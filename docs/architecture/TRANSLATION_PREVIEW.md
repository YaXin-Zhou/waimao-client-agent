# 中文翻译预览

## 目标

让销售人员在审核开发信前阅读中文预览，同时保留英文原文作为发送候选。中文预览不调用 DeepSeek，不进入邮件发送链路，也不覆盖数据库中的英文草稿。

## 当前实现

- `TranslationService`：应用层用例，负责目标语言校验、缓存和预览结果组装。
- `GoogleMachineTranslationProvider`：基础设施适配器，使用 `deep-translator` 调用 Google 网页翻译，不需要 API Key 和大模型 Token。
- `POST /api/drafts/{draft_id}/translate`：返回临时中文主题和正文。
- 前端“中文预览”按钮：首次点击翻译，之后使用当前页面缓存；“EN”按钮回到原文。

## 边界与风险

这是阅读辅助，不是最终交付译文；正式发送仍以人工审核后的英文草稿为准。翻译服务依赖外网和第三方网页接口，不能作为高稳定性 SLA 的唯一方案。若后续要求离线或数据不出本机，应替换为同一接口下的 Argos Translate 语言包，并增加模型包安装与版本管理。

## 安装

```powershell
python -m pip install -r requirements.txt
```

若翻译服务不可用，前端应保留英文原文并提示检查网络，不得生成假中文内容。
