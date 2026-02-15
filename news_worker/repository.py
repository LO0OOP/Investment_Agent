"""news_worker.repository

新闻存储与查询层，负责与数据库交互，不包含业务逻辑。

职责：
- 初始化数据库和表结构；
- 插入新闻记录；
- 查询新闻是否存在；
- 更新情绪分析字段。

当前实现使用 SQLite，数据库文件位于 data/news/news.db。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import sqlite3

from src.common.logger import get_logger


logger = get_logger(__name__)

# 数据库存放路径
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "news"
DB_PATH = DATA_DIR / "news.db"


def _get_conn() -> sqlite3.Connection:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(DB_PATH)
  # 返回 dict-like 行
  conn.row_factory = sqlite3.Row
  return conn


def init_db() -> None:
  """初始化数据库表结构（如不存在则创建）。"""
  conn = _get_conn()
  try:
    cur = conn.cursor()
    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        publish_time TEXT,
        source TEXT,
        url TEXT,
        raw_json TEXT,
        sentiment_label TEXT,
        sentiment_score REAL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      );
      """
    )
    # 唯一索引，用于避免重复插入同一条新闻
    cur.execute(
      """
      CREATE UNIQUE INDEX IF NOT EXISTS idx_news_unique
      ON news(symbol, title, publish_time);
      """
    )
    conn.commit()
    logger.info("[repository] 数据库已初始化: %s", DB_PATH)
  finally:
    conn.close()


def insert_news_batch(items: Iterable[Dict[str, object]]) -> int:
  """批量插入新闻记录，返回成功插入的条数。

  注意：依赖唯一索引避免重复插入。
  """
  conn = _get_conn()
  inserted = 0
  try:
    cur = conn.cursor()
    for item in items:
      try:
        cur.execute(
          """
          INSERT OR IGNORE INTO news
          (symbol, title, content, publish_time, source, url, raw_json)
          VALUES (?, ?, ?, ?, ?, ?, ?);
          """,
          (
            item.get("symbol"),
            item.get("title"),
            item.get("content"),
            item.get("publish_time"),
            item.get("source"),
            item.get("url"),
            str(item.get("raw")),
          ),
        )
        if cur.rowcount > 0:
          inserted += 1
      except sqlite3.Error as e:  # noqa: BLE001
        logger.error("[repository] 插入新闻失败: %s", e)
    conn.commit()
  finally:
    conn.close()

  logger.info("[repository] 本次插入新闻条数: %s", inserted)
  return inserted


def news_exists(symbol: str, title: str, publish_time: str) -> bool:
  """判断新闻是否已存在。"""
  conn = _get_conn()
  try:
    cur = conn.cursor()
    cur.execute(
      "SELECT 1 FROM news WHERE symbol=? AND title=? AND publish_time=? LIMIT 1;",
      (symbol, title, publish_time),
    )
    row = cur.fetchone()
    return row is not None
  finally:
    conn.close()


def update_sentiment(news_id: int, label: str, score: Optional[float]) -> None:
  """更新指定新闻的情绪标签和分数。"""
  conn = _get_conn()
  try:
    cur = conn.cursor()
    cur.execute(
      """
      UPDATE news
      SET sentiment_label = ?, sentiment_score = ?, updated_at = datetime('now')
      WHERE id = ?;
      """,
      (label, score, news_id),
    )
    conn.commit()
  finally:
    conn.close()
