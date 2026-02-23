"""Tool 注册中心

负责自动发现并注册 `src.tools` 包下的所有 LangChain Tool，避免在 Agent 代码中手动维护工具列表。

约定：
- 每个 Tool 模块（例如 `backtest_tool.py`、`news_tool.py`）中，至少暴露一个 `BaseTool`/`StructuredTool` 实例；
- 注册中心会遍历 `src.tools` 子模块，收集所有 `BaseTool` 实例，并以 `tool.name` 作为键；
- 新增 Tool 时只需在 `src/tools` 下新增模块并定义 Tool 实例，不需要修改 Agent 代码。
"""

from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules
from typing import Dict

try:
  from langchain_core.tools import BaseTool  # type: ignore
except Exception:  # pragma: no cover
  from langchain.tools import BaseTool  # type: ignore

from src.common.logger import get_logger


logger = get_logger(__name__)


def _iter_tool_modules():
  """遍历 `src.tools` 包下所有 Tool 模块（排除内部模块和本 registry 本身）。"""
  package_name = __name__.rsplit(".", 1)[0]  # "src.tools"
  pkg = import_module(package_name)

  for module_info in iter_modules(pkg.__path__):
    name = module_info.name
    # 跳过私有模块和本注册中心模块
    if name.startswith("_") or name in {"registry"}:
      continue
    full_name = f"{package_name}.{name}"
    try:
      module = import_module(full_name)
      yield module
    except Exception as e:  # noqa: BLE001
      logger.warning("[tool_registry] 导入 Tool 模块失败: %s (%s)", full_name, e)


def discover_all_tools() -> Dict[str, BaseTool]:
  """自动发现并返回所有已注册的 Tool 实例。

  返回一个字典：{tool.name: tool_instance}。
  """
  tools: Dict[str, BaseTool] = {}

  for module in _iter_tool_modules():
    for attr_name in dir(module):
      attr = getattr(module, attr_name)
      if isinstance(attr, BaseTool):
        tool = attr
        # 以 Tool 的 name 作为键，后发现的同名 Tool 会覆盖之前的（通常不会发生）
        tools[tool.name] = tool

  logger.info("[tool_registry] 已发现 Tool 个数: %s -> %s", len(tools), list(tools.keys()))
  return tools


# 在模块导入时就完成一次发现，供 Agent 直接使用
ALL_TOOLS: Dict[str, BaseTool] = discover_all_tools()


__all__ = ["ALL_TOOLS", "discover_all_tools"]
