"""策略基类

所有交易策略都应继承此基类，并实现 `generate_signal` 方法。
未来 Agent 生成的策略也应遵循相同接口，方便统一回测与实盘对接。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.common.logger import get_logger


logger = get_logger(__name__)


class BaseStrategy(ABC):
    """策略基类。

    约定：
    - `generate_signal(data)` 接收一段历史 K 线数据（通常为 DataFrame），返回信号：
      * 1 = 开多 / 买入
      * -1 = 平多 / 卖出
      * 0 = 无操作
    - 策略内部可维护自身状态（如仓位、入场价等），但资金曲线与成交明细由回测引擎负责。
    """

    def __init__(self, name: str) -> None:
        """初始化策略。

        :param name: 策略名称
        """
        self.name = name
        self.position: int = 0  # 当前持仓状态: 0=空仓, 1=多头, -1=空头
        self.entry_price: float = 0.0  # 入场价格（如策略内部需要用）
        self.trades: list[dict[str, Any]] = []  # 策略内部记录的信号/交易，可选

    @abstractmethod
    def generate_signal(self, data: Any) -> int:
        """生成交易信号。

        :param data: 市场数据（通常为 pandas.DataFrame 的一个切片）
        :return: 1=买入, -1=卖出, 0=持有
        """

    def on_bar(self, data: Any) -> int:
        """每个 K 线周期调用，默认直接调用 `generate_signal`。

        子类如需在每根 K 线上做额外维护逻辑，可以重写此方法。
        """
        return self.generate_signal(data)

    def execute_trade(self, signal: int, price: float, timestamp: Any) -> None:
        """执行交易（可选辅助方法）。

        当前项目中成交撮合与权益计算由回测引擎负责，因此此方法主要用于：
        - 策略自用的日志记录
        - 统计内部性能指标
        """
        if signal == 1 and self.position == 0:
            # 买入
            self.position = 1
            self.entry_price = price
            self.trades.append(
                {
                    "timestamp": timestamp,
                    "action": "BUY",
                    "price": price,
                }
            )
            logger.info("[%s] 策略买入 @ %s", timestamp, price)

        elif signal == -1 and self.position == 1:
            # 卖出
            profit = (price - self.entry_price) / self.entry_price if self.entry_price else 0.0
            self.position = 0
            self.trades.append(
                {
                    "timestamp": timestamp,
                    "action": "SELL",
                    "price": price,
                    "profit": profit,
                }
            )
            logger.info("[%s] 策略卖出 @ %s, 收益率: %.2f%%", timestamp, price, profit * 100)
            self.entry_price = 0.0

    def get_performance(self) -> list[dict[str, Any]]:
        """获取策略内部记录的信号/交易表现。"""
        return self.trades
