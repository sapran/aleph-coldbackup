import hashlib
from pathlib import Path

import pytest

from aleph_coldbackup.archive_fs import FsArchive


def _make_blob(root: Path, content_hash: str, data: bytes, name: str = "orig.bin") -> Path:
    d = root / content_hash[0:2] / content_hash[2:4] / content_hash[4:6] / content_hash
    d.mkdir(parents=True)
    (d / name).write_bytes(data)
    return d / name


def test_locate_resolves_sharded_path(tmp_path):
    h = "abcdef0123456789" + "0" * 24
    blob = _make_blob(tmp_path, h, b"hello", name="orig.txt")
    assert FsArchive(tmp_path).locate(h) == blob


def test_locate_returns_none_when_absent(tmp_path):
    assert FsArchive(tmp_path).locate("ff" * 20) is None


def test_copy_default_copies_bytes_no_hash_unless_verify(tmp_path):
    h = "11" * 20
    _make_blob(tmp_path, h, b"payload")
    arch = FsArchive(tmp_path)
    src = arch.locate(h)
    n, sha = arch.copy(src, tmp_path / "out" / "f.bin", verify=False)
    assert (tmp_path / "out" / "f.bin").read_bytes() == b"payload"
    assert n == 7 and sha is None


def test_copy_verify_returns_sha1(tmp_path):
    h = "22" * 20
    _make_blob(tmp_path, h, b"payload")
    arch = FsArchive(tmp_path)
    n, sha = arch.copy(arch.locate(h), tmp_path / "f.bin", verify=True)
    assert n == 7
    assert sha == hashlib.sha1(b"payload").hexdigest()


def test_hardlink_shares_inode(tmp_path):
    h = "33" * 20
    src = _make_blob(tmp_path, h, b"data")
    arch = FsArchive(tmp_path, mode="hardlink")
    dest = tmp_path / "hl.bin"
    arch.copy(arch.locate(h), dest, verify=False)
    assert dest.read_bytes() == b"data"
    assert dest.stat().st_ino == src.stat().st_ino


def test_reflink_falls_back_to_valid_copy(tmp_path):
    # On non-CoW filesystems FICLONE fails and we fall back to a real copy.
    h = "44" * 20
    _make_blob(tmp_path, h, b"reflinked")
    arch = FsArchive(tmp_path, mode="reflink")
    dest = tmp_path / "rl.bin"
    n, _ = arch.copy(arch.locate(h), dest, verify=False)
    assert dest.read_bytes() == b"reflinked" and n == 9


def test_unknown_mode_rejected(tmp_path):
    with pytest.raises(ValueError):
        FsArchive(tmp_path, mode="nope")
