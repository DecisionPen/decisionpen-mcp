# Connect DecisionPen MCP to Claude or Cursor

Step-by-step setup for the Context Engine. For the product story and tool list, see [README.md](./README.md).  
Canonical marketing guide: [decisionpen.com/docs/connect-mcp-cursor-claude](https://decisionpen.com/docs/connect-mcp-cursor-claude).

## What you will have when finished

Claude Desktop or Cursor can call DecisionPen MCP tools: search the Enterprise Knowledge Graph, read evidence, and (if you enable propose mode) publish documents for human review. No Anthropic API key is required for MCP itself.

## 1. Create an Edge API token (Admin)

1. Sign in to DecisionPen as an **Administrator**.  
2. Open **Admin → Security & audit**.  
3. Open **Edge API tokens**.  
4. **Create** a token. Copy the secret once (`dp_edge_…`). You will not see it again.  
5. Store it as `DP_API_TOKEN` in your edge env (never commit it).

**Interactive tryouts only:** you may paste a browser session JWT instead. Prefer Edge tokens for anything lasting (Cursor daily use, cron, Docker).

Revoke tokens anytime from the same Admin screen.

## 2. Install the MCP server

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
cp examples/.env.mcp.example .env.mcp
```

Edit `.env.mcp` (minimum for graph + Ask tools):

```bash
DP_API_BASE=https://<your-decisionpen-host>   # or http://localhost:8000 locally
DP_API_TOKEN=dp_edge_...
DP_MCP_MODE=cite_only                         # use propose when ready to publish
```

S3 variables are **optional** until you connect a document repository — see [SYNC.md](./SYNC.md) and [mcp-s3-document-store](https://decisionpen.com/docs/mcp-s3-document-store).

Templates: [examples/cursor.mcp.json](./examples/cursor.mcp.json) · [examples/claude_desktop.mcp.json](./examples/claude_desktop.mcp.json)

## 3. Connect Cursor

Add a server entry to your Cursor MCP config (paths must be absolute):

```json
{
  "mcpServers": {
    "decisionpen": {
      "command": "/ABSOLUTE/PATH/decisionpen-mcp/.venv/bin/python",
      "args": ["-m", "decisionpen_mcp", "mcp"],
      "env": {
        "DP_API_BASE": "https://<your-decisionpen-host>",
        "DP_API_TOKEN": "dp_edge_...",
        "DP_MCP_MODE": "cite_only"
      }
    }
  }
}
```

Windows: point `command` at `.venv\\Scripts\\python.exe`.

Reload MCP in Cursor. Ask the agent to call `describe_context_model`, then try a landscape question using `search_entities` and `get_entity_evidence`.

## 4. Connect Claude Desktop

Same server shape in Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "decisionpen": {
      "command": "/ABSOLUTE/PATH/decisionpen-mcp/.venv/bin/python",
      "args": ["-m", "decisionpen_mcp", "mcp"],
      "env": {
        "DP_API_BASE": "https://<your-decisionpen-host>",
        "DP_API_TOKEN": "dp_edge_...",
        "DP_MCP_MODE": "cite_only"
      }
    }
  }
}
```

Restart Claude Desktop after changes.

## 5. Enable publish (optional)

When you want agents to push ADRs, requirements, or notes:

1. Set `DP_MCP_MODE=propose`.  
2. Reload MCP.  
3. Use `submit_document` (or `propose_enrichment` with S3).  
4. Review proposals in DecisionPen **Inbox**. Humans approve; the Confirmed map does not auto-update.

## 6. Optional: document repositories

To let agents list/search/fetch under an allowlisted S3 prefix, configure bucket + prefix + AWS auth, then follow [SYNC.md](./SYNC.md). Product summary: [Connect S3 via MCP](https://decisionpen.com/docs/mcp-s3-document-store).

## Test without an LLM

```bash
npx @modelcontextprotocol/inspector -- .venv/bin/python -m decisionpen_mcp mcp
```

## Tips

- Prefer Context Engine tools (`search_entities`, relationships, evidence) over `ask_decisionpen` so the agent owns the research plan.  
- Cite `fragment_id` / `source_title` when quoting evidence.  
- Do not invent Confirmed relationships from prose alone.  
- Ask spend uses the org LLM budget (same as in-app Ask).

## Related

- [README.md](./README.md) — overview and tool table  
- [CONTEXT.md](./CONTEXT.md) — research and solution-design recipes  
- [Product: Context Engine](https://decisionpen.com/docs/context-engine-mcp)  
