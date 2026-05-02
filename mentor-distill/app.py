#!/usr/bin/env python3
"""
Mentor Distill — 导师蒸馏器

将学者的论文、调查报告等资料上传后，由 AI 现场整理、蒸馏，
生成可对话的学术知识库。对外提供 OpenAI 兼容的 API 接口。

Usage:
    cp .env.example .env
    # 编辑 .env 填入你的 API Key
    pip install -r requirements.txt
    python app.py

API Endpoints:
    POST /api/upload       上传文件
    POST /api/distill      蒸馏处理
    POST /api/chat         内部对话接口
    POST /v1/chat/completions  OpenAI 格式对话接口
    GET  /v1/models        OpenAI 格式模型列表
"""

import argparse
import json
import os
from dotenv import load_dotenv
load_dotenv()
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
PORT = int(os.getenv("PORT", "5050"))
HOST = os.getenv("HOST", "127.0.0.1")

# ---------------------------------------------------------------------------
# Logging (minimal)
# ---------------------------------------------------------------------------
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ---------------------------------------------------------------------------
# TF-IDF Vector Store
# ---------------------------------------------------------------------------
class TfidfVectorStore:
    def __init__(self, save_path: Optional[Path] = None):
        self.save_path = save_path
        self.vectorizer = None
        self.tfidf_matrix = None
        self.texts = []
        self.metadata = []

    def fit(self, texts: list[str], metadata: list[dict]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        import jieba

        def tokenize(text):
            return list(jieba.cut(text))

        self.vectorizer = TfidfVectorizer(
            tokenizer=tokenize,
            token_pattern=None,
            max_features=20000,
            ngram_range=(1, 2),
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        self.texts = texts
        self.metadata = metadata
        log(f"TF-IDF fitted: {len(texts)} docs, {len(self.vectorizer.get_feature_names_out())} features")

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, dict, float]]:
        if self.vectorizer is None or self.tfidf_matrix is None:
            return []
        query_vec = self.vectorizer.transform([query])
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = scores.argsort()[::-1][:top_k]
        return [(self.texts[i], self.metadata[i], float(scores[i])) for i in top_indices if scores[i] > 0]

    def save(self):
        import pickle
        if self.save_path:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, "wb") as f:
                pickle.dump({
                    "vectorizer": self.vectorizer,
                    "tfidf_matrix": self.tfidf_matrix,
                    "texts": self.texts,
                    "metadata": self.metadata,
                }, f)
            log(f"TF-IDF store saved: {self.save_path}")

    def load(self) -> bool:
        import pickle
        if not self.save_path or not self.save_path.exists():
            return False
        with open(self.save_path, "rb") as f:
            data = pickle.load(f)
        self.vectorizer = data["vectorizer"]
        self.tfidf_matrix = data["tfidf_matrix"]
        self.texts = data["texts"]
        self.metadata = data["metadata"]
        log(f"TF-IDF store loaded: {len(self.texts)} docs from {self.save_path}")
        return True

    def stats(self) -> dict:
        return {"chunk_count": len(self.texts), "features": len(self.vectorizer.get_feature_names_out()) if self.vectorizer else 0}

# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------
class StyleTemplate:
    def __init__(self, template_id: str, name: str, description: str, system_prompt: str):
        self.id = template_id
        self.name = name
        self.description = description
        self.system_prompt = system_prompt.strip()

