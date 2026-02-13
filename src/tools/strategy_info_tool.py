"""策略信息查询 Tool。

提供给 LangChain Agent 的标准 Tool，用于查询当前支持的策略以及参数说明。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.common.logger import get_logger
from src.services.strategies.registry import get_strategy_meta, strategies_as_dict

try:
    from langchain_core.tools import StructuredTool  # type: ignore
except Exception:  # pragma: no cover
    from langchain.tools import StructuredTool  # type: ignore


logger = get_logger(__name__)


class StrategyInfoInput(BaseModel):
    """策略信息查询入参。

    - 不传 name: 返回所有策略及其参数说明
    - 传入 name: 只返回指定策略的信息
    """

    name: Optional[str] = Field(
        default=None,
        description="策略标识（如 ma_cross、rsi）。不传则返回所有策略。",
    )




def _get_strategy_info(name: Optional[str] = None) -> Dict[str, Any]:
    """查询策略元信息，供 Agent 使用。

    注意：此函数签名需要与 StructuredTool 参数风格兼容，因此使用普通关键字参数，
    然后在内部构造 Pydantic 模型进行校验与文档生成。
    """
    args = StrategyInfoInput(name=name)

    if args.name:
        try:
            meta = get_strategy_meta(args.name)
        except ValueError as e:
            # 返回结构化错误，方便 Agent 解释给用户
            return {
                "ok": False,
                "error": str(e),
                "strategies": strategies_as_dict(),
            }

        from dataclasses import asdict

        return {
            "ok": True,
            "strategies": [
                {
                    "key": meta.key,
                    "display_name": meta.display_name,
                    "description": meta.description,
                    "params": [asdict(p) for p in meta.params],
                }
            ],
        }

    # 未指定 name，返回所有策略
    return {
        "ok": True,
        "strategies": strategies_as_dict(),
    }



strategy_info_tool: StructuredTool = StructuredTool.from_function(
    func=_get_strategy_info,
    name="list_strategies",
    description=(
        "查询当前支持的回测策略及其参数说明。\n"
        "当模型不确定有哪些可用策略，或不知道策略需要哪些参数时，应先调用此 Tool。"
    ),
    args_schema=StrategyInfoInput,
)


__all__ = ["StrategyInfoInput", "strategy_info_tool"]
