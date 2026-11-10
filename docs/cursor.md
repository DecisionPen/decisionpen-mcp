# Cursor + DecisionPen MCP

Use [DecisionPen](https://decisionpen.com/) inside [Cursor](https://cursor.com) as an MCP **enterprise architecture context engine**: research the Confirmed map and evidence, and optionally propose document ingestion via Edge.

## Install

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
cp examples/.env.mcp.example .env.mcp
# set DP_API_BASE + DP_API_TOKEN
```

## Cursor MCP config

Cursor Settings → MCP, or project `.cursor/mcp.json`:

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

Windows: point `command` at `.venv\\Scripts\\python.exe`.  
Template: [examples/cursor.mcp.json](../examples/cursor.mcp.json)

Reload MCP after editing.

## Suggested research workflow

1. Call `describe_context_model` once.  
2. For landscape questions, search **capabilities/processes** first, then follow Confirmed relationships to applications.  
3. Cite evidence with `fragment_id` / `source_title`; never invent map edges from notes.  

Details: [context-engine.md](./context-engine.md) · Product: [Enterprise Ask](https://decisionpen.com/docs/enterprise-ask)
