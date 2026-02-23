"""A 股股票 K 线查询 Tool

提供给 LangChain Agent 使用的 Tool，用于按股票名/代码 + 时间尺度 + 时间范围
获取本地/远程的 A 股日线 OHLCV 数据（当前实现直接通过 akshare 拉取）。

底层使用 `services.market_data_service.get_stock_ohlcv`，返回结构化 JSON，
适合 Agent 进行个股走势分析、风控评估等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.common.logger import get_logger
from src.services.market_data_service import get_stock_ohlcv

try:
  from langchain_core.tools import StructuredTool  # type: ignore
except Exception:  # pragma: no cover
  from langchain.tools import StructuredTool  # type: ignore


logger = get_logger(__name__)


class StockKlineInput(BaseModel):
  """A 股 K 线查询入参。

  - symbol_or_name: 股票代码或中文名称；
  - timeframe: 时间尺度（当前仅支持日线）；
  - start_date/end_date: 可选日期范围，任意常见日期格式；
  - limit: 最大返回条数，默认 500，最大 2000。
  """

  symbol_or_name: str = Field(
    ...,
    description="A 股股票代码或中文名称，例如 '600000' 或 '浦发银行'。",
  )
  timeframe: str = Field(
    "1d",
    description="时间尺度，目前仅支持 '1d' (日线)。",
  )
  start_date: Optional[str] = Field(
    default=None,
    description="起始日期，可选，例如 '2020-01-01'。",
  )
  end_date: Optional[str] = Field(
    default=None,
    description="结束日期，可选，例如 '2020-12-31'。",
  )
  limit: Optional[int] = Field(
    default=500,
    ge=1,
    le=2000,
    description="最大返回条数，默认 500，最大 2000。",
  )



def _query_stock_kline(**kwargs: Any) -> Dict[str, Any]:
  """内部实现：包装 get_stock_ohlcv，供 StructuredTool 调用。"""
  args = StockKlineInput(**kwargs)

  logger.info(
    "[StockKlineTool] 请求 K 线: symbol_or_name=%s, timeframe=%s, start=%s, end=%s, limit=%s",
    args.symbol_or_name,
    args.timeframe,
    args.start_date,
    args.end_date,
    args.limit,
  )

  try:
    bars: List[Dict[str, Any]] = get_stock_ohlcv(
      symbol_or_name=args.symbol_or_name,
      timeframe=args.timeframe,
      start_date=args.start_date,
      end_date=args.end_date,
      limit=args.limit,
    )
  except Exception as e:  # noqa: BLE001
    logger.error("[StockKlineTool] 查询 K 线失败: %s", e, exc_info=True)
    return {
      "ok": False,
      "error_type": e.__class__.__name__,
      "error_message": str(e),
    }

  return {
    "ok": True,
    "symbol_or_name": args.symbol_or_name,
    "timeframe": args.timeframe,
    "start_date": args.start_date,
    "end_date": args.end_date,
    "limit": args.limit,
    "count": len(bars),
    "bars": bars,
  }


stock_kline_tool: StructuredTool = StructuredTool.from_function(
  func=_query_stock_kline,
  name="query_stock_ohlcv",
  description=(
    "查询 A 股股票 K 线数据 (日线 OHLCV)，可使用股票代码或中文名称，并指定时间范围。\n"
    "适合用于个股走势分析、风控评估或与新闻数据结合进行研究。"
  ),
  args_schema=StockKlineInput,
)


__all__ = ["StockKlineInput", "stock_kline_tool"]
