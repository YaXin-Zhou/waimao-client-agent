# 本地运行说明

当前交付形态为本机内部使用，不依赖 WorkBuddy，也不需要云端数据库或部署服务器。

## 运行组件

```text
浏览器
  │
  ├── http://127.0.0.1:5174/     React + Vite 工作台
  │
  └── http://127.0.0.1:8001/     Python 本地 API
                                  │
                                  └── data/runtime/acquisition.db
```

## 启动

在项目根目录打开两个 PowerShell 窗口：

```powershell
python -B -u scripts/serve_api.py
```

```powershell
npm run dev
```

然后访问 `http://127.0.0.1:5174/`。

## 配置

复制 `config/.env.example` 为 `config/.env`，只在本机填写真实 API 和邮箱配置。`config/.env` 不得提交 Git。

## 运行检查

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/ready
```

返回 `status=ready` 后，才开始搜索或背调。真实客户资料、来源证据、筛选结果和邮件草稿保存在 `data/runtime/acquisition.db`。

## 当前边界

- 搜索和官网采集使用外部公开网页；结果必须经过清洗、证据保存和合格筛选。
- 邮件发送仍由人工审核和发送安全策略控制。
- WorkBuddy 集成暂缓，现有本地 Skill 和相关文件保留，后续可恢复。
- 当前不是公网生产部署，不包含 HTTPS、多人权限和云端数据库。

