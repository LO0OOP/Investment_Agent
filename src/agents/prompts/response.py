"""最终回复相关的补充指令。

当前版本主提示在 system.py 中，这里保留扩展点。"""
from __future__ import annotations


def get_response_instructions() -> str:
    """返回对最终回复的补充要求（可拼接到主 Prompt 中）。"""
    return (
        "在总结回测结果时，请尽量做到：\n"
        "- 先给出总体评价（例如：收益/回撤/胜率的大致水平）；\n"
        "- 再简要说明策略在当前市场环境下可能的优缺点；\n"
        "- 最后提醒用户：回测只反映历史表现，不保证未来收益。\n"
    )
