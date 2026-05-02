import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from services.case_store import store
from services.llm_client import llm, SKILL_TOOLS
from services.intent_parser import parse_intent
from services.web_fetcher import fetch_url, search_and_fetch
from services.script_runner import run_script, list_available_scripts
from services.skill_library import get_section
from services.dsml_filter import DSMLFilter, clean_dsml
from models.schemas import ChatRequest

router = APIRouter(prefix="/api/cases", tags=["chat"])


async def _build_messages(case_id: str, user_message: str) -> list:
    """Build message list for LLM context."""
    case = store.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    messages = []
    # Add recent context (last 5 messages)
    for msg in case["messages"][-5:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages


async def _stream_response(case_id: str, user_message: str):
    """SSE stream generator. Yields data: JSON lines."""
    case = store.get(case_id)
    if not case:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Case not found'}, ensure_ascii=False)}\n\n"
        return

    # Save user message
    store.add_message(case_id, "user", user_message)

    # Parse intent
    intent, params = parse_intent(user_message)

    # Simulate agent status for non-chat intents
    if intent == "init":
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'zhu', 'task': '创建案件目录', 'state': 'running'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'zhu', 'task': '创建案件目录', 'state': 'completed'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.3)
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'dududu', 'task': '解析调查需求', 'state': 'running'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'dududu', 'task': '解析调查需求', 'state': 'completed'}, ensure_ascii=False)}\n\n"

    elif intent == "execute":
        tool_name = params.get("tool", "text_profiler")
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'zhu', 'task': tool_name, 'state': 'running'}, ensure_ascii=False)}\n\n"
        try:
            result = await run_script(tool_name, case_dir=case["case_dir"])
            if result["success"]:
                script_output = f"脚本 {tool_name} 执行成功。\n输出:\n{result['stdout'][:4000]}"
            else:
                script_output = f"脚本 {tool_name} 执行失败 (返回码 {result['returncode']})。\n错误:\n{result['stderr'][:2000]}\n输出:\n{result['stdout'][:2000]}"
            store.add_message(case_id, "system", script_output)
        except Exception as e:
            script_output = f"脚本 {tool_name} 调用异常: {str(e)}"
            store.add_message(case_id, "system", script_output)
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'zhu', 'task': tool_name, 'state': 'completed'}, ensure_ascii=False)}\n\n"

    # Web search / fetch intent
    search_context = ""
    if intent == "search":
        query = params.get('query', user_message)
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'huangmao', 'task': '网络搜索: ' + query, 'state': 'running'}, ensure_ascii=False)}\n\n"
        yield "data: " + json.dumps({'type': 'text', 'content': '\n正在启动深度并联搜索...'}, ensure_ascii=False) + "\n\n"
        try:
            search_context = await search_and_fetch(query, max_results=3)
        except Exception as e:
            search_context = f"搜索失败: {str(e)}"
        # Count how many sources were found
        source_count = search_context.count('【来源') if search_context else 0
        if source_count == 0 and search_context and len(search_context) > 50:
            source_count = 1
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'huangmao', 'task': '网络搜索完成', 'state': 'completed'}, ensure_ascii=False)}\n\n"
        yield "data: " + json.dumps({'type': 'text', 'content': '\n已并行抓取 ' + str(source_count) + ' 个信息源，正在交叉验证...\n'}, ensure_ascii=False) + "\n\n"

    elif intent == "fetch":
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'huangmao', 'task': '获取网页内容', 'state': 'running'}, ensure_ascii=False)}\n\n"
        try:
            search_context = await fetch_url(params.get('url', ''), max_chars=6000)
        except Exception as e:
            search_context = f"获取失败: {str(e)}"
        yield f"data: {json.dumps({'type': 'agent_status', 'agent': 'huangmao', 'task': '网页获取完成', 'state': 'completed'}, ensure_ascii=False)}\n\n"

    # Build LLM messages
    try:
        messages = await _build_messages(case_id, user_message)
    except HTTPException:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Case not found'}, ensure_ascii=False)}\n\n"
        return

    # Inject search context if available
    if search_context:
        messages.append({
            "role": "system",
            "content": f"以下是从网络获取的参考信息（已自动抓取），请基于这些信息回答用户问题。注意：信息来源可靠性需标注。\n\n{search_context[:8000]}"
        })

    # === Phase 1: Function calling — let LLM read SKILL.md sections on demand ===
    skill_sections_read = []
    try:
        tool_result = await llm.call_tools(messages, tools=SKILL_TOOLS)
        choice = tool_result.get("choices", [{}])[0]
        msg = choice.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        if tool_calls:
            # Execute each tool call and collect results as plain text
            for tc in tool_calls:
                fn = tc.get("function", {})
                if fn.get("name") == "read_skill_section":
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                        section = args.get("section_name", "")
                        content = get_section(section, max_chars=8000)
                        skill_sections_read.append({"section": section, "content": content})
                    except Exception as e:
                        skill_sections_read.append({"section": "unknown", "content": f"[读取章节失败: {str(e)}]"})

            # Convert tool results into plain-text system messages (no tool_calls / tool roles)
            # This removes function-calling context traces so Phase 2 LLM won't output DSML
            if skill_sections_read:
                sections_text = "\n\n---\n\n".join(
                    f"【已查阅章节: {s['section']}】\n{s['content'][:3000]}"
                    for s in skill_sections_read
                )
                messages.append({
                    "role": "system",
                    "content": f"以下是从学术调查技能手册中查阅的相关章节内容，请基于这些信息进行分析：\n\n{sections_text}"
                })
    except Exception as e:
        # Tool calling failed, proceed without skill sections
        pass

    # Stream LLM response
    full_response = ""
    import re as _re
    dsml_filter = DSMLFilter()
    try:
        async for chunk in llm.chat(messages, stream=True):
            clean_chunk = dsml_filter.feed(chunk)
            if clean_chunk:
                full_response += clean_chunk
                yield f"data: {json.dumps({'type': 'text', 'content': clean_chunk}, ensure_ascii=False)}\n\n"
    except Exception as e:
        # Never expose Python traceback to users
        err_type = type(e).__name__
        if "Connect" in err_type or "Timeout" in err_type:
            friendly = "网络连接不稳定，正在尝试重试..."
        elif "HTTP" in err_type or "Status" in err_type:
            friendly = "服务暂时不可用，请稍后再试。"
        else:
            friendly = "处理过程中遇到异常，请刷新页面重试。"
        yield f"data: {json.dumps({'type': 'error', 'message': friendly}, ensure_ascii=False)}\n\n"
        return

    # Flush remaining buffer and add to response
    remaining = dsml_filter.flush()
    if remaining:
        full_response += remaining
        yield f"data: {json.dumps({'type': 'text', 'content': remaining}, ensure_ascii=False)}\n\n"

    # Clean markdown stars and any residual DSML before saving
    full_response = _re.sub(r'\*\*(.+?)\*\*', r'\1', full_response)
    full_response = _re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', full_response)
    full_response = clean_dsml(full_response)

    # Save assistant message
    store.add_message(case_id, "assistant", full_response)

    # Done
    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"


@router.post("/{case_id}/chat")
async def chat(case_id: str, body: ChatRequest):
    case = store.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return StreamingResponse(
        _stream_response(case_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
