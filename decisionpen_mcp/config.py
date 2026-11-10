"""Environment-driven configuration for Edge MCP (S3)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class McpMode(str, Enum):
    """Trust ladder: how much DecisionPen may retain from a fetch."""

    CITE_ONLY = "cite_only"
    PROPOSE = "propose"
    # Persist happens only after Inbox approve in the app; MCP never Confirmed-writes.
    PERSIST_APPROVED = "persist_approved"


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class EdgeConfig:
    """Local / Edge runtime settings. Secrets never appear in tool arguments."""

    mode: McpMode
    bucket: str
    prefix: str
    region: Optional[str]
    aws_profile: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    max_object_bytes: int
    max_list_items: int
    max_search_results: int
    max_text_chars: int
    api_base: Optional[str]
    api_token: Optional[str]
    connector_id: Optional[str]
    tenant_id: Optional[str]
    audit_log_path: Path
    sync_state_path: Path
    include_binary_base64: bool

    @property
    def allowlist_prefix(self) -> str:
        """Normalized prefix with trailing slash (empty = whole bucket — discouraged)."""
        p = (self.prefix or "").strip().lstrip("/")
        if not p:
            return ""
        return p if p.endswith("/") else p + "/"

    @property
    def propose_allowed(self) -> bool:
        return self.mode in (McpMode.PROPOSE, McpMode.PERSIST_APPROVED)

    @classmethod
    def from_env(cls) -> "EdgeConfig":
        mode_raw = (_env("DP_MCP_MODE", "cite_only") or "cite_only").lower()
        try:
            mode = McpMode(mode_raw)
        except ValueError as e:
            allowed = ", ".join(m.value for m in McpMode)
            raise ValueError(
                f"Invalid DP_MCP_MODE={mode_raw!r}. Allowed: {allowed}"
            ) from e

        # Optional when using Ask-only tools; S3 tools still need a bucket at call time.
        bucket = _env("DP_S3_BUCKET") or _env("AWS_S3_BUCKET") or ""

        audit_raw = _env(
            "DP_MCP_AUDIT_LOG",
            str(Path.cwd() / ".decisionpen_mcp_audit.jsonl"),
        )
        sync_raw = _env(
            "DP_SYNC_STATE_PATH",
            str(Path.cwd() / "sync_state.json"),
        )
        return cls(
            mode=mode,
            bucket=bucket,
            prefix=_env("DP_S3_PREFIX", "") or "",
            region=_env("DP_S3_REGION") or _env("AWS_DEFAULT_REGION") or _env("AWS_REGION"),
            aws_profile=_env("AWS_PROFILE") or _env("DP_AWS_PROFILE"),
            aws_access_key_id=_env("AWS_ACCESS_KEY_ID") or _env("DP_AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY")
            or _env("DP_AWS_SECRET_ACCESS_KEY"),
            max_object_bytes=_env_int("DP_MCP_MAX_OBJECT_BYTES", 10 * 1024 * 1024),
            max_list_items=_env_int("DP_MCP_MAX_LIST_ITEMS", 100),
            max_search_results=_env_int("DP_MCP_MAX_SEARCH_RESULTS", 50),
            max_text_chars=_env_int("DP_MCP_MAX_TEXT_CHARS", 100_000),
            api_base=(_env("DP_API_BASE") or "http://localhost:8000") or None,
            api_token=_env("DP_API_TOKEN"),
            connector_id=_env("DP_CONNECTOR_ID"),
            tenant_id=_env("DP_TENANT_ID"),
            audit_log_path=Path(audit_raw or ".decisionpen_mcp_audit.jsonl"),
            sync_state_path=Path(sync_raw or "sync_state.json"),
            include_binary_base64=(_env("DP_MCP_INCLUDE_BINARY_BASE64", "false") or "")
            .lower()
            in ("1", "true", "yes"),
        )
