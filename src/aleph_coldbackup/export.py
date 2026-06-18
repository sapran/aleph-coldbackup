from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .bundle import (
    write_collection_json, write_entities_ijson, write_manifest, write_restore_md,
)
from .client import http_fetch
from .manifest import Manifest
from .directwalk import DocRow, walk_direct
from .walker import walk_collection


class CollectionNotFound(Exception):
    pass


def _alephclient_version() -> str:
    try:
        return importlib.metadata.version("alephclient")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def export_collection(
    api,
    foreign_id: str,
    out_root: Path,
    *,
    fetch=http_fetch,
    verify_hashes: bool = False,
    overwrite: bool = False,
    generated_at: str,
) -> dict:
    collection = api.get_collection_by_foreign_id(foreign_id)
    if collection is None:
        raise CollectionNotFound(
            f"No collection with foreign_id={foreign_id!r} (or no read permission)."
        )
    cid = str(collection["id"])

    base = Path(out_root) / foreign_id
    files_root = base / "files"
    files_root.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(foreign_id=foreign_id, collection_id=cid)
    walk_collection(api, collection, files_root, manifest,
                    fetch=fetch, verify_hashes=verify_hashes, overwrite=overwrite)

    write_entities_ijson(api, collection, base / "entities.ijson")
    write_collection_json(collection, base / "collection.json")
    write_restore_md(collection, base / "RESTORE.md")
    meta = {
        "tool_version": __version__,
        "alephclient_version": _alephclient_version(),
        "host": getattr(api, "base_url", ""),
        "generated_at": generated_at,
    }
    write_manifest(manifest, base / "manifest.json", **meta)
    return manifest.to_dict(**meta)


def export_collection_direct(
    api,
    archive,
    foreign_id: str,
    out_root: Path,
    *,
    fetch_documents: Callable[[str], list[DocRow]],
    verify_hashes: bool = False,
    overwrite: bool = False,
    workers: int = 8,
    generated_at: str,
) -> dict:
    collection = api.get_collection_by_foreign_id(foreign_id)
    if collection is None:
        raise CollectionNotFound(
            f"No collection with foreign_id={foreign_id!r} (or no read permission)."
        )
    cid = str(collection["id"])

    base = Path(out_root) / foreign_id
    files_root = base / "files"
    files_root.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(foreign_id=foreign_id, collection_id=cid)
    rows = fetch_documents(cid)
    walk_direct(rows, archive, files_root, manifest,
                verify_hashes=verify_hashes, overwrite=overwrite, workers=workers)

    write_entities_ijson(api, collection, base / "entities.ijson")
    write_collection_json(collection, base / "collection.json")
    write_restore_md(collection, base / "RESTORE.md")
    meta = {
        "tool_version": __version__,
        "alephclient_version": _alephclient_version(),
        "host": getattr(api, "base_url", ""),
        "generated_at": generated_at,
    }
    write_manifest(manifest, base / "manifest.json", **meta)
    return manifest.to_dict(**meta)
