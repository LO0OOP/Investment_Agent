"""news_worker.embedder

负责调用向量模型，将新闻内容转换为向量并写入向量库。

注意：
- 本模块不做数据库/存储逻辑，只负责“文本 -> 向量”的转换接口定义；
- 实际的向量入库可以放在 repository 等位置统一管理。

当前版本仅占位，后续可接入 OpenAI Embedding、向量数据库等。
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from src.common.logger import get_logger


logger = get_logger(__name__)


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
  """将一批文本转换为向量列表（占位实现）。

  后续可在此处接入具体的 embedding 模型，例如：
  - OpenAI / 百炼 embedding 接口；
  - 本地向量模型。
  当前仅返回空列表，并打印日志，避免影响主流程。
  """
  logger.info("[embedder] 收到需要生成向量的文本数: %s", len(texts))
  # TODO: 接入实际的 embedding 模型
  return [[] for _ in texts]


def embed_news_batch(news_items: Iterable[dict]) -> None:
  """对新闻批量生成向量（占位）。"""
  texts = [str(item.get("content") or item.get("title") or "") for item in news_items]
  _ = embed_texts(texts)
  # TODO: 将生成的向量与 news_id 关联，并写入向量库（由上层或 repository 负责）
