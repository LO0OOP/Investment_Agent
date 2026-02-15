from src.infra.data.stock_data_fetcher import StockDataFetcher

if __name__ == "__main__":
    fetcher = StockDataFetcher()

    # 只拉取 DataFrame（不落盘）
    df = fetcher.fetch_stock_ohlcv(symbol="600000", start_date="20240101")
    print(df.tail())

    # 同步到本地 CSV，并自动增量
    df_local = fetcher.sync_stock_ohlcv_to_local(symbol="600000", start_date="20200101")
    print("本地数据行数:", len(df_local))
