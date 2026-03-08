"""记忆管理器。

统一管理 Summary Memory 和 User Profile 的读取、更新与持久化。
- 每 UPDATE_INTERVAL 轮对话触发一次 LLM 更新（摘要 + 用户画像）。
- 采用懒加载：首次 get_* 时才从磁盘加载数据。

注意：本模块位于 `src.agents.memory`，供 Agent 执行器直接使用。
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI

from src.common.config import settings
from src.common.logger import get_logger
from .summary_memory import load_summary, save_summary
from .user_profile import load_profile, save_profile, format_profile_for_prompt

logger = get_logger(__name__)

# 每隔多少轮触发一次记忆更新
UPDATE_INTERVAL = 5



class MemoryManager:
    """长期记忆管理器（摘要记忆 + 用户画像）。

    Usage::

        mm = MemoryManager()

        # 在 Agent 回答前读取
        profile_text = mm.get_formatted_profile()
        summary_text = mm.get_summary()

        # Agent 回答后记录消息
        mm.record_message("user", user_input)
        mm.record_message("assistant", output_text)

        # 检查是否需要更新记忆
        mm.maybe_update_memory()
    """

    def __init__(self, update_interval: int = UPDATE_INTERVAL) -> None:
        self.update_interval = update_interval

        # 内存缓存（首次 get 时从磁盘加载）
        self._profile: Optional[Dict[str, Any]] = None
        self._summary: Optional[str] = None

        # 当前会话的对话记录，格式 (role, content)
        self._session_messages: List[Tuple[str, str]] = []
        # 自上次更新以来积累的消息数量（每条消息算 1 条）
        self._messages_since_update: int = 0

        # 懒加载 LLM（只在实际需要更新时才创建），摘要与画像各自可独立配置
        self._summary_llm: Optional[ChatOpenAI] = None
        self._profile_llm: Optional[ChatOpenAI] = None

        # 后台更新线程控制
        self._update_thread: Optional[threading.Thread] = None
        self._update_lock = threading.Lock()
        self._update_in_progress: bool = False


    # ------------------------------------------------------------------
    # 公开读接口
    # ------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """返回用户画像字典。"""
        if self._profile is None:
            self._profile = load_profile()
        return self._profile

    def get_formatted_profile(self) -> str:
        """返回适合注入 prompt 的用户画像文本。"""
        return format_profile_for_prompt(self.get_user_profile())

    def get_summary(self) -> str:
        """返回历史摘要文本。"""
        if self._summary is None:
            self._summary = load_summary()
        return self._summary

    # ------------------------------------------------------------------
    # 记录消息
    # ------------------------------------------------------------------

    def record_message(self, role: str, content: str) -> None:
        """记录一条对话消息（role: 'user' 或 'assistant'）。"""
        self._session_messages.append((role, content))
        self._messages_since_update += 1

    # ------------------------------------------------------------------
    # 周期性更新入口
    # ------------------------------------------------------------------

    def maybe_update_memory(self) -> None:
        """当积累消息数达到阈值时，触发摘要和用户画像的更新。

        - 改为后台线程执行，避免阻塞用户输入。
        - 若已有后台更新在运行，则本轮跳过，等待下一轮累积。
        """
        threshold = self.update_interval * 2  # 10 轮 = 20 条消息
        if self._messages_since_update < threshold:
            return

        # 如果后台正在跑更新，直接跳过，等待下一轮触发
        if self._update_in_progress:
            logger.info("已有长期记忆更新正在进行，本轮跳过。")
            return

        recent_text = self._format_recent_messages()
        # 触发后立即重置计数，避免重复触发
        self._messages_since_update = 0

        def _run():
            with self._update_lock:
                self._update_in_progress = True
            try:
                logger.info("后台更新长期记忆开始…")
                self._update_summary(recent_text)
                self._update_profile(recent_text)
                logger.info("后台更新长期记忆完成。")
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("长期记忆更新失败：%s", exc)
            finally:
                self._update_in_progress = False

        # 后台线程，避免阻塞主流程
        self._update_thread = threading.Thread(target=_run, daemon=True)
        self._update_thread.start()


    # ------------------------------------------------------------------
    # 内部更新逻辑
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # LLM 构建（摘要/画像可使用独立模型配置）
    # ------------------------------------------------------------------

    @staticmethod
    def _build_llm_from_cfg(cfg: Dict[str, Any], default_temperature: float = 0.3) -> ChatOpenAI:
        provider = str(cfg.get("provider") or settings.llm.get("provider", "openai")).lower()
        model_name = cfg.get("model") or settings.llm.get("model") or os.getenv("LLM_MODEL", "gpt-4o-mini")
        temperature = float(cfg.get("temperature", default_temperature))

        base_url = (
            cfg.get("base_url")
            or settings.llm.get("base_url")
            or os.getenv("BAILIAN_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or None
        )
        api_key = os.getenv("BAILIAN_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("未找到大模型 API Key")

        if provider in {"openai", "openai_compatible", "bailian", "dashscope"}:
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                base_url=base_url,
                api_key=api_key,
                streaming=False,  # 记忆更新不需要流式
            )
        raise ValueError(f"不支持的 provider: {provider}")

    def _get_summary_llm(self) -> ChatOpenAI:
        if self._summary_llm is None:
            cfg = settings.llm.get("summary_llm", {}) if hasattr(settings, "llm") else {}
            self._summary_llm = self._build_llm_from_cfg(cfg, default_temperature=0.2)
        return self._summary_llm

    def _get_profile_llm(self) -> ChatOpenAI:
        if self._profile_llm is None:
            cfg = settings.llm.get("profile_llm", {}) if hasattr(settings, "llm") else {}
            self._profile_llm = self._build_llm_from_cfg(cfg, default_temperature=0.2)
        return self._profile_llm


    def _format_recent_messages(self) -> str:
        """将最近 update_interval*2 条消息格式化为文本。"""
        recent = self._session_messages[-(self.update_interval * 2):]
        return "\n".join(f"{role}: {text}" for role, text in recent)

    def _update_summary(self, recent_text: str) -> None:
        """调用 LLM 更新摘要并持久化。"""
        old_summary = self.get_summary()

        prompt = f"""你是一个对话总结助手。

