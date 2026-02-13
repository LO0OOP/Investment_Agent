"""数据获取模块

负责从交易所获取历史数据和实时数据。

适配当前项目：
- 使用 `common.config` 读取交易所配置
- 使用 `infra.http.HttpClient` 调用 REST API（默认 Binance 公共 K 线/行情接口）
- 支持将 K 线数据增量同步到本地 CSV
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from src.common.config import settings
from src.common.logger import get_logger
from src.infra.http import (
    HttpClient,
    HttpClientConfig,
    RetryConfig,
    RequestError,
    ResponseError,
)


logger = get_logger(__name__)

# 项目根目录 / 数据存储目录
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "ohlcv"


@dataclass(slots=True)
class ExchangeHttpConfig:
    """从 Settings 映射出的 HTTP 访问配置。"""

    name: str
    base_url: str
    timeout: float = 10.0
    max_retries: int = 3


class DataFetcher:
    """数据获取器（基于 HTTP 客户端）。"""

    def __init__(
        self,
        exchange_name: Optional[str] = None,
    ) -> None:

        # 1️⃣ 交易所基础配置
        exchange_cfg = settings.exchange  # 结构类似 {"name": "binance", "use_mock": true, ...}
        ex_name = exchange_name or exchange_cfg.get("name", "binance")
        if ex_name.lower() != "binance":
            raise ValueError(f"当前 DataFetcher 仅实现了 binance，收到: {ex_name}")

        # 从配置里读取扩展字段（如果有）
        base_url = exchange_cfg.get("base_url") or "https://api.binance.com"
        timeout = float(exchange_cfg.get("timeout", 10.0))
        max_retries = int(exchange_cfg.get("max_retries", 3))


        self._cfg = ExchangeHttpConfig(
            name=ex_name,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

        # 2️⃣ HTTP 客户端（统一 timeout / retry / 日志）
        self._client = HttpClient(
            HttpClientConfig(
                base_url=self._cfg.base_url,
                timeout=self._cfg.timeout,
                retry=RetryConfig(max_attempts=self._cfg.max_retries, backoff_factor=0.5),
                default_headers={
                    "User-Agent": "investment-agent-data-fetcher/0.1",
                },
            )
        )

    # =============================
    # 公共接口方法（仅请求，不落盘）
    # =============================
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        start_time: Optional[object] = None,
    ) -> Optional[pd.DataFrame]:
        """获取 K 线数据，返回 pandas.DataFrame（不做本地存储）。

        对应 Binance `/api/v3/klines` 接口。

        :param symbol: 如 "BTCUSDT"
        :param timeframe: Binance 的 interval，例如 "1m"、"5m"、"1h"、"1d"
        :param limit: 最大返回条数（Binance 限制，通常 <= 1000）
        :param start_time: 可选的开始时间（datetime/timestamp/ms），用于增量拉取
        """
        params = {
            "symbol": symbol,
            "interval": timeframe,
            "limit": limit,
        }

        if start_time is not None:
            # 支持传入 datetime / pandas Timestamp / ms 数值
            try:
                if isinstance(start_time, (int, float)):
                    start_ms = int(start_time)
                else:
                    ts = pd.to_datetime(start_time)
                    start_ms = int(ts.value // 10**6)  # ns -> ms
                params["startTime"] = start_ms
            except Exception as e:  # noqa: BLE001
                logger.warning("解析 start_time 失败，将忽略该参数: %s", e)

        try:
            resp = self._client.get("/api/v3/klines", params=params)
            data = resp.json()

            if not isinstance(data, list):
                logger.error("/klines 返回数据格式异常: %r", data)
                return None

            # Binance kline 返回: [
            #   [openTime, open, high, low, close, volume, closeTime, ...],
            #   ...
            # ]
            columns = [
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_volume",
                "taker_buy_quote_volume",
                "ignore",
            ]
            df = pd.DataFrame(data, columns=columns)
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df.set_index("open_time", inplace=True)

            # 只暴露常用的 OHLCV 列，并转成 float
            ohlcv = df[["open", "high", "low", "close", "volume"]].astype(float)
            return ohlcv
        except (RequestError, ResponseError) as e:
            logger.error("获取 OHLCV 失败: %s", e)
            return None
        except Exception as e:  # noqa: BLE001
            logger.exception("处理 OHLCV 数据时发生异常: %s", e)
            return None

    def fetch_ticker(self, symbol: str):
        """获取 24 小时价格变动等 ticker 信息。

        对应 Binance `/api/v3/ticker/24hr`。
        """
        params = {"symbol": symbol}
        try:
            resp = self._client.get("/api/v3/ticker/24hr", params=params)
            data = resp.json()
            if not isinstance(data, dict):
                logger.error("/ticker/24hr 返回数据格式异常: %r", data)
                return None
            return data
        except (RequestError, ResponseError) as e:
            logger.error("获取 ticker 失败: %s", e)
            return None
        except Exception as e:  # noqa: BLE001
            logger.exception("处理 ticker 数据时发生异常: %s", e)
            return None

    # =============================
    # 增量同步到本地 CSV
    # =============================
    def sync_ohlcv_to_local(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 1000,
    ) -> Optional[pd.DataFrame]:
        """增量拉取并将 K 线数据保存到本地 CSV。

        - 本地文件路径: data/ohlcv/{exchange}/{symbol}_{timeframe}.csv
        - 如文件已存在: 从最后一根 K 线之后开始增量拉取并追加
        - 如文件不存在: 从最新历史拉取一批并写入
        """
        safe_symbol = symbol.replace("/", "")
        file_path = DATA_DIR / self._cfg.name / f"{safe_symbol}_{timeframe}.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.exists():
            # 已有历史数据，读取并找到最后一根 K 线时间
            try:
                df_local = pd.read_csv(file_path, parse_dates=["open_time"])
                df_local.set_index("open_time", inplace=True)
            except Exception as e:  # noqa: BLE001
                logger.error("读取本地 K 线文件失败，将重新拉取: %s", e)
                df_local = None

            last_ts = df_local.index.max() if df_local is not None and not df_local.empty else None
            if last_ts is not None:
                # 注意：最后一根 K 线通常未收盘，必须在下次拉取时覆盖掉
                # 因此这里从最后一根的 open_time 开始重新拉取，后续用去重逻辑保留最新一条
                start_ms = int(last_ts.value // 10**6)
                logger.info(
                    "从本地最后一根开始重新增量拉取 K 线(会覆盖最后一根): %s %s start_ms=%s",
                    symbol,
                    timeframe,
                    start_ms,
                )
                df_new = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, start_time=start_ms)

            else:
                logger.info("本地文件为空，将重新全量拉取一批: %s %s", symbol, timeframe)
                df_new = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            if df_new is None or df_new.empty:
                logger.info("没有新的 K 线数据: %s %s", symbol, timeframe)
                return df_local

            df_all = pd.concat([df_local, df_new]) if df_local is not None else df_new
            # 去重同一时间戳的 K 线，以最新为准
            df_all = df_all[~df_all.index.duplicated(keep="last")].sort_index()
        else:
            # 第一次拉取
            logger.info("本地无历史文件，将首次拉取 K 线: %s %s", symbol, timeframe)
            df_all = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if df_all is None or df_all.empty:
                logger.warning("首次拉取 K 线失败或无数据: %s %s", symbol, timeframe)
                return None

        # 写回到 CSV
        df_to_save = df_all.copy()
        df_to_save.to_csv(file_path, index=True, index_label="open_time")
        logger.info("已同步并保存 K 线到本地: %s (行数=%s)", file_path, len(df_to_save))

        return df_all
