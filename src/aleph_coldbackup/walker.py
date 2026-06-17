from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Callable

from .client import FetchError, file_url, pick_filename
from .manifest import FileRecord, Manifest, Status
from .names import PathAllocator, safe_component

Fetch = Callable[[str, Path], "tuple[int, str]"]


def _first(values: list | None) -> str | None:
    return values[0] if values else None


def walk_collection(
    api,
    collection: dict,
    files_root: Path,
    manifest: Manifest,
    *,
    fetch: Fetch,
    verify_hashes: bool,
    overwrite: bool,
) -> None:
    cid = collection["id"]
    alloc = PathAllocator()
    top = api.search(
        "",
        filters=[("collection_id", cid)],
        schemata="Document",
        params={"empty:properties.parent": "true"},
    )
    _walk_set(api, cid, top, "", files_root, manifest, alloc,
              fetch=fetch, verify_hashes=verify_hashes, overwrite=overwrite)


def _walk_set(api, cid, result_set, rel_dir, files_root, manifest, alloc,
              *, fetch, verify_hashes, overwrite) -> None:
    iterated = 0
    for entity in result_set:
        iterated += 1
        _process(api, cid, entity, rel_dir, files_root, manifest, alloc,
                 fetch=fetch, verify_hashes=verify_hashes, overwrite=overwrite)
    total = len(result_set)
    if total > iterated:
        parent_id = rel_dir or "(root)"
        manifest.add(FileRecord(
            entity_id=parent_id, content_hash=None, file_name=None,
            output_path=rel_dir or None, parent=None, status=Status.NOT_WALKED,
            note=f"{total - iterated} of {total} children unreachable (search window)",
        ))


def _process(api, cid, entity, rel_dir, files_root, manifest, alloc,
             *, fetch, verify_hashes, overwrite) -> None:
    eid = entity["id"]
    props = entity.get("properties", {})
    content_hash = _first(props.get("contentHash"))
    file_name = pick_filename(entity)
    parent = _first(props.get("parent"))

    if content_hash is None:
        # Folder: allocate a dir name, recurse into children.
        name, _ = alloc.allocate(rel_dir, safe_component(file_name, eid), eid)
        sub_rel = posixpath.join(rel_dir, name) if rel_dir else name
        (files_root / sub_rel).mkdir(parents=True, exist_ok=True)
        children = api.search(
            "",
            filters=[("collection_id", cid), ("properties.parent", eid)],
            schemata="Document",
        )
        _walk_set(api, cid, children, sub_rel, files_root, manifest, alloc,
                  fetch=fetch, verify_hashes=verify_hashes, overwrite=overwrite)
        return

    # File: allocate a unique name, download.
    name, renamed = alloc.allocate(rel_dir, safe_component(file_name, eid), content_hash)
    rel_path = posixpath.join(rel_dir, name) if rel_dir else name
    dest = files_root / rel_path
    url = file_url(api.base_url, entity)

    if url is None:
        manifest.add(FileRecord(eid, content_hash, file_name, None, parent, Status.MISSING))
        return

    if dest.exists() and not overwrite:
        manifest.add(FileRecord(eid, content_hash, file_name, rel_path, parent,
                                Status.OK, bytes=dest.stat().st_size))
        return

    try:
        nbytes, sha = fetch(url, dest)
    except FetchError:
        manifest.add(FileRecord(eid, content_hash, file_name, None, parent, Status.MISSING))
        return

    status = Status.OK
    if verify_hashes and sha != content_hash:
        status = Status.HASH_MISMATCH
    elif renamed:
        status = Status.COLLISION_RENAMED
    manifest.add(FileRecord(eid, content_hash, file_name, rel_path, parent, status, bytes=nbytes))
