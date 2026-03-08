"""Agent 运行主入口。

当前版本采用 ReAct + OpenAI Function Calling 风格：
- 不再显式做单独的意图识别；
- 通过工具 schema + System Prompt，让 Agent 自己决定是否以及如何调用工具；
- 结合简单的会话级内存，在多轮对话中理解用户诉求。
"""
from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, Optional


from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.common.config import settings
from src.common.logger import get_logger, setup_logging
from src.tools.registry import ALL_TOOLS


from .memory import InMemorySessionMemory, MemoryManager
from .prompts import get_system_prompt



logger = get_logger(__name__)
# 默认会话内存，用于 CLI 等简单场景。实际接入 API 时可为每个会话维护独立实例。
_GLOBAL_MEMORY = InMemorySessionMemory()
# 全局长期记忆管理器（单用户 CLI 模式共享同一实例）
_GLOBAL_LONG_TERM_MEMORY = MemoryManager()


def _build_llm() -> ChatOpenAI:
    """根据配置构建 LLM 客户端（阿里云百炼 OpenAI 兼容模式优先）。"""
    llm_cfg = settings.llm
    provider = str(llm_cfg.get("provider", "openai")).lower()
    model_name = llm_cfg.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(llm_cfg.get("temperature", os.getenv("LLM_TEMPERATURE", 0.3)))
    streaming = bool(llm_cfg.get("streaming", False))

    base_url = (

        llm_cfg.get("base_url")
        or os.getenv("BAILIAN_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or None
    )
    api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未找到大模型 API Key，请在 .env 中配置 BAILIAN_API_KEY 或 OPENAI_API_KEY")

    logger.info(
        "初始化 LLM: provider=%s model=%s temperature=%s base_url=%s streaming=%s",
        provider,
        model_name,
        temperature,
        base_url,
        streaming,
    )

    if provider in {"openai", "openai_compatible", "bailian", "dashscope"}:
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
            streaming=streaming,
        )


    raise ValueError(f"当前示例暂不支持 provider={provider}")


def _build_tools_agent(
    llm: ChatOpenAI,
    history_text: Optional[str] = None,
    user_profile_text: Optional[str] = None,
    summary_text: Optional[str] = None,
) -> AgentExecutor:
    """构建一个基于 ReAct + OpenAI Function Calling 的通用工具 Agent。

    不再显式做意图分类，而是通过系统提示 + 工具 schema，
    让大模型自行决定是否以及如何调用工具。
    """
    system_prompt = get_system_prompt(
        user_profile_text=user_profile_text,
        summary_text=summary_text,
    )
    if history_text:
        system_prompt += (
            "\n以下是本轮对话之前的历史记录，仅供你理解上下文，请综合考虑：\n"
            f"{history_text}\n"
        )

    # 自动注册的所有工具；新增 Tool 只需在 src.tools 下定义，无需修改此处
    tools = list(ALL_TOOLS.values())

    # ReAct + Tools 模式的 Prompt：System 约束 + 用户输入 + agent_scratchpad

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    # create_openai_tools_agent 会使用 OpenAI Function Calling 协议描述 tools schema
    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return executor


def run_query(
    user_input: str,
    memory: InMemorySessionMemory | None = None,
    long_term_memory: MemoryManager | None = None,
) -> Dict[str, Any]:
    """执行一次完整的 Agent 流程，并返回 LangChain 的原始结果字典。

    ReAct 风格：不显式做意图识别，而是让工具 Agent 自行决定
    是否以及如何调用工具（或直接对话回答）。

    Args:
        user_input: 用户当前输入。
        memory: 会话级短期记忆，默认使用全局实例。
        long_term_memory: 长期记忆管理器，默认使用全局实例。
    """
    # 初始化日志
    app_log_level = settings.app.get("log_level", "INFO")
    setup_logging(level=app_log_level)

    llm = _build_llm()

    # 选择会话内存
    session_memory = memory or _GLOBAL_MEMORY
    # 选择长期记忆管理器
    lt_memory = long_term_memory or _GLOBAL_LONG_TERM_MEMORY

    # 读取长期记忆（用户画像 + 历史摘要）
    user_profile_text = lt_memory.get_formatted_profile()
    summary_text = lt_memory.get_summary()

    # 从短期内存中取出历史文本，注入到系统提示中，帮助 Agent 在多轮对话中理解上下文
    history_text = session_memory.as_formatted_text()

    # 构建通用工具 Agent（ReAct + function calling），注入长期记忆
    executor = _build_tools_agent(
        llm,
        history_text=history_text,
        user_profile_text=user_profile_text,
        summary_text=summary_text,
    )

    # 交给 AgentExecutor 执行，本身会根据工具 schema 和用户输入自行决定是否调用工具
    streaming_enabled = bool(settings.llm.get("streaming", False))

    if streaming_enabled:
        # 使用流式事件接口打印输出，同时在最后拿到完整结果
        async def _run_with_streaming() -> Dict[str, Any]:
            final: Dict[str, Any] | None = None
            async for event in executor.astream_events({"input": user_input}, version="v1"):
                kind = event.get("event")
                data = event.get("data") or {}

                # 打印模型生成的 token（包括中间思考和最终回答）
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk is not None:
                        # 对于 OpenAI 兼容模型，content 通常是字符串或列表，这里做一次统一处理
                        content = getattr(chunk, "content", "")
                        if isinstance(content, list):
                            text = "".join(getattr(p, "text", "") or getattr(p, "content", "") for p in content)
                        else:
                            text = str(content or "")
                        if text:
                            print(text, end="", flush=True)

                # 链路结束事件，一般包含最终 output
                if kind == "on_chain_end":
                    output = data.get("output")
                    if isinstance(output, dict):
                        final = output
                    # 打印一个换行，结束当前回答
                    print()

            return final or {}

        result: Dict[str, Any] = asyncio.run(_run_with_streaming())
    else:
        result = executor.invoke({"input": user_input})

    # 从结果中提取最终回复
    output_text = str(result.get("output", ""))

    # 写入短期会话内存
    session_memory.add("user", user_input)
    session_memory.add("assistant", output_text)

    # 写入长期记忆并根据阈值触发更新
    lt_memory.record_message("user", user_input)
    lt_memory.record_message("assistant", output_text)
    lt_memory.maybe_update_memory()

    return result



def create_agent_executor() -> AgentExecutor:
    """为了兼容外部调用，返回一个基于工具的通用 AgentExecutor。

    外部如需完整的对话 + 记忆效果，建议直接调用 `run_query`。
    """
    app_log_level = settings.app.get("log_level", "INFO")
    setup_logging(level=app_log_level)
    llm = _build_llm()
    # 这里不注入历史，只构建一个通用 tools agent，供外部自行管理 history
    return _build_tools_agent(llm, history_text=None)


if __name__ == "__main__":
    setup_logging()
    logger.info("启动回测 Agent 交互示例，输入中文问题，Ctrl+C 退出。")

    try:
        while True:
            question = input("你: ")
            if not question.strip():
                continue
            resp = run_query(question)
            # 如果启用了流式输出，内容已经在流式过程中打印过，这里只在非流式模式下再打印一次完整结果
            if not bool(settings.llm.get("streaming", False)):
                print("Agent:", resp.get("output"))

    except KeyboardInterrupt:
        print("\n退出。")
