"""news_worker.collector

负责从外部数据源（当前为 akshare）拉取原始新闻，并输出统一的结构化格式。

后续如果要接入其他新闻源，可以在这里做封装，保持对外结构不变。
"""
from __future__ import annotations

from datetime import datetime
from html import unescape
import re
from typing import Any, Dict, List

import akshare as ak  # type: ignore

from src.common.logger import get_logger
from src.infra.data.stock_mapping import code_to_name, resolve_code
from src.infra.http import HttpClient, HttpClientConfig, RetryConfig, RequestError, ResponseError


logger = get_logger(__name__)

# 仅用于调试：控制“详情页 HTML 完整 dump”只打印一次
_DEBUG_DETAIL_HTML_DUMPED = False

# 为 Eastmoney 新闻页面构造一个简单的 HTTP 客户端
_http_client = HttpClient(

  HttpClientConfig(
    base_url=None,  # 直接使用完整 URL
    timeout=8.0,
    retry=RetryConfig(max_attempts=2, backoff_factor=0.5),
    default_headers={
      "User-Agent": "investment-agent-news-fetcher/0.1",
    },
  )
)

# 仅用于调试：控制“详情页 HTML 完整 dump”只打印一次
_DEBUG_DETAIL_HTML_DUMPED = False


NewsItem = Dict[str, Any]



def _parse_datetime(value: Any) -> str:
  """将 akshare 返回的日期/时间转换为 ISO8601 字符串。"""
  if value is None:
    return ""
  if isinstance(value, datetime):
    return value.isoformat()
  try:
    # akshare 新闻时间字段通常是字符串格式，例如 "2024-01-01 12:34:56"
    dt = datetime.fromisoformat(str(value).replace("/", "-").strip())
    return dt.isoformat()
  except Exception:  # noqa: BLE001
    return str(value)


def _fetch_full_content_from_url(url: str) -> str:
  """尝试从新闻详情链接中抓取完整正文文本。

  为了避免对外部站点压力过大，仅在 content 为空或明显过短时调用，
  并采用简单的 HTML 清洗策略：
  - 去除 <script>/<style>；
  - 尝试截取 <div id="ContentBody"> 或 <body> 内部内容；
  - 去除所有标签，做基本空白归一化。
  """
  if not url:
    return ""

  logger.debug("[collector] 尝试从详情页抓取正文: url=%s", url)

  try:
    resp = _http_client.get(url)
  except (RequestError, ResponseError) as e:  # noqa: BLE001
    logger.warning("[collector] 拉取新闻详情页失败: %s (%s)", url, e)
    return ""

  html = resp.text or ""

  # global _DEBUG_DETAIL_HTML_DUMPED
  # if not _DEBUG_DETAIL_HTML_DUMPED:
  #   _DEBUG_DETAIL_HTML_DUMPED = True
  #   logger.debug("[collector] 详情页 HTML 完整 dump (仅此一次):\n%s", html)

  if not html:
    logger.debug("[collector] 详情页 HTML 为空: url=%s", url)
    return ""

  logger.debug("[collector] 详情页 HTML 长度: %s 字符", len(html))


  # 去掉脚本和样式，避免噪音
  html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\\1>", " ", html)

  # 尝试定位正文区域（根据 Eastmoney 常见结构做一个简单猜测）
  match = re.search(r"(?is)<div[^>]+id=\"ContentBody\"[^>]*>(.*?)</div>", html)
  region = "ContentBody"
  if not match:
    match = re.search(r"(?is)<div[^>]+class=\"article-body\"[^>]*>(.*?)</div>", html)
    region = "article-body"
  if not match:
    match = re.search(r"(?is)<body[^>]*>(.*?)</body>", html)
    region = "body"

  inner_html = match.group(1) if match else html
  logger.debug("[collector] 选取正文区域: %s, 长度: %s 字符", region, len(inner_html))

  # 去掉所有剩余标签
  text = re.sub(r"(?is)<[^>]+>", " ", inner_html)
  text = unescape(text)
  text = re.sub(r"\s+", " ", text).strip()

  logger.debug("[collector] 提取到正文文本长度: %s 字符, 预览: %r", len(text), text[:200])
  return text




