"""Diff cursor → download changed → push batches → commit on success."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from decisionpen_mcp.adapters.base import SourceAdapter
from decisionpen_mcp.api_client import DecisionPenApiClient, DecisionPenApiError
from decisionpen_mcp.audit import AuditLogger
from decisionpen_mcp.config import EdgeConfig
from decisionpen_mcp.policy import PolicyDenied, assert_propose_allowed, is_supported_extension
from decisionpen_mcp.sync.state import SyncState


class SyncEngine:
    def __init__(
        self,
        cfg: EdgeConfig,
        adapter: SourceAdapter,
        api: DecisionPenApiClient,
        state: SyncState,
        audit: Optional[AuditLogger] = None,
    ):
        self._cfg = cfg
        self._adapter = adapter
        self._api = api
        self._state = state
        self._audit = audit

    def run(
        self,
        *,
        dry_run: bool = False,
        max_keys: Optional[int] = None,
        batch_size: int = 10,
        source_label: Optional[str] = None,
        anchor_application_id: Optional[str] = None,
        preflight: bool = True,
    ) -> Dict[str, Any]:
        assert_propose_allowed(self._cfg)
        if not self._cfg.allowlist_prefix:
            raise PolicyDenied(
                "DP_S3_PREFIX must be set for sync/propose (refuse empty allowlist)",
                code="empty_prefix",
            )

        limit = max_keys if max_keys and max_keys > 0 else self._cfg.max_list_items * 50
        listed = self._adapter.list_items_recursive(max_keys=limit)

        would_push: List[Dict[str, Any]] = []
        skipped_unchanged: List[str] = []
        skipped_unsupported: List[str] = []

        for item in listed:
            if not is_supported_extension(item.remote_id):
                skipped_unsupported.append(item.remote_id)
                continue
            if self._state.is_unchanged(
                item.remote_id,
                etag=item.etag,
                last_modified=item.last_modified,
                size=item.size,
            ):
                skipped_unchanged.append(item.remote_id)
                continue
            would_push.append(
                {
                    "remote_id": item.remote_id,
                    "name": item.name,
                    "etag": item.etag,
                    "last_modified": item.last_modified,
                    "size": item.size,
                    "uri": item.uri,
                }
            )

        summary: Dict[str, Any] = {
            "ok": True,
            "dry_run": dry_run,
            "listed": len(listed),
            "would_push": len(would_push),
            "skipped_unchanged": len(skipped_unchanged),
            "skipped_unsupported": len(skipped_unsupported),
            "candidates": would_push[:50],
            "results": [],
        }

        if dry_run:
            if self._audit:
                self._audit.record(
                    tool="sync",
                    ok=True,
                    mode=self._cfg.mode.value,
                    tenant_id=self._cfg.tenant_id,
                    detail=(
                        f"dry_run listed={len(listed)} would_push={len(would_push)} "
                        f"unchanged={len(skipped_unchanged)}"
                    ),
                )
            return summary

        results: List[Dict[str, Any]] = []
        batch_size = max(1, min(batch_size, 20))

        for i in range(0, len(would_push), batch_size):
            chunk = would_push[i : i + batch_size]
            push_items: List[Dict[str, Any]] = []
            meta_by_id: Dict[str, Dict[str, Any]] = {}

            for cand in chunk:
                rid = cand["remote_id"]
                downloaded = self._adapter.download_item(rid)
                meta_by_id[rid] = {
                    "etag": downloaded.item.etag,
                    "last_modified": downloaded.item.last_modified,
                    "size": downloaded.item.size,
                    "content_sha256": downloaded.content_sha256,
                    "uri": downloaded.item.uri,
                }
                push_items.append(
                    {
                        "filename": downloaded.item.name,
                        "content_type": downloaded.content_type,
                        "content_bytes": downloaded.content,
                        "content_sha256": downloaded.content_sha256,
                        "source_system": "s3",
                        "source_uri": downloaded.item.uri,
                        "remote_id": downloaded.item.remote_id,
                        "etag": downloaded.item.etag,
                        "last_modified": downloaded.item.last_modified,
                    }
                )

            if preflight and push_items:
                try:
                    status = self._api.content_status(
                        [
                            {
                                "remote_id": p["remote_id"],
                                "etag": p.get("etag"),
                                "content_sha256": p["content_sha256"],
                            }
                            for p in push_items
                        ]
                    )
                    need = {
                        str(r.get("content_sha256") or "").lower(): bool(
                            r.get("needs_processing", True)
                        )
                        for r in (status.get("items") or [])
                    }
                    filtered = []
                    for p in push_items:
                        sha = str(p["content_sha256"]).lower()
                        if need.get(sha, True):
                            filtered.append(p)
                        else:
                            # Server already has this digest — advance cursor, $0 LLM.
                            m = meta_by_id[p["remote_id"]]
                            self._state.commit(
                                p["remote_id"],
                                etag=m.get("etag"),
                                last_modified=m.get("last_modified"),
                                size=m.get("size"),
                                content_sha256=m.get("content_sha256"),
                            )
                            results.append(
                                {
                                    "remote_id": p["remote_id"],
                                    "status": "skipped_unchanged",
                                    "content_sha256": sha,
                                }
                            )
                    push_items = filtered
                    self._state.save()
                except DecisionPenApiError:
                    # Preflight optional; fall through to push.
                    pass

            if not push_items:
                continue

            try:
                resp = self._api.push_enrichment(
                    push_items,
                    source_label=source_label,
                    anchor_application_id=anchor_application_id,
                )
            except DecisionPenApiError as e:
                # Do not advance cursor on 429/5xx.
                results.append(
                    {
                        "status": "error",
                        "detail": str(e),
                        "status_code": e.status_code,
                        "batch_remote_ids": [p["remote_id"] for p in push_items],
                    }
                )
                summary["ok"] = False
                summary["results"] = results
                if self._audit:
                    self._audit.record(
                        tool="sync",
                        ok=False,
                        mode=self._cfg.mode.value,
                        tenant_id=self._cfg.tenant_id,
                        detail=str(e),
                    )
                return summary

            for row in resp.get("results") or []:
                rid = row.get("remote_id")
                st = row.get("status")
                results.append(row)
                if rid and st in (
                    "queued",
                    "skipped_unchanged",
                    "skipped_duplicate_content",
                ):
                    m = meta_by_id.get(rid) or {}
                    self._state.commit(
                        rid,
                        etag=m.get("etag"),
                        last_modified=m.get("last_modified"),
                        size=m.get("size"),
                        content_sha256=row.get("content_sha256") or m.get("content_sha256"),
                    )
            self._state.save()

        summary["results"] = results
        summary["queued"] = sum(1 for r in results if r.get("status") == "queued")
        if self._audit:
            self._audit.record(
                tool="sync",
                ok=summary["ok"],
                mode=self._cfg.mode.value,
                tenant_id=self._cfg.tenant_id,
                detail=(
                    f"listed={len(listed)} queued={summary.get('queued', 0)} "
                    f"unchanged={len(skipped_unchanged)}"
                ),
            )
        return summary
