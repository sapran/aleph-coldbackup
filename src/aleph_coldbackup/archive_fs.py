from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

# Linux FICLONE ioctl for reflink (btrfs/XFS/bcachefs). Best-effort; falls back to copy.
try:
    import fcntl

    _FICLONE = 0x40049409
except Exception:  # pragma: no cover - platform without fcntl
    fcntl = None  # type: ignore[assignment]
    _FICLONE = 0


def _sha1(path: Path) -> str:
    h = hashlib.sha1(usedforsecurity=False)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class FsArchive:
    """Reads original blobs from a servicelayer `file`-backend archive.

    Layout (servicelayer path_prefix): <root>/<h[0:2]>/<h[2:4]>/<h[4:6]>/<h>/<blob>.
    The blob filename is the sanitized original name (NOT always 'data'), so we take
    the first file in the hash directory, mirroring servicelayer's _locate_key.
    """

    def __init__(self, root: Path, *, mode: str = "copy") -> None:
        if mode not in ("copy", "reflink", "hardlink"):
            raise ValueError(f"unknown copy mode: {mode!r}")
        self.root = Path(root)
        self.mode = mode

    def _hash_dir(self, content_hash: str) -> Path:
        h = content_hash
        return self.root / h[0:2] / h[2:4] / h[4:6] / h

    def locate(self, content_hash: str) -> Path | None:
        d = self._hash_dir(content_hash)
        if not d.is_dir():
            return None
        # One blob per hash dir in practice; sort for a deterministic pick.
        for entry in sorted(d.iterdir()):
            if entry.is_file():
                return entry
        return None

    def copy(self, src: Path, dest: Path, *, verify: bool) -> tuple[int, str | None]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        if self.mode == "hardlink":
            self._hardlink(src, dest)
        elif self.mode == "reflink":
            self._reflink(src, dest)
        else:
            shutil.copyfile(src, dest)
        sha = _sha1(dest) if verify else None
        return dest.stat().st_size, sha

    @staticmethod
    def _hardlink(src: Path, dest: Path) -> None:
        try:
            os.link(src, dest)
        except OSError:
            shutil.copyfile(src, dest)

    @staticmethod
    def _reflink(src: Path, dest: Path) -> None:
        if fcntl is None:
            shutil.copyfile(src, dest)
            return
        try:
            with open(src, "rb") as s, open(dest, "wb") as d:
                fcntl.ioctl(d.fileno(), _FICLONE, s.fileno())
        except OSError:
            # FICLONE unsupported on this fs/kernel: discard the empty dest the
            # failed clone may have created, then fall back to a real copy.
            dest.unlink(missing_ok=True)
            shutil.copyfile(src, dest)
