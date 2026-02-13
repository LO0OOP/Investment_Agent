from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional

import requests
from requests import Response

from src.common.logger import get_logger, setup_logging


logger = get_logger(__name__)


class HttpError(RuntimeError):
    """所有 HTTP 相关异常的基类。"""


class RequestError(HttpError):
    """请求在发送前或发送过程中失败（网络错误、超时等）。"""


class ResponseError(HttpError):
    """请求已发送成功，但返回了非预期的 HTTP 状态码。"""

    def __init__(self, status_code: int, message: str, *, response_text: str | None = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.response_text = response_text

# dataclass类似于struct，不过会自动定义_init_等函数
@dataclass(slots=True)
class RetryConfig:
    max_attempts: int = 3
    backoff_factor: float = 0.5  # 线性退避系数


@dataclass(slots=True)
class HttpClientConfig:
    base_url: str | None = None
    timeout: float = 10.0
    retry: RetryConfig = field(default_factory=RetryConfig)
    default_headers: Dict[str, str] | None = None


class HttpClient:
    """统一的同步 HTTP 客户端。

    - 自动拼接 base_url
    - 统一超时配置
    - 简单重试（幂等 GET/HEAD/OPTIONS）
    - 结构化日志
    - 统一异常类型
    """

    def __init__(self, config: HttpClientConfig) -> None:
        setup_logging()  # 确保日志初始化一次
        self._config = config
        self._session = requests.Session()
        if config.default_headers:
            self._session.headers.update(config.default_headers)

    # ---- 公共方法 ----

    def get(self, path: str, **kwargs: Any) -> Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Response:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Response:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Response:
        return self._request("DELETE", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> Response:
        return self._request(method.upper(), path, **kwargs)

    # ---- 内部实现 ----

    def _build_url(self, path: str) -> str:
        if self._config.base_url and not path.startswith("http"):
            return f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        return path

    def _request(self, method: str, path: str, **kwargs: Any) -> Response:
        url = self._build_url(path)
        timeout = kwargs.pop("timeout", self._config.timeout)

        attempt = 0
        max_attempts = max(1, self._config.retry.max_attempts)

        while True:
            attempt += 1
            try:
                start = time.perf_counter()
                logger.debug(
                    "HTTP %s %s attempt=%s", method, url, attempt,
                )
                resp = self._session.request(method, url, timeout=timeout, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000

                logger.info(
                    "HTTP %s %s -> %s (%.1f ms)",
                    method,
                    url,
                    resp.status_code,
                    elapsed,
                )

                if 200 <= resp.status_code < 300:
                    return resp

                # 非 2xx 视为错误
                body_preview = resp.text[:500] if resp.text else ""
                logger.warning(
                    "HTTP error %s %s -> %s, body=%r",
                    method,
                    url,
                    resp.status_code,
                    body_preview,
                )

                raise ResponseError(
                    status_code=resp.status_code,
                    message=f"Unexpected status for {method} {url}",
                    response_text=body_preview,
                )

            except ResponseError:
                # 服务端已返回响应，不做重试（除非以后有白名单）
                raise
            except (requests.Timeout, requests.ConnectionError) as exc:
                # 网络异常可按配置重试
                logger.warning(
                    "HTTP %s %s network error on attempt %s/%s: %s",
                    method,
                    url,
                    attempt,
                    max_attempts,
                    exc,
                )
                if not self._should_retry(method, attempt, max_attempts):
                    raise RequestError(f"Network error for {method} {url}: {exc}") from exc

                self._sleep_backoff(attempt)
            except Exception as exc:  # noqa: BLE001
                logger.error("HTTP %s %s unexpected error: %s", method, url, exc)
                raise RequestError(f"Unexpected error for {method} {url}: {exc}") from exc

    def _should_retry(self, method: str, attempt: int, max_attempts: int) -> bool:
        if attempt >= max_attempts:
            return False
        # 只对幂等方法做简单重试
        return method in {"GET", "HEAD", "OPTIONS"}

    def _sleep_backoff(self, attempt: int) -> None:
        delay = self._config.retry.backoff_factor * attempt
        time.sleep(delay)


__all__ = [
    "HttpClient",
    "HttpClientConfig",
    "RetryConfig",
    "HttpError",
    "RequestError",
    "ResponseError",
]
