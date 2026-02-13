"""回测引擎

用于在本地历史行情数据上测试策略的表现。

设计目标：
- 与具体行情来源解耦：只依赖传入的 pandas.DataFrame（索引为时间、包含 `close` 列）。
- 使用统一日志体系而非 print。
- 接口尽量简单，方便未来被 Agent 自动调用。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from src.common.logger import get_logger


logger = get_logger(__name__)


@dataclass(slots=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    commission: float = 0.001  # 手续费率（单边）


class BacktestEngine:
    """简单的单标的多头回测引擎。"""

    def __init__(self, strategy: Any, config: BacktestConfig | None = None) -> None:
        """初始化回测引擎。

        :param strategy: 实现了 `on_bar(data) -> int` 的策略实例
        :param config: 回测配置，不传则使用默认
        """
        self.strategy = strategy
        self.config = config or BacktestConfig()

        self.initial_capital: float = self.config.initial_capital
        self.commission: float = self.config.commission

        self.capital: float = self.initial_capital
        self.position: int = 0  # 0=空仓, 1=多头
        self.shares: float = 0.0

        self.equity_curve: list[dict[str, Any]] = []
        self.trades: list[dict[str, Any]] = []

    def run(self, data: pd.DataFrame) -> dict[str, Any]:
        """运行回测。

        :param data: 历史数据 DataFrame，索引为时间，至少包含 `close` 列。
        :return: 回测结果字典
        """
        if data.empty:
            raise ValueError("回测数据为空")

        logger.info("开始回测策略: %s", getattr(self.strategy, "name", type(self.strategy).__name__))
        logger.info("初始资金: %.2f", self.initial_capital)
        logger.info("数据范围: %s -> %s", data.index[0], data.index[-1])

        for i in range(len(data)):
            # 截取截至当前的历史数据片段
            current_data = data.iloc[: i + 1]
            current_bar = data.iloc[i]
            timestamp = current_bar.name
            price = float(current_bar["close"])

            # 生成信号
            signal = self.strategy.on_bar(current_data)

            # 执行交易逻辑（仅支持多头）
            if signal == 1 and self.position == 0:
                # 开多：全仓买入
                cost = self.capital * (1 - self.commission)
                self.shares = cost / price
                self.position = 1
                self.capital = 0.0
                self.trades.append(
                    {
                        "timestamp": timestamp,
                        "action": "BUY",
                        "price": price,
                        "shares": self.shares,
                    }
                )
                logger.debug("[%s] BUY @ %s, shares=%.6f", timestamp, price, self.shares)

            elif signal == -1 and self.position == 1:
                # 平多：全部卖出
                self.capital = self.shares * price * (1 - self.commission)
                self.trades.append(
                    {
                        "timestamp": timestamp,
                        "action": "SELL",
                        "price": price,
                        "shares": self.shares,
                        "capital": self.capital,
                    }
                )
                logger.debug("[%s] SELL @ %s, shares=%.6f, capital=%.2f", timestamp, price, self.shares, self.capital)
                self.shares = 0.0
                self.position = 0

            # 计算当前权益
            if self.position == 1:
                equity = self.shares * price
            else:
                equity = self.capital

            self.equity_curve.append({"timestamp": timestamp, "equity": equity})

        # 如果最后还有持仓，按最后收盘价平仓
        if self.position == 1 and self.shares > 0:
            final_price = float(data.iloc[-1]["close"])
            self.capital = self.shares * final_price * (1 - self.commission)
            self.trades.append(
                {
                    "timestamp": data.index[-1],
                    "action": "FINAL_SELL",
                    "price": final_price,
                    "shares": self.shares,
                    "capital": self.capital,
                }
            )
            self.shares = 0.0
            self.position = 0

        return self.get_results()

    def get_results(self) -> dict[str, Any]:
        """汇总并返回回测结果。"""
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index("timestamp", inplace=True)

        # 计算收益率
        final_equity = float(equity_df["equity"].iloc[-1]) if not equity_df.empty else self.initial_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 计算最大回撤
        equity_df["cummax"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (equity_df["equity"] - equity_df["cummax"]) / equity_df["cummax"]
        max_drawdown = float(equity_df["drawdown"].min()) if not equity_df.empty else 0.0

        # 计算胜率
        sell_trades: Iterable[dict[str, Any]] = [t for t in self.trades if t["action"].startswith("SELL")]
        total_trades = len(list(sell_trades))
        winning_trades = [t for t in self.trades if t["action"].startswith("SELL") and t.get("capital", 0) > self.initial_capital]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0

        results: dict[str, Any] = {
            "initial_capital": self.initial_capital,
            "final_capital": final_equity,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "equity_curve": equity_df,
            "trades": self.trades,
        }

        self.print_results(results)
        return results

    def print_results(self, results: dict[str, Any]) -> None:
        """打印回测结果（使用日志而非裸 print）。"""
        logger.info("===== 回测结果 =====")
        logger.info("初始资金: %.2f", results["initial_capital"])
        logger.info("最终资金: %.2f", results["final_capital"])
        logger.info("总收益率: %.2f%%", results["total_return"] * 100)
        logger.info("最大回撤: %.2f%%", results["max_drawdown"] * 100)
        logger.info("交易次数: %s", results["total_trades"])
        logger.info("胜率: %.2f%%", results["win_rate"] * 100)
