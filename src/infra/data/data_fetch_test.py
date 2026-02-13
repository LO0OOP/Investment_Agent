"""数据拉取与本地增量存储测试脚本。

运行方式（在项目根目录）：
    python -m src.infra.data.data_fetch_test

要求：
- 已正确配置 configs/exchange.yaml 中的交易所信息（默认 binance）
- 已安装 requirements.txt 中的依赖
"""
from __future__ import annotations

from src.common.logger import get_logger, setup_logging
from src.infra.data.data_fetcher import DataFetcher


logger = get_logger(__name__)


def main() -> None:
    # 初始化全局日志（只应调用一次）
    setup_logging()

    fetcher = DataFetcher()

    symbol = "BTCUSDT"
    timeframe = "1h"

    logger.info("开始同步 K 线数据: %s %s", symbol, timeframe)
    df = fetcher.sync_ohlcv_to_local(symbol=symbol, timeframe=timeframe, limit=1000)

    if df is None or df.empty:
        logger.error("同步 K 线失败或无数据: %s %s", symbol, timeframe)
        return

    logger.info("同步完成，K 线总条数: %s", len(df))
    logger.info("最新 5 条数据:\n%s", df.tail())


if __name__ == "__main__":
    main()
