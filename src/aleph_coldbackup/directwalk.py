from __future__ import annotations

import posixpath
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .manifest import FileRecord, Manifest, Status
from .names import PathAllocator, safe_component


@dataclass
class DocRow:
    id: str
    content_hash: str | None
    file_name: str | None
    parent_id: str | None
    schema: str | None = None


@dataclass
class _CopyTask:
    content_hash: str
    file_name: str | None
    eid: str
    parent: str | None
    rel_path: str
    dest: Path
    renamed: bool


def _children_map(rows: list[DocRow]) -> dict[str | None, list[DocRow]]:
    by_parent: dict[str | None, list[DocRow]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)
    for kids in by_parent.values():
        # Deterministic sibling order (by id). NOTE: differs from API mode's ES
        # order, so the suffixed member of an in-folder name collision may differ
        # across modes (a documented cross-mode caveat; all bytes are preserved).
        kids.sort(key=lambda r: r.id)
    return by_parent


def walk_direct(
    rows: list[DocRow],
    archive,
    files_root: Path,
    manifest: Manifest,
    *,
    verify_hashes: bool = False,
    overwrite: bool = False,
    workers: int = 8,
) -> None:
    by_parent = _children_map(rows)
    alloc = PathAllocator()
    tasks: list[_CopyTask] = []
    _plan(by_parent, None, "", files_root, alloc, tasks)
    _execute(tasks, archive, manifest,
             verify_hashes=verify_hashes, overwrite=overwrite, workers=workers)


def _plan(by_parent, parent_id, rel_dir, files_root, alloc, tasks) -> None:
    for row in by_parent.get(parent_id, []):
        eid, content_hash, file_name = row.id, row.content_hash, row.file_name
        if content_hash is None:
            # Folder: allocate a dir name, recurse into children.
            name, _ = alloc.allocate(rel_dir, safe_component(file_name, eid), eid)
            sub_rel = posixpath.join(rel_dir, name) if rel_dir else name
            (files_root / sub_rel).mkdir(parents=True, exist_ok=True)
            _plan(by_parent, eid, sub_rel, files_root, alloc, tasks)
            continue
        # File (leaf): allocate a unique name; do NOT descend into its children.
        name, renamed = alloc.allocate(rel_dir, safe_component(file_name, eid), content_hash)
        rel_path = posixpath.join(rel_dir, name) if rel_dir else name
        tasks.append(_CopyTask(content_hash, file_name, eid, parent_id, rel_path,
                               files_root / rel_path, renamed))


def _execute(tasks, archive, manifest, *, verify_hashes, overwrite, workers) -> None:
    def run(task: _CopyTask) -> FileRecord:
        if task.dest.exists() and not overwrite:
            return FileRecord(task.eid, task.content_hash, task.file_name, task.rel_path,
                              task.parent, Status.OK, bytes=task.dest.stat().st_size)
        src = archive.locate(task.content_hash)
        if src is None:
            return FileRecord(task.eid, task.content_hash, task.file_name, None,
                              task.parent, Status.MISSING)
        nbytes, sha = archive.copy(src, task.dest, verify=verify_hashes)
        status = Status.OK
        if verify_hashes and sha != task.content_hash:
            status = Status.HASH_MISMATCH
        elif task.renamed:
            status = Status.COLLISION_RENAMED
        return FileRecord(task.eid, task.content_hash, task.file_name, task.rel_path,
                          task.parent, status, bytes=nbytes)

    if workers <= 1:
        records = [run(t) for t in tasks]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(run, tasks))
    for rec in records:
        manifest.add(rec)
