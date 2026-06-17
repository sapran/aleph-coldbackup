from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .client import ConfigError, http_fetch, make_api
from .export import CollectionNotFound, export_collection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aleph-coldbackup",
        description="Export an Aleph investigation into a re-ingestable cold backup.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export", help="Export one collection to a backup directory.")
    exp.add_argument("foreign_id", help="Collection foreign_id to export.")
    exp.add_argument("--out", required=True, help="Output directory root.")
    exp.add_argument("--verify-hashes", action="store_true",
                     help="Verify each downloaded file's SHA-1 against its contentHash.")
    exp.add_argument("--overwrite", action="store_true",
                     help="Re-download files even if present with matching size.")
    return parser


def _run_export(args: argparse.Namespace) -> int:
    try:
        api = make_api()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        result = export_collection(
            api, args.foreign_id, Path(args.out),
            fetch=http_fetch, verify_hashes=args.verify_hashes,
            overwrite=args.overwrite, generated_at=generated_at,
        )
    except CollectionNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    s = result["summary"]
    counts = s["counts"]
    print(
        f"exported {args.foreign_id}: files_written={s['files_written']} "
        f"bytes={s['total_bytes']} "
        f"missing={counts.get('missing', 0)} "
        f"collisions={counts.get('collision-renamed', 0)} "
        f"not_walked={counts.get('not-walked', 0)} "
        f"hash_mismatch={counts.get('hash-mismatch', 0)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        return _run_export(args)
    return 0
