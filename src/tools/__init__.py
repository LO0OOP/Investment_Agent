"""Agent Tool 注册入口。

目前提供：
- `backtest_tool`：运行回测引擎的 LangChain StructuredTool
- `strategy_info_tool`：查询当前支持的策略及参数说明
"""
from __future__ import annotations

from .backtest_tool import BacktestToolInput, backtest_tool
from .strategy_info_tool import StrategyInfoInput, strategy_info_tool

__all__ = [
    "BacktestToolInput",
    "backtest_tool",
    "StrategyInfoInput",
    "strategy_info_tool",
]
