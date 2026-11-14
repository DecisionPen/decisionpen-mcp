# Edge ingestion — S3 → DecisionPen (via MCP / sync CLI)

This is the **ingestion** side of DecisionPen MCP: bring institutional memory (HLDs, PDFs, architecture packs) into DecisionPen for rapid enterprise discovery, AI proposal, and **human curation**, without giving DecisionPen your AWS keys. From the corpus, DecisionPen can propose LeanIX-aligned structure; if you already seeded from a CMDB, document knowledge attaches to those entities.

Research (asking the map) is covered in [context-engine.md](./context-engine.md). Product loop: [how DecisionPen works](https://decisionpen.com/product) — seed/ingest → propose → curate → map → ask. Marketing guide: [Connect S3 documents](https://decisionpen.com/docs/mcp-s3-document-store).

## Why Edge?

DecisionPen can ingest documents in-app. The **Edge** path is for customer-side object stores:

- Your IAM / keys stay on the edge (laptop, VPC, Cloud Run, etc.)  
- Edge downloads allowlisted objects and pushes content + provenance to DecisionPen  
- Humans approve in **Insights Inbox** before anything becomes Confirmed on the map  

## 1. Create an Edge API token

In DecisionPen: **Admin → Security & audit → Edge API tokens → Create**.  
Put `dp_edge_…` in `edge.env` as `DP_API_TOKEN`.

Session JWTs are fine for interactive Claude/Cursor tests; use Edge tokens for cron/Docker.

## 2. Fill `edge.env`

```bash
cp examples/edge.env.example edge.env
```

```bash
DP_API_BASE=https://api.decisionpen.com
DP_API_TOKEN=dp_edge_...
DP_MCP_MODE=propose
DP_S3_BUCKET=my-ea-docs
DP_S3_PREFIX=architecture/
```

| Edge runs on | Recommended AWS auth |
|--------------|----------------------|
| Customer AWS (EC2/ECS/EKS) | IAM task/instance role |
| GCP | Workload Identity Federation or keys in Secret Manager |
| Laptop / Claude Desktop | `AWS_PROFILE` or prefix-scoped access keys |

## 3. Dry-run sync

```bash
docker build -t decisionpen-mcp .
docker run --rm --env-file edge.env -v dp-sync:/data decisionpen-mcp sync --dry-run
```

Or native (venv activated, repo root):

```bash
python -m decisionpen_mcp sync --dry-run
python -m decisionpen_mcp sync
```

## 4. MCP ingestion tools

Same server as research; with `DP_MCP_MODE=propose` Claude/Cursor can:

- `list_sources` / `search_docs` / `get_document` — cite without persisting  
- `propose_enrichment` / `run_sync` — push to Inbox  
- `get_enrichment_job` / `rerun_enrichment_job` — poll / retry  

See [propose-inbox.md](./propose-inbox.md) and [security.md](./security.md).

## 5. Schedule

```bash
# cron example
0 2 * * * cd /opt/decisionpen-mcp && docker compose run --rm edge sync
```

After sync, architects review Inbox proposals in DecisionPen — AI drafts; people decide — then Ask/research tools see the enriched Confirmed map.
