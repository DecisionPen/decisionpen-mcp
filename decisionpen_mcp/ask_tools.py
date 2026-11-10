"""Helpers for Ask MCP tools (compact DecisionPen Ask / evidence responses)."""

from __future__ import annotations

# Re-export compactors for callers that prefer a dedicated module.
from decisionpen_mcp.api_client import compact_ask_response, compact_evidence_fragments

__all__ = ["compact_ask_response", "compact_evidence_fragments"]
