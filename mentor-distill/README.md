# Mentor Distill — 导师蒸馏器

将学者的论文、调查报告等资料上传后，由 AI 现场整理、蒸馏，生成可对话的学术知识库。对外提供 **OpenAI 兼容的 API 接口**，可被任何支持 OpenAI 格式的客户端接入。

## 核心概念

**知识蒸馏**（Knowledge Distillation）源自 Hinton 的模型压缩方法。此处将其迁移到学术场景：

1. 上传学者的公开著作（PDF / Markdown / TXT）
2. AI 自动提取学者档案（姓名、机构、研究方向、教育背景等）
3. 文本分块 + TF-IDF 向量化，构建可检索的知识库
4. 以该学者的口吻和风格回答问题

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/mentor-distill.git
cd mentor-distill

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OpenAI 兼容 API Key

# 4. 启动服务
python app.py
```

服务启动后：
- **Web UI**: http://127.0.0.1:5050/
- **OpenAI API**: http://127.0.0.1:5050/v1/chat/completions

## API 接口

### 1. 上传文件

```bash
curl -X POST http://127.0.0.1:5050/api/upload \
  -F "files=@论文.pdf" \
  -F "files=@调查报告.md" \
  -F "name=学者姓名" \
  -F "institution=所在机构"
```

返回：
```json
{"session_id": "abc123", "files": ["论文.pdf", "调查报告.md"]}
```

### 2. 蒸馏处理

```bash
curl -X POST http://127.0.0.1:5050/api/distill \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123"}'
```

AI 自动分析文件内容，提取学者档案，构建向量知识库。

返回：
```json
{"profile": {"name": "...", "institution": "..."}, "chunks": 281}
```

### 3. 对话（内部接口）

```bash
curl -X POST http://127.0.0.1:5050/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc123",
    "message": "这位学者的研究方向是什么？",
    "style": "normal"
  }'
```

### 4. OpenAI 格式对话（兼容接口）

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

**兼容客户端**：ChatGPT-Next-Web、LobeChat、OpenCat 等支持自定义 Base URL 的客户端均可接入。配置时：
- Base URL: `http://127.0.0.1:5050/v1`
- API Key: 任意值（或你的真实 Key）
- Model: `mentor-distill`
- 自定义 Header: `X-Session-ID: abc123`

### 5. 模型列表

```bash
curl http://127.0.0.1:5050/v1/models
```

## 三种对话风格

| 风格 | 特点 |
|:---|:---|
| **普通教授** | 第一人称，沉稳、严谨、简洁，像课堂上跟学生聊天 |
| **疯癫教授** | 夸张、情绪化、话题跳跃，爱自吹自擂 |
| **老年健忘** | 讲到一半忘词跑题，突然想起来又绕回去 |

## 技术栈

| 组件 | 选型 | 说明 |
|:---|:---|:---|
| Web 框架 | Flask | 轻量，单文件部署 |
| 向量检索 | TF-IDF + sklearn | 纯本地，无需 Embedding API |
| 分词 | jieba | 中文支持 |
| LLM 调用 | httpx | OpenAI 兼容格式 |
| 文本提取 | pdfplumber / PyMuPDF / python-docx | 支持 PDF/TXT/DOCX/MD |

## 环境变量

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `OPENAI_API_KEY` | — | LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 基础地址 |
| `LLM_MODEL` | `gpt-4o-mini` | 对话模型 |
| `HOST` | `127.0.0.1` | 绑定地址 |
| `PORT` | `5050` | 服务端口 |

## License

MIT
