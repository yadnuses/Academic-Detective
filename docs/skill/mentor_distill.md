### 附录：导师蒸馏服务 (Mentor Distill)

#### 概述

导师蒸馏服务是学术侦探系统的**最终交付增强组件**。当七步调查完成、报告生成后，调查成果可被蒸馏为一个可对话的学术知识库。用户上传学者的论文、调查报告等资料，AI 现场整理并生成基于检索增强生成（RAG）的对话接口。

#### 核心能力

| 能力 | 说明 |
|:---|:---|
| **档案自动提取** | 从上传文件中自动提取学者姓名、机构、研究方向、教育背景、代表作等 |
| **本地向量检索** | 基于 TF-IDF 的纯本地向量化，无需调用 Embedding API，保护隐私 |
| **OpenAI 兼容接口** | 提供 `/v1/chat/completions` 标准接口，任何支持 OpenAI 格式的客户端均可接入 |
| **多风格对话** | 支持客观中立、普通教授、疯癫教授、老年健忘四种对话风格 |

#### 与调查工作流的集成

```
七步调查完成 → 报告生成 → 上传学者资料 → 蒸馏 → 可对话知识库
```

在调查后期，可将以下资料上传进行蒸馏：
- 学者本人论文 PDF
- 调查过程中生成的 Markdown 报告
- CNKI/Wanfang 导出的文献列表
- 机构官网保存的 HTML 快照

#### 快速启动

服务代码位于项目根目录 `mentor-distill/` 下：

```bash
cd mentor-distill

# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OpenAI 兼容 API Key 和接口地址

# 3. 启动服务
python app.py
```

服务启动后：
- **Web UI**: http://127.0.0.1:5050/
- **OpenAI API**: http://127.0.0.1:5050/v1/chat/completions

#### API 接口

**1. 上传文件**

```bash
curl -X POST http://127.0.0.1:5050/api/upload \
  -F "files=@论文.pdf" \
  -F "files=@调查报告.md" \
  -F "name=学者姓名" \
  -F "institution=所在机构"
```

返回 `session_id`，后续所有请求均需携带此 ID。

**2. 蒸馏处理**

```bash
curl -X POST http://127.0.0.1:5050/api/distill \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123"}'
```

AI 自动分析文件，提取学者档案，构建 TF-IDF 向量知识库。

**3. OpenAI 格式对话（兼容接口）**

```bash
curl -X POST http://127.0.0.1:5050/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: abc123" \
  -d '{
    "model": "mentor-distill",
    "messages": [
      {"role": "user", "content": "这位学者的研究方向是什么？"}
    ]
  }'
```

兼容客户端：ChatGPT-Next-Web、LobeChat、OpenCat 等支持自定义 Base URL 的客户端。配置时：
- Base URL: `http://127.0.0.1:5050/v1`
- API Key: 任意值（或你的真实 Key）
- Model: `mentor-distill`
- 自定义 Header: `X-Session-ID: {你的session_id}`

#### 环境变量配置

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `OPENAI_API_KEY` | — | LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 基础地址，支持任何 OpenAI 兼容接口 |
| `LLM_MODEL` | `gpt-4o-mini` | 对话模型 |
| `HOST` | `127.0.0.1` | 绑定地址 |
| `PORT` | `5050` | 服务端口 |

#### 技术栈

| 组件 | 选型 | 说明 |
|:---|:---|:---|
| Web 框架 | Flask | 轻量，单文件部署 |
| 向量检索 | TF-IDF + sklearn | 纯本地计算，无需外部 Embedding 服务 |
| 分词 | jieba | 中文支持 |
| LLM 调用 | httpx | OpenAI 兼容格式，支持任意兼容接口 |
| 文本提取 | pdfplumber / PyMuPDF / python-docx | 支持 PDF / TXT / DOCX / MD |

#### 文件组织

```
mentor-distill/
├── app.py                  # 主服务（Flask 单文件）
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板（去敏化）
├── style_templates.yaml    # 四种对话风格模板
├── README.md               # 服务说明文档
└── static/
    └── index.html          # Web UI 前端
```

---

