"""回测服务接口与示例脚本。

本模块提供两个能力：
- `run_backtest`：供上层（Agent / API / UI）调用的回测接口，可指定品种、周期、策略与参数。
- `main`：示例脚本，使用固定参数调用 `run_backtest`，便于本地调试。

运行示例（项目根目录）：
    python -m src.services.backtest.backtest_runner
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.common.logger import get_logger, setup_logging
from src.infra.data.data_fetcher import DataFetcher
from src.services.backtest.backtest_engine import BacktestConfig, BacktestEngine
from src.services.strategies.base_strategy import BaseStrategy
from src.services.strategies.registry import get_strategy_cls, list_strategies



logger = get_logger(__name__)


def create_strategy(name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
    """根据名称与参数创建策略实例。

    :param name: 策略标识，例如 "ma_cross"、"rsi" 等
    :param params: 传递给策略构造函数的参数字典
    """
    cls = get_strategy_cls(name)
    params = params or {}
    return cls(**params)



def run_backtest(
    symbol: str,
    timeframe: str,
    strategy_name: str,
    strategy_params: Optional[Dict[str, Any]] = None,
    *,
    initial_capital: float = 10_000.0,
    commission: float = 0.001,
    limit: int = 1000,
    lookback_days: Optional[int] = None,
) -> Dict[str, Any]:
    """运行一次完整回测并返回结果。

    这是给上层（Agent / API / UI）调用的核心接口。

    :param symbol: 交易对，例如 "BTCUSDT"
    :param timeframe: 周期，例如 "1h"、"4h"、"1d"
    :param strategy_name: 策略名称（在 `STRATEGY_REGISTRY` 中注册的 key）
    :param strategy_params: 策略构造参数
    :param initial_capital: 初始资金
    :param commission: 手续费率（单边）
    :param limit: 每次增量拉取的最大 K 线条数
    :param lookback_days: 仅使用最近 N 天的数据进行回测（None 表示使用全部本地数据）
    :return: 回测结果字典（由 `BacktestEngine.get_results` 定义）
    """
    fetcher = DataFetcher()

    logger.info("开始同步并加载 K 线数据用于回测: %s %s", symbol, timeframe)
    df = fetcher.sync_ohlcv_to_local(symbol=symbol, timeframe=timeframe, limit=limit)
    if df is None or df.empty:
        raise RuntimeError(f"无法获取回测数据: {symbol} {timeframe}")

    # 根据 lookback_days 限制回测窗口
    if lookback_days is not None and lookback_days > 0:
        import pandas as pd  # 延迟导入，避免在未使用回测时强依赖 pandas

        max_ts = df.index.max()
        window_start = max_ts - pd.Timedelta(days=lookback_days)
        df = df[df.index >= window_start]
        logger.info(
            "仅使用最近 %s 天的数据进行回测: %s -> %s",
            lookback_days,
            df.index[0],
            df.index[-1],
        )

    strategy = create_strategy(strategy_name, strategy_params)
    engine = BacktestEngine(
        strategy=strategy,
        config=BacktestConfig(initial_capital=initial_capital, commission=commission),
    )

    results = engine.run(df)
    logger.info(
        "回测完成: 策略=%s, 总收益率=%.2f%%, 最大回撤=%.2f%%",
        strategy.name,
        results["total_return"] * 100,
        results["max_drawdown"] * 100,
    )
    return results



def main() -> None:
    """示例入口：使用固定参数跑一遍回测。"""
    setup_logging()

    # 示例：使用 MA 双均线策略回测 BTCUSDT 1h
    run_backtest(
        symbol="BTCUSDT",
        timeframe="1h",
        strategy_name="ma_cross",
        strategy_params={"fast_period": 10, "slow_period": 30},
        initial_capital=10_000.0,
        commission=0.001,
        limit=1000,
        lookback_days=30,
    )



if __name__ == "__main__":
    main()
