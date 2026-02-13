"""Agent Prompt 统一入口。"""
from __future__ import annotations

from .system import get_system_prompt
from .intent_classifier import get_intent_classifier_prompt
from .response import get_response_instructions
from .strategy_create import get_strategy_creation_prompt

__all__ = [
    "get_system_prompt",
    "get_intent_classifier_prompt",
    "get_response_instructions",
    "get_strategy_creation_prompt",
]
