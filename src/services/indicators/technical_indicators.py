"""技术指标工具。

封装常用技术指标计算逻辑，便于在策略与回测中复用。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class TechnicalIndicators:
    """常用技术指标集合。"""

    def sma(self, series: pd.Series, period: int) -> pd.Series:
        """简单移动平均线。"""
        return series.rolling(window=period, min_periods=period).mean()

    def rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """相对强弱指数 (RSI)。

        使用经典的 Wilder 平滑算法：
        - 先计算价格变化 `delta`
        - 分别计算上涨与下跌部分的指数移动平均
        - 再根据 RS = avg_gain / avg_loss 计算 RSI
        """
        series = series.astype(float)
        delta = series.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # 使用 EMA 近似 Wilder 平滑
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        return rsi
