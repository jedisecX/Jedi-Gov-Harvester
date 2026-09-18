from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")


class Config:
    def __init__(self, data: dict[str, Any], path: Path | None = None):
        self._data = data
        self.path = path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        p = Path(path) if path else DEFAULT_CONFIG_PATH
        if not p.exists():
            raise FileNotFoundError(f"Config not found: {p}")
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(data, p)

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self._data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    @property
    def database_path(self) -> Path:
        return Path(self.get("database", "data/harvester.sqlite"))

    @property
    def storage_root(self) -> Path:
        return Path(self.get("storage.root", "data/pdfs"))

    @property
    def storage_temp(self) -> Path:
        return Path(self.get("storage.temp", "data/partials"))

    @property
    def user_agent(self) -> str:
        return str(self.get("network.user_agent", "GovernmentPDFHarvester/1.0"))

    @property
    def allowed_domains(self) -> list[str]:
        return list(self.get("allowed_domains", ["*.gov"]))

    @property
    def denied_domains(self) -> list[str]:
        return list(self.get("denied_domains", []))
