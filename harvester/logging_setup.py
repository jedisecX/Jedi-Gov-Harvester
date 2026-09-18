from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "event": record.getMessage(),
        }
        for key in ("url", "worker", "error", "domain", "query"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_dir: str | Path = "logs") -> None:
    root = Path(log_dir)
    root.mkdir(parents=True, exist_ok=True)
    fmt = JsonFormatter()
    file_handler = logging.FileHandler(root / "harvester.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream], force=True)
    for name in ("search", "crawl", "download"):
        h = logging.FileHandler(root / f"{name}.log", encoding="utf-8")
        h.setFormatter(fmt)
        logging.getLogger(name).addHandler(h)
