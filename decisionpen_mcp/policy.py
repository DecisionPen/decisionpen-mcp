"""PolicyGate: prefix allowlist, size quotas, mode checks."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import Optional

from decisionpen_mcp.config import EdgeConfig, McpMode

# Extensions DecisionPen FileProcessor can ingest (keep in sync with src.file_processor).
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
}


class PolicyDenied(Exception):
    """Raised when a tool call violates Edge policy."""

    def __init__(self, reason: str, code: str = "policy_denied"):
        super().__init__(reason)
        self.reason = reason
        self.code = code


@dataclass(frozen=True)
class AllowedObject:
    """Object key confirmed inside the allowlisted prefix."""

    key: str
    uri: str


def normalize_key(key: str) -> str:
    """Normalize an S3 object key; reject empty / traversal."""
    raw = (key or "").strip().lstrip("/")
    if not raw:
        raise PolicyDenied("item_id / key must be non-empty", code="empty_key")
    if "\\" in raw:
        raise PolicyDenied("key must use '/' separators, not backslashes", code="bad_separator")
    # Collapse . and .. using posix rules on the key path
    collapsed = posixpath.normpath(raw)
    if collapsed.startswith("../") or collapsed == "..":
        raise PolicyDenied("path traversal is not allowed", code="path_traversal")
    if collapsed.startswith("/"):
        collapsed = collapsed.lstrip("/")
    # normpath removes trailing slash; restore if original was a "folder" marker
    if raw.endswith("/") and not collapsed.endswith("/"):
        collapsed = collapsed + "/"
    return collapsed


def is_under_prefix(key: str, allowlist_prefix: str) -> bool:
    if not allowlist_prefix:
        # Empty allowlist = entire bucket (ops must set DP_S3_PREFIX in prod).
        return True
    return key == allowlist_prefix.rstrip("/") or key.startswith(allowlist_prefix)


def assert_key_allowed(cfg: EdgeConfig, key: str) -> AllowedObject:
    normalized = normalize_key(key)
    if not is_under_prefix(normalized, cfg.allowlist_prefix):
        raise PolicyDenied(
            f"key {normalized!r} is outside allowlisted prefix "
            f"{cfg.allowlist_prefix!r} on bucket {cfg.bucket!r}",
            code="outside_allowlist",
        )
    return AllowedObject(
        key=normalized,
        uri=f"s3://{cfg.bucket}/{normalized}",
    )


def assert_path_allowed(cfg: EdgeConfig, path: str) -> str:
    """
    Browse/search path relative to allowlist, or absolute key under allowlist.
    Returns the full S3 prefix to list (no leading slash, may be empty).
    """
    path = (path or "").strip().lstrip("/")
    if not path:
        return cfg.allowlist_prefix
    # If caller passes a full key/prefix under allowlist, accept it.
    try:
        full = normalize_key(path if path.endswith("/") else path)
    except PolicyDenied:
        raise
    # Relative path under allowlist
    if cfg.allowlist_prefix and not is_under_prefix(full, cfg.allowlist_prefix):
        candidate = normalize_key(cfg.allowlist_prefix + path)
        if not is_under_prefix(candidate, cfg.allowlist_prefix):
            raise PolicyDenied(
                f"path {path!r} is outside allowlisted prefix {cfg.allowlist_prefix!r}",
                code="outside_allowlist",
            )
        return candidate if candidate.endswith("/") else candidate + "/"
    if not full.endswith("/"):
        # Treat as folder prefix for listing
        return full + "/"
    return full


def assert_size_allowed(cfg: EdgeConfig, size: int, *, label: str = "object") -> None:
    if size < 0:
        raise PolicyDenied(f"invalid {label} size", code="bad_size")
    if size > cfg.max_object_bytes:
        raise PolicyDenied(
            f"{label} size {size} exceeds DP_MCP_MAX_OBJECT_BYTES={cfg.max_object_bytes}",
            code="too_large",
        )


def _peek_jwt_role(token: Optional[str]) -> Optional[str]:
    """Best-effort role claim from an unverified JWT payload (API still enforces)."""
    if not token or token.count(".") < 2:
        return None
    try:
        import base64
        import json

        payload_b64 = token.split(".")[1]
        pad = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + pad)
        data = json.loads(raw.decode("utf-8"))
        role = str(data.get("role") or "").strip()
        return role or None
    except Exception:
        return None


def assert_api_configured(cfg: EdgeConfig) -> None:
    """Require DecisionPen API base + token for Ask / push tools."""
    if not (cfg.api_base or "").strip():
        raise PolicyDenied(
            "DP_API_BASE is required for DecisionPen API tools",
            code="missing_api_base",
        )
    if not (cfg.api_token or "").strip():
        raise PolicyDenied(
            "DP_API_TOKEN is required (Edge API token or session JWT)",
            code="missing_api_token",
        )


def assert_ask_allowed(cfg: EdgeConfig) -> None:
    """Ask/search tools: any mode; needs API auth (Viewer+ enforced server-side)."""
    assert_api_configured(cfg)


def assert_s3_configured(cfg: EdgeConfig) -> None:
    if not (cfg.bucket or "").strip():
        raise PolicyDenied(
            "DP_S3_BUCKET is required for S3 tools (list/search/get/propose/sync)",
            code="missing_s3_bucket",
        )


def assert_propose_allowed(cfg: EdgeConfig) -> None:
    assert_s3_configured(cfg)
    if not cfg.propose_allowed:
        raise PolicyDenied(
            f"propose_enrichment is disabled in mode={cfg.mode.value}; "
            f"set DP_MCP_MODE=propose (or persist_approved) to enable",
            code="mode_forbids_propose",
        )
    if not cfg.allowlist_prefix:
        raise PolicyDenied(
            "DP_S3_PREFIX must be set for propose/sync (empty prefix refused)",
            code="empty_prefix",
        )
    assert_api_configured(cfg)
    # MCP never Confirmed-writes; Inbox accept is human-only.
    # Edge API tokens (dp_edge_…) are scoped server-side; JWT Viewers blocked here.
    token = cfg.api_token or ""
    if token.startswith("dp_edge_"):
        return
    role = _peek_jwt_role(cfg.api_token)
    if role and role.strip().lower() == "viewer":
        raise PolicyDenied(
            "DP_API_TOKEN is a Viewer; propose_enrichment requires Editor or Administrator",
            code="viewer_cannot_propose",
        )


def extension_of(key: str) -> str:
    name = key.rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def is_supported_extension(key: str) -> bool:
    return extension_of(key) in SUPPORTED_EXTENSIONS


def mode_label(mode: McpMode) -> str:
    return mode.value
