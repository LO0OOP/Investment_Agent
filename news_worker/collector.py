"""news_worker.collector

负责从外部数据源（当前为 akshare）拉取原始新闻，并输出统一的结构化格式。

后续如果要接入其他新闻源，可以在这里做封装，保持对外结构不变。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import akshare as ak  # type: ignore

from src.common.logger import get_logger


logger = get_logger(__name__)


NewsItem = Dict[str, Any]


def _parse_datetime(value: Any) -> str:
  """将 akshare 返回的日期/时间转换为 ISO8601 字符串。"""
  if value is None:
    return ""
  if isinstance(value, datetime):
    return value.isoformat()
  try:
    # akshare 新闻时间字段通常是字符串格式，例如 "2024-01-01 12:34:56"
    dt = datetime.fromisoformat(str(value).replace("/", "-").strip())
    return dt.isoformat()
  except Exception:  # noqa: BLE001
    return str(value)


def collect_stock_news(symbol: str, limit: int = 50) -> List[NewsItem]:
  """拉取单只股票的新闻列表，返回标准化结构。

  当前示例使用 Eastmoney 的股票新闻接口 `stock_news_em`，
  如果 akshare 版本有差异，可根据实际文档调整字段名。

  返回的每条新闻为一个字典，字段包括：
  - symbol: 股票代码
  - title: 标题
  - content: 正文（如接口不提供，则为摘要或空字符串）
  - publish_time: 发布时间（ISO8601 字符串）
  - source: 新闻来源
  - url: 新闻详情地址（如有）
  - raw: 原始记录（便于后续调试）
  """
  logger.info("[collector] 拉取股票新闻: symbol=%s, limit=%s", symbol, limit)

  try:
    # 示例使用 ak.stock_news_em；如果接口签名不同，可在此处调整
    #TODO: 注意：stock_news_em拉取的方式为直接搜索股票代码，搜出的新闻参考意义不大，待完善
    df = ak.stock_news_em(symbol=symbol, page=1, size=limit)  # type: ignore[attr-defined]
  except Exception as e:  # noqa: BLE001
    logger.error("[collector] 拉取股票新闻失败: %s", e)
    return []

  if df is None or df.empty:
    logger.info("[collector] 无新闻数据: %s", symbol)
    return []

  items: List[NewsItem] = []
  for _, row in df.iterrows():
    # 根据 akshare 实际返回字段名做映射，这里给出常见示例
    title = str(row.get("title") or row.get("新闻标题") or "").strip()
    content = str(row.get("content") or row.get("摘要") or "").strip()
    publish_time = _parse_datetime(row.get("datetime") or row.get("发布时间") or row.get("pub_time"))
    source = str(row.get("source") or row.get("来源") or "").strip()
    url = str(row.get("url") or row.get("新闻链接") or "").strip()

    if not title:
      continue

    items.append(
      {
        "symbol": symbol,
        "title": title,
        "content": content,
        "publish_time": publish_time,
        "source": source,
        "url": url,
        "raw": row.to_dict(),
      }
    )

  logger.info("[collector] 拉取到新闻条数: %s (%s)", len(items), symbol)
  return items


def collect_news_for_symbols(symbols: list[str], limit_per_symbol: int = 50) -> list[NewsItem]:
  """批量拉取多只股票的新闻。"""
  all_items: list[NewsItem] = []
  for sym in symbols:
    sym = sym.strip()
    if not sym:
      continue
    items = collect_stock_news(sym, limit=limit_per_symbol)
    all_items.extend(items)
  return all_items
