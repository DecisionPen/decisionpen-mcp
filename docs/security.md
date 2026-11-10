# Security model

DecisionPen MCP keeps **secrets at the edge** and the architecture map **human-governed** — consistent with DecisionPen’s product rule: AI proposes, humans curate, nothing is canonical until approved ([product](https://decisionpen.com/product)).

## Trust ladder (`DP_MCP_MODE`)

| Mode | Research | Ingestion |
|------|----------|-----------|
| `cite_only` (default) | Context Engine + Ask APIs; cite S3 objects | No persist to DecisionPen |
| `propose` | Same | Push enrichment jobs to **Insights Inbox** |
| `persist_approved` | Same | Same push path; Confirmed map writes still require **in-app human approval** |

MCP **never** Confirmed-writes the architecture map by itself.

## Authentication

| Secret | Where it lives | Purpose |
|--------|----------------|---------|
| `DP_API_TOKEN` | Edge / laptop env | Edge API token (`dp_edge_…`) preferred; session JWT for interactive tests only |
| AWS keys / instance role | Customer edge only | S3 list/get under allowlisted prefix |

On the Edge push path, DecisionPen does **not** need your AWS keys — the edge downloads and POSTs content + provenance.

## S3 allowlist

```bash
DP_S3_BUCKET=my-ea-docs
DP_S3_PREFIX=architecture/
```

IAM: `s3:ListBucket` + `s3:GetObject` **only** on that prefix. Whole-bucket access is discouraged.

## Audit

Set `DP_MCP_AUDIT_LOG` to a local JSONL path for tool audit trails.

## Do not commit

`.env.mcp`, `edge.env`, real tokens, AWS keys, or sync/audit files that contain customer content. Use `examples/` as templates only.
