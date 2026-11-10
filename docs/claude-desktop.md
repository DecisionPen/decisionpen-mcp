# Claude Desktop + DecisionPen MCP

Connect [Claude Desktop](https://claude.ai/download) to [DecisionPen](https://decisionpen.com/) so Claude can **research** your Confirmed architecture map and evidence over MCP — and optionally help with **ingestion** proposals from S3 (Edge mode).

No Anthropic API key is required for DecisionPen tools. Claude Desktop already provides the model. You need a DecisionPen Edge API token (or a session JWT for local trials).

## What you’ll get

- Map-grounded answers (entities + relationships), not a generic wiki summary  
- Evidence citations when notes are used  
- Optional Edge tools to cite or propose documents from your S3 (human approval before Confirmed)

Background: [README](../README.md) · [Context Engine](./context-engine.md)

## Install the server

```bash
git clone https://github.com/DecisionPen/decisionpen-mcp.git
cd decisionpen-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e .
cp examples/.env.mcp.example .env.mcp
# edit .env.mcp — DP_API_BASE + DP_API_TOKEN
```

## Claude Desktop config

**Settings → Developer → Edit Config**, then fully quit and reopen Claude.

### macOS / Linux

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

### Windows

```json
{
  "mcpServers": {
    "decisionpen": {
      "command": "C:\\Users\\YOU\\Documents\\decisionpen-mcp\\.venv\\Scripts\\python.exe",
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

Template: [examples/claude_desktop.mcp.json](../examples/claude_desktop.mcp.json)

## First research prompts

- *Using DecisionPen, describe the context model, then find applications that support clinical trials.*  
- *What is the Confirmed connection between CTMS and RAMS?*  
- *Summarize evidence notes for &lt;application&gt; and cite fragment ids. Do not invent map edges.*  

Prefer Context Engine tools ([context-engine.md](./context-engine.md)). Use `ask_decisionpen` only as a last resort.

## Tips

- After changing env or code, fully quit and reopen Claude Desktop.  
- Keep tokens out of git — never commit `.env.mcp`.  
- Ask spend uses your DecisionPen org LLM budget when you call `ask_decisionpen`.  
- For S3 ingestion tools, see [edge-sync.md](./edge-sync.md) and set `DP_MCP_MODE=propose` only when you intend to push to Inbox.
