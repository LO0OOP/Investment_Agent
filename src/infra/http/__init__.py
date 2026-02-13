"""HTTP 基础设施层

封装本项目所有对外 HTTP 访问，统一：
- 会话管理（连接复用）
- 超时配置
- 重试策略
- 日志格式
- 错误模型

上层代码（如行情、交易、LLM 调用）只依赖这里暴露的接口，避免直接使用 requests。
"""
from __future__ import annotations

from .client import (
    HttpClient,
    HttpClientConfig,
    RetryConfig,
    HttpError,
    RequestError,
    ResponseError,
)

__all__ = [
    "HttpClient",
    "HttpClientConfig",
    "RetryConfig",
    "HttpError",
    "RequestError",
    "ResponseError",
]

