"""Tool 调度与权限控制。

根据识别出来的 Intent，决定当前对话允许使用哪些 Tool。
"""
from __future__ import annotations

from typing import List

from langchain_core.tools import BaseTool

from src.agents.intent import Intent
from src.tools import backtest_tool, strategy_info_tool, news_query_tool



def get_tools_for_intent(intent: Intent) -> List[BaseTool]:
    """根据意图返回允许使用的 Tool 列表。"""
    if intent == Intent.VIEW_STRATEGIES:
        return [strategy_info_tool]
    if intent == Intent.RUN_BACKTEST:
        # 回测时既可能需要先查策略，也可能直接跑，因此两个都开放
        return [strategy_info_tool, backtest_tool]
    # UNKNOWN 或其他情况：先不开放任何工具，仅让模型做解释性回复
    return []
