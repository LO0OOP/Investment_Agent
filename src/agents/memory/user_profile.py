"""用户画像模块。

负责维护和持久化用户的投资偏好信息。
数据存储在 data/memory/user_profile.json。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

PROFILE_PATH = Path("data/memory/user_profile.json")

# 用户画像默认字段
DEFAULT_PROFILE: Dict[str, Any] = {
    "investment_style": "",
    "risk_preference": "",
    "preferred_sectors": [],
    "watched_stocks": [],
    "investment_horizon": "",
}


def load_profile() -> Dict[str, Any]:
    """从磁盘加载用户画像，不存在则返回默认空画像。"""
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_PROFILE)


def save_profile(profile: Dict[str, Any]) -> None:
    """将用户画像写入磁盘。"""
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def format_profile_for_prompt(profile: Dict[str, Any]) -> str:
    """将用户画像格式化为可读文本，用于注入 System Prompt。"""
    if not any(profile.values()):
        return "暂无用户画像信息。"

    lines = []
    style = profile.get("investment_style", "")
    risk = profile.get("risk_preference", "")
    sectors = profile.get("preferred_sectors", [])
    stocks = profile.get("watched_stocks", [])
    horizon = profile.get("investment_horizon", "")

    if style:
        lines.append(f"投资风格：{style}")
    if risk:
        lines.append(f"风险偏好：{risk}")
    if sectors:
        lines.append(f"关注行业：{'、'.join(sectors)}")
    if stocks:
        lines.append(f"关注股票：{'、'.join(stocks)}")
    if horizon:
        lines.append(f"投资周期：{horizon}")

    return "\n".join(lines) if lines else "暂无用户画像信息。"