def collect_stock_news(symbol: str, limit: int = 50) -> List[NewsItem]:
  """拉取单只股票相关新闻列表，返回标准化结构。

  参数说明：
  - symbol: 股票关键词输入，可以是中文名（推荐，例如 "浦发银行"），也可以是股票代码（例如 "600000"），用于解析得到标准股票代码并作为搜索关键字；
  - limit: 返回的新闻最大条数。

  当前示例使用 Eastmoney 的股票新闻接口 `stock_news_em`，
  如果 akshare 版本有差异，可根据实际文档调整字段名。

  返回的每条新闻为一个字典，字段包括：
  - symbol: 股票代码（6 位，如解析失败则退回原始输入）；
  - keyword: 原始搜索关键词（名称或代码）；
  - title: 标题
  - content: 正文（如接口不提供，则为摘要或空字符串）
  - publish_time: 发布时间（ISO8601 字符串）
  - source: 新闻来源
  - url: 新闻详情地址（如有）
  - raw: 原始记录（便于后续调试）
  """

  # 1. 解析标准股票代码（用于写入数据库）
  input_keyword = str(symbol).strip()
  codes = resolve_code(input_keyword)
  if codes:
    db_symbol = codes[0]
  else:
    db_symbol = input_keyword
    logger.warning("[collector] 未能为关键词解析到股票代码，将使用原始值作为 symbol: %s", input_keyword)

  # 2. 确定用于 akshare 搜索的关键字
  if input_keyword.isdigit() and len(input_keyword) == 6:
    # 用户传入的是代码，优先尝试用名称搜索，提高相关新闻相关度
    name = code_to_name(db_symbol)
    search_keyword = name or input_keyword
  else:
    # 用户传入的是名称或其他关键字，直接用于搜索
    search_keyword = input_keyword

  logger.info(
    "[collector] 拉取股票新闻: search_keyword=%s, db_symbol=%s, limit=%s",
    search_keyword,
    db_symbol,
    limit,
  )

  try:
    # 示例使用 ak.stock_news_em；如果接口签名不同，可在此处调整
    # stock_news_em 实际是通过 keyword 搜索，这里统一传入 search_keyword
    df = ak.stock_news_em(symbol=search_keyword)  # type: ignore[attr-defined]
  except Exception as e:  # noqa: BLE001
    logger.error("[collector] 拉取股票新闻失败: %s", e)
    return []

  if df is None or df.empty:
    logger.info("[collector] 无新闻数据: %s", search_keyword)
    return []

  items: List[NewsItem] = []

  for _, row in df.iterrows():
    # 根据 akshare 实际返回字段名做映射，这里给出常见示例
    title = str(row.get("title") or row.get("新闻标题") or "").strip()
    content = str(row.get("content") or row.get("新闻内容") or row.get("摘要") or "").strip()
    publish_time = _parse_datetime(row.get("datetime") or row.get("发布时间") or row.get("pub_time"))
    source = str(row.get("source") or row.get("来源") or "").strip()
    url = str(row.get("url") or row.get("新闻链接") or "").strip()

    if not title:
      continue

    # 如 content 为空或明显过短，尝试从详情页抓取完整正文
    if url and (not content or len(content) < 50):
      logger.debug(
        "[collector] content 过短，将从详情页抓取正文: title=%s, len=%s, url=%s",
        title,
        len(content),
        url,
      )
      full_text = _fetch_full_content_from_url(url)
      if full_text:
        logger.debug(
          "[collector] 详情页正文抓取成功: title=%s, len=%s", title, len(full_text)
        )
        content = full_text
      else:
        logger.debug("[collector] 详情页正文抓取失败或为空: title=%s, url=%s", title, url)

    items.append(
      {
        "symbol": db_symbol,
        "keyword": input_keyword,
        "title": title,
        "content": content,
        "publish_time": publish_time,
        "source": source,
        "url": url,
        "raw": row.to_dict(),
      }
    )



  logger.info(
    "[collector] 拉取到新闻条数: %s (db_symbol=%s, search_keyword=%s)",
    len(items),
    db_symbol,
    search_keyword,
  )
  return items



def collect_news_for_symbols(symbols: list[str], limit_per_symbol: int = 50) -> list[NewsItem]:
  """批量拉取多只股票的新闻。"""
  all_items: list[NewsItem] = []
  for sym in symbols:
    sym = sym.strip()
    if not sym:
      continue
    items = collect_stock_news(sym, limit=limit_per_symbol)
    all_items.extend(items)
  return all_items
