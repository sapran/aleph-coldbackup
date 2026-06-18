from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from .archive_fs import FsArchive
from .client import ConfigError, http_fetch, make_api
from .export import CollectionNotFound, export_collection, export_collection_direct
from .pgmeta import PgMetadata


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
    exp.add_argument("--direct", action="store_true",
                     help="Server-side mode: read the file tree from PostgreSQL and "
                          "bytes from the archive filesystem (much faster).")
    exp.add_argument("--archive-path",
                     help="(--direct) Root path of the servicelayer file archive.")
    exp.add_argument("--archive-type", default="file", choices=["file"],
                     help="(--direct) Archive backend type (only 'file' is supported).")
    exp.add_argument("--workers", type=int, default=8,
                     help="(--direct) Parallel copy workers (default 8).")
    grp = exp.add_mutually_exclusive_group()
    grp.add_argument("--reflink", action="store_true",
                     help="(--direct) Copy-on-write clone where supported (falls back to copy).")
    grp.add_argument("--hardlink", action="store_true",
                     help="(--direct) Hardlink blobs (fastest; shares inodes with the live archive).")
    return parser


def _print_summary(foreign_id: str, result: dict) -> None:
    s = result["summary"]
    counts = s["counts"]
    print(
        f"exported {foreign_id}: files_written={s['files_written']} "
        f"bytes={s['total_bytes']} "
        f"missing={counts.get('missing', 0)} "
        f"collisions={counts.get('collision-renamed', 0)} "
        f"not_walked={counts.get('not-walked', 0)} "
        f"hash_mismatch={counts.get('hash-mismatch', 0)}"
    )


def _db_uri() -> str | None:
    return os.environ.get("COLDBACKUP_DB_URI") or os.environ.get("ALEPH_DATABASE_URI")


def _run_export(args: argparse.Namespace) -> int:
    try:
        api = make_api()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.direct:
        return _run_export_direct(args, api, generated_at)
    try:
        result = export_collection(
            api, args.foreign_id, Path(args.out),
            fetch=http_fetch, verify_hashes=args.verify_hashes,
            overwrite=args.overwrite, generated_at=generated_at,
        )
    except CollectionNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_summary(args.foreign_id, result)
    return 0


def _run_export_direct(args: argparse.Namespace, api, generated_at: str) -> int:
    if not args.archive_path:
        print("error: --direct requires --archive-path", file=sys.stderr)
        return 2
    dsn = _db_uri()
    if not dsn:
        print("error: --direct requires COLDBACKUP_DB_URI or ALEPH_DATABASE_URI",
              file=sys.stderr)
        return 2
    mode = "hardlink" if args.hardlink else "reflink" if args.reflink else "copy"
    archive = FsArchive(Path(args.archive_path), mode=mode)
    try:
        pg = PgMetadata.connect(dsn)
    except psycopg.Error as exc:
        print(f"error: PostgreSQL connection failed: {exc}", file=sys.stderr)
        return 2
    try:
        result = export_collection_direct(
            api, archive, args.foreign_id, Path(args.out),
            fetch_documents=pg.fetch_documents, verify_hashes=args.verify_hashes,
            overwrite=args.overwrite, workers=args.workers, generated_at=generated_at,
        )
    except CollectionNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except psycopg.Error as exc:
        print(f"error: database query failed: {exc}", file=sys.stderr)
        return 2
    finally:
        pg.close()
    _print_summary(args.foreign_id, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export":
        return _run_export(args)
    return 0
