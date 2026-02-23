"""新闻查询服务

提供给 Agent / 上层调用的新闻查询接口，从本地 SQLite 数据库中按股票代码/名称、时间范围、条数限制拉取新闻。

- 股票名会通过 `stock_mapping.resolve_code` 映射为标准 6 位股票代码；
- 时间范围使用 `publish_time` 文本比较，假定存储为 ISO8601 字符串；
- 返回值为新闻记录列表，每条为一个 dict。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
import sqlite3

from src.common.logger import get_logger
from src.infra.data.stock_mapping import resolve_code



logger = get_logger(__name__)

NewsRecord = Dict[str, Any]

# 与 news_worker 使用同一 SQLite 文件路径
BASE_DIR = Path(__file__).resolve().parents[2]
NEWS_DB_PATH = BASE_DIR / "data" / "news" / "news.db"

MAX_NEWS_LIMIT = 50
DEFAULT_NEWS_LIMIT = 10


def _get_conn() -> sqlite3.Connection:
  """获取新闻数据库连接（只在本模块内部使用）。"""
  NEWS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(NEWS_DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn


def _query_news_by_symbol(
  symbol: str,
  *,
  start_time: Optional[str] = None,
  end_time: Optional[str] = None,
  limit: int = DEFAULT_NEWS_LIMIT,
) -> List[NewsRecord]:
  """按股票代码从 SQLite 新闻库查询新闻记录。"""
  if not symbol:
    return []

  sql = [
    "SELECT id, symbol, title, content, publish_time, source, url, ",
    "       sentiment_label, sentiment_score",
    "  FROM news",
    " WHERE symbol = ?",
  ]
  params: list[Any] = [symbol]

  if start_time:
    sql.append("   AND publish_time >= ?")
    params.append(start_time)
  if end_time:
    sql.append("   AND publish_time <= ?")
    params.append(end_time)

  sql.append(" ORDER BY publish_time DESC")
  sql.append(" LIMIT ?")
  params.append(int(limit))

  query = "\n".join(sql)

  conn = _get_conn()
  try:
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    return [dict(row) for row in rows]
  finally:
    conn.close()



def fetch_news(
  symbol_or_name: str,
  start_time: Optional[str] = None,
  end_time: Optional[str] = None,
  limit: int = DEFAULT_NEWS_LIMIT,
) -> List[NewsRecord]:
  """按股票代码或名称从本地新闻数据库查询新闻。

  参数：
  - symbol_or_name: 股票代码或中文名称，例如 "600000" 或 "浦发银行"；
  - start_time: 起始时间（可选），应与数据库中的 `publish_time` 使用同一时间格式，
    推荐 ISO8601 字符串，例如 "2025-01-01" 或 "2025-01-01T00:00:00"；
  - end_time: 结束时间（可选），格式同上；
  - limit: 返回的最大新闻条数，可选，默认 50，最大不超过 200。

  返回：
  - 按 `publish_time` 倒序排列的新闻记录列表，每条为 dict，字段大致包括：
    id / symbol / title / content / publish_time / source / url / sentiment_label / sentiment_score。
  """
  if not symbol_or_name:
    raise ValueError("symbol_or_name 不能为空")

  # 统一限制 limit，避免一次性返回过多记录
  if limit <= 0:
    limit = DEFAULT_NEWS_LIMIT
  limit = min(limit, MAX_NEWS_LIMIT)

  key = str(symbol_or_name).strip()

  # 使用映射表解析得到标准股票代码
  codes = resolve_code(key)
  if not codes:
    logger.warning("[news_service] 无法解析股票代码: %s", key)
    raise ValueError(f"无法根据输入解析股票代码: {key}")

  db_symbol = codes[0]

  logger.info(
    "[news_service] 查询新闻: input=%s, db_symbol=%s, start=%s, end=%s, limit=%s",
    key,
    db_symbol,
    start_time,
    end_time,
    limit,
  )

  items = _query_news_by_symbol(
    db_symbol,
    start_time=start_time,
    end_time=end_time,
    limit=limit,
  )


  logger.info(
    "[news_service] 查询新闻完成: db_symbol=%s, 返回条数=%s",
    db_symbol,
    len(items),
  )

  return items
