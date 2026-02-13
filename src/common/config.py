from pathlib import Path
from typing import Any, Dict

import os
import yaml
from dotenv import load_dotenv


# 项目根目录（假设 config.py 在 src/common 下）
BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "configs"


def _load_yaml(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_env(value: Any) -> Any:
    """
    支持在 yaml 中写 ${ENV_VAR}
    """
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.getenv(env_key)
    return value


def _resolve_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归解析 dict 中的 ${ENV_VAR}
    """
    resolved = {}
    for k, v in data.items():
        if isinstance(v, dict):
            resolved[k] = _resolve_dict(v)
        else:
            resolved[k] = _resolve_env(v)
    return resolved


class Settings:
    """
    全局配置对象
    使用方式：
        from common.config import settings
        settings.app["env"]
    """

    def __init__(self) -> None:
        # 1️⃣ 加载 .env
        load_dotenv(BASE_DIR / ".env")

        # 2️⃣ 加载各类 yaml
        self.app = self._load_section("app.yaml", "app")
        self.llm = self._load_section("llm.yaml", "llm")
        # exchange.yaml 也按根键 "exchange" 展开，保持与 app/llm/risk 一致
        self.exchange = self._load_section("exchange.yaml", "exchange")
        self.risk = self._load_section("risk.yaml", "risk", optional=True)


    def _load_section(
        self,
        filename: str,
        root_key: str | None,
        optional: bool = False,
    ) -> Dict[str, Any]:
        path = CONFIG_DIR / filename
        if not path.exists():
            if optional:
                return {}
            raise FileNotFoundError(f"Missing config file: {filename}")

        raw = _load_yaml(path)
        resolved = _resolve_dict(raw)

        if root_key:
            if root_key not in resolved:
                raise KeyError(f"Missing root key '{root_key}' in {filename}")
            return resolved[root_key]

        return resolved

    @property
    def env(self) -> str:
        return self.app.get("env", "dev")

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


# ✅ 全局唯一配置实例
settings = Settings()
