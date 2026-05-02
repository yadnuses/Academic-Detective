import asyncio
import json
import os
import httpx
from typing import AsyncIterator, List, Dict, Optional, Any

DEEPSEEK_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

# Load Meiying behavior spec as core system prompt (cleaned: no script-calling descriptions)
_BEHAVIOR_PATH = "/Users/xiaoy/Desktop/端上台来/魅影行为逻辑规范_clean.md"
try:
    with open(_BEHAVIOR_PATH, "r", encoding="utf-8") as f:
        _BEHAVIOR_SPEC = f.read()
except Exception:
    _BEHAVIOR_SPEC = "你是魅影，学术调查系统的对话式指挥台。"

# Phase 2 (streaming chat) uses CLEAN system prompt — no function calling mention
# This prevents LLM from outputting DSML thinking tokens in streaming mode
SYSTEM_PROMPT = _BEHAVIOR_SPEC

# Phase 1 (tool call round) appends function calling instructions
_TOOLS_APPEND = """

---

你拥有一份完整的学术调查技能手册（SKILL.md）。当你需要执行具体调查步骤、评估论文质量、或生成报告时，可以调用工具 read_skill_section 来查阅对应章节。

可用章节：overview, 7_step_framework, step_1_basic_profile, step_2_output_quantity, step_3_quality_assessment, step_4_relationship_network, step_5_anomaly_detection, step_6_cross_validation, step_7_report_generation, investigation_checklist, module_a_admin_output, module_b_home_advantage, module_c_paper_upstream, module_d_influence_fraud, module_e_ghostwriting, v3_deep_evidence, v3_multi_agent

调用规则：仅在需要具体方法论指导时调用，每次最多请求3个章节，收到后融入分析中。日常对话不需要调用。"""

_SYSTEM_PROMPT_WITH_TOOLS = _BEHAVIOR_SPEC + _TOOLS_APPEND

# Tool schema for function calling
SKILL_TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_skill_section",
        "description": "从学术调查技能手册SKILL.md中读取指定章节的内容，用于获取详细的调查方法论、评估框架或工具使用指南。",
        "parameters": {
            "type": "object",
            "properties": {
                "section_name": {
                    "type": "string",
                    "description": "要读取的章节名称",
                    "enum": [
                        "overview", "when_to_use", "workflow_philosophy", "7_step_framework",
                        "step_1_basic_profile", "step_2_output_quantity", "step_3_quality_assessment",
                        "step_4_relationship_network", "step_5_anomaly_detection",
                        "step_6_cross_validation", "step_7_report_generation",
                        "investigation_checklist", "special_investigation_types", "case_studies",
                        "module_a_admin_output", "module_b_home_advantage", "module_c_paper_upstream",
                        "module_d_influence_fraud", "module_e_ghostwriting",
                        "module_f_funding_network", "module_g_digital_archaeology",
                        "module_h_corruption_network", "v3_deep_evidence", "v3_state_machine",
                        "v3_multi_agent", "full_architecture"
                    ]
                }
            },
            "required": ["section_name"]
        }
    }
}]


class LLMClient:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL.rstrip("/")
        self.model = DEFAULT_MODEL
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Stream LLM response with CLEAN system prompt (no function calling mention)."""
        model = model or self.model
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": temperature,
            "stream": stream,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with self.client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def call_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Non-streaming call with tool support. Uses system prompt WITH tools description."""
        model = model or self.model
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT_WITH_TOOLS}] + messages,
            "temperature": temperature,
            "stream": False,
            "tools": tools,
            "tool_choice": "auto",
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise last_err

    async def close(self):
        await self.client.aclose()


llm = LLMClient()
