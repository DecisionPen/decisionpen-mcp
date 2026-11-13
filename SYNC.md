# Edge push sync (S3) — 5-minute setup

Customer-edge process downloads from **your** S3 and pushes content + provenance to DecisionPen. **DecisionPen never holds your AWS keys** on this path.

Product overview (SEO / plain English): [Connect an S3 document repository via MCP](https://decisionpen.com/docs/mcp-s3-document-store).  
Claude/Cursor connection: [CONNECT.md](./CONNECT.md) · [README.md](./README.md).

## 1. Create an Edge API token

In DecisionPen: **Admin → Security & audit → Edge API tokens → Create**.  
Copy the `dp_edge_…` secret once into `edge.env` as `DP_API_TOKEN`.

Session JWTs still work for interactive Claude/Cursor tests; use Edge tokens for cron/Docker.

## 2. Fill `edge.env`

```bash
DP_API_BASE=https://<your-decisionpen-host>
DP_API_TOKEN=dp_edge_...
DP_MCP_MODE=propose
DP_S3_BUCKET=my-ea-docs
DP_S3_PREFIX=architecture/
```

AWS auth depends on where the edge runs:

| Edge runs on | Recommended |
|--------------|-------------|
| Customer AWS (EC2/ECS/EKS) | IAM task/instance role |
| GCP | Workload Identity Federation or keys in Secret Manager |
| Laptop / Claude Desktop | `AWS_PROFILE` or access keys (prefix-scoped) |

## 3. Dry-run

```bash
docker build -t decisionpen-edge .
docker run --rm --env-file edge.env -v dp-sync:/data decisionpen-edge sync --dry-run
```

Or native (after `pip install -e .`):

```bash
python -m decisionpen_mcp sync --dry-run
```

## 4. Optional: MCP in Claude / Cursor

Same image/code; entrypoint `mcp` (stdio). Set `DP_MCP_MODE=propose`, then try cite → propose one file → `run_sync`.

## 5. Schedule daily sync

```bash
# cron example
0 2 * * * docker run --rm --env-file /etc/decisionpen/edge.env -v dp-sync:/data decisionpen-edge sync
```

Review jobs in **Insights Inbox**. Unchanged files cost **$0 LLM** (etag cursor + content-sha short-circuit). Exhausted org AI budget or edge rate limits return **429**; the cursor does not advance for failed items.

## Spend guards

| Guard | Default |
|-------|---------|
| Org LLM monthly $ budget | existing Admin LLM usage panel |
| Edge push requests / min / tenant | `EDGE_RATE_LIMIT_PER_MIN=10` |
| Files queued / day / tenant | `EDGE_FILES_PER_DAY=200` |
| Max files / request | `EDGE_MAX_FILES_PER_REQUEST=20` |
| Max bytes / file | `EDGE_MAX_BYTES_PER_FILE=10485760` |

## Security defaults

- Image ships `cite_only` unless you set `DP_MCP_MODE=propose`
- Empty `DP_S3_PREFIX` is refused for propose/sync
- Tokens are hashed at rest; revoke anytime in Admin
