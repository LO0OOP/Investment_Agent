"""摘要记忆模块。

负责将历史对话压缩为结构化摘要，便于 Agent 在后续对话中快速获取用户背景。
摘要持久化存储在 data/memory/summary.txt。
"""
from __future__ import annotations

from pathlib import Path

SUMMARY_PATH = Path("data/memory/summary.txt")


def load_summary() -> str:
    """从磁盘加载摘要，不存在则返回空字符串。"""
    if SUMMARY_PATH.exists():
        return SUMMARY_PATH.read_text(encoding="utf-8").strip()
    return ""


def save_summary(summary: str) -> None:
    """将摘要写入磁盘。"""
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(summary.strip(), encoding="utf-8")
