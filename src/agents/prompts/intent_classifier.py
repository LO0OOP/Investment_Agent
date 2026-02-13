"""意图识别 Prompt。

用于指导 LLM 在不同用户请求之间做分类，例如：
- 查看支持的策略
- 运行回测
- 其他/暂不支持
"""
from __future__ import annotations

from .system import get_system_prompt


def get_intent_classifier_prompt(history_snippet: str | None = None) -> str:
    """返回用于意图分类的系统提示文本。

    要求模型仅返回一个意图标签，而不是自然语言。
    可以额外传入一段会话历史摘要，帮助模型在多轮对话中更准确地理解意图。
    """
    base = get_system_prompt()
    extra = (
        "\n现在你的任务是**仅做意图分类**，不要执行具体操作。\n"
        "根据用户的最新一句话，在如下候选中选择一个最合适的意图，并只输出该标签：\n"
        "- view_strategies: 用户想知道有哪些策略、策略含义或参数。\n"
        "- run_backtest: 用户想对某个品种/周期/时间区间使用某个策略跑回测。\n"
        "- unknown: 其他与回测/策略无关，或你无法判断。\n"
        "输出要求：\n"
        "- 只能输出以上三个标签之一；\n"
        "- 不要包含任何多余文字或解释。\n"
    )
    if history_snippet:
        extra += (
            "\n以下是本轮对话之前的历史记录，仅用于帮助你理解当前上下文：\n"
            f"{history_snippet}\n"
            "请结合这些上下文，但仍然只针对用户的最新一句话，选择最合适的意图标签。\n"
        )
    return base + extra

