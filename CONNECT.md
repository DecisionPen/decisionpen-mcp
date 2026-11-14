# Connect DecisionPen MCP to Claude or Cursor

Step-by-step setup for the Context Engine. For the product story and tool list, see [README.md](./README.md).  
Canonical marketing guide: [decisionpen.com/docs/connect-mcp-cursor-claude](https://decisionpen.com/docs/connect-mcp-cursor-claude).

## What you will have when finished

Claude Desktop or Cursor can call DecisionPen MCP tools: search the Enterprise Knowledge Graph, read evidence and standards, and (if you enable propose mode) publish documents for human review. Use Claude for decision research on the Context of Record; use Cursor so delivery follows approved patterns and can write architecture back. No Anthropic API key is required for MCP itself.

**Customers and trials use the hosted MCP endpoint.** You do not need a local DecisionPen (or Archimedes) install on your laptop.

## Why Claude

Use Claude when you need deep research over the Context of Record before an important decision. After DecisionPen holds entities and evidence — from a CMDB seed, document discovery, or both — Claude can interrogate landscape, dependencies, standards, and prior decisions without rebuilding the estate in the chat window. Connecting Claude is a natural part of a DecisionPen trial.

## Why Cursor

Use Cursor when agentic delivery must follow enterprise patterns and standards. DecisionPen holds approved reference architectures, design patterns, security, compliance, and privacy context. Cursor can query that pack while designing and implementing, then publish ADRs and design notes back so institutional memory stays current for the next programme.

## 1. Create an Edge API token (Admin)

1. Sign in to DecisionPen as an **Administrator**.  
2. Open **Admin → Security & audit**.  
3. Open **Edge API tokens**.  
4. **Create** a token. Copy the secret once (`dp_edge_…`). You will not see it again.  
5. Keep it for the client config below (never commit it).

Revoke tokens anytime from the same Admin screen.

## 2. Connect Cursor or Claude (hosted — recommended)

Point the client at DecisionPen’s remote MCP server. There is no local Python process and **no `DP_API_BASE`** in this config.

```json
{
  "mcpServers": {
    "decisionpen": {
      "url": "https://mcp.decisionpen.com/mcp",
      "headers": {
        "Authorization": "Bearer dp_edge_..."
      }
    }
  }
}
```

Templates: [examples/cursor.remote.mcp.json](./examples/cursor.remote.mcp.json) · [examples/claude_desktop.remote.mcp.json](./examples/claude_desktop.remote.mcp.json)

Reload MCP (Cursor) or restart Claude Desktop. Ask the agent to call `describe_context_model`, then try a landscape question using `search_entities` and `get_entity_evidence`.

Health: `https://mcp.decisionpen.com/health`

### Two different hosts

| Role | URL |
|------|-----|
| Agents (Claude, Cursor) | `https://mcp.decisionpen.com/mcp` |
| Edge / ops processes (`DP_API_BASE`) | `https://api.decisionpen.com` |

Do **not** put the MCP URL in `DP_API_BASE`. The API host serves REST (`/api/...`). The MCP host serves Streamable HTTP (`/mcp`).

## 3. Enable publish (optional)

When agents should push ADRs, requirements, or notes, use propose-capable tools from an allowed session, then review proposals in DecisionPen **Inbox**. Humans approve; the Confirmed map does not auto-update. For S3 document discovery, see [SYNC.md](./SYNC.md) and [mcp-s3-document-store](https://decisionpen.com/docs/mcp-s3-document-store).

## 4. Optional: local stdio (contributors only)

If you are developing the Context Engine itself, clone this repo and run stdio locally. Customers on a DecisionPen trial do not need this path.

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
cp examples/.env.mcp.example .env.mcp
```

```bash
DP_API_BASE=https://api.decisionpen.com
DP_API_TOKEN=dp_edge_...
DP_MCP_MODE=cite_only
```

Local client example: [examples/cursor.mcp.json](./examples/cursor.mcp.json) · [examples/claude_desktop.mcp.json](./examples/claude_desktop.mcp.json)

## Tips

- Prefer Context Engine tools (`search_entities`, relationships, evidence) over `ask_decisionpen` so the agent owns the research plan.  
- Cite `fragment_id` / `source_title` when quoting evidence.  
- Do not invent Confirmed relationships from prose alone.  

## Related

- [README.md](./README.md) — overview and tool table  
- [CONTEXT.md](./CONTEXT.md) — research and solution-design recipes  
- [Product: Context Engine](https://decisionpen.com/docs/context-engine-mcp)  
