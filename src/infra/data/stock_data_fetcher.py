"""股票数据获取模块

基于 akshare 拉取 A 股/港股等股票日线/分钟 K 线数据，并提供与 DataFetcher
类似的接口风格：
- fetch_stock_ohlcv: 直接拉取 K 线数据（不落盘）；
- sync_stock_ohlcv_to_local: 同步到本地 CSV，并做增量更新。

注意：
- 需要在 requirements.txt 中安装 akshare；
- 这里只做基础示例，实际使用时可按需扩展市场、复权方式等参数。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import akshare as ak  # type: ignore
except Exception as e:  # pragma: no cover - 如果未安装 akshare，提示更友好错误
    raise ImportError("请安装 akshare 包以使用股票数据获取功能: pip install akshare") from e

from src.common.logger import get_logger


logger = get_logger(__name__)

# 项目根目录 / 股票数据存储目录
BASE_DIR = Path(__file__).resolve().parents[2]
STOCK_DATA_DIR = BASE_DIR / "data" / "stock_ohlcv"


class StockDataFetcher:
    """基于 akshare 的股票 K 线数据获取器。

    当前实现偏简单，默认使用 A 股日线前复权数据接口。
    后续如需支持港股/美股或其他周期，可在此基础上扩展。
    """

    def __init__(self) -> None:  # 保留占位，便于后续扩展配置
        STOCK_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # =============================
    # 公共接口方法（仅请求，不落盘）
    # =============================
    def fetch_stock_ohlcv(
        self,
        symbol: str,
        start_date: str = "20100101",
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取单只股票的日线 K 线数据。

        :param symbol: 股票代码，例如 "000001"、"600000"（不带交易所后缀）。
        :param start_date: 起始日期，格式 "YYYYMMDD"。
        :param end_date: 结束日期，格式 "YYYYMMDD"，None 表示到最新。
        :param adjust: 复权方式，"qfq"=前复权, "hfq"=后复权, ""=不复权。
        :return: 以日期为索引的 DataFrame，列为 [open, high, low, close, volume]。
        """
        logger.info(
            "[StockDataFetcher] 拉取股票 K 线: symbol=%s, start=%s, end=%s, adjust=%s",
            symbol,
            start_date,
            end_date,
            adjust,
        )

        # 示例使用 A 股前复权日线接口；如果需要其他市场，可按 akshare 文档扩展。
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date or "99991231",
            adjust=adjust,
        )
        if df is None or df.empty:
            logger.warning("[StockDataFetcher] 未获取到股票 K 线数据: %s", symbol)
            return pd.DataFrame()

        # 标准化列名和索引
        # akshare 返回列一般包含: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额 等
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        ohlcv = df[["open", "high", "low", "close", "volume"]].astype(float)
        return ohlcv

    # =============================
    # 增量同步到本地 CSV
    # =============================
    def sync_stock_ohlcv_to_local(
        self,
        symbol: str,
        start_date: str = "20100101",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """增量同步股票日线 K 线到本地 CSV。

        - 本地文件路径: data/stock_ohlcv/{symbol}.csv
        - 如文件已存在: 从最后一日之后开始增量拉取并追加；
        - 如文件不存在: 从 start_date 开始拉取至今。
        """
        file_path = STOCK_DATA_DIR / f"{symbol}.csv"

        if file_path.exists():
            try:
                df_local = pd.read_csv(file_path, parse_dates=["date"])
                df_local.set_index("date", inplace=True)
            except Exception as e:  # noqa: BLE001
                logger.error("读取本地股票 K 线文件失败，将重新拉取: %s", e)
                df_local = pd.DataFrame()

            last_date = df_local.index.max() if not df_local.empty else None
            if last_date is not None:
                # 下一个交易日的开始日期
                next_start = (last_date + pd.Timedelta(days=1)).strftime("%Y%m%d")
                logger.info(
                    "[StockDataFetcher] 增量拉取股票 K 线: %s 从 %s 之后",
                    symbol,
                    last_date.date(),
                )
                df_new = self.fetch_stock_ohlcv(symbol, start_date=next_start, end_date=None, adjust=adjust)
            else:
                df_new = self.fetch_stock_ohlcv(symbol, start_date=start_date, end_date=None, adjust=adjust)

            if df_new is None or df_new.empty:
                logger.info("[StockDataFetcher] 没有新的股票 K 线数据: %s", symbol)
                return df_local

            df_all = pd.concat([df_local, df_new]) if not df_local.empty else df_new
            df_all = df_all[~df_all.index.duplicated(keep="last")].sort_index()
        else:
            logger.info(
                "[StockDataFetcher] 本地无历史文件，将首次拉取股票 K 线: %s 从 %s 起",
                symbol,
                start_date,
            )
            df_all = self.fetch_stock_ohlcv(symbol, start_date=start_date, end_date=None, adjust=adjust)
            if df_all is None or df_all.empty:
                logger.warning("[StockDataFetcher] 首次拉取股票 K 线失败或无数据: %s", symbol)
                return pd.DataFrame()

        # 写回到 CSV
        df_to_save = df_all.copy()
        df_to_save.to_csv(file_path, index=True, index_label="date")
        logger.info("[StockDataFetcher] 已同步并保存股票 K 线到本地: %s (行数=%s)", file_path, len(df_to_save))

        return df_all
