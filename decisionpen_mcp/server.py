"""
DecisionPen Edge MCP server (S3 + Context Engine + Ask).

Context tools (prefer these for EA Q&A):
  describe_context_model, search_entities, get_entity, get_entity_relationships,
  get_entity_evidence, search_evidence, get_relationship_summary,
  list_entity_types, batch_get_entities

Also: S3 cite/propose/sync; ask_decisionpen (last resort).

Run:
  python -m decisionpen_mcp
  python -m decisionpen_mcp sync --dry-run

Configure via environment (see README.md / CONTEXT.md / SYNC.md).
"""

from __future__ import annotations

import base64
import json
import sys
from typing import Any, Dict, List, Optional

from decisionpen_mcp.adapters.s3 import S3SourceAdapter
from decisionpen_mcp.api_client import (
    DecisionPenApiClient,
    DecisionPenApiError,
    compact_ask_response,
    compact_batch_entities,
    compact_entity,
    compact_entity_evidence,
    compact_entity_search,
    compact_entity_types,
    compact_evidence_fragments,
    compact_relationship_summary,
    compact_relationships,
)
from decisionpen_mcp.audit import AuditLogger
from decisionpen_mcp.config import EdgeConfig
from decisionpen_mcp.content import build_document_envelope, extract_text, sha256_hex
from decisionpen_mcp.context_model import build_context_model
from decisionpen_mcp.policy import (
    PolicyDenied,
    assert_ask_allowed,
    assert_key_allowed,
    assert_path_allowed,
    assert_propose_allowed,
    assert_s3_configured,
    assert_size_allowed,
    is_supported_extension,
)
from decisionpen_mcp.s3_client import S3EdgeClient, object_to_item
from decisionpen_mcp.sync.engine import SyncEngine
from decisionpen_mcp.sync.state import SyncState

# --- MCP SDK (v1 FastMCP or v2 MCPServer) ------------------------------------
try:
    from mcp.server.mcpserver import MCPServer as _Server

    _SDK = "v2"
except ImportError:  # pragma: no cover - v1 fallback
    try:
        from mcp.server.fastmcp import FastMCP as _Server

        _SDK = "v1"
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "The MCP Python SDK is required. Install with: pip install 'mcp>=1.2'"
        ) from e


