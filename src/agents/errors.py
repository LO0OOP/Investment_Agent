"""Agent 层异常定义。"""
from __future__ import annotations


class AgentError(RuntimeError):
    """Agent 顶层异常。"""


class IntentRecognitionError(AgentError):
    """意图识别失败或结果不可靠。"""


class PlannerError(AgentError):
    """规划/模板选择出错。"""


class ToolExecutionError(AgentError):
    """Tool 调用失败。"""


__all__ = [
    "AgentError",
    "IntentRecognitionError",
    "PlannerError",
    "ToolExecutionError",
]
