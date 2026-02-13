"""策略注册与元信息模块。

集中管理当前支持的策略：
- 统一注册 key -> 策略类
- 提供策略描述、参数说明，供 Agent/Tool 查询
- 统一校验策略是否受支持
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Type

from src.services.strategies.base_strategy import BaseStrategy
from src.services.strategies.ma_cross_strategy import MACrossStrategy
from src.services.strategies.rsi_strategy import RSIStrategy


@dataclass(slots=True)
class StrategyParamMeta:
    name: str
    type: str
    default: Any
    description: str


@dataclass(slots=True)
class StrategyMeta:
    key: str
    display_name: str
    description: str
    cls: Type[BaseStrategy]
    params: List[StrategyParamMeta]


# 当前支持的策略注册表
_STRATEGIES: Dict[str, StrategyMeta] = {
    "ma_cross": StrategyMeta(
        key="ma_cross",
        display_name="双均线交叉策略",
        description="当短期均线上穿长期均线时买入，下穿时卖出。适合趋势跟随场景。",
        cls=MACrossStrategy,
        params=[
            StrategyParamMeta(
                name="fast_period",
                type="int",
                default=10,
                description="快线周期，例如 5/10/20，数值越小越敏感。",
            ),
            StrategyParamMeta(
                name="slow_period",
                type="int",
                default=30,
                description="慢线周期，例如 30/60/120，数值越大趋势越平滑。",
            ),
        ],
    ),
    "rsi": StrategyMeta(
        key="rsi",
        display_name="RSI 超买超卖策略",
        description="当 RSI 低于超卖阈值时买入，高于超买阈值时卖出，偏震荡反转。",
        cls=RSIStrategy,
        params=[
            StrategyParamMeta(
                name="period",
                type="int",
                default=14,
                description="RSI 计算周期，经典取值为 14。",
            ),
            StrategyParamMeta(
                name="oversold",
                type="float",
                default=30.0,
                description="超卖阈值，RSI 低于该值时认为价格超卖。",
            ),
            StrategyParamMeta(
                name="overbought",
                type="float",
                default=70.0,
                description="超买阈值，RSI 高于该值时认为价格超买。",
            ),
        ],
    ),
}


def get_strategy_meta(key: str) -> StrategyMeta:
    """按 key 获取策略元信息，如不存在则抛出 ValueError。

    供上层做校验与报错提示。
    """
    k = key.lower()
    if k not in _STRATEGIES:
        raise ValueError(f"未知策略: {key}. 当前支持: {list(_STRATEGIES.keys())}")
    return _STRATEGIES[k]


def get_strategy_cls(key: str) -> Type[BaseStrategy]:
    """获取策略类，用于实例化策略。"""
    return get_strategy_meta(key).cls


def list_strategies() -> List[StrategyMeta]:
    """列出当前支持的所有策略元信息。"""
    return list(_STRATEGIES.values())


def strategies_as_dict() -> List[Dict[str, Any]]:
    """将策略元信息转换为可 JSON 序列化的字典列表。"""
    result: List[Dict[str, Any]] = []
    for meta in _STRATEGIES.values():
        result.append(
            {
                "key": meta.key,
                "display_name": meta.display_name,
                "description": meta.description,
                "params": [asdict(p) for p in meta.params],
            }
        )
    return result
