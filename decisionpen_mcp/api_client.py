"""HTTP client for DecisionPen APIs used by Edge MCP (push + job poll)."""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

import requests

from decisionpen_mcp.config import EdgeConfig


class DecisionPenApiError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DecisionPenApiClient:
    def __init__(self, cfg: EdgeConfig):
        self._cfg = cfg

    def _headers(self, *, json_body: bool = True) -> Dict[str, str]:
        if not self._cfg.api_token:
            raise DecisionPenApiError(
                "DP_API_TOKEN is required "
                "(Edge API token from Admin → Security & audit → Edge API tokens, "
                "or a session JWT for interactive tests)."
            )
        headers = {
            "Authorization": f"Bearer {self._cfg.api_token}",
            "Accept": "application/json",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _url(self, path: str) -> str:
        if not self._cfg.api_base:
            raise DecisionPenApiError("DP_API_BASE is required")
        return f"{self._cfg.api_base.rstrip('/')}{path}"

    def _raise_for_status(self, resp: requests.Response, label: str) -> None:
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail") or detail
            except Exception:
                pass
            raise DecisionPenApiError(
                f"{label} failed ({resp.status_code}): {detail}",
                status_code=resp.status_code,
            )

    def content_status(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Preflight: which content digests still need processing."""
        url = self._url("/api/edge/content-status")
        body = {
            "items": [
                {
                    "remote_id": i.get("remote_id"),
                    "etag": i.get("etag"),
                    "content_sha256": i.get("content_sha256"),
                }
                for i in items
            ]
        }
        try:
            resp = requests.post(
                url, headers=self._headers(), json=body, timeout=60
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "content-status")
        return resp.json()

    def push_enrichment(
        self,
        items: List[Dict[str, Any]],
        *,
        source_label: Optional[str] = None,
        anchor_application_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Push file bytes + provenance to DecisionPen.
        Each item may include content_bytes (bytes) or content_base64 (str).
        """
        url = self._url("/api/edge/push-enrichment")
        payload_items: List[Dict[str, Any]] = []
        for item in items:
            raw: Optional[bytes] = item.get("content_bytes")
            b64 = item.get("content_base64")
            if raw is None and b64:
                raw = base64.b64decode(b64)
            if raw is None:
                raise DecisionPenApiError("push item missing content_bytes/content_base64")
            payload_items.append(
                {
                    "filename": item.get("filename") or "document",
                    "content_type": item.get("content_type"),
                    "content_base64": base64.b64encode(raw).decode("ascii"),
                    "source_system": item.get("source_system") or "s3",
                    "source_uri": item.get("source_uri"),
                    "remote_id": item.get("remote_id"),
                    "etag": item.get("etag"),
                    "content_sha256": item.get("content_sha256"),
                    "last_modified": item.get("last_modified"),
                    "source_label": item.get("source_label"),
                    "anchor_application_id": item.get("anchor_application_id"),
                }
            )
        body: Dict[str, Any] = {"items": payload_items}
        if source_label:
            body["source_label"] = source_label
        if anchor_application_id:
            body["anchor_application_id"] = anchor_application_id

        try:
            resp = requests.post(
                url, headers=self._headers(), json=body, timeout=300
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "push-enrichment")
        data = resp.json()
        # Normalize job ids for agents.
        results = data.get("results") or []
        job_ids = [
            str(r.get("job_id")).strip()
            for r in results
            if r.get("status") == "queued" and r.get("job_id")
        ]
        data["jobIds"] = job_ids
        data["job_ids"] = job_ids
        data["jobId"] = job_ids[0] if job_ids else None
        data["job_id"] = data["jobId"]
        data["job_count"] = len(job_ids)
        return data

    def process_enrichment(
        self,
        *,
        item_ids: List[str],
        source_label: Optional[str] = None,
        anchor_application_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Legacy pull path via connector (kept for DP_CONNECTOR_ID environments).
        Prefer push_enrichment for edge sync.
        """
        if not self._cfg.connector_id:
            raise DecisionPenApiError(
                "DP_CONNECTOR_ID is required for legacy process-enrichment; "
                "use push_enrichment (no connector) instead."
            )
        url = self._url(
            f"/api/connectors/{self._cfg.connector_id}/process-enrichment"
        )
        body: Dict[str, Any] = {
            "itemIds": item_ids,
            "containerPaths": [],
            "sourceLabel": source_label
            or "Add knowledge — Edge MCP S3 import",
        }
        if anchor_application_id:
            body["anchorApplicationId"] = anchor_application_id

        try:
            resp = requests.post(
                url, headers=self._headers(), json=body, timeout=120
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "process-enrichment")
        data = resp.json()
        job_ids = data.get("jobIds") or data.get("job_ids") or []
        if not job_ids and data.get("jobId"):
            job_ids = [data["jobId"]]
        if not isinstance(job_ids, list):
            job_ids = [job_ids]
        job_ids = [str(j).strip() for j in job_ids if str(j).strip()]
        first = job_ids[0] if job_ids else (data.get("jobId") or data.get("job_id"))
        data["jobId"] = first
        data["job_id"] = first
        data["jobIds"] = job_ids
        data["job_ids"] = job_ids
        data["job_count"] = len(job_ids)
        return data

    def get_job(self, job_id: str) -> Dict[str, Any]:
        url = self._url(f"/api/jobs/{job_id}")
        try:
            resp = requests.get(url, headers=self._headers(), timeout=60)
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "get job")
        return resp.json()

    def rerun_job(self, job_id: str) -> Dict[str, Any]:
        url = self._url(f"/api/jobs/{job_id}/rerun")
        try:
            resp = requests.post(
                url, headers=self._headers(), json={}, timeout=60
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "rerun job")
        return resp.json()

    def ask_query(
        self,
        query: str,
        *,
        thread_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /api/rag/v2/query — DecisionPen Ask over curated map + evidence."""
        url = self._url("/api/rag/v2/query")
        body: Dict[str, Any] = {
            "query": query,
            "run_kind": "interactive",
        }
        if thread_id:
            body["thread_id"] = thread_id
        if skill_id:
            body["skill_id"] = skill_id
        if conversation_context:
            body["conversation_context"] = conversation_context
        try:
            # Local Ask agent loops can exceed 3 minutes (LLM + tools).
            resp = requests.post(
                url, headers=self._headers(), json=body, timeout=600
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "ask query")
        return resp.json()

    def search_evidence_fragments(
        self,
        query: str,
        *,
        limit: int = 10,
        entity_id: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> Dict[str, Any]:
        """GET /api/evidence/fragments/search — semantic evidence retrieval (no LLM answer)."""
        url = self._url("/api/evidence/fragments/search")
        params: Dict[str, Any] = {
            "q": query,
            "limit": max(1, min(int(limit or 10), 50)),
            "min_similarity": min_similarity,
        }
        if entity_id:
            params["entity_id"] = entity_id
        try:
            resp = requests.get(
                url, headers=self._headers(json_body=False), params=params, timeout=60
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "evidence search")
        return resp.json()

    def list_ask_skills(self) -> Dict[str, Any]:
        """GET /api/agent/skills — user-invocable Ask skills."""
        url = self._url("/api/agent/skills")
        try:
            resp = requests.get(
                url, headers=self._headers(json_body=False), timeout=30
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, "list skills")
        return resp.json()

    def _get(self, path: str, *, params: Optional[Dict[str, Any]] = None, label: str = "GET") -> Dict[str, Any]:
        url = self._url(path)
        try:
            resp = requests.get(
                url,
                headers=self._headers(json_body=False),
                params=params or None,
                timeout=60,
            )
        except requests.RequestException as e:
            raise DecisionPenApiError(f"DecisionPen API request failed: {e}") from e
        self._raise_for_status(resp, label)
        return resp.json()

    def search_entities(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/entities/search"""
        params: Dict[str, Any] = {
            "q": query,
            "limit": max(1, min(int(limit or 20), 100)),
            "offset": max(0, int(offset or 0)),
        }
        if entity_type:
            params["entity_type"] = entity_type
        return self._get("/api/entities/search", params=params, label="entity search")

    def get_entity(
        self,
        entity_id: str,
        *,
        include_relationships: bool = False,
        include_related_entities: bool = False,
    ) -> Dict[str, Any]:
        """GET /api/entities/{id}"""
        params: Dict[str, Any] = {}
        if include_relationships:
            params["include_relationships"] = "true"
        if include_related_entities:
            params["include_related_entities"] = "true"
        return self._get(
            f"/api/entities/{entity_id}",
            params=params or None,
            label="get entity",
        )

    def get_entity_relationships(
        self,
        entity_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """GET /api/relationships/by-entity/{id}"""
        return self._get(
            f"/api/relationships/by-entity/{entity_id}",
            params={
                "limit": max(1, min(int(limit or 100), 200)),
                "offset": max(0, int(offset or 0)),
            },
            label="entity relationships",
        )

    def get_entity_evidence(self, entity_id: str) -> Dict[str, Any]:
        """GET /api/entities/{id}/evidence — linked fragments + summary_node."""
        return self._get(
            f"/api/entities/{entity_id}/evidence",
            label="entity evidence",
        )

    def get_relationship_summary(self, entity_id: str) -> Dict[str, Any]:
        """GET /api/entities/{id}/relationship-summary"""
        return self._get(
            f"/api/entities/{entity_id}/relationship-summary",
            label="relationship summary",
        )

    def list_entity_types(self) -> Any:
        """GET /api/entity-types"""
        return self._get("/api/entity-types", label="entity types")

    def batch_get_entities(self, entity_ids: List[str]) -> Dict[str, Any]:
        """GET /api/entities/batch?ids=…"""
        ids = [str(i).strip() for i in (entity_ids or []) if str(i).strip()]
        if not ids:
            return {"success": True, "entities": []}
        return self._get(
            "/api/entities/batch",
            params={"ids": ",".join(ids[:50])},
            label="batch entities",
        )


def compact_ask_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Shrink Ask payload for MCP clients (answer + citations, drop bulky debug)."""
    citations_in = data.get("citations") or []
    citations = []
    for c in citations_in[:20]:
        if not isinstance(c, dict):
            continue
        citations.append(
            {
                k: (str(c.get(k))[:400] if k == "excerpt" else c.get(k))
                for k in (
                    "key",
                    "kind",
                    "title",
                    "label",
                    "chip_label",
                    "excerpt",
                    "fragment_id",
                    "source_title",
                    "entity_id",
                    "url",
                )
                if c.get(k) not in (None, "", [], {})
            }
        )
    linked = []
    for row in data.get("linked_entities") or []:
        if not isinstance(row, dict):
            continue
        linked.append(
            {
                k: row.get(k)
                for k in ("id", "name", "entity_type", "type")
                if row.get(k) not in (None, "")
            }
        )
        if len(linked) >= 30:
            break
    follow_ups = []
    for a in data.get("suggested_actions") or data.get("suggested_follow_ups") or []:
        if isinstance(a, dict):
            follow_ups.append(
                {
                    k: a.get(k)
                    for k in ("id", "label", "message", "entity_id", "entity_name")
                    if a.get(k) not in (None, "")
                }
            )
        elif isinstance(a, str) and a.strip():
            follow_ups.append({"label": a.strip()})
        if len(follow_ups) >= 8:
            break
    return {
        "answer": data.get("response") or data.get("answer") or "",
        "success": bool(data.get("success", True)),
        "thread_id": data.get("thread_id"),
        "skill_id": data.get("skill_id"),
        "clarification_needed": data.get("clarification_needed"),
        "clarification_context": data.get("clarification_context"),
        "citations": citations,
        "linked_entities": linked,
        "suggested_follow_ups": follow_ups,
        "visible_steps": list(data.get("visible_steps") or [])[:12],
    }


def _pick_provenance(f: Dict[str, Any]) -> Dict[str, Any]:
    """Keep source attribution fields; never strip when present."""
    out: Dict[str, Any] = {}
    for k in (
        "fragment_id",
        "source_title",
        "source_id",
        "source_version_id",
        "link_type",
        "similarity",
        "score",
        "entity_id",
        "section_path",
        "confidence",
    ):
        v = f.get(k)
        if k == "fragment_id" and not v:
            v = f.get("id")
        if k == "source_title" and not v:
            v = f.get("title")
        if k == "similarity" and v is None:
            v = f.get("score")
        if v not in (None, "", [], {}):
            out[k if k != "score" else "similarity"] = v
    return out


def compact_evidence_fragments(data: Dict[str, Any]) -> Dict[str, Any]:
    frags = []
    for f in data.get("fragments") or []:
        if not isinstance(f, dict):
            continue
        text = (
            f.get("text")
            or f.get("fragment_text")
            or f.get("content")
            or f.get("excerpt")
            or ""
        )
        row = _pick_provenance(f)
        row["text"] = str(text)[:1200]
        frags.append(row)
        if len(frags) >= 30:
            break
    return {
        "query": data.get("query"),
        "count": data.get("count", len(frags)),
        "scoped_entity_ids": data.get("scoped_entity_ids"),
        "scope_mode": data.get("scope_mode"),
        "fragments": frags,
    }


def compact_entity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical entity for MCP — keep attrs/aliases/description."""
    if not isinstance(data, dict):
        return {}
    # Some routes wrap under entity / data
    ent = data.get("entity") if isinstance(data.get("entity"), dict) else data
    out: Dict[str, Any] = {}
    for k in (
        "id",
        "name",
        "type",
        "entity_type",
        "subtype",
        "description",
        "alias_names",
        "custom_attributes",
        "status",
        "lifecycle_status",
    ):
        if ent.get(k) not in (None, "", [], {}):
            out[k] = ent.get(k)
    if data.get("relationships") is not None:
        rels = data.get("relationships") or []
        out["relationships"] = [
            {
                k: r.get(k)
                for k in (
                    "id",
                    "source_entity_id",
                    "target_entity_id",
                    "type",
                    "description",
                )
                if isinstance(r, dict) and r.get(k) not in (None, "")
            }
            for r in rels[:100]
            if isinstance(r, dict)
        ]
    if data.get("related_entities") is not None:
        out["related_entities"] = data.get("related_entities")
    out["ok"] = True
    return out


def compact_entity_search(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = data.get("data") or data.get("entities") or []
    items = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        items.append(
            {
                k: r.get(k)
                for k in ("id", "name", "type", "entity_type", "description", "subtype")
                if r.get(k) not in (None, "")
            }
        )
        if len(items) >= 50:
            break
    return {
        "ok": True,
        "count": len(items),
        "pagination": data.get("pagination"),
        "entities": items,
        "note": (
            "For landscape questions, prefer capability/process types first, "
            "then follow relationships to applications."
        ),
    }


def compact_relationships(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = data.get("data") or data.get("relationships") or []
    items = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        items.append(
            {
                k: r.get(k)
                for k in (
                    "id",
                    "source_entity_id",
                    "target_entity_id",
                    "type",
                    "description",
                    "created_at",
                )
                if r.get(k) not in (None, "")
            }
        )
        if len(items) >= 200:
            break
    return {
        "ok": True,
        "count": len(items),
        "pagination": data.get("pagination"),
        "relationships": items,
        "note": (
            "These are Confirmed map edges (incoming/outgoing by endpoint ids). "
            "Label separately from evidence-only mentions."
        ),
    }


def compact_entity_evidence(data: Dict[str, Any]) -> Dict[str, Any]:
    frags_in = data.get("fragments") or []
    frags = []
    for f in frags_in:
        if not isinstance(f, dict):
            continue
        text = f.get("fragment_text") or f.get("text") or ""
        row = _pick_provenance(f)
        # Entity evidence route may lack source_title — keep link_metadata hints.
        lm = f.get("link_metadata") if isinstance(f.get("link_metadata"), dict) else {}
        if "source_title" not in row and lm.get("source_title"):
            row["source_title"] = lm.get("source_title")
        if "source_id" not in row and lm.get("source_id"):
            row["source_id"] = lm.get("source_id")
        row["text"] = str(text)[:1200]
        frags.append(row)
        if len(frags) >= 40:
            break
    summary = data.get("summary_node")
    summary_out = None
    if isinstance(summary, dict):
        summary_out = {
            k: summary.get(k)
            for k in (
                "id",
                "summary_kind",
                "title",
                "text",
                "content",
                "created_at",
                "updated_at",
            )
            if summary.get(k) not in (None, "")
        }
        body = summary_out.get("text") or summary_out.get("content")
        if isinstance(body, str) and len(body) > 4000:
            summary_out["text"] = body[:4000]
            summary_out.pop("content", None)
    return {
        "ok": True,
        "entity_id": data.get("entity_id"),
        "fragment_count": data.get("fragment_count", len(frags)),
        "fragments": frags,
        "summary_node": summary_out,
        "note": (
            "Unstructured pack for this entity. Cite fragment_id/source_title. "
            "Do not treat note-only integrations as Confirmed map edges."
        ),
    }


def compact_relationship_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "entity_id": data.get("entity_id"),
        "total_relationships": data.get("total_relationships"),
        "summary": data.get("summary") or [],
        "note": "Cheap typed/direction counts (incoming|outgoing). Confirmed map only.",
    }


def compact_entity_types(data: Any) -> Dict[str, Any]:
    rows = data if isinstance(data, list) else (data.get("types") or data.get("data") or [])
    types = []
    for r in rows:
        if isinstance(r, dict):
            types.append(
                {
                    k: r.get(k)
                    for k in ("value", "label", "description", "id", "name")
                    if r.get(k) not in (None, "")
                }
            )
        elif isinstance(r, str):
            types.append({"value": r})
        if len(types) >= 100:
            break
    return {"ok": True, "count": len(types), "entity_types": types}


def compact_batch_entities(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = data.get("entities") or []
    items = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        items.append(
            {
                k: r.get(k)
                for k in (
                    "id",
                    "name",
                    "type",
                    "entity_type",
                    "description",
                    "subtype",
                    "status",
                )
                if r.get(k) not in (None, "")
            }
        )
    return {"ok": True, "count": len(items), "entities": items}
