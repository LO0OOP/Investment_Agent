"""Agent 层对外入口。

第一版对外提供两个便捷函数：
- `run_query`: 给定用户输入，完成一次完整的意图识别 + 工具调用 + 回复生成。
- `create_agent_executor`: 返回一个基础的 AgentExecutor（默认不开放工具），主要用于后续集成。"""
from __future__ import annotations

from .agent_executor import create_agent_executor, run_query

__all__ = ["create_agent_executor", "run_query"]
