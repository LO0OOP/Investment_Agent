"""加密货币 K 线查询 Tool

提供给 LangChain Agent 使用的 Tool，用于按交易对 + 时间尺度 + 时间范围
从交易所（当前为 Binance 公共接口）获取 OHLCV 数据。

底层使用 `services.market_data_service.get_crypto_ohlcv`，返回结构化 JSON，
适合 Agent 进行回测前数据检查、行情分析可视化等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.common.logger import get_logger
from src.services.market_data_service import get_crypto_ohlcv

try:
  from langchain_core.tools import StructuredTool  # type: ignore
except Exception:  # pragma: no cover
  from langchain.tools import StructuredTool  # type: ignore


logger = get_logger(__name__)


class CryptoKlineInput(BaseModel):
  """加密货币 K 线查询入参。

  - symbol: 交易对，例如 "BTCUSDT"；
  - timeframe: K 线周期，例如 "1m"、"5m"、"1h"、"4h"、"1d"；
  - start_time/end_time: 可选时间范围，使用 ISO8601 字符串；
  - limit: 最大返回条数，默认 500，最大 2000。
  """

  symbol: str = Field(
    ...,
    description="加密货币交易对，例如 'BTCUSDT'、'ETHUSDT'。",
  )
  timeframe: str = Field(
    ...,
    description="K 线周期，例如 '1m'、'5m'、'15m'、'1h'、'4h'、'1d'。",
  )
  start_time: Optional[str] = Field(
    default=None,
    description="起始时间，可选，ISO8601 字符串，例如 '2025-01-01T00:00:00'。",
  )
  end_time: Optional[str] = Field(
    default=None,
    description="结束时间，可选，ISO8601 字符串，例如 '2025-01-02T00:00:00'。",
  )
  limit: Optional[int] = Field(
    default=500,
    ge=1,
    le=2000,
    description="最大返回条数，默认 500，最大 2000。",
  )



def _query_crypto_kline(**kwargs: Any) -> Dict[str, Any]:
  """内部实现：包装 get_crypto_ohlcv，供 StructuredTool 调用。"""
  args = CryptoKlineInput(**kwargs)

  logger.info(
    "[CryptoKlineTool] 请求 K 线: symbol=%s, timeframe=%s, start=%s, end=%s, limit=%s",
    args.symbol,
    args.timeframe,
    args.start_time,
    args.end_time,
    args.limit,
  )

  try:
    bars: List[Dict[str, Any]] = get_crypto_ohlcv(
      symbol=args.symbol,
      timeframe=args.timeframe,
      start_time=args.start_time,
      end_time=args.end_time,
      limit=args.limit,
    )
  except Exception as e:  # noqa: BLE001
    logger.error("[CryptoKlineTool] 查询 K 线失败: %s", e, exc_info=True)
    return {
      "ok": False,
      "error_type": e.__class__.__name__,
      "error_message": str(e),
    }

  return {
    "ok": True,
    "symbol": args.symbol,
    "timeframe": args.timeframe,
    "start_time": args.start_time,
    "end_time": args.end_time,
    "limit": args.limit,
    "count": len(bars),
    "bars": bars,
  }


crypto_kline_tool: StructuredTool = StructuredTool.from_function(
  func=_query_crypto_kline,
  name="query_crypto_ohlcv",
  description=(
    "查询加密货币 K 线数据 (OHLCV)，可指定交易对、时间尺度和时间范围。\n"
    "适合在做行情分析、回测前检查数据区间、或绘制价格走势时调用。"
  ),
  args_schema=CryptoKlineInput,
)


__all__ = ["CryptoKlineInput", "crypto_kline_tool"]
