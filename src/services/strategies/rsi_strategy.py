"""RSI 策略

当 RSI 低于超卖区时买入，高于超买区时卖出。
"""
from __future__ import annotations

import pandas as pd

from src.services.strategies.base_strategy import BaseStrategy
from src.services.indicators.technical_indicators import TechnicalIndicators


class RSIStrategy(BaseStrategy):
    """RSI 策略。"""

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70) -> None:
        """初始化策略。

        :param period: RSI 周期
        :param oversold: 超卖阈值
        :param overbought: 超买阈值
        """
        super().__init__("RSI Strategy")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.indicators = TechnicalIndicators()

    def generate_signal(self, data: pd.DataFrame) -> int:
        """生成交易信号。

        :param data: 市场数据 (DataFrame)，索引为时间，包含 `close` 列
        :return: 1=买入, -1=卖出, 0=持有
        """
        if len(data) < self.period + 1:
            return 0

        # 计算 RSI
        rsi = self.indicators.rsi(data["close"], self.period)

        # 获取当前 RSI 值
        rsi_current = rsi.iloc[-1]

        # 判断信号
        if rsi_current < self.oversold and self.position == 0:
            # RSI 超卖 - 买入信号
            return 1
        if rsi_current > self.overbought and self.position == 1:
            # RSI 超买 - 卖出信号
            return -1

        return 0