class PromptBuilder:
    def __init__(self, templates_path: Optional[Path] = None):
        self.templates: dict[str, StyleTemplate] = {}
        path = templates_path or Path(__file__).parent / "style_templates.yaml"
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for tid, tdef in data.get("templates", {}).items():
            self.templates[tid] = StyleTemplate(tid, tdef["name"], tdef["description"], tdef["system_prompt"])
        log(f"Loaded {len(self.templates)} style templates")

    def get_template(self, template_id: str) -> StyleTemplate:
        if template_id not in self.templates:
            log(f"Template '{template_id}' not found, fallback to 'neutral'")
            template_id = "neutral"
        return self.templates[template_id]

    def build_prompt(self, query: str, retrieved_chunks: list, scholar_profile: dict, style_id: str = "neutral") -> dict:
        template = self.get_template(style_id)

        context_parts = []
        for idx, (text, meta, score) in enumerate(retrieved_chunks, 1):
            source = meta.get("source", "未知来源")
            header = f"[片段{idx}] 来源: {source} | 相关度: {score:.3f}"
            context_parts.append(f"{header}\n{text}")

        context_block = "\n\n---\n\n".join(context_parts) if context_parts else "（未检索到相关文献片段）"

        name = scholar_profile.get("name", "该学者")
        institution = scholar_profile.get("institution", "")
        current_title = scholar_profile.get("current_title", "")
        discipline = scholar_profile.get("discipline", "")

        header_info = f"{name}"
        if institution:
            header_info += f"，{institution}"
        if current_title:
            header_info += f"，{current_title}"
        if discipline:
            header_info += f"，{discipline}领域"

        user_prompt = f"""学者信息：{header_info}

用户问题：{query}

以下是从该学者公开发表成果中检索到的相关片段：

{context_block}

请基于以上资料回答问题。"""

        system_prompt = template.system_prompt.replace("{name}", name)
        return {"system": system_prompt, "user": user_prompt}

# ---------------------------------------------------------------------------
# LLM Client (OpenAI-compatible)
# ---------------------------------------------------------------------------
class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=120.0)
        return self._client

    def chat(self, messages: list[dict], temperature: float = 0.5) -> str:
        resp = self._get_client().post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": temperature},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

