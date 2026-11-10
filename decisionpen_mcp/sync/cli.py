"""CLI: decisionpen_mcp sync [--dry-run]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from decisionpen_mcp.adapters.s3 import S3SourceAdapter
from decisionpen_mcp.api_client import DecisionPenApiClient
from decisionpen_mcp.audit import AuditLogger
from decisionpen_mcp.config import EdgeConfig
from decisionpen_mcp.policy import PolicyDenied
from decisionpen_mcp.sync.engine import SyncEngine
from decisionpen_mcp.sync.state import SyncState


def _load_dotenv_files() -> None:
    """Load edge.env / .env.mcp from cwd or repo root (same as MCP server)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    repo_root = Path(__file__).resolve().parents[2]
    for candidate in (
        Path.cwd() / "edge.env",
        Path.cwd() / ".env.mcp",
        repo_root / "edge.env",
        repo_root / ".env.mcp",
        Path(__file__).resolve().parents[1] / "edge.env",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="decisionpen_mcp",
        description="DecisionPen Edge MCP / sync (S3 push ingest)",
    )
    sub = p.add_subparsers(dest="command")

    sync = sub.add_parser("sync", help="Sync allowlisted S3 prefix into DecisionPen Inbox")
    sync.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be pushed without downloading/uploading",
    )
    sync.add_argument("--max-keys", type=int, default=0, help="Cap listed objects")
    sync.add_argument("--batch-size", type=int, default=10)
    sync.add_argument("--source-label", default="")
    sync.add_argument("--anchor-application-id", default="")
    sync.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip content-status preflight before push",
    )

    sub.add_parser("mcp", help="Run MCP stdio server (default when no command)")
    return p


def run_sync(args: argparse.Namespace) -> int:
    _load_dotenv_files()
    try:
        cfg = EdgeConfig.from_env()
    except Exception as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    adapter = S3SourceAdapter(cfg)
    api = DecisionPenApiClient(cfg)
    state = SyncState(cfg.sync_state_path)
    audit = AuditLogger(cfg.audit_log_path)
    engine = SyncEngine(cfg, adapter, api, state, audit=audit)
    try:
        result = engine.run(
            dry_run=bool(args.dry_run),
            max_keys=args.max_keys or None,
            batch_size=args.batch_size,
            source_label=args.source_label.strip() or None,
            anchor_application_id=args.anchor_application_id.strip() or None,
            preflight=not bool(args.no_preflight),
        )
    except PolicyDenied as e:
        print(json.dumps({"ok": False, "error": e.reason, "code": e.code}, indent=2))
        return 1
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sync":
        return run_sync(args)
    # mcp or no command → stdio server
    from decisionpen_mcp.server import main as mcp_main

    mcp_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
