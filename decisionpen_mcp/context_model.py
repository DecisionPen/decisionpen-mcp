"""Static Context Engine model for Claude (describe_context_model)."""

from __future__ import annotations

from typing import Any, Dict


# Common DecisionPen entity types Claude should try first for landscape questions.
CAPABILITY_LIKE_TYPES = (
    "capability",
    "business_capability",
    "process",
    "business_process",
    "value_stream",
)
APPLICATION_LIKE_TYPES = (
    "application",
    "system",
    "technology",
)


def build_context_model() -> Dict[str, Any]:
    """Payload for describe_context_model — how to use DecisionPen as context."""
    return {
        "product": "DecisionPen",
        "role": "Enterprise Context Engine",
        "mcp_role": (
            "Read-only tools over Confirmed map entities/relationships and the "
            "evidence index. You (Claude) own intent and synthesis."
        ),
        "layers": {
            "confirmed_map": (
                "Approved entities and relationships. Treat as governed truth. "
                "Use search_entities, get_entity, get_entity_relationships, "
                "get_relationship_summary."
            ),
            "evidence_notes": (
                "Unstructured document fragments linked to entities or searchable "
                "across the tenant. Use get_entity_evidence and search_evidence. "
                "These are notes — not automatically Confirmed map edges."
            ),
            "inbox": (
                "Human review queue for enrichment proposals. MCP does not write "
                "to Inbox or Confirmed in this tool set."
            ),
        },
        "capability_first": {
            "rule": (
                "For landscape questions like 'what applications support X?', "
                "first search_entities for capabilities/processes named like X "
                "(pass entity_type when known), then follow relationships to "
                "applications. Do not assume the answer is an application name."
            ),
            "example": (
                "'applications supporting clinical trials' → "
                "search_entities(q='clinical trial', entity_type=capability or process) → "
                "get_entity_relationships → applications → optional get_entity_evidence"
            ),
            "capability_like_types": list(CAPABILITY_LIKE_TYPES),
            "application_like_types": list(APPLICATION_LIKE_TYPES),
        },
        "recommended_call_order": [
            "describe_context_model (once)",
            "search_entities (capability/process first for landscape Qs)",
            "get_entity + get_entity_relationships (Confirmed topology)",
            "get_entity_evidence (unstructured pack for that entity)",
            "search_evidence(q, entity_id=…) for focused notes",
            "ask_decisionpen only as last resort / narrative",
        ],
        "citation_rules": [
            "Label Confirmed on map vs from evidence notes only.",
            "When quoting notes, cite fragment_id and source_title.",
            "Do not invent relationships that are only mentioned in notes.",
        ],
        "ask_decisionpen": (
            "Last resort. Prefer structured tools above — they avoid DecisionPen "
            "intent routing and are usually faster/more accurate for catalog Q&A."
        ),
    }