# ---------------------------------------------------------------------------
# Text Extraction & Chunking
# ---------------------------------------------------------------------------
def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in (".md", ".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if suffix == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(file_path))
            text = "".join(page.get_text() + "\n" for page in doc)
            doc.close()
            if text.strip():
                return text
        except Exception as e:
            log(f"fitz failed: {e}")
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    pt = page.extract_text()
                    if pt:
                        text += pt + "\n"
            return text
        except Exception as e:
            log(f"pdfplumber failed: {e}")
    return ""


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(para) <= max_chars:
            if current and len(current) + len(para) + 1 > max_chars:
                chunks.append(current.strip())
                current = para
            else:
                current = (current + "\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current.strip())
                current = ""
            sentences = re.split(r'(?<=[。．.!?！？])\s+', para)
            for sent in sentences:
                if len(current) + len(sent) + 1 > max_chars:
                    if current:
                        chunks.append(current.strip())
                    current = sent
                else:
                    current = (current + " " + sent).strip() if current else sent
            if current:
                chunks.append(current.strip())
                current = ""
    if current:
        chunks.append(current.strip())
    if overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_tail = chunks[i - 1][-overlap:]
                chunk = prev_tail + chunk
            overlapped.append(chunk)
        chunks = overlapped
    return [c for c in chunks if len(c) > 20]

# ---------------------------------------------------------------------------
# Session Store
# ---------------------------------------------------------------------------
distilled_sessions: dict[str, dict] = {}

# Initialize prompt builder (shared)
prompt_builder = PromptBuilder()

# ---------------------------------------------------------------------------
# API: Upload
# ---------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload files and create a distill session."""
    session_id = str(uuid.uuid4())[:12]
    tmp_dir = Path(tempfile.gettempdir()) / "mentor_distill" / session_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    files = request.files.getlist("files")
    saved = []
    for f in files:
        if f.filename:
            path = tmp_dir / f.filename
            f.save(path)
            saved.append(f.filename)

    info = {
        "name": request.form.get("name", "").strip(),
        "institution": request.form.get("institution", "").strip(),
        "current_title": request.form.get("title", "").strip(),
        "discipline": request.form.get("discipline", "").strip(),
    }

    distilled_sessions[session_id] = {
        "tmp_dir": str(tmp_dir),
        "files": saved,
        "info": info,
        "profile": None,
        "store": None,
    }

    log(f"Upload: session={session_id} files={len(saved)}")
    return jsonify({"session_id": session_id, "files": saved})


# ---------------------------------------------------------------------------
# API: Distill
# ---------------------------------------------------------------------------
@app.route("/api/distill", methods=["POST"])
def api_distill():
    """Process uploaded files: extract profile, build vector store."""
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    session = distilled_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    tmp_dir = Path(session["tmp_dir"])
    files = session["files"]

    # Extract all texts
    all_texts = []
    for fname in files:
        text = extract_text(tmp_dir / fname)
        if text.strip():
            all_texts.append(f"===== {fname} =====\n{text}")

    combined = "\n\n".join(all_texts)
    if len(combined) > 30000:
        combined = combined[:30000] + "\n...（内容截断）"

    # LLM extract profile
    info = session["info"]
    system_prompt = """你是一位学术信息提取专家。请根据提供的学者论文、调查报告等资料，提取以下信息并以 JSON 格式返回。

必须返回的 JSON 格式：
{
  "name": "学者姓名",
  "institution": "所在机构",
  "current_title": "当前职称",
  "department": "院系",
  "discipline": "学科领域",
  "education_background": [{"degree": "学位", "field": "专业", "institution": "学校", "year": 年份}],
  "career_timeline": [{"year": 年份, "event": "事件", "institution": "机构"}],
  "research_focus": "主要研究方向",
  "key_works": ["代表作1", "代表作2"],
  "abstract": "学者的学术概况摘要，200字以内"
}

注意：
1. 只返回 JSON，不要有任何其他文字
2. name 必须是一个具体的人名
3. 如果无法确定某项信息，用空字符串"" """

    user_prompt = f"""用户提供的学者信息：
姓名：{info.get('name') or '未提供'}
机构：{info.get('institution') or '未提供'}
职称：{info.get('current_title') or '未提供'}
学科：{info.get('discipline') or '未提供'}

以下是上传的文件内容：
{combined}

请提取学者档案信息并以 JSON 返回。"""

    client = LLMClient(API_KEY, API_BASE, MODEL)
    try:
        llm_output = client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], temperature=0.3)
        json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        profile = json.loads(json_match.group()) if json_match else json.loads(llm_output)
    except Exception as e:
        log(f"LLM extraction failed: {e}")
        profile = {"name": info.get("name") or "未知学者", "institution": info.get("institution") or ""}

    # Merge user-provided info
    for k in ["name", "institution", "current_title", "discipline"]:
        if info.get(k):
            profile[k] = info[k]

    # Build scholar_data
    scholar_data = {
        "name": profile.get("name", "未知学者"),
        "institution": profile.get("institution", ""),
        "current_title": profile.get("current_title", ""),
        "department": profile.get("department", ""),
        "discipline": profile.get("discipline", ""),
        "education_background": profile.get("education_background", []),
        "career_timeline": profile.get("career_timeline", []),
        "academic_outputs": {"paper_list": [{"title": t, "type": "论文/著作"} for t in profile.get("key_works", [])]},
        "abstract": profile.get("abstract", ""),
    }

    # Save
    (tmp_dir / "scholar_data.json").write_text(json.dumps(scholar_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build vector store
    vector_path = tmp_dir / "mentor_vectors.pkl"
    store = TfidfVectorStore(vector_path)

    all_chunks = []
    all_metadata = []
    for fname in files:
        text = extract_text(tmp_dir / fname)
        if text.strip():
            for chunk in chunk_text(text):
                all_chunks.append(chunk)
                all_metadata.append({"source": fname, "type": "document", "path": str(fname)})

    for paper in scholar_data.get("academic_outputs", {}).get("paper_list", []):
        t = paper.get("title", "")
        if t:
            all_chunks.append(t)
            all_metadata.append({"source": "论文列表", "type": "abstract", "path": "scholar_data"})

    if scholar_data.get("abstract"):
        all_chunks.append(scholar_data["abstract"])
        all_metadata.append({"source": "学者概况", "type": "abstract", "path": "scholar_data"})

    store.fit(all_chunks, all_metadata)
    store.save()

    session["profile"] = scholar_data
    session["store"] = store

    log(f"Distill complete: session={session_id} chunks={len(all_chunks)}")
    return jsonify({"profile": scholar_data, "chunks": len(all_chunks)})


# ---------------------------------------------------------------------------
# API: Chat (internal)
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Chat with a distilled mentor."""
    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    query = data.get("message", "").strip()
    style = data.get("style", "neutral")
    client_history = data.get("history", [])

    session = distilled_sessions.get(session_id)
    if not session:
        return jsonify({"reply": "Session 不存在，请重新蒸馏。", "citations": []})

    store = session.get("store")
    profile = session.get("profile")
    if not store or not profile:
        return jsonify({"reply": "导师尚未准备就绪。", "citations": []})

    if not query:
        return jsonify({"reply": "请输入问题。", "citations": []})

    results = store.search(query, top_k=15)
    prompt = prompt_builder.build_prompt(query, results, profile, style)

    messages = [{"role": "system", "content": prompt["system"]}]
    for h in client_history:
        messages.append(h)
    messages.append({"role": "user", "content": prompt["user"]})

    client = LLMClient(API_KEY, API_BASE, MODEL)
    try:
        answer = client.chat(messages, temperature=0.5)
    except Exception as e:
        log(f"LLM call failed: {e}")
        return jsonify({"reply": f"调用失败: {e}", "citations": []})

    citations = []
    for text, meta, score in results[:5]:
        citations.append({
            "source": meta.get("source", "未知"),
            "score": f"{score:.3f}",
            "text": text[:200] + "..." if len(text) > 200 else text,
        })

    return jsonify({"reply": answer, "citations": citations, "style": style})


# ---------------------------------------------------------------------------
# OpenAI-compatible API
# ---------------------------------------------------------------------------
@app.route("/v1/models", methods=["GET"])
def openai_models():
    """List available models (OpenAI format)."""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "mentor-distill",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "mentor-distill",
            }
        ],
    })


@app.route("/v1/chat/completions", methods=["POST"])
def openai_chat_completions():
    """OpenAI-compatible chat completions endpoint.

    Requires X-Session-ID header to identify the distilled mentor session.
    """
    data = request.get_json(force=True)
    session_id = request.headers.get("X-Session-ID", "")

    if not session_id:
        return jsonify({"error": "Missing X-Session-ID header. Upload and distill first."}), 400

    session = distilled_sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    store = session.get("store")
    profile = session.get("profile")
    if not store or not profile:
        return jsonify({"error": "Mentor not ready. Run /api/distill first."}), 400

    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    # Extract style from messages if present (last user message may contain style hint)
    style = "neutral"
    # Use last user message as query
    query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            query = m.get("content", "")
            break

    if not query:
        return jsonify({"error": "No user message found"}), 400

    # Retrieve and build prompt
    results = store.search(query, top_k=15)
    prompt = prompt_builder.build_prompt(query, results, profile, style)

    # Build full message list for LLM
    llm_messages = [{"role": "system", "content": prompt["system"]}]
    for m in messages:
        if m.get("role") in ("user", "assistant", "system"):
            llm_messages.append(m)

    # Call LLM
    client = LLMClient(API_KEY, API_BASE, MODEL)
    try:
        answer = client.chat(llm_messages, temperature=data.get("temperature", 0.5))
    except Exception as e:
        log(f"OpenAI API LLM call failed: {e}")
        return jsonify({"error": str(e)}), 500

    # OpenAI format response
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    return jsonify({
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": data.get("model", "mentor-distill"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": -1,
            "completion_tokens": -1,
            "total_tokens": -1,
        },
    })


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Session-ID")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Mentor Distill Server")
    parser.add_argument("--port", type=int, default=PORT, help="Server port")
    parser.add_argument("--host", default=HOST, help="Bind address")
    args = parser.parse_args()

    if not API_KEY:
        log("Warning: OPENAI_API_KEY not set. LLM calls will fail.")

    log(f"Mentor Distill Server starting")
    log(f"API Base: {API_BASE}")
    log(f"Model: {MODEL}")
    log(f"OpenAI API: http://{args.host}:{args.port}/v1/chat/completions")
    log(f"Web UI: http://{args.host}:{args.port}/")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
