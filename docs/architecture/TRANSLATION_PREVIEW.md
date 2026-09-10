# 中文翻译预览

## 目标

让销售人员在审核开发信前阅读中文预览，同时保留英文原文作为发送候选。中文预览不调用 DeepSeek，不进入邮件发送链路，也不覆盖数据库中的英文草稿。

## 当前实现

- `TranslationService`：应用层用例，负责目标语言校验、缓存和预览结果组装。
- `LocalArgosTranslationProvider`：基础设施适配器，使用本机 Argos Translate 英译中语言包，不调用外部翻译服务、不需要 API Key 和大模型 Token。
- `POST /api/drafts/{draft_id}/translate`：返回临时中文主题和正文。
- 前端“中文预览”按钮：首次点击翻译，之后使用当前页面缓存；“EN”按钮回到原文。

## 边界与风险

这是阅读辅助，不是最终交付译文；正式发送仍以人工审核后的英文草稿为准。当前翻译模型运行在本机，翻译时不访问外网。模型包需要随开发环境或后续 EXE 打包流程一起安装和验证。

## 安装

```powershell
python -m pip install -r requirements.txt
```

安装 Argos 运行库后，还需要安装一次英译中模型包。开发机可执行：

```powershell
python -c "import argostranslate.package as p; p.update_package_index(); x=next(x for x in p.get_available_packages() if x.from_code == 'en' and x.to_code == 'zh'); x.install()"
```

若本地模型缺失，前端保留英文原文并提示安装本地翻译组件，不得调用外部接口或生成假中文内容。
