"""S3 SourceAdapter wrapping S3EdgeClient."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from decisionpen_mcp.adapters.base import DownloadedItem, RemoteItem
from decisionpen_mcp.config import EdgeConfig
from decisionpen_mcp.content import sha256_hex
from decisionpen_mcp.policy import assert_key_allowed, assert_size_allowed
from decisionpen_mcp.s3_client import S3EdgeClient, object_to_item


class S3SourceAdapter:
    def __init__(self, cfg: EdgeConfig, client: Optional[S3EdgeClient] = None):
        self._cfg = cfg
        self._client = client or S3EdgeClient(cfg)

    def list_items_recursive(self, *, max_keys: int) -> List[RemoteItem]:
        prefix = self._cfg.allowlist_prefix
        raw = self._client.list_recursive(prefix, max_keys=max_keys)
        out: List[RemoteItem] = []
        for obj in raw:
            meta = object_to_item(obj, self._cfg.bucket)
            etag = (obj.get("ETag") or "").strip('"') or None
            out.append(
                RemoteItem(
                    remote_id=meta["item_id"],
                    name=meta["name"],
                    size=int(meta.get("size") or 0),
                    etag=etag,
                    last_modified=meta.get("last_modified"),
                    uri=meta["uri"],
                    source_system="s3",
                )
            )
        return out

    def download_item(self, remote_id: str) -> DownloadedItem:
        allowed = assert_key_allowed(self._cfg, remote_id)
        head = self._client.head(allowed.key)
        size = int(head.get("ContentLength") or 0)
        assert_size_allowed(self._cfg, size)
        data, meta = self._client.get_bytes(allowed.key)
        assert_size_allowed(self._cfg, len(data))
        etag = (meta.get("etag") or "").strip('"') or None
        item = RemoteItem(
            remote_id=allowed.key,
            name=allowed.key.rsplit("/", 1)[-1],
            size=len(data),
            etag=etag,
            last_modified=meta.get("last_modified"),
            uri=allowed.uri,
            source_system="s3",
        )
        return DownloadedItem(
            item=item,
            content=data,
            content_type=meta.get("content_type"),
            content_sha256=sha256_hex(data),
        )

    def fingerprint(self, item: RemoteItem) -> Dict[str, Any]:
        return {
            "etag": item.etag,
            "last_modified": item.last_modified,
            "size": item.size,
        }
