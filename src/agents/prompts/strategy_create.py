"""生成策略 Prompt（预留）。

当前版本暂不实际调用，只作为将来由 Agent 生成策略代码时使用的占位。"""
from __future__ import annotations


def get_strategy_creation_prompt() -> str:
    """返回用于生成策略的 System Prompt（占位）。"""
    return (
        "你是一个量化策略研发助手，将根据用户用自然语言描述的交易想法，生成 Python 策略代码。\n"
        "当前版本仍在迭代中，请勿实际调用此能力。\n"
    )
