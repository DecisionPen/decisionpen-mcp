# DecisionPen Context Engine (MCP)

**Works with [Claude Desktop](https://claude.ai/download), [Cursor](https://cursor.com), and any [Model Context Protocol (MCP)](https://modelcontextprotocol.io) client.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![DecisionPen](https://img.shields.io/badge/Product-decisionpen.com-0B3D5C.svg)](https://decisionpen.com/)

**DecisionPen** is the Architecture Context Plane — institutional memory of how the enterprise is built and why. Agents help keep it current. Humans review what becomes trusted.

This repository ships the **Context Engine**: an MCP server that connects Claude, Cursor, and other agents to that plane. Agents can read the Enterprise Knowledge Graph, evidence, and decisions; read allowlisted document stores; and publish requirements, ADRs, and notes back. **MCP never Confirmed-writes the architecture map.** Humans approve what joins the graph.

| Guide | What it covers |
|-------|----------------|
| **This page** | What DecisionPen is, what MCP does, and the tools in plain English |
| [CONNECT.md](./CONNECT.md) | Connect Claude or Cursor (including Edge API tokens) |
| [CONTEXT.md](./CONTEXT.md) | Tool recipes for research and solution design |
| [SYNC.md](./SYNC.md) | S3 allowlist sync runbook |
| Product docs | [decisionpen.com/docs/context-engine-mcp](https://decisionpen.com/docs/context-engine-mcp) |

Marketing setup guides (SEO / step-by-step):

- [Connect DecisionPen to Cursor or Claude](https://decisionpen.com/docs/connect-mcp-cursor-claude)
- [Connect an S3 document repository via MCP](https://decisionpen.com/docs/mcp-s3-document-store)

---

## Why MCP matters here

Enterprise discovery, institutional memory, agentic SDLC, agentic solution architecture, and living enterprise architecture all need the **same** harnessed context. Without it, agents invent topology or burn tokens re-reading the same HLDs.

MCP is the two-way door:

1. **Read** — graph, evidence, decisions, open estate changes  
2. **Read documents** — allowlisted object store (optional S3)  
3. **Publish** — `submit_document` / `propose_enrichment` → Inbox → human approve  

Same plane as built-in Enterprise Ask. Two doors; one Context of Record.

---

## Tools in plain English

### Orient

| Tool | What it does |
|------|----------------|
| `describe_context_model` | Once per session: how the plane is layered (map, evidence, surfaces, Inbox). |

### Read the Enterprise Knowledge Graph

| Tool | What it does |
|------|----------------|
| `search_entities` | Find applications, capabilities, etc. by name. |
| `get_entity` | Description, aliases, attributes for one entity. |
| `get_entity_relationships` | Confirmed links on the map. |
| `get_relationship_summary` | Quick counts by type/direction. |
| `list_entity_types` / `batch_get_entities` | Filters and hydrate many entities. |

### Read institutional memory

| Tool | What it does |
|------|----------------|
| `get_entity_evidence` | Documents and notes bound to an entity (current by default). |
| `search_evidence` | Semantic search; pass `entity_id` or a knowledge surface when you can. |
| `list_derived_decisions` | Living architecture-decision / ADR cards on an entity. |
| `list_entity_changes` | Open or recent estate changes (e.g. pending tech replace). |
| `list_context_surfaces` / `get_surface_evidence` | Shared patterns, principles, security standards. |

### Read document repositories (optional S3)

| Tool | What it does |
|------|----------------|
| `list_sources` | Browse folders/files under the allowlisted prefix. |
| `search_docs` | Search object keys. |
| `get_document` | Fetch one object to cite (**does not** save into DecisionPen). |
| `propose_enrichment` | Push an S3 object into DecisionPen for Inbox review. |
| `run_sync` | Sync new/changed objects (also available as CLI). |
| `get_enrichment_job` / `rerun_enrichment_job` | Poll or retry enrichment jobs. |

### Publish (agents write; humans approve)

| Tool | What it does |
|------|----------------|
| `submit_document` | Push UTF-8 text onto an entity or knowledge surface (no S3 required). |
| `propose_enrichment` | Same Inbox path from an S3 object. |

Requires `DP_MCP_MODE=propose` (or `persist_approved`). Nothing becomes Confirmed on the map until a steward accepts it in Inbox.

### Ask (last resort)

| Tool | What it does |
|------|----------------|
| `ask_decisionpen` | Server-side Ask with citations. Prefer structured tools above so the agent owns the research plan. |
| `list_ask_skills` | Optional skill ids for Ask. |

---

## Modes

| `DP_MCP_MODE` | Behaviour |
|---------------|-----------|
| `cite_only` (default) | Read / cite. No push into DecisionPen. |
| `propose` | Agents can submit documents and propose enrichment (Inbox). |
| `persist_approved` | Advanced; still does not Confirmed-write the map from MCP. |

---

## Quick start

1. Create an **Edge API token**: DecisionPen → **Admin → Security & audit → Edge API tokens → Create**.  
2. Follow **[CONNECT.md](./CONNECT.md)** for Claude Desktop or Cursor.  
3. For document repositories, follow **[SYNC.md](./SYNC.md)** and the [S3 docs page](https://decisionpen.com/docs/mcp-s3-document-store).

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
cp examples/.env.mcp.example .env.mcp
# set DP_API_BASE + DP_API_TOKEN
```

---

## Security defaults

- DecisionPen does **not** store customer S3 keys on the edge push path. Credentials stay on the edge (your laptop, VPC, or container).  
- Prefix allowlisting, audit log, and rate limits apply.  
- Tokens are hashed at rest; revoke anytime in Admin.

---

## Related product story

- [Architecture Context Plane](https://decisionpen.com/docs/architecture-context-plane)  
- [Architecture Decision Workspace](https://decisionpen.com/docs/architecture-decision-workspace)  
- [Incremental modelling](https://decisionpen.com/docs/incremental-modelling)  
- [Enterprise Ask](https://decisionpen.com/docs/enterprise-ask)  
