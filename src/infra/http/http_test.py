"""简单 HTTP 客户端连通性测试。

运行方式（在项目根目录）：
    python -m src.infra.http.http_test
"""
from __future__ import annotations

from src.common.logger import get_logger, setup_logging
from src.infra.http import HttpClient, HttpClientConfig, RetryConfig, RequestError, ResponseError


logger = get_logger(__name__)


def main() -> None:
    setup_logging()

    client = HttpClient(
        HttpClientConfig(
            base_url="https://www.baidu.com",  # 任意国内可访问网站
            timeout=5.0,
            retry=RetryConfig(max_attempts=3, backoff_factor=0.5),
            default_headers={
                "User-Agent": "investment-agent-http-test/0.1",
            },
        )
    )

    try:
        resp = client.get("/")
        logger.info("响应长度: %s 字符", len(resp.text))
        # 简单打印下标题，确认编码没问题
        text_preview = resp.text[:200]
        logger.info("响应内容前 200 字符: %r", text_preview)
    except ResponseError as e:
        logger.error("HTTP 响应错误: %s (status=%s)", e, e.status_code)
    except RequestError as e:
        logger.error("HTTP 请求/网络错误: %s", e)


if __name__ == "__main__":
    main()
