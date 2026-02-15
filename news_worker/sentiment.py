"""news_worker.sentiment

负责调用 LLM 或专门的情绪分析模型，对新闻打情绪标签。

职责：
- 输入一批新闻文本，输出情绪 label/score；
- 不直接做数据库写入，由 repository 负责落库。

当前版本为占位实现，保留接口方便后续接入。
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from src.common.logger import get_logger


logger = get_logger(__name__)


def analyze_sentiment_batch(news_items: Iterable[Dict]) -> List[Dict]:
  """对一批新闻做情绪分析，并返回带有情绪字段的新列表。

  返回的每个元素应在原有字段基础上新增：
  - sentiment_label: 例如 "positive" / "negative" / "neutral"；
  - sentiment_score: 一个 0~1 或 -1~1 的情绪评分（具体由模型决定）。

  当前占位实现：不做真正分析，只返回原样列表。
  """
  items = list(news_items)
  logger.info("[sentiment] 占位情绪分析，新闻条数: %s", len(items))
  # TODO: 接入实际 LLM 或情绪分类模型
  return items