当前摘要：

{old_summary if old_summary else "（暂无摘要）"}

新的对话：

{recent_text}

请更新摘要，使其更好地描述用户的投资背景和历史讨论内容。
要求：
- 保持简洁，不超过 200 字
- 重点记录用户关注的股票、行业、投资观点和重要结论
- 如果没有新的有价值信息，可以保持原摘要不变

直接输出更新后的摘要文本，不需要额外说明。"""

        llm = self._get_summary_llm()
        result = llm.invoke(prompt)
        new_summary = result.content.strip()


        if new_summary:
            self._summary = new_summary
            save_summary(new_summary)
            logger.info("摘要已更新（%d 字）。", len(new_summary))

    def _update_profile(self, recent_text: str) -> None:
        """调用 LLM 更新用户画像并持久化。"""
        old_profile = self.get_user_profile()
        old_profile_json = json.dumps(old_profile, ensure_ascii=False, indent=2)

        prompt = f"""你是一个投资用户画像提取助手。

当前用户画像：

{old_profile_json}

以下是最近的用户对话：

{recent_text}

请更新用户画像，并输出 JSON。

字段包括：
- investment_style：投资风格（如 value investing / growth investing / short-term trading 等）
- risk_preference：风险偏好（low / medium / high）
- preferred_sectors：关注行业列表（如 ["banking", "liquor"]）
- watched_stocks：关注股票列表（如 ["贵州茅台", "浦发银行"]）
- investment_horizon：投资周期（short-term / medium-term / long-term）

规则：
- 如果对话中没有相关新信息，请保持原值不变
- watched_stocks 和 preferred_sectors 使用追加方式（不删除已有内容，只新增）
- 只输出 JSON，不要任何额外说明

示例输出：
{{
  "investment_style": "value investing",
  "risk_preference": "medium",
  "preferred_sectors": ["banking", "liquor"],
  "watched_stocks": ["贵州茅台", "浦发银行"],
  "investment_horizon": "long-term"
}}"""

        llm = self._get_profile_llm()
        result = llm.invoke(prompt)
        raw = result.content.strip()


        # 提取 JSON（兼容 LLM 可能输出 markdown 代码块的情况）
        new_profile = self._parse_json_from_llm(raw, old_profile)

        if new_profile:
            self._profile = new_profile
            save_profile(new_profile)
            logger.info("用户画像已更新：%s", new_profile)

    @staticmethod
    def _parse_json_from_llm(
        raw: str, fallback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON，提取失败时返回 fallback。"""
        # 去除 markdown 代码块
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试提取 {...} 内容
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning("无法解析 LLM 返回的用户画像 JSON，保留原画像。原始内容：%s", raw[:200])
            return fallback
