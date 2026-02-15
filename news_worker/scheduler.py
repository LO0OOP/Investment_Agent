"""news_worker.scheduler

简单的调度器，负责以固定频率运行新闻拉取 Pipeline。

当前实现使用 while True + sleep 的方式，适合作为独立进程长期运行。
后续如果需要更复杂的调度（如多任务、cron 表达式），可以接入 APScheduler 等库。
"""
from __future__ import annotations

import time
from typing import Callable

from src.common.logger import get_logger


logger = get_logger(__name__)


def run_schedule_forever(interval_seconds: int, job: Callable[[], None]) -> None:
  """以固定间隔持续运行指定任务。"""
  logger.info("[scheduler] 启动调度，间隔 %s 秒", interval_seconds)
  try:
    while True:
      start = time.time()
      try:
        logger.info("[scheduler] 开始执行一次任务")
        job()
      except Exception as e:  # noqa: BLE001
        logger.exception("[scheduler] 任务执行异常: %s", e)
      elapsed = time.time() - start
      sleep_sec = max(0.0, interval_seconds - elapsed)
      logger.info("[scheduler] 本轮耗时 %.2f 秒，休眠 %.2f 秒后再次执行", elapsed, sleep_sec)
      time.sleep(sleep_sec)
  except KeyboardInterrupt:
    logger.info("[scheduler] 收到中断信号，退出调度循环")
