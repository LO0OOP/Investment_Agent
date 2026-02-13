"""双均线交叉策略

当短期均线上穿长期均线时买入，下穿时卖出。
"""
from __future__ import annotations

import pandas as pd

from src.services.strategies.base_strategy import BaseStrategy
from src.services.indicators.technical_indicators import TechnicalIndicators


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略。"""

    def __init__(self, fast_period: int = 10, slow_period: int = 30) -> None:
        """初始化策略。

        :param fast_period: 快线周期
        :param slow_period: 慢线周期
        """
        super().__init__("MA Cross Strategy")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.indicators = TechnicalIndicators()

    def generate_signal(self, data: pd.DataFrame) -> int:
        """生成交易信号。

        :param data: 市场数据 (DataFrame)，索引为时间，包含 `close` 列
        :return: 1=买入, -1=卖出, 0=持有
        """
        if len(data) < self.slow_period:
            return 0

        # 计算快慢均线
        fast_ma = self.indicators.sma(data["close"], self.fast_period)
        slow_ma = self.indicators.sma(data["close"], self.slow_period)

        # 获取最近两个值
        fast_ma_current = fast_ma.iloc[-1]
        fast_ma_previous = fast_ma.iloc[-2]
        slow_ma_current = slow_ma.iloc[-1]
        slow_ma_previous = slow_ma.iloc[-2]

        # 判断交叉
        if fast_ma_previous <= slow_ma_previous and fast_ma_current > slow_ma_current:
            # 金叉 - 买入信号
            return 1
        if fast_ma_previous >= slow_ma_previous and fast_ma_current < slow_ma_current:
            # 死叉 - 卖出信号
            return -1

        return 0
