"""简单的会话级内存实现。

当前仅作为占位，记录最近的若干轮对话，未与 LangChain Memory 深度集成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class InMemorySessionMemory:
    """用 (role, content) 形式保存对话。"""

    max_turns: int = 20
    messages: List[Tuple[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append((role, content))
        if len(self.messages) > self.max_turns:
            # 保留最近 max_turns 条
            self.messages = self.messages[-self.max_turns :]

    def as_formatted_text(self) -> str:
        """将历史对话格式化为纯文本，供 prompt 拼接使用。"""
        return "\n".join(f"{role}: {text}" for role, text in self.messages)
