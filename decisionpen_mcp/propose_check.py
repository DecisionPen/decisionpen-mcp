"""
Validate Propose → Inbox wiring for Edge MCP.

Usage (from repo root, with API running and .env.mcp filled):

  .\\.venv-mcp\\Scripts\\python.exe -m decisionpen_mcp.propose_check
  .\\.venv-mcp\\Scripts\\python.exe -m decisionpen_mcp.propose_check --list-connectors
  .\\.venv-mcp\\Scripts\\python.exe -m decisionpen_mcp.propose_check --propose ITEM_ID
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

import requests

from decisionpen_mcp.api_client import DecisionPenApiClient, DecisionPenApiError
from decisionpen_mcp.config import EdgeConfig, McpMode
from decisionpen_mcp.server import _load_dotenv_files


def _headers(cfg: EdgeConfig) -> Dict[str, str]:
    if not cfg.api_token:
        raise SystemExit(
            "DP_API_TOKEN is missing in .env.mcp\n"
            "In the DecisionPen app (browser): DevTools → Application → Local Storage → "
            "copy access_token"
        )
    return {
        "Authorization": f"Bearer {cfg.api_token}",
        "Accept": "application/json",
    }


def list_connectors(cfg: EdgeConfig) -> List[Dict[str, Any]]:
    url = f"{cfg.api_base.rstrip('/')}/api/connectors"
    try:
        resp = requests.get(url, headers=_headers(cfg), timeout=30)
    except requests.RequestException as e:
        raise SystemExit(f"Cannot reach DecisionPen API at {cfg.api_base}: {e}") from e
    if resp.status_code >= 400:
        raise SystemExit(f"GET /api/connectors failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected connectors response: {data!r}")
    return data


def print_status(cfg: EdgeConfig) -> None:
    print("=== Edge MCP Propose → Inbox status ===")
    print(f"DP_API_BASE      = {cfg.api_base}")
    print(f"DP_MCP_MODE      = {cfg.mode.value}")
    print(f"DP_S3_BUCKET     = {cfg.bucket}")
    print(f"DP_S3_PREFIX     = {cfg.allowlist_prefix}")
    print(f"DP_CONNECTOR_ID  = {cfg.connector_id or '(not set)'}")
    print(f"DP_API_TOKEN     = {'set (' + str(len(cfg.api_token)) + ' chars)' if cfg.api_token else '(not set)'}")
    print()
    if cfg.mode == McpMode.CITE_ONLY:
        print("WARN: DP_MCP_MODE=cite_only — propose_enrichment is blocked.")
        print("      Set DP_MCP_MODE=propose in .env.mcp and reload the MCP server in Cursor.")
        print()
    if not cfg.connector_id:
        print("WARN: DP_CONNECTOR_ID not set — create an S3 connector in DecisionPen, then paste its id.")
        print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check Propose → Inbox MCP wiring")
    parser.add_argument(
        "--list-connectors",
        action="store_true",
        help="List S3 connectors for the token's tenant",
    )
    parser.add_argument(
        "--propose",
        metavar="ITEM_ID",
        help="Call process-enrichment for one S3 object key (full key)",
    )
    args = parser.parse_args(argv)

    _load_dotenv_files()
    try:
        cfg = EdgeConfig.from_env()
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    print_status(cfg)

    if args.list_connectors or not cfg.connector_id or args.propose:
        if not cfg.api_token:
            _headers(cfg)  # raises SystemExit with help
        connectors = list_connectors(cfg)
        if not connectors:
            print("No connectors found. Create one in DecisionPen (Add knowledge → Amazon S3).")
            return 1
        print("Connectors:")
        for c in connectors:
            conf = c.get("config") or {}
            print(
                f"  id={c.get('id')}  name={c.get('name')!r}  "
                f"bucket={conf.get('bucket')!r}  prefix={conf.get('prefix')!r}  "
                f"region={conf.get('region')!r}"
            )
        print()
        if not cfg.connector_id:
            print("Next: set DP_CONNECTOR_ID=<id> in .env.mcp (same bucket/prefix as DP_S3_*).")

    if args.propose:
        if cfg.mode == McpMode.CITE_ONLY:
            print("Refusing --propose while DP_MCP_MODE=cite_only", file=sys.stderr)
            return 1
        if not cfg.connector_id:
            print("DP_CONNECTOR_ID required for --propose", file=sys.stderr)
            return 1
        api = DecisionPenApiClient(cfg)
        try:
            result = api.process_enrichment(
                item_ids=[args.propose],
                source_label="Add knowledge — Edge MCP propose_check",
            )
        except DecisionPenApiError as e:
            print(f"propose failed: {e}", file=sys.stderr)
            return 1
        print("Queued enrichment:")
        print(json.dumps(result, indent=2))
        print()
        print("Open DecisionPen → Insights Inbox and refresh to review proposals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
