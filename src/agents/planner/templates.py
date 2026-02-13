"""各 Intent 对应的执行模板。

当前版本采用极简规划：
- view_strategies: 仅调用 list_strategies 工具
- run_backtest: 仅调用 run_backtest 工具
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.agents.intent import Intent


@dataclass(slots=True)
class StepTemplate:
    """单步执行模板（预留扩展多步规划）。"""

    description: str
    tool_names: List[str]


_INTENT_PLANS = {
    Intent.VIEW_STRATEGIES: StepTemplate(
        description="查询当前支持的策略及参数。",
        tool_names=["list_strategies"],
    ),
    Intent.RUN_BACKTEST: StepTemplate(
        description="在本地历史数据上运行策略回测。",
        tool_names=["run_backtest"],
    ),
    Intent.UNKNOWN: StepTemplate(
        description="意图不明确，无需调用工具。",
        tool_names=[],
    ),
}


def get_intent_plan(intent: Intent) -> StepTemplate:
    """返回给定意图对应的执行模板。"""
    return _INTENT_PLANS.get(intent, _INTENT_PLANS[Intent.UNKNOWN])
