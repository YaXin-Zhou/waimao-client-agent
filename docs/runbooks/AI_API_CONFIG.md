# AI API 配置说明

## 1. 配置文件

项目使用两个文件：

```text
config/.env.example   # 可提交的模板，不包含真实密钥
config/.env           # 当前电脑的真实配置，不提交 Git
```

`config/.env` 已被 `.gitignore` 排除。真实 API Key 不要写入源码、截图、日志或聊天消息。

## 2. 推荐配置

第一版默认使用 DeepSeek：

```text
AI_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
```

`deepseek-v4-flash` 用于网页文本提取、数据清洗、初步评分、开发信和回复分类；复杂背调或多来源冲突时使用 `deepseek-v4-pro`。

## 3. 填写步骤

1. 复制 `config/.env.example`，新建 `config/.env`。
2. 将 `DEEPSEEK_API_KEY` 的值替换为真实 API Key。
3. 如果 FlClash 使用透明代理或系统代理模式，`HTTP_PROXY` 和 `HTTPS_PROXY` 可以保持为空。
4. 如果 Python 程序无法跟随系统代理，再填写 FlClash 提供的 HTTP 代理地址，例如：

```text
HTTP_PROXY=http://127.0.0.1:端口
HTTPS_PROXY=http://127.0.0.1:端口
```

不要猜测端口；以 FlClash 当前显示的实际端口为准。

## 4. 当前需要你填写的唯一敏感项

```text
DEEPSEEK_API_KEY=你的真实 API Key
```

其他字段已经给出默认值。

## 5. 配置验证标准

验证分三层：

### 静态检查

- 文件存在；
- Key 不为空；
- 模型名称不为空；
- `config/.env` 未被 Git 跟踪。

### 连接检查

- 能够访问 DeepSeek API；
- API 返回正常文本；
- 超时、网络错误和鉴权错误能被区分。

### 业务检查

- 能够根据虚构公司资料生成结构化 JSON；
- 能够输出背调字段、评分信号和证据引用；
- 失败时不会把错误伪装成空结果。

## 6. 不支持视觉模型是否影响当前项目

不影响。当前第一阶段输入是 Google 搜索结果、官网 HTML、网页正文、邮件正文和表格数据，文本模型即可完成。

视觉模型以后作为可选适配器接入，用于扫描 PDF、图片文字、产品图片或网页截图分析，不作为当前 API 配置前置条件。

## 7. 安全要求

- 不把 API Key 发到聊天中；
- 不把 API Key 提交到 GitHub；
- 不在日志中打印完整请求头；
- 不把真实客户数据写入测试 fixture；
- 共享错误日志前先移除 Key、邮箱和客户信息；
- 更换 Key 后检查 Git 历史和本地日志是否出现旧 Key。
