"""
FastAPI 接口层：为 Agent 暴露 HTTP 接口（支持流式输出）。

使用方式（项目根目录）：

    uvicorn src.api.server:app --reload

- POST /api/chat         : 普通请求，返回完整回答 JSON
- POST /api/chat/stream  : 流式请求，使用 Server-Sent Events (text/event-stream)

前端可以通过 EventSource 或 Fetch 逐步消费流式输出。
"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.common.logger import get_logger, setup_logging
from src.agents.agent_executor import _build_llm, _build_tools_agent, InMemorySessionMemory


logger = get_logger(__name__)

app = FastAPI(title="Investment Agent API", version="0.1.0")

# 允许本地文件页面（file://）或任意前端域名访问，避免 CORS/预检请求 405
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# 简单的内存级会话存储：实际生产中建议换成 Redis 等持久化存储
_SESSIONS: dict[str, InMemorySessionMemory] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


def _get_session_memory(session_id: str | None) -> InMemorySessionMemory:
    """按 session_id 获取/创建会话内存。"""
    if not session_id:
        # 无 session_id 则使用一次性内存
        return InMemorySessionMemory()
    memory = _SESSIONS.get(session_id)
    if memory is None:
        memory = InMemorySessionMemory()
        _SESSIONS[session_id] = memory
    return memory


@app.on_event("startup")
async def _on_startup() -> None:  # pragma: no cover - 启动钩子
    setup_logging()
    logger.info("FastAPI Investment Agent 服务启动")


@app.post("/api/chat")
async def chat(request: ChatRequest) -> JSONResponse:
    """非流式接口：返回完整回答 JSON。

    适合简单集成或调试使用。
    """
    from src.agents.agent_executor import run_query

    memory = _get_session_memory(request.session_id)
    try:
        result = run_query(request.message, memory=memory)
    except Exception as e:  # noqa: BLE001
        logger.exception("/api/chat 处理失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return JSONResponse(result)


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式接口：使用 `.astream_events()` 驱动，返回 SSE 流。

    响应内容类型为 `text/event-stream`，每条消息形如：

        data: {"event": "token", "text": "..."}\n\n
    最后会发送一条 `event=done` 的消息，包含最终的结构化结果。
    """
    memory = _get_session_memory(request.session_id)

    # 为当前请求构建独立的 LLM 和 AgentExecutor
    llm = _build_llm()
    history_text = memory.as_formatted_text()
    executor = _build_tools_agent(llm, history_text)

    async def event_generator() -> AsyncGenerator[bytes, None]:
        final_result: Dict | None = None

        try:
            async for event in executor.astream_events({"input": request.message}, version="v1"):
                kind = event.get("event")
                data = event.get("data") or {}

                # 模型增量输出
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk is not None:
                        content = getattr(chunk, "content", "")
                        if isinstance(content, list):
                            text = "".join(
                                getattr(p, "text", "") or getattr(p, "content", "")
                                for p in content
                            )
                        else:
                            text = str(content or "")
                        if text:
                            payload = {"event": "token", "text": text}
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

                # 链路结束事件
                if kind == "on_chain_end":
                    output = data.get("output")
                    if isinstance(output, dict):
                        final_result = output

            # 结束时发送最终结果，并更新会话记忆
            if final_result is None:
                final_result = {}

            output_text = str(final_result.get("output", ""))
            memory.add("user", request.message)
            memory.add("assistant", output_text)

            done_payload = {"event": "done", "result": final_result}
            # 注意：LangChain 的 output 中可能包含诸如 ToolAgentAction 等非 JSON 可序列化对象，
            # 这里使用 default=str 做一次降级序列化，避免直接抛异常导致流中断。
            yield f"data: {json.dumps(done_payload, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


        except Exception as e:  # noqa: BLE001
            logger.exception("/api/chat/stream 流式处理失败: %s", e)
            error_payload = {"event": "error", "message": str(e)}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode("utf-8")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
