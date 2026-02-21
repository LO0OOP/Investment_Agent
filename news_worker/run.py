"""news_worker.run

新闻 Worker 启动入口：
- 从本地配置读取拉取频率和**股票关键词**（推荐股票中文名，例如 "浦发银行"）；
- 周期性地拉取新闻、清洗去重，并写入数据库。

使用方式（项目根目录）：

    python -m news_worker.run

后续可以将本模块配置为独立进程或服务长期运行。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.common.logger import get_logger, setup_logging

from .collector import collect_news_for_symbols
from .processor import clean_and_deduplicate
from .repository import init_db, insert_news_batch
from .scheduler import run_schedule_forever


logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "news_worker" / "config.yaml"


def load_config() -> Dict[str, Any]:
  if not CONFIG_PATH.exists():
    raise FileNotFoundError(f"未找到新闻配置文件: {CONFIG_PATH}")
  with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
  return data.get("news", {})


def run_once(config: Dict[str, Any]) -> None:
  symbols: List[str] = list(config.get("symbols", []))
  if not symbols:
    logger.warning("[run_once] 配置中未找到任何股票关键词（名称/代码），跳过本轮")
    return

  limit = int(config.get("per_symbol_limit", 50))

  logger.info("[run_once] 开始本轮新闻拉取: keywords=%s, limit=%s", symbols, limit)


  # 1. 拉取原始新闻
  raw_items = collect_news_for_symbols(symbols, limit_per_symbol=limit)
  if not raw_items:
    logger.info("[run_once] 本轮未拉取到任何新闻")
    return

  # 2. 清洗 & 去重
  processed_items = clean_and_deduplicate(raw_items)
  if not processed_items:
    logger.info("[run_once] 清洗后无有效新闻")
    return

  # 3. 写入数据库
  inserted = insert_news_batch(processed_items)
  logger.info("[run_once] 本轮插入新闻条数: %s", inserted)


def main() -> None:
  setup_logging()
  logger.info("[news_worker] 启动新闻 Worker")

  init_db()
  config = load_config()

  interval = int(config.get("fetch_interval_seconds", 600))
  logger.info("[news_worker] 拉取间隔 %s 秒", interval)

  # 首先执行一次，再进入调度循环
  run_once(config)
  run_schedule_forever(interval_seconds=interval, job=lambda: run_once(config))


if __name__ == "__main__":
  main()
