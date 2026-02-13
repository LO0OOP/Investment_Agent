"""LangChain 回测 Tool 封装。

提供一个可被大模型 / LangChain Agent 调用的标准化 Tool，用于运行本地回测。

核心能力：
- 根据入参（品种、周期、策略、回测窗口等）调用 `services.backtest.backtest_runner.run_backtest`
- 支持限制回测区间为最近 N 天的数据
- 返回结构化 JSON，方便大模型生成自然语言总结
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

import json

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from src.common.logger import get_logger

from src.services.backtest.backtest_runner import run_backtest
from src.services.strategies.registry import get_strategy_meta

try:

    # LangChain >= 0.1 推荐使用 langchain_core.tools
    from langchain_core.tools import StructuredTool  # type: ignore
except Exception:  # pragma: no cover - 兼容旧版本
    from langchain.tools import StructuredTool  # type: ignore


logger = get_logger(__name__)


class BacktestToolInput(BaseModel):
    """回测 Tool 的入参模型（供 LangChain 使用）。"""

    symbol: str = Field(..., description="交易对符号，例如 BTCUSDT 或 ETHUSDT")
    timeframe: str = Field(
        ...,
        description="K 线周期，使用交易所原生标记，例如 1m/5m/1h/4h/1d",
    )
    strategy_name: str = Field(
        ...,
        description="要使用的策略标识，例如 ma_cross、rsi 等（可通过查询策略列表 Tool 获取）",
    )

    lookback_days: int = Field(
        30,
        ge=1,
        description="回测所使用的最近天数，例如 30 表示最近 30 天的数据",
    )
    initial_capital: float = Field(
        10_000.0,
        gt=0,
        description="回测初始资金，单位与报价货币一致（例如 USDT）",
    )
    commission: float = Field(
        0.001,
        ge=0,
        description="单边手续费率，例如 0.001 表示万分之一",
    )
    limit: int = Field(
        1000,
        gt=0,
        le=1000,
        description="每次从交易所增量拉取的最大 K 线条数（受交易所限制）",
    )
    strategy_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="策略特定参数，例如 ma_cross 的 fast_period/slow_period，rsi 的 period/oversold/overbought",
    )

    @field_validator("strategy_params", mode="before")
    @classmethod
    def parse_strategy_params(cls, value: Any) -> Optional[Dict[str, Any]]:
        """允许 strategy_params 既可以是字典，也可以是 JSON 字符串。

        LangChain 在调用工具时，有时会将参数序列化为 JSON 字符串传入，此处做兼容处理。
        """
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:  # noqa: TRY003
                raise ValueError(
                    "strategy_params 应该是字典或可解析为 JSON 对象的字符串"
                ) from exc
            if not isinstance(parsed, dict):
                raise ValueError("strategy_params JSON 必须是对象类型")
            return parsed
        raise ValueError("strategy_params 必须是字典或 JSON 字符串")



def _run_backtest_with_window(**kwargs: Any) -> Dict[str, Any]:

    """内部实现：先调用 run_backtest，再按 lookback_days 限制窗口。

    注意：
    - DataFetcher 会负责增量同步历史数据；
    - 这里再根据 lookback_days 对本地数据做时间窗口过滤。

    由于 StructuredTool 会以关键字参数形式调用本函数，这里使用 **kwargs，
    再在内部用 BacktestToolInput 做一次验证与默认值填充。
    """
    args = BacktestToolInput(**kwargs)

    logger.info(
        "[BacktestTool] 收到回测请求: symbol=%s, timeframe=%s, strategy=%s, lookback_days=%s",
        args.symbol,
        args.timeframe,
        args.strategy_name,
        args.lookback_days,
    )

    # 先校验策略是否受支持，便于给 Agent 友好报错
    try:
        _ = get_strategy_meta(args.strategy_name)
    except ValueError:
        # 直接抛出，让上层 Agent 获取到错误信息并反馈给用户
        raise

    # 直接调用现有的回测服务，并捕获可能的异常，避免 Agent 直接崩溃。
    try:
        results = run_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            strategy_name=args.strategy_name,
            strategy_params=args.strategy_params,
            initial_capital=args.initial_capital,
            commission=args.commission,
            limit=args.limit,
            lookback_days=args.lookback_days,
        )
    except Exception as e:  # noqa: BLE001
        # 将错误转为结构化结果返回给 Agent，由 Agent 决定是否提示重试/检查网络
        logger.error("[BacktestTool] 回测执行失败: %s", e, exc_info=True)
        message = str(e)
        return {
            "ok": False,
            "error_type": e.__class__.__name__,
            "error_message": message,
        }


    # equity_curve 是 DataFrame，这里根据 lookback_days 做截断并转换为可 JSON 化结构
    equity_df = results.get("equity_curve")
    if isinstance(equity_df, pd.DataFrame) and not equity_df.empty:
        max_ts = equity_df.index.max()
        if args.lookback_days is not None and args.lookback_days > 0:
            window_start = max_ts - pd.Timedelta(days=args.lookback_days)
            equity_df = equity_df[equity_df.index >= window_start]

        # 转成 records 方便大模型消费
        results["equity_curve"] = [
            {"timestamp": ts.isoformat(), "equity": float(row["equity"])}
            for ts, row in equity_df.iterrows()
        ]

    # trades 已经是 list[dict]，只需要确保 timestamp 可序列化
    trades = results.get("trades") or []
    normalized_trades: list[Dict[str, Any]] = []
    for t in trades:
        t_copy = dict(t)
        ts = t_copy.get("timestamp")
        if hasattr(ts, "isoformat"):
            t_copy["timestamp"] = ts.isoformat()
        normalized_trades.append(t_copy)
    results["trades"] = normalized_trades

    # 只保留核心统计字段 + 处理后的曲线与交易明细
    return {
        "ok": True,
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "strategy": args.strategy_name,
        "lookback_days": args.lookback_days,
        "initial_capital": float(results.get("initial_capital", args.initial_capital)),
        "final_capital": float(results.get("final_capital", 0.0)),
        "total_return": float(results.get("total_return", 0.0)),
        "max_drawdown": float(results.get("max_drawdown", 0.0)),
        "total_trades": int(results.get("total_trades", 0)),
        "win_rate": float(results.get("win_rate", 0.0)),
        "equity_curve": results.get("equity_curve", []),
        "trades": results.get("trades", []),
    }




# LangChain 可直接使用的 Tool 实例
backtest_tool: StructuredTool = StructuredTool.from_function(
    func=_run_backtest_with_window,
    name="run_backtest",
    description=(
        "运行本地回测引擎，对指定交易对和周期在最近 N 天的数据上执行策略回测。\n"
        "适合在用户提出诸如 '用 RSI 策略在最近 30 天 BTC/USDT 上跑一轮回测' 这类请求时调用。"
    ),
    args_schema=BacktestToolInput,
)


__all__ = ["BacktestToolInput", "backtest_tool"]
