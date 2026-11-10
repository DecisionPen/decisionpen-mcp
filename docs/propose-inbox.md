# Propose → Insights Inbox

Edge MCP can **list/get** from your S3 and **push** into DecisionPen **application enrichment** → **Insights Inbox**. Humans approve before anything becomes **Confirmed** on the architecture map — same governance as the product loop on [decisionpen.com/product](https://decisionpen.com/product).

```text
Claude / Cursor / sync CLI
  → propose_enrichment / run_sync  (edge downloads from S3)
    → DecisionPen POST /api/edge/push-enrichment
      → enrichment job
        → Insights Inbox  →  human accept / edit / reject
          → Confirmed map (only after approval)
```

| Who | Credentials |
|-----|-------------|
| Edge list / get / download | Your edge `AWS_PROFILE` / IAM role / keys |
| DecisionPen push API | `DP_API_TOKEN` (Edge API token from Admin) |

DecisionPen does **not** store your AWS keys on this push path.

## Prerequisites

- DecisionPen tenant with Edge API tokens enabled  
- `DP_API_BASE` + `DP_API_TOKEN` set  
- `DP_MCP_MODE=propose` (or `persist_approved`)  
- S3 bucket + prefix allowlisted; IAM scoped to that prefix  
- Optional: Claude Desktop / Cursor MCP pointed at this server  

## Typical flow

1. `list_sources` / `search_docs` — find objects under the prefix  
2. `get_document` — cite without persisting (`cite_only` or before propose)  
3. `propose_enrichment` — edge downloads and pushes one object  
4. Or `run_sync` / `python -m decisionpen_mcp sync` — cursor over new/changed keys  
5. In DecisionPen UI → **Insights Inbox** → review proposals  
6. After curation, use Context Engine tools to **research** the updated map  

See [edge-sync.md](./edge-sync.md) and [security.md](./security.md).

## What MCP will not do

- Auto-Confirmed write entities or relationships  
- Upload your AWS secrets to DecisionPen  
- Replace in-app CMDB/spreadsheet import (that remains a first-class DecisionPen on-ramp)
