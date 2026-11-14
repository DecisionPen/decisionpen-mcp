# Context Engine — research your enterprise architecture via MCP

This guide is for **research**: asking Claude Desktop, Cursor, or any MCP client questions against DecisionPen’s curated landscape.

For product background, see [decisionpen.com](https://decisionpen.com/). For feeding documents into DecisionPen, see [edge-sync.md](./edge-sync.md). Marketing story: [Context Engine (MCP)](https://decisionpen.com/docs/context-engine-mcp).

## What DecisionPen is (short)

DecisionPen is the **Context of Record for IT architecture** — an Architecture Decision Workspace. It keeps two layers together:

1. **Confirmed map** — structured EA entities and relationships (applications, capabilities, technology, integrations, initiatives), metamodel-aware and LeanIX-aligned when you need that standard.  
2. **Evidence** — documents, transcripts, and notes that justify the map, with citations.

AI can propose; humans curate. Enterprise Ask then answers from the **accepted** model — map-grounded and evidence-aware — not from raw document similarity alone. See [Enterprise Ask](https://decisionpen.com/docs/enterprise-ask).

## Three jobs the MCP door supports

1. **Rapid discovery** — connect an allowlisted S3 corpus; propose LeanIX-aligned structure; enrich CMDB-seeded entities; keep document evidence queryable ([edge-sync.md](./edge-sync.md)).  
2. **Claude** — deep research over the Context of Record before important decisions ([claude-desktop.md](./claude-desktop.md)).  
3. **Cursor** — pull approved patterns and standards during delivery; publish ADRs back for curation ([cursor.md](./cursor.md)).

Hosted remote endpoint: `https://mcp.decisionpen.com/mcp` with `Authorization: Bearer dp_edge_…`.

## What MCP does here

MCP exposes DecisionPen as tools so the **client model** (Claude, Cursor’s agent, etc.) owns intent and synthesis, while DecisionPen remains the system of record.

Typical research loop:

1. Resolve names → entity ids (`search_entities`)  
2. Read Confirmed relationships (`get_entity_relationships`, …)  
3. Optionally load evidence (`get_entity_evidence`, `search_evidence`)  
4. Answer in plain language; label **Confirmed on the map** vs **from notes only**  
5. Cite `fragment_id` / `source_title` when quoting notes  

Prefer structured tools. Use `ask_decisionpen` only as a last resort (server-side Ask).

## Prefer these tools

| Tool | Use |
|------|-----|
| `describe_context_model` | Once per session — map vs notes, capability-first workflow |
| `search_entities` | Name → id; for landscape questions search **capability/process first** |
| `get_entity` | Description, aliases, custom attributes |
| `get_entity_relationships` | Confirmed edges on the map |
| `get_relationship_summary` | Cheap typed / direction counts |
| `get_entity_evidence` | Unstructured pack for one entity |
| `search_evidence` | Semantic search; pass `entity_id` when possible |
| `list_entity_types` / `batch_get_entities` | Filters and hydrating peers |
| `ask_decisionpen` | Last-resort server Ask |

## Capability-first example

Prompt: *“What applications support clinical trials?”*

1. `describe_context_model` (optional if already known)  
2. `search_entities(q="clinical trial", entity_type="capability")` (also try `process`)  
3. `get_entity_relationships` on the capability → application ids  
4. `batch_get_entities` / `get_entity` on those apps  
5. `get_entity_evidence` for rich notes; cite `fragment_id` / `source_title`  
6. Label **Confirmed on the map** vs **from evidence notes only**

Other good prompts (from DecisionPen’s Ask practice):

- What depends on &lt;application&gt; — blast radius if it changes?  
- Who owns this capability / integration?  
- Why was this platform chosen — which documents support that?  
- Which apps have a name but no purpose or evidence yet?  

## Provenance rules

- Quoting notes → always cite `fragment_id` and `source_title` (and `source_id` when present).  
- **Do not invent Confirmed relationships from prose alone.**  
- Prefer “not on the map yet” over a confident fabrication.

## Config (research-only)

```bash
DP_API_BASE=https://YOUR_DECISIONPEN_HOST
DP_API_TOKEN=dp_edge_…
DP_MCP_MODE=cite_only
# S3 env vars are optional for Context Engine-only use
```

Install clients: [claude-desktop.md](./claude-desktop.md) · [cursor.md](./cursor.md)
