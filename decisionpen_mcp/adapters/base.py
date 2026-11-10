"""Source adapter interface for edge sync (S3 first; SharePoint later)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class RemoteItem:
    """One remote object under an allowlisted prefix."""

    remote_id: str
    name: str
    size: int
    etag: Optional[str]
    last_modified: Optional[str]
    uri: str
    source_system: str


@dataclass(frozen=True)
class DownloadedItem:
    item: RemoteItem
    content: bytes
    content_type: Optional[str]
    content_sha256: str


class SourceAdapter(Protocol):
    def list_items_recursive(self, *, max_keys: int) -> List[RemoteItem]:
        """List objects under the configured allowlist (files only)."""

    def download_item(self, remote_id: str) -> DownloadedItem:
        """Download one object and return bytes + fingerprint fields."""

    def fingerprint(self, item: RemoteItem) -> Dict[str, Any]:
        """Stable fingerprint fields for cursor comparison."""
