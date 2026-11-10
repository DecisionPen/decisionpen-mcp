# DecisionPen MCP Server — Enterprise Architecture Context Engine

**Works with [Claude Desktop](https://claude.ai/download), [Cursor](https://cursor.com), and any [Model Context Protocol (MCP)](https://modelcontextprotocol.io) client.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![DecisionPen](https://img.shields.io/badge/Product-decisionpen.com-0B3D5C.svg)](https://decisionpen.com/)

Connect your AI assistant to a **governed enterprise architecture context engine** — not a wiki chatbot, and not an empty EA repository.

---

## What is DecisionPen?

[DecisionPen](https://decisionpen.com/) is an **Architecture Decision Workspace** for the agentic era. It blends:

| Layer | What it holds |
|-------|----------------|
| **Structured map** | Applications, capabilities, technology, integrations, initiatives — metamodel-aware relationships (LeanIX-aligned when that standard matters) |
| **Evidence context** | HLDs, PDFs, wiki pages, transcripts, notes — the How-and-Why behind the map, with citations |

**AI proposes. Humans curate. The organisation interrogates a living map.**

It is built for questions like:

- Which applications support this business capability, and who owns them?
- What depends on this platform — and what is the blast radius if it changes?
- Why was this pattern chosen, and which documents support that decision?
- Which integrations are undocumented, inferred, or missing an owner?

Answers are **map-grounded** and **evidence-aware** — not assembled from document similarity alone. Unknown is preferred to fabricated certainty. Learn more: [product overview](https://decisionpen.com/product) · [Enterprise Ask](https://decisionpen.com/docs/enterprise-ask) · [Architecture Decision Workspace](https://decisionpen.com/docs/architecture-decision-workspace).

### The DecisionPen loop (product)

1. **Seed or ingest** — CMDB/inventory spreadsheet, documents, transcripts, or natural language  
2. **Propose** — AI drafts metamodel-aware entities, relationships, and enrichment  
3. **Curate** — architects accept, edit, reject, or defer (nothing is canonical just because AI suggested it)  
4. **Map & enrich** — accepted knowledge joins the living landscape  
5. **Ask & generate** — plain-English interrogation; blueprints, ADRs, and diagrams as byproducts of truth  

---

## What is this MCP server?

[MCP](https://modelcontextprotocol.io) (Model Context Protocol) is how tools like Claude Desktop and Cursor call external systems safely.

This repository is the **DecisionPen MCP server**. It lets your assistant:

| Mode | Job | MCP role |
|------|-----|----------|
| **Research** (Context Engine) | Ask the curated landscape | Read Confirmed entities, relationships, and evidence; cite sources |
| **Ingestion** (Edge connector) | Feed institutional memory | Browse/cite allowlisted S3 docs; optionally **propose** enrichment into DecisionPen’s Insights Inbox for human approval |

```text
                    RESEARCH                         INGESTION
                         │                                │
 Claude / Cursor  ──MCP──┼──► search / relationships /    │
                         │    evidence / Ask              │
                         │                                │
                         │         Edge (optional)        │
                         │    ◄── list / get S3 ──────────┤
                         │    ──► propose → Inbox ────────►│
                         ▼                                ▼
                 DecisionPen API              Human curation
              Confirmed map + evidence         then Confirmed map
```

**Division of labour**

- **Claude / Cursor** — intent, reasoning, and writing  
- **DecisionPen** — repository of record (Confirmed map + evidence)  
- **This MCP server** — the bridge (stdio today; hosted/remote later)  

MCP **never** Confirmed-writes the architecture map. Persist = human approve in Inbox.

---

## Why use MCP instead of pasting docs into chat?

| Without DecisionPen MCP | With DecisionPen MCP |
|-------------------------|----------------------|
| AI invents integrations | Tools return **Confirmed** relationships only |
| Paste screenshots / PDFs into Claude | Structured `search_entities` → relationships → evidence |
| Catalogue search under-answers; RAG over-confidently invents | Map-grounded + evidence-cited answers; honest gaps |
| SaaS holds your AWS keys | Optional **Edge** path keeps S3 credentials on your side |

Ideal for enterprise architects, solution architects, platform teams, and anyone doing due diligence or transformation planning.

---

## 5-minute setup — Research (Context Engine)

You need a DecisionPen workspace ([decisionpen.com](https://decisionpen.com/)), an **Edge API token** (Admin → Security & audit → Edge API tokens) or a session JWT for trials, and Python 3.10+.

### 1. Install

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp examples/.env.mcp.example .env.mcp
```

Minimum for architecture Q&A (**no S3 required**):

```bash
DP_API_BASE=https://YOUR_DECISIONPEN_HOST
DP_API_TOKEN=dp_edge_…
DP_MCP_MODE=cite_only
```

### 3. Connect Claude Desktop

**Settings → Developer → Edit Config**, then restart Claude:

```json
{
  "mcpServers": {
    "decisionpen": {
      "command": "/ABSOLUTE/PATH/decisionpen-mcp/.venv/bin/python",
      "args": ["-m", "decisionpen_mcp", "mcp"],
      "env": {
        "DP_API_BASE": "https://YOUR_DECISIONPEN_HOST",
        "DP_API_TOKEN": "dp_edge_…",
        "DP_MCP_MODE": "cite_only"
      }
    }
  }
}
```

Windows: use `…\\decisionpen-mcp\\.venv\\Scripts\\python.exe`.  
Guide: **[docs/claude-desktop.md](./docs/claude-desktop.md)** · Cursor: **[docs/cursor.md](./docs/cursor.md)**

### 4. Try a research prompt

> Using DecisionPen, what applications support clinical trials? Prefer Confirmed map relationships; label evidence notes separately and cite sources.

Claude should call Context Engine tools — not guess.

---

## Research tools (Context Engine)

| Tool | Purpose |
|------|---------|
| `describe_context_model` | Map vs notes; capability-first workflow |
| `search_entities` | Name → id (search **capability/process first** for landscape asks) |
| `get_entity` | Description, aliases, attributes |
| `get_entity_relationships` | Confirmed edges |
| `get_relationship_summary` | Typed / direction counts |
| `get_entity_evidence` / `search_evidence` | Unstructured notes + provenance |
| `list_entity_types` / `batch_get_entities` | Filters & hydrate peers |
| `ask_decisionpen` | Last-resort server Ask (prefer structured tools above) |

Deep dive: **[docs/context-engine.md](./docs/context-engine.md)**

**Capability-first pattern** (from DecisionPen’s Enterprise Ask practice): for “what apps support X?”, search capabilities/processes named like X, follow Confirmed relationships to applications, then optionally load evidence — always separating **Confirmed on the map** from **notes only**.

---

## Ingestion tools (Edge connector — optional)

Feed DecisionPen from documents you already trust (HLDs, PDFs, architecture packs in S3) **without** giving DecisionPen your AWS keys.

| Tool / command | Purpose |
|----------------|---------|
| `list_sources` / `search_docs` / `get_document` | Cite from an allowlisted S3 prefix (no persist) |
| `propose_enrichment` / `run_sync` | Push content → Insights Inbox for human review |
| `python -m decisionpen_mcp sync` | Cron-friendly sync |

Trust ladder (`DP_MCP_MODE`): `cite_only` → `propose` → human approve in-app before Confirmed.  
Guides: **[docs/edge-sync.md](./docs/edge-sync.md)** · **[docs/security.md](./docs/security.md)** · **[docs/propose-inbox.md](./docs/propose-inbox.md)**

---

## Docker

```bash
docker build -t decisionpen-mcp .
docker run --rm -i --env-file .env.mcp decisionpen-mcp mcp
docker run --rm --env-file edge.env -v dp-sync:/data decisionpen-mcp sync --dry-run
```

---

## Documentation

| Doc | Topic |
|-----|--------|
| [Context Engine](./docs/context-engine.md) | Research: map-grounded EA Q&A |
| [Claude Desktop](./docs/claude-desktop.md) | Install for Claude |
| [Cursor](./docs/cursor.md) | Install for Cursor |
| [Edge sync](./docs/edge-sync.md) | Ingestion: S3 → Inbox |
| [Security](./docs/security.md) | Tokens, allowlists, trust ladder |
| [Propose / Inbox](./docs/propose-inbox.md) | Human approval before Confirmed |

---

## Requirements

- Python 3.10+
- DecisionPen API reachable from the machine running MCP
- Edge API token (recommended) or session JWT (interactive only)
- Optional: AWS credentials scoped to one S3 prefix for Edge ingestion

---

## Roadmap

- Hosted / remote MCP transport for teams  
- PyPI / GHCR packaged releases  
- More Edge adapters beyond S3  

---

## Related

- Product: [decisionpen.com](https://decisionpen.com/)  
- [What is an Architecture Decision Workspace?](https://decisionpen.com/docs/architecture-decision-workspace)  
- [Enterprise Ask](https://decisionpen.com/docs/enterprise-ask)  
- Protocol: [Model Context Protocol](https://modelcontextprotocol.io)  

## License

MIT — see [LICENSE](./LICENSE).

---

**Keywords:** MCP server, Claude Desktop MCP, Cursor MCP, enterprise architecture AI, Architecture Decision Workspace, enterprise architecture context engine, Confirmed application landscape, LeanIX-aligned MCP, evidence-grounded EA assistant, architecture ingestion MCP.
