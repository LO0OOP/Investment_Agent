"""Agent 运行主入口。

当前版本采用 ReAct + OpenAI Function Calling 风格：
- 不再显式做单独的意图识别；
- 通过工具 schema + System Prompt，让 Agent 自己决定是否以及如何调用工具；
- 结合简单的会话级内存，在多轮对话中理解用户诉求。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.common.config import settings
from src.common.logger import get_logger, setup_logging
from src.tools import backtest_tool, strategy_info_tool

from .memory import InMemorySessionMemory
from .prompts import get_system_prompt


logger = get_logger(__name__)
# 默认会话内存，用于 CLI 等简单场景。实际接入 API 时可为每个会话维护独立实例。
_GLOBAL_MEMORY = InMemorySessionMemory()


def _build_llm() -> ChatOpenAI:
    """根据配置构建 LLM 客户端（阿里云百炼 OpenAI 兼容模式优先）。"""
    llm_cfg = settings.llm
    provider = str(llm_cfg.get("provider", "openai")).lower()
    model_name = llm_cfg.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(llm_cfg.get("temperature", os.getenv("LLM_TEMPERATURE", 0.3)))

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
        "初始化 LLM: provider=%s model=%s temperature=%s base_url=%s",
        provider,
        model_name,
        temperature,
        base_url,
    )

    if provider in {"openai", "openai_compatible", "bailian", "dashscope"}:
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
        )

    raise ValueError(f"当前示例暂不支持 provider={provider}")


def _build_tools_agent(
    llm: ChatOpenAI,
    history_text: Optional[str] = None,
) -> AgentExecutor:
    """构建一个基于 ReAct + OpenAI Function Calling 的通用工具 Agent。

    不再显式做意图分类，而是通过系统提示 + 工具 schema，
    让大模型自行决定是否以及如何调用工具。
    """
    system_prompt = get_system_prompt() + (
        "\n你可以使用提供的工具(list_strategies, run_backtest)来获取结构化数据。"
        "\n- 当用户询问支持的策略或策略参数时，优先调用 list_strategies；"
        "\n- 当用户希望对某个标的/周期/区间进行回测时，优先调用 run_backtest；"
        "\n- 如果问题与策略/回测无关，可以直接用自然语言回答，并说明当前系统主要聚焦于策略说明和回测分析。"
        "\n在使用工具时，请遵循以下流程："
        "\n1. 先用简短的思考确定是否需要调用工具；"
        "\n2. 如需要，规划好要调用的工具及参数；"
        "\n3. 调用工具并根据返回的结构化数据进行分析；"
        "\n4. 用简体中文给出清晰的结论和解释，提醒用户回测不构成投资建议。"
    )
    if history_text:
        system_prompt += (
            "\n以下是本轮对话之前的历史记录，仅供你理解上下文，请综合考虑：\n"
            f"{history_text}\n"
        )

    tools = [strategy_info_tool, backtest_tool]

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


def run_query(user_input: str, memory: InMemorySessionMemory | None = None) -> Dict[str, Any]:
    """执行一次完整的 Agent 流程，并返回 LangChain 的原始结果字典。

    ReAct 风格：不显式做意图识别，而是让工具 Agent 自行决定
    是否以及如何调用工具（或直接对话回答）。
    """
    # 初始化日志
    app_log_level = settings.app.get("log_level", "INFO")
    setup_logging(level=app_log_level)

    llm = _build_llm()

    # 选择会话内存
    session_memory = memory or _GLOBAL_MEMORY

    # 从内存中取出历史文本，注入到系统提示中，帮助 Agent 在多轮对话中理解上下文
    history_text = session_memory.as_formatted_text()

    # 构建通用工具 Agent（ReAct + function calling）
    executor = _build_tools_agent(llm, history_text)

    # 交给 AgentExecutor 执行，本身会根据工具 schema 和用户输入自行决定是否调用工具
    result = executor.invoke({"input": user_input})

    # 从结果中提取最终回复并写入内存
    output_text = str(result.get("output", ""))
    session_memory.add("user", user_input)
    session_memory.add("assistant", output_text)

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
            print("Agent:", resp.get("output"))
    except KeyboardInterrupt:
        print("\n退出。")
