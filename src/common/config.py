"""Configuration management module."""

import os
import json
from typing import Any, Dict, Optional


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        if config_path:
            self.load(config_path)
        self._load_env_overrides()

    def load(self, path: str) -> None:
        with open(path) as f:
            self._data = json.load(f)

    def _load_env_overrides(self) -> None:
        prefix = "AO_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace("_", ".")
                self._set_nested(config_key, value)

    def _set_nested(self, key: str, value: Any) -> None:
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        self._set_nested(key, value)

    def to_dict(self) -> Dict:
        return self._data


def validate_sandbox_config(config: Config) -> None:
    """Validate sandbox resource-limit configuration values.

    Ensures cpu_time, memory_mb, and disk_mb are positive integers
    before they flow into ResourceLimits.  Called at startup after
    config loading and before sandbox creation.

    Raises ValueError for any invalid (non‑positive) limit.
    """
    limits = (
        ("sandbox.cpu_time", 60),
        ("sandbox.memory_mb", 512),
        ("sandbox.disk_mb", 100),
    )
    for key, default in limits:
        raw = config.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"Config key '{key}' must be an integer, got {raw!r}"
            )
        if value <= 0:
            raise ValueError(
                f"Config key '{key}' must be positive, got {value}"
            )
