"""Local JSON cursor for edge sync (etag / last_modified / content_sha256)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class SyncState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._items: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._items = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("items") if isinstance(data, dict) else None
            self._items = dict(items) if isinstance(items, dict) else {}
        except Exception:
            self._items = {}

    def get(self, remote_id: str) -> Optional[Dict[str, Any]]:
        return self._items.get(remote_id)

    def is_unchanged(
        self,
        remote_id: str,
        *,
        etag: Optional[str],
        last_modified: Optional[str],
        size: Optional[int] = None,
    ) -> bool:
        prev = self.get(remote_id)
        if not prev:
            return False
        # Prefer ETag when both sides have it (changed etag ⇒ not unchanged).
        if etag and prev.get("etag"):
            return str(prev.get("etag")) == str(etag)
        if (
            last_modified
            and prev.get("last_modified")
            and str(prev.get("last_modified")) == str(last_modified)
            and (size is None or prev.get("size") == size)
        ):
            return True
        return False

    def commit(
        self,
        remote_id: str,
        *,
        etag: Optional[str],
        last_modified: Optional[str],
        size: Optional[int],
        content_sha256: Optional[str],
    ) -> None:
        self._items[remote_id] = {
            "etag": etag,
            "last_modified": last_modified,
            "size": size,
            "content_sha256": content_sha256,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "items": self._items}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
