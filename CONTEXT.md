# Context Engine tools — research and design recipes

Claude or Cursor owns **intent**. DecisionPen exposes the Architecture Context Plane through structured MCP tools. Full overview: [README.md](./README.md). Setup: [CONNECT.md](./CONNECT.md).

Call `describe_context_model` once per session for the live contract.

## Layers of the plane

| Layer | Meaning | Typical tools |
|------|---------|----------------|
| **Enterprise Knowledge Graph** | Governed entities and relationships (Confirmed) | `search_entities`, `get_entity`, `get_entity_relationships` |
| **Evidence** | Unstructured notes on an entity (HLDs, URS, assessments) | `get_entity_evidence`, `search_evidence` |
| **Derived decisions** | Living ADR / architecture-decision cards | `list_derived_decisions` |
| **Estate changes** | Open or recent deltas (invalidate + relation propose) | `list_entity_changes` |
| **Shared surfaces** | Patterns, principles, security standards | `list_context_surfaces`, `get_surface_evidence` |
| **Inbox** | Human review before Confirmed map updates | Filled by `submit_document` / `propose_enrichment` |

**Default truth for agents:** Confirmed edges + current evidence + open/recent `list_entity_changes`. Use historical evidence when explaining why something changed.

Evidence can be marked historical automatically when new claims supersede old tech/hosting notes. **Confirmed relationships never auto-update** — stewards accept relation proposes.

## Prefer these tools (read)

| Tool | Use in plain English |
|------|----------------------|
| `describe_context_model` | Orient once: map vs surfaces vs notes |
| `search_entities` | Name → id; for landscape questions search **capability/process first** |
| `get_entity` | Description, aliases, attributes |
| `get_entity_relationships` | Confirmed edges |
| `get_relationship_summary` | Cheap typed/direction counts |
| `get_entity_evidence` | Unstructured pack for that entity |
| `list_entity_changes` | Pending/applied estate deltas |
| `list_derived_decisions` | Living decision cards |
| `list_context_surfaces` / `get_surface_evidence` | Shared knowledge |
| `search_evidence` | Semantic search; pass `entity_id` when you can |
| `list_entity_types` / `batch_get_entities` | Filters and hydrating peers |

**Last resort:** `ask_decisionpen` (server-side LLM). Prefer structured tools so the agent plans the research.

## Write path (publish; humans approve)

| Tool | Use |
|------|-----|
| `submit_document` | Push UTF-8 text onto an **entity** or **knowledge_surface** (no S3 required) |
| `propose_enrichment` | S3 object → same Inbox path |

Requires `DP_MCP_MODE=propose` (or `persist_approved`). **MCP never Confirmed-writes the map.**

### `submit_document` sketch

```
submit_document(
  anchor_kind="entity",          # or knowledge_surface
  anchor_id="<uuid>",
  content="...",                 # markdown / plain text
  title="URS — Payment Service",
  doc_class="urs",               # optional
  extract_mode="auto",
  remote_id="docs/urs/payment.md",
  source_uri="file:///…/payment.md"
)
```

For ADR/tech docs with migrate/replace language (e.g. Neon → Cloud SQL): evidence indexes, conflicting claims can move to historical, relation replaces wait for steward accept, and agents see pending deltas via `list_entity_changes`.

## Capability-first research example

“What applications support clinical trials?”

1. `search_entities(q="clinical trial", entity_type="capability")` (also try `process`)  
2. `get_entity_relationships` on the capability → application ids  
3. `batch_get_entities` / `get_entity` on those apps  
4. `get_entity_evidence` + `list_entity_changes`  
5. Label **Confirmed on map** vs **evidence only** vs **pending change**

## Solution-design context pack

1. Resolve target Application / Solution Component  
2. `get_entity` + relationships + evidence + `list_entity_changes`  
3. `list_derived_decisions`  
4. Load patterns / principles / security surfaces  
5. Design in Cursor or Claude  
6. `submit_document` ADR or SA notes back (`doc_class=architecture_decision` or `technical_architecture`)  
7. Steward approves Inbox / relation proposals  

## Provenance

When quoting notes, cite `fragment_id` and `source_title`. Do not invent Confirmed relationships from prose alone. Treat `relation_propose` rows as **pending**.

## Config

`DP_API_BASE` + `DP_API_TOKEN` (Edge token or session JWT). See [CONNECT.md](./CONNECT.md). S3 env is optional if you only use Context / `submit_document` tools.
