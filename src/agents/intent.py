"""Agent 意图枚举与解析函数。

第一版仅支持少量核心意图，后续可以按需扩展。
"""
from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    """Agent 支持的高层意图类型。"""

    VIEW_STRATEGIES = "view_strategies"  # 查询支持的策略/参数
    RUN_BACKTEST = "run_backtest"        # 运行回测
    UNKNOWN = "unknown"                  # 无法识别或暂不支持


def parse_intent(label: str) -> Intent:
    """将 LLM 返回的字符串解析为 Intent。

    解析规则比较宽松，允许大小写差异。
    """
    normalized = (label or "").strip().lower()
    for intent in Intent:
        if normalized == intent.value:
            return intent
    # 简单别名映射
    if normalized in {"list_strategies", "strategy_list", "view_strategy"}:
        return Intent.VIEW_STRATEGIES
    if normalized in {"backtest", "run_backtest", "strategy_backtest"}:
        return Intent.RUN_BACKTEST
    return Intent.UNKNOWN
