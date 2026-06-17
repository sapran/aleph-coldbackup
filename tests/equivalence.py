from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path


def _sha1(path: Path) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(root: Path, path: Path) -> str:
    # NFC-normalize so macOS NFD on-disk names compare equal to Aleph's NFC names.
    return unicodedata.normalize("NFC", path.relative_to(root).as_posix())


def scan_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        out[_rel(root, path)] = _sha1(path)
    return out


def symlink_targets(root: Path) -> set[str]:
    """NFC relative paths of symlinks in `root` that resolve to files.
    Aleph ingests these as real file copies, so they show up as 'extra'."""
    out: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            if path.resolve().is_file():
                out.add(_rel(root, path))
        except OSError:
            pass
    return out


def compare(example_dir: Path, backup_files_dir: Path) -> dict:
    src = scan_tree(example_dir)
    dst = scan_tree(backup_files_dir)
    src_paths, dst_paths = set(src), set(dst)
    byte_mismatch = sorted(p for p in (src_paths & dst_paths) if src[p] != dst[p])
    src_hashes, dst_hashes = set(src.values()), set(dst.values())
    extra = dst_paths - src_paths
    return {
        "matched": sorted(p for p in (src_paths & dst_paths) if src[p] == dst[p]),
        "missing_in_backup": sorted(src_paths - dst_paths),
        "extra_in_backup": sorted(extra),
        "unexplained_extra": sorted(extra - symlink_targets(example_dir)),
        "byte_mismatch": byte_mismatch,
        "content_only_in_example": sorted(src_hashes - dst_hashes),
    }
