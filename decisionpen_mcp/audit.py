"""Append-only JSONL audit log for every Edge MCP tool call."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class AuditLogger:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        tool: str,
        ok: bool,
        mode: str,
        tenant_id: Optional[str] = None,
        uri: Optional[str] = None,
        item_id: Optional[str] = None,
        bytes_count: Optional[int] = None,
        detail: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        row: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "ok": ok,
            "mode": mode,
        }
        if tenant_id:
            row["tenant_id"] = tenant_id
        if uri:
            row["uri"] = uri
        if item_id:
            row["item_id"] = item_id
        if bytes_count is not None:
            row["bytes"] = bytes_count
        if detail:
            row["detail"] = detail
        if extra:
            row["extra"] = extra
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
