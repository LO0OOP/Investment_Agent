"""Agent 运行时状态对象。

第一版实现尽量简单，主要用于：
- 记录当前意图
- 预留对话历史/会话信息的挂载点
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from langchain_core.messages import BaseMessage

from .intent import Intent


@dataclass
class AgentState:
    """Agent 在一次会话中的基本状态。"""

    intent: Intent = Intent.UNKNOWN
    history: List[BaseMessage] = field(default_factory=list)
    # 可选扩展字段
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: BaseMessage) -> None:
        self.history.append(message)
