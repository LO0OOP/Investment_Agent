"""news_worker.processor

负责对原始新闻做清洗、去重和过滤。

当前版本仅提供占位实现：
- 保留接口与基本结构，后续可以逐步补充 HTML 清洗、去重、过滤逻辑。
"""
from __future__ import annotations

from typing import Dict, List

from src.common.logger import get_logger


logger = get_logger(__name__)

NewsItem = Dict[str, object]


def clean_and_deduplicate(items: List[NewsItem]) -> List[NewsItem]:
  """清洗和去重新闻条目。

  目标行为（后续可逐步完善）：
  - 清洗 HTML 标签，保留纯文本；
  - 以 (symbol, title, publish_time) 或 hash 作为去重依据；
  - 过滤明显的垃圾内容；
  - 对过长的正文做截断（例如保留前 N 字）。

  当前占位实现：仅简单去掉重复 (symbol, title, publish_time) 组合。
  """
  if not items:
    return []

  seen_keys = set()
  result: List[NewsItem] = []

  for item in items:
    symbol = str(item.get("symbol", ""))
    title = str(item.get("title", ""))
    publish_time = str(item.get("publish_time", ""))
    key = (symbol, title, publish_time)
    if key in seen_keys:
      continue
    seen_keys.add(key)
    result.append(item)

  logger.info("[processor] 清洗/去重前后条数: %s -> %s", len(items), len(result))
  return result
