"""行情数据查询服务

封装 infra 层的加密货币 K 线 (`DataFetcher`) 和 A 股 K 线 (`StockDataFetcher`)，
对上提供统一的结构化 JSON 风格输出，便于 Agent / API 调用。

主要能力：
- get_crypto_ohlcv: 按交易对 + 时间尺度 + 时间范围返回加密货币 OHLCV；
- get_stock_ohlcv: 按股票名/代码 + 时间尺度 + 时间范围返回 A 股 OHLCV（当前仅支持日线）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from src.common.logger import get_logger
from src.infra.data.data_fetcher import DataFetcher
from src.infra.data.stock_data_fetcher import StockDataFetcher
from src.infra.data.stock_mapping import resolve_code


logger = get_logger(__name__)

Bar = Dict[str, Any]

# 通用限制，避免一次查询返回过多 K 线
MAX_OHLCV_LIMIT = 2000
DEFAULT_OHLCV_LIMIT = 500


def _normalize_limit(limit: int | None, default: int = DEFAULT_OHLCV_LIMIT) -> int:
  if limit is None or limit <= 0:
    limit = default
  return min(limit, MAX_OHLCV_LIMIT)


def get_crypto_ohlcv(
  symbol: str,
  timeframe: str,
  *,
  start_time: Optional[str] = None,
  end_time: Optional[str] = None,
  limit: int | None = None,
) -> List[Bar]:
  """获取加密货币 K 线数据，返回 JSON 友好的 OHLCV 列表。

  参数：
  - symbol: 交易对符号，例如 "BTCUSDT"；
  - timeframe: K 线周期，例如 "1m"、"5m"、"1h"、"4h"、"1d"；
  - start_time: 可选，ISO8601 字符串，作为起始时间（包含）；
  - end_time: 可选，ISO8601 字符串，作为结束时间（包含）；
  - limit: 可选，最大返回条数，默认 500，最大 2000。
  """
  if not symbol:
    raise ValueError("symbol 不能为空")
  if not timeframe:
    raise ValueError("timeframe 不能为空")

  n_limit = _normalize_limit(limit)

  # DataFetcher 只支持 start_time + limit，我们使用 start_time 做粗过滤，
  # 然后在本地按 end_time 进一步截断。
  df_start = None
  if start_time:
    try:
      df_start = pd.to_datetime(start_time)
    except Exception as e:  # noqa: BLE001
      logger.warning("[market_data] 解析 start_time 失败，将忽略该参数: %s", e)
      df_start = None

  fetcher = DataFetcher()
  df = fetcher.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=n_limit, start_time=df_start)
  if df is None or df.empty:
    return []

  # 按时间范围过滤
  if start_time:
    try:
      ts_start = pd.to_datetime(start_time)
      df = df[df.index >= ts_start]
    except Exception:  # noqa: BLE001
      pass
  if end_time:
    try:
      ts_end = pd.to_datetime(end_time)
      df = df[df.index <= ts_end]
    except Exception:  # noqa: BLE001
      pass

  # 再次限制条数（防止时间窗口太大）
  if len(df) > n_limit:
    df = df.iloc[-n_limit:]

  bars: List[Bar] = []
  for ts, row in df.iterrows():
    bars.append(
      {
        "timestamp": ts.isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
      }
    )

  return bars


def _parse_date_yyyymmdd(value: str) -> str:
  """将任意常见日期字符串转为 "YYYYMMDD" 格式。"""
  dt = pd.to_datetime(value)
  return dt.strftime("%Y%m%d")


def get_stock_ohlcv(
  symbol_or_name: str,
  timeframe: str = "1d",
  *,
  start_date: Optional[str] = None,
  end_date: Optional[str] = None,
  limit: int | None = None,
) -> List[Bar]:
  """获取 A 股股票 K 线数据（当前仅支持日线），返回 JSON 友好的 OHLCV 列表。

  参数：
  - symbol_or_name: 股票代码（如 "600000"）或中文名称（如 "浦发银行"）；
  - timeframe: 时间尺度，目前仅支持 "1d" / "D" / "daily"（日线）；
  - start_date: 起始日期，支持任意常见日期格式，会转为 "YYYYMMDD"；
  - end_date: 结束日期，格式同上；
  - limit: 可选，最大返回条数，默认 500，最大 2000（按时间倒序截取）。
  """
  if not symbol_or_name:
    raise ValueError("symbol_or_name 不能为空")

  tf_norm = timeframe.lower()
  if tf_norm not in {"1d", "d", "daily"}:
    raise ValueError(f"当前仅支持日线 K 线 (1d)，收到: {timeframe}")

  n_limit = _normalize_limit(limit)

  # 解析股票代码
  key = str(symbol_or_name).strip()
  codes = resolve_code(key)
  if not codes:
    logger.warning("[market_data] 无法解析股票代码: %s", key)
    raise ValueError(f"无法根据输入解析股票代码: {key}")

  code = codes[0]

  start_yyyymmdd = _parse_date_yyyymmdd(start_date) if start_date else "20100101"
  end_yyyymmdd = _parse_date_yyyymmdd(end_date) if end_date else None

  fetcher = StockDataFetcher()
  df = fetcher.fetch_stock_ohlcv(symbol=code, start_date=start_yyyymmdd, end_date=end_yyyymmdd)
  if df is None or df.empty:
    return []

  # 按 limit 截断（倒序取最近 N 条）
  if len(df) > n_limit:
    df = df.iloc[-n_limit:]

  bars: List[Bar] = []
  for ts, row in df.iterrows():
    bars.append(
      {
        "timestamp": ts.isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
        "symbol": code,
      }
    )

  return bars


__all__ = ["get_crypto_ohlcv", "get_stock_ohlcv"]
