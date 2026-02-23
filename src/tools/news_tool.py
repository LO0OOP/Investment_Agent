"""新闻查询 Tool

提供给 LangChain Agent 使用的 Tool，用于按股票代码或名称从本地新闻数据库中查询新闻。

- 使用 `services.news_service.fetch_news` 从 SQLite 中读取新闻；
- 支持可选的时间范围过滤和条数限制；
- 返回结构化 JSON，便于大模型总结或进一步处理。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.common.logger import get_logger
from src.services.news_service import fetch_news

try:
  from langchain_core.tools import StructuredTool  # type: ignore
except Exception:  # pragma: no cover
  from langchain.tools import StructuredTool  # type: ignore


logger = get_logger(__name__)


class NewsQueryInput(BaseModel):
  """新闻查询 Tool 入参模型。

  - symbol_or_name: 股票代码或中文名称；
  - start_time/end_time: 可选时间范围，使用 ISO8601 字符串（例如 "2025-01-01"）；
  - limit: 返回的最大新闻条数，默认 50，最大 200。
  """

  symbol_or_name: str = Field(
    ...,
    description="A 股股票代码或中文名称，例如 '600000' 或 '浦发银行'。",
  )
  start_time: Optional[str] = Field(
    default=None,
    description=(
      "起始时间，可选，使用 ISO8601 字符串，例如 '2025-01-01' 或 '2025-01-01T00:00:00'。"
    ),
  )
  end_time: Optional[str] = Field(
    default=None,
    description=(
      "结束时间，可选，使用 ISO8601 字符串，例如 '2025-02-01' 或 '2025-02-01T23:59:59'。"
    ),
  )
  limit: int = Field(
    50,
    ge=1,
    le=200,
    description="返回的最大新闻条数，默认 50，最大 200。",
  )



def _query_news_tool(**kwargs: Any) -> Dict[str, Any]:
  """内部实现：包装 `fetch_news`，供 StructuredTool 调用。

  使用关键字参数接收 LangChain 传入的参数，然后交给 Pydantic 进行校验与默认值填充。
  """
  args = NewsQueryInput(**kwargs)

  logger.info(
    "[NewsTool] 收到新闻查询请求: symbol_or_name=%s, start=%s, end=%s, limit=%s",
    args.symbol_or_name,
    args.start_time,
    args.end_time,
    args.limit,
  )

  try:
    items: List[Dict[str, Any]] = fetch_news(
      symbol_or_name=args.symbol_or_name,
      start_time=args.start_time,
      end_time=args.end_time,
      limit=args.limit,
    )
  except Exception as e:  # noqa: BLE001
    logger.error("[NewsTool] 新闻查询失败: %s", e, exc_info=True)
    return {
      "ok": False,
      "error_type": e.__class__.__name__,
      "error_message": str(e),
    }

  return {
    "ok": True,
    "symbol_or_name": args.symbol_or_name,
    "start_time": args.start_time,
    "end_time": args.end_time,
    "limit": args.limit,
    "count": len(items),
    "items": items,
  }


news_query_tool: StructuredTool = StructuredTool.from_function(
  func=_query_news_tool,
  name="query_stock_news",
  description=(
    "按股票代码或中文名称查询本地新闻数据库中的新闻记录，可选时间范围和条数限制。\n"
    "适合在 Agent 需要获取某支股票在一段时间内的相关新闻列表时调用。"
  ),
  args_schema=NewsQueryInput,
)


__all__ = ["NewsQueryInput", "news_query_tool"]