def _load_dotenv_files() -> None:
    """Load edge.env / .env.mcp from cwd / repo root when present."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    for candidate in (
        Path.cwd() / "edge.env",
        Path.cwd() / ".env.mcp",
        repo_root / "edge.env",
        repo_root / ".env.mcp",
        Path(__file__).resolve().parent / "edge.env",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


def _load_runtime():
    _load_dotenv_files()
    cfg = EdgeConfig.from_env()
    return cfg, S3EdgeClient(cfg), AuditLogger(cfg.audit_log_path), DecisionPenApiClient(cfg)


_CFG: Optional[EdgeConfig] = None
_S3: Optional[S3EdgeClient] = None
_AUDIT: Optional[AuditLogger] = None
_API: Optional[DecisionPenApiClient] = None


def _rt():
    global _CFG, _S3, _AUDIT, _API
    if _CFG is None:
        _CFG, _S3, _AUDIT, _API = _load_runtime()
    assert _CFG and _S3 and _AUDIT and _API
    return _CFG, _S3, _AUDIT, _API


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _err(tool: str, exc: Exception, *, item_id: Optional[str] = None) -> str:
    cfg, _, audit, _ = _rt()
    code = getattr(exc, "code", None) or type(exc).__name__
    reason = getattr(exc, "reason", None) or str(exc)
    audit.record(
        tool=tool,
        ok=False,
        mode=cfg.mode.value,
        tenant_id=cfg.tenant_id,
        item_id=item_id,
        detail=f"{code}: {reason}",
    )
    return _json(
        {
            "ok": False,
            "error": {"code": code, "message": reason},
            "mode": cfg.mode.value,
        }
    )


mcp = _Server("decisionpen-edge-s3")


@mcp.tool()
def list_sources(path: str = "", next_token: str = "") -> str:
    """
    List folders and files under the allowlisted S3 prefix.
    path: optional subfolder relative to DP_S3_PREFIX (or absolute key under it).
    next_token: pagination token from a previous list_sources call.
    """
    cfg, s3, audit, _ = _rt()
    try:
        assert_s3_configured(cfg)
        prefix = assert_path_allowed(cfg, path)
        token = next_token.strip() or None
        resp = s3.list_level(
            prefix, max_keys=cfg.max_list_items, continuation_token=token
        )
        containers: List[Dict[str, Any]] = []
        for cp in resp.get("CommonPrefixes") or []:
            p = (cp.get("Prefix") or "").rstrip("/")
            name = p.split("/")[-1] if p else ""
            if name:
                containers.append(
                    {
                        "id": p + "/",
                        "name": name,
                        "path": p + "/",
                        "uri": f"s3://{cfg.bucket}/{p}/",
                    }
                )
        items = [
            object_to_item(obj, cfg.bucket)
            for obj in (resp.get("Contents") or [])
            if (obj.get("Key") or "") and not (obj.get("Key") or "").endswith("/")
        ]
        out = {
            "ok": True,
            "source_system": "s3",
            "bucket": cfg.bucket,
            "allowlist_prefix": cfg.allowlist_prefix,
            "path": path or "",
            "resolved_prefix": prefix,
            "mode": cfg.mode.value,
            "containers": containers,
            "items": items,
            "next_token": resp.get("NextContinuationToken"),
        }
        audit.record(
            tool="list_sources",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"prefix={prefix} items={len(items)} folders={len(containers)}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("list_sources", e)
    except Exception as e:
        return _err("list_sources", e)


@mcp.tool()
def search_docs(query: str, path: str = "", max_results: int = 0) -> str:
    """
    Search object keys/names under the allowlisted prefix (substring match, case-insensitive).
    query: text to match in the object key.
    path: optional subfolder to search within.
    max_results: optional cap (defaults to DP_MCP_MAX_SEARCH_RESULTS).
    """
    cfg, s3, audit, _ = _rt()
    try:
        assert_s3_configured(cfg)
        q = (query or "").strip().lower()
        if not q:
            raise PolicyDenied("query must be non-empty", code="empty_query")
        prefix = assert_path_allowed(cfg, path)
        limit = max_results if max_results and max_results > 0 else cfg.max_search_results
        limit = min(limit, cfg.max_search_results)
        # Over-fetch then filter by name/key
        raw = s3.list_recursive(prefix, max_keys=min(500, max(limit * 10, limit)))
        matches: List[Dict[str, Any]] = []
        for obj in raw:
            item = object_to_item(obj, cfg.bucket)
            blob = f"{item['item_id']} {item['name']}".lower()
            if q in blob:
                item["supported"] = is_supported_extension(item["item_id"])
                matches.append(item)
            if len(matches) >= limit:
                break
        out = {
            "ok": True,
            "source_system": "s3",
            "query": query,
            "mode": cfg.mode.value,
            "count": len(matches),
            "items": matches,
        }
        audit.record(
            tool="search_docs",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"query={query!r} hits={len(matches)}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("search_docs", e)
    except Exception as e:
        return _err("search_docs", e)


@mcp.tool()
async def get_document(item_id: str, include_text: bool = True) -> str:
    """
    Fetch one object from the allowlisted S3 prefix.
    Returns provenance + text when extractable. Does not persist into DecisionPen
    (mode=cite_only|propose|persist_approved — MCP itself never Confirmed-writes).
    item_id: full S3 object key (from list_sources / search_docs).
    include_text: when true, attempt text extraction for cite-only use.
    """
    cfg, s3, audit, _ = _rt()
    try:
        assert_s3_configured(cfg)
        allowed = assert_key_allowed(cfg, item_id)
        head = s3.head(allowed.key)
        size = int(head.get("ContentLength") or 0)
        assert_size_allowed(cfg, size)
        data, meta = s3.get_bytes(allowed.key)
        assert_size_allowed(cfg, len(data))
        digest = sha256_hex(data)
        title = allowed.key.rsplit("/", 1)[-1]

        text = None
        method = "skipped"
        if include_text:
            text, method = await extract_text(title, data)

        binary_b64 = None
        if cfg.include_binary_base64 and text is None:
            binary_b64 = base64.b64encode(data).decode("ascii")

        env = build_document_envelope(
            item_id=allowed.key,
            uri=allowed.uri,
            mode=cfg.mode.value,
            size=len(data),
            digest=digest,
            mime_type=meta.get("content_type"),
            last_modified=meta.get("last_modified"),
            text=text,
            extraction_method=method,
            max_text_chars=cfg.max_text_chars,
            binary_base64=binary_b64,
        )
        env["ok"] = True
        env["supported_for_enrichment"] = is_supported_extension(allowed.key)
        audit.record(
            tool="get_document",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            uri=allowed.uri,
            item_id=allowed.key,
            bytes_count=len(data),
            detail=method,
        )
        return _json(env)
    except PolicyDenied as e:
        return _err("get_document", e, item_id=item_id)
    except Exception as e:
        return _err("get_document", e, item_id=item_id)


@mcp.tool()
def propose_enrichment(
    item_id: str,
    source_label: str = "",
    anchor_application_id: str = "",
) -> str:
    """
    Download the object at the edge and push bytes + provenance to DecisionPen
    (Insights Inbox). Requires DP_MCP_MODE=propose|persist_approved, DP_API_TOKEN
    (Edge API token preferred), DP_API_BASE. No S3 keys are sent to DecisionPen.
    Nothing is Confirmed on the map until a human approves in the Inbox.
    item_id: S3 object key under the allowlisted prefix.
    """
    cfg, s3, audit, api = _rt()
    try:
        assert_propose_allowed(cfg)
        allowed = assert_key_allowed(cfg, item_id)
        if not is_supported_extension(allowed.key):
            raise PolicyDenied(
                f"unsupported file type for enrichment: {allowed.key}",
                code="unsupported_type",
            )
        head = s3.head(allowed.key)
        size = int(head.get("ContentLength") or 0)
        assert_size_allowed(cfg, size)
        data, meta = s3.get_bytes(allowed.key)
        assert_size_allowed(cfg, len(data))
        digest = sha256_hex(data)
        result = api.push_enrichment(
            [
                {
                    "filename": allowed.key.rsplit("/", 1)[-1],
                    "content_type": meta.get("content_type"),
                    "content_bytes": data,
                    "content_sha256": digest,
                    "source_system": "s3",
                    "source_uri": allowed.uri,
                    "remote_id": allowed.key,
                    "etag": meta.get("etag"),
                    "last_modified": meta.get("last_modified"),
                }
            ],
            source_label=source_label.strip() or None,
            anchor_application_id=anchor_application_id.strip() or None,
        )
        row = (result.get("results") or [{}])[0]
        status = row.get("status") or "unknown"
        queued = status == "queued"
        out = {
            "ok": True,
            "mode": cfg.mode.value,
            "uri": allowed.uri,
            "item_id": allowed.key,
            "persisted": False,
            "queued": queued,
            "status": status,
            "job_id": result.get("job_id") or row.get("job_id"),
            "job_ids": result.get("job_ids") or [],
            "job_count": result.get("job_count"),
            "result": row,
            "note": (
                "Push path: edge downloaded, DecisionPen holds no S3 keys. "
                "Poll get_enrichment_job; Review in Insights Inbox. "
                "Map Confirmed only after human approve."
            ),
        }
        audit.record(
            tool="propose_enrichment",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            uri=allowed.uri,
            item_id=allowed.key,
            bytes_count=len(data),
            detail=f"status={status} jobId={out.get('job_id')}",
            extra={"jobId": out.get("job_id"), "status": status},
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("propose_enrichment", e, item_id=item_id)
    except DecisionPenApiError as e:
        return _err("propose_enrichment", e, item_id=item_id)
    except Exception as e:
        return _err("propose_enrichment", e, item_id=item_id)


@mcp.tool()
def run_sync(
    dry_run: bool = False,
    max_keys: int = 0,
    source_label: str = "",
    anchor_application_id: str = "",
) -> str:
    """
    Run edge sync: list allowlisted S3 prefix, push new/modified files to DecisionPen.
    dry_run: report candidates without download/push.
    Requires DP_MCP_MODE=propose|persist_approved and DP_API_TOKEN.
    """
    cfg, _, audit, api = _rt()
    try:
        adapter = S3SourceAdapter(cfg)
        state = SyncState(cfg.sync_state_path)
        engine = SyncEngine(cfg, adapter, api, state, audit=audit)
        result = engine.run(
            dry_run=bool(dry_run),
            max_keys=max_keys or None,
            source_label=source_label.strip() or None,
            anchor_application_id=anchor_application_id.strip() or None,
        )
        return _json(result)
    except PolicyDenied as e:
        return _err("run_sync", e)
    except DecisionPenApiError as e:
        return _err("run_sync", e)
    except Exception as e:
        return _err("run_sync", e)


@mcp.tool()
def get_enrichment_job(job_id: str) -> str:
    """
    Poll DecisionPen enrichment job status. Review-ready when status=completed
    and a preview is present. Same auth caps as propose_enrichment.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_propose_allowed(cfg)
        jid = str(job_id or "").strip()
        if not jid:
            raise PolicyDenied("job_id is required", code="missing_job_id")
        job = api.get_job(jid)
        status = str(job.get("status") or "").lower()
        result = job.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = None
        preview = (result or {}).get("preview") if isinstance(result, dict) else None
        review_ready = status == "completed" and bool(preview)
        out = {
            "ok": True,
            "job_id": jid,
            "status": status,
            "review_ready": review_ready,
            "job_type": job.get("job_type"),
            "error_message": job.get("error_message") or job.get("error"),
            "name": job.get("name"),
            "job": job,
            "note": (
                "Open Insights Inbox Review when review_ready is true. "
                "rerun_enrichment_job works for failed or completed (not in-flight)."
            ),
        }
        audit.record(
            tool="get_enrichment_job",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"jobId={jid} status={status} review_ready={review_ready}",
            extra={"jobId": jid, "status": status},
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("get_enrichment_job", e)
    except DecisionPenApiError as e:
        return _err("get_enrichment_job", e)
    except Exception as e:
        return _err("get_enrichment_job", e)


@mcp.tool()
def rerun_enrichment_job(job_id: str) -> str:
    """
    Re-queue a failed or completed application_enrichment job (same sources).
    Blocked while pending/queued/running. Suggestions are replaced; map items stay.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_propose_allowed(cfg)
        jid = str(job_id or "").strip()
        if not jid:
            raise PolicyDenied("job_id is required", code="missing_job_id")
        result = api.rerun_job(jid)
        out = {
            "ok": True,
            "job_id": jid,
            "queued": True,
            "result": result,
            "note": (
                "Job re-queued. Poll get_enrichment_job; previous Inbox suggestions "
                "will be replaced. Items already approved onto the map are unchanged."
            ),
        }
        audit.record(
            tool="rerun_enrichment_job",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"jobId={jid}",
            extra={"jobId": jid},
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("rerun_enrichment_job", e)
    except DecisionPenApiError as e:
        return _err("rerun_enrichment_job", e)
    except Exception as e:
        return _err("rerun_enrichment_job", e)


@mcp.tool()
def describe_context_model() -> str:
    """
    How to use DecisionPen as a Context Engine: Confirmed map vs evidence notes,
    capability-first landscape workflow, and recommended tool call order.
    Call once at the start of an EA Q&A session.
    """
    cfg, _, audit, _ = _rt()
    try:
        out = {"ok": True, **build_context_model()}
        audit.record(
            tool="describe_context_model",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail="static",
        )
        return _json(out)
    except Exception as e:
        return _err("describe_context_model", e)


@mcp.tool()
def search_entities(
    query: str,
    entity_type: str = "",
    limit: int = 20,
) -> str:
    """
    Search Confirmed map entities by name/description.
    For landscape questions (e.g. what supports clinical trials), search
    capability/process types FIRST, then follow relationships to applications.
    query: search text.
    entity_type: optional type filter (capability, process, application, …).
    limit: max results.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        q = (query or "").strip()
        if not q:
            raise PolicyDenied("query must be non-empty", code="empty_query")
        raw = api.search_entities(
            q,
            limit=limit,
            entity_type=entity_type.strip() or None,
        )
        out = compact_entity_search(raw)
        audit.record(
            tool="search_entities",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"q={q!r} type={entity_type!r} hits={out.get('count')}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("search_entities", e)
    except DecisionPenApiError as e:
        return _err("search_entities", e)
    except Exception as e:
        return _err("search_entities", e)


@mcp.tool()
def get_entity(
    entity_id: str,
    include_relationships: bool = False,
    include_related_entities: bool = False,
) -> str:
    """
    Fetch one Confirmed map entity (description, aliases, custom_attributes).
    Optionally include relationships / related entity stubs.
    entity_id: from search_entities.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        eid = (entity_id or "").strip()
        if not eid:
            raise PolicyDenied("entity_id is required", code="missing_entity_id")
        raw = api.get_entity(
            eid,
            include_relationships=bool(include_relationships),
            include_related_entities=bool(include_related_entities),
        )
        out = compact_entity(raw)
        audit.record(
            tool="get_entity",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"entity_id={eid}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("get_entity", e)
    except DecisionPenApiError as e:
        return _err("get_entity", e)
    except Exception as e:
        return _err("get_entity", e)


@mcp.tool()
def get_entity_relationships(
    entity_id: str,
    limit: int = 100,
) -> str:
    """
    Confirmed map relationships for an entity (incoming/outgoing endpoints).
    Label these as Confirmed — not evidence-only mentions.
    entity_id: from search_entities / get_entity.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        eid = (entity_id or "").strip()
        if not eid:
            raise PolicyDenied("entity_id is required", code="missing_entity_id")
        raw = api.get_entity_relationships(eid, limit=limit)
        out = compact_relationships(raw)
        out["entity_id"] = eid
        audit.record(
            tool="get_entity_relationships",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"entity_id={eid} count={out.get('count')}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("get_entity_relationships", e)
    except DecisionPenApiError as e:
        return _err("get_entity_relationships", e)
    except Exception as e:
        return _err("get_entity_relationships", e)


@mcp.tool()
def get_entity_evidence(entity_id: str) -> str:
    """
    Unstructured evidence pack for one entity: linked fragments + summary_node.
    Use after resolving CTMS/EDC/any app id. Cite fragment_id and source_title.
    Do not promote note-only integrations to Confirmed map edges.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        eid = (entity_id or "").strip()
        if not eid:
            raise PolicyDenied("entity_id is required", code="missing_entity_id")
        raw = api.get_entity_evidence(eid)
        out = compact_entity_evidence(raw)
        audit.record(
            tool="get_entity_evidence",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"entity_id={eid} fragments={out.get('fragment_count')}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("get_entity_evidence", e)
    except DecisionPenApiError as e:
        return _err("get_entity_evidence", e)
    except Exception as e:
        return _err("get_entity_evidence", e)


@mcp.tool()
def search_evidence(
    query: str,
    limit: int = 10,
    entity_id: str = "",
) -> str:
    """
    Semantic search over DecisionPen evidence fragments (no generative answer).
    Prefer passing entity_id to scope to one application/capability.
    Prefer get_entity_evidence for the full linked pack of one entity.
    query: search text.
    limit: max fragments (1–50).
    entity_id: strongly recommended — filter to fragments linked to that entity.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        q = (query or "").strip()
        if not q:
            raise PolicyDenied("query must be non-empty", code="empty_query")
        raw = api.search_evidence_fragments(
            q,
            limit=limit,
            entity_id=entity_id.strip() or None,
        )
        compact = compact_evidence_fragments(raw)
        out = {"ok": True, **compact}
        audit.record(
            tool="search_evidence",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"hits={out.get('count')} entity_id={entity_id!r}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("search_evidence", e)
    except DecisionPenApiError as e:
        return _err("search_evidence", e)
    except Exception as e:
        return _err("search_evidence", e)


@mcp.tool()
def get_relationship_summary(entity_id: str) -> str:
    """
    Cheap Confirmed relationship counts by type and direction (incoming|outgoing).
    Use before deep get_entity_relationships when exploring a busy entity.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        eid = (entity_id or "").strip()
        if not eid:
            raise PolicyDenied("entity_id is required", code="missing_entity_id")
        raw = api.get_relationship_summary(eid)
        out = compact_relationship_summary(raw)
        audit.record(
            tool="get_relationship_summary",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"entity_id={eid}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("get_relationship_summary", e)
    except DecisionPenApiError as e:
        return _err("get_relationship_summary", e)
    except Exception as e:
        return _err("get_relationship_summary", e)


@mcp.tool()
def list_entity_types() -> str:
    """
    List valid map entity types for search_entities entity_type filters
    (capability, application, process, …).
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        raw = api.list_entity_types()
        out = compact_entity_types(raw)
        audit.record(
            tool="list_entity_types",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"count={out.get('count')}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("list_entity_types", e)
    except DecisionPenApiError as e:
        return _err("list_entity_types", e)
    except Exception as e:
        return _err("list_entity_types", e)


@mcp.tool()
def batch_get_entities(entity_ids: str) -> str:
    """
    Hydrate many entity ids (e.g. peers from relationships).
    entity_ids: comma-separated ids (max 50).
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        ids = [p.strip() for p in (entity_ids or "").split(",") if p.strip()]
        if not ids:
            raise PolicyDenied("entity_ids is required", code="missing_entity_ids")
        raw = api.batch_get_entities(ids)
        out = compact_batch_entities(raw)
        audit.record(
            tool="batch_get_entities",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"count={out.get('count')}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("batch_get_entities", e)
    except DecisionPenApiError as e:
        return _err("batch_get_entities", e)
    except Exception as e:
        return _err("batch_get_entities", e)


@mcp.tool()
def ask_decisionpen(
    query: str,
    thread_id: str = "",
    skill_id: str = "",
) -> str:
    """
    LAST RESORT narrative Ask over DecisionPen (server-side agent + LLM).
    Prefer structured Context tools first: search_entities → relationships →
    get_entity_evidence / search_evidence. Use this only when those are insufficient.
    query: natural-language question.
    thread_id: optional prior thread_id to continue a conversation.
    skill_id: optional skill from list_ask_skills.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        q = (query or "").strip()
        if not q:
            raise PolicyDenied("query must be non-empty", code="empty_query")
        raw = api.ask_query(
            q,
            thread_id=thread_id.strip() or None,
            skill_id=skill_id.strip() or None,
        )
        compact = compact_ask_response(raw)
        out = {
            "ok": True,
            **compact,
            "note": (
                "Last-resort Ask answer. Prefer structured Context tools next time. "
                "Cite linked_entities and citations. Pass thread_id for follow-ups."
            ),
        }
        audit.record(
            tool="ask_decisionpen",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"thread={out.get('thread_id')} citations={len(out.get('citations') or [])}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("ask_decisionpen", e)
    except DecisionPenApiError as e:
        return _err("ask_decisionpen", e)
    except Exception as e:
        return _err("ask_decisionpen", e)


@mcp.tool()
def list_ask_skills() -> str:
    """
    List user-invocable DecisionPen Ask skills (for ask_decisionpen skill_id only).
    Prefer Context tools over Ask for catalog Q&A.
    """
    cfg, _, audit, api = _rt()
    try:
        assert_ask_allowed(cfg)
        raw = api.list_ask_skills()
        skills = raw.get("skills") or []
        out = {
            "ok": True,
            "count": raw.get("count", len(skills)),
            "skills": skills,
        }
        audit.record(
            tool="list_ask_skills",
            ok=True,
            mode=cfg.mode.value,
            tenant_id=cfg.tenant_id,
            detail=f"count={out['count']}",
        )
        return _json(out)
    except PolicyDenied as e:
        return _err("list_ask_skills", e)
    except DecisionPenApiError as e:
        return _err("list_ask_skills", e)
    except Exception as e:
        return _err("list_ask_skills", e)


def main() -> None:
    # Fail fast on bad config so Cursor/Inspector show a clear error.
    try:
        _rt()
    except Exception as e:
        print(f"decisionpen_mcp config error: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    # stdio is the local Edge transport (Cursor, Inspector).
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
