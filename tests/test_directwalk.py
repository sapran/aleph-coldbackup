import hashlib

from aleph_coldbackup.directwalk import walk_direct
from aleph_coldbackup.manifest import Manifest, Status
from tests.conftest import FakeArchive, make_doc


def _run(rows, blobs, tmp_path, *, verify=False, overwrite=True, workers=1, missing=frozenset()):
    m = Manifest("example", "1")
    walk_direct(rows, FakeArchive(blobs, missing=missing), tmp_path, m,
                verify_hashes=verify, overwrite=overwrite, workers=workers)
    return m


def test_single_top_level_file(tmp_path):
    rows = [make_doc("e1", content_hash="h1", file_name="a.txt")]
    m = _run(rows, {"h1": b"A"}, tmp_path)
    assert (tmp_path / "a.txt").read_bytes() == b"A"
    rec = [r for r in m.records if r.status is Status.OK][0]
    assert rec.output_path == "a.txt"


def test_nested_folder(tmp_path):
    rows = [
        make_doc("f1", content_hash=None, file_name="dir"),
        make_doc("e2", content_hash="h2", file_name="b.txt", parent_id="f1"),
    ]
    m = _run(rows, {"h2": b"B"}, tmp_path)
    assert (tmp_path / "dir" / "b.txt").read_bytes() == b"B"
    assert {r.output_path for r in m.records if r.status is Status.OK} == {"dir/b.txt"}
    assert len([r for r in m.records if r.status is Status.OK]) == 1


def test_file_children_are_not_descended(tmp_path):
    # A child whose parent is a FILE must not be emitted (leaf rule).
    rows = [
        make_doc("file1", content_hash="h1", file_name="mail.eml"),
        make_doc("page1", content_hash="hp", file_name="page.txt", parent_id="file1"),
    ]
    m = _run(rows, {"h1": b"M", "hp": b"P"}, tmp_path)
    paths = {r.output_path for r in m.records if r.status is Status.OK}
    assert paths == {"mail.eml"}
    assert not (tmp_path / "page.txt").exists()


def test_collision_renamed(tmp_path):
    rows = [
        make_doc("e1", content_hash="aaaaaaaa1111", file_name="x.txt"),
        make_doc("e2", content_hash="bbbbbbbb2222", file_name="x.txt"),
    ]
    m = _run(rows, {"aaaaaaaa1111": b"1", "bbbbbbbb2222": b"2"}, tmp_path)
    assert sorted(r.output_path for r in m.records) == ["x-bbbbbbbb.txt", "x.txt"]
    assert any(r.status is Status.COLLISION_RENAMED for r in m.records)


def test_missing_blob_marked_missing(tmp_path):
    rows = [make_doc("e1", content_hash="h1", file_name="a.txt")]
    m = _run(rows, {}, tmp_path, missing={"h1"})
    assert m.records[0].status is Status.MISSING
    assert not (tmp_path / "a.txt").exists()


def test_hash_mismatch_when_verify(tmp_path):
    # content_hash "h1" but the bytes hash to something else -> mismatch under verify.
    rows = [make_doc("e1", content_hash="h1", file_name="a.txt")]
    m = _run(rows, {"h1": b"not-h1"}, tmp_path, verify=True)
    assert m.records[0].status is Status.HASH_MISMATCH


def test_hash_ok_when_verify_and_match(tmp_path):
    data = b"good"
    h = hashlib.sha1(data).hexdigest()
    rows = [make_doc("e1", content_hash=h, file_name="a.txt")]
    m = _run(rows, {h: data}, tmp_path, verify=True)
    assert m.records[0].status is Status.OK


def test_skip_existing_without_overwrite(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"old")
    rows = [make_doc("e1", content_hash="h1", file_name="a.txt")]
    m = _run(rows, {"h1": b"new"}, tmp_path, overwrite=False)
    assert m.records[0].status is Status.OK
    assert (tmp_path / "a.txt").read_bytes() == b"old"  # not overwritten


def test_parallel_nested_and_collision_deterministic(tmp_path_factory):
    # A nested folder with several same-named files (forcing collisions) plus a
    # top-level file. Allocation must stay single-threaded, so output is identical
    # regardless of worker count.
    rows = [
        make_doc("d1", content_hash=None, file_name="dir"),
        *[make_doc(f"e{i}", content_hash=f"h{i}", file_name="x.txt", parent_id="d1")
          for i in range(5)],
        make_doc("top", content_hash="htop", file_name="top.txt"),
    ]
    blobs = {f"h{i}": f"d{i}".encode() for i in range(5)}
    blobs["htop"] = b"top"

    def run(workers):
        out = tmp_path_factory.mktemp(f"w{workers}")
        m = Manifest("example", "1")
        walk_direct(rows, FakeArchive(blobs), out, m, workers=workers)
        files = {p.relative_to(out).as_posix(): p.read_bytes()
                 for p in out.rglob("*") if p.is_file()}
        recs = sorted((r.output_path, r.content_hash, r.status.value) for r in m.records)
        return files, recs

    assert run(1) == run(8)


def test_parallel_workers_produce_same_output(tmp_path):
    rows = [make_doc(f"e{i}", content_hash=f"h{i}", file_name=f"f{i}.txt") for i in range(20)]
    blobs = {f"h{i}": f"data{i}".encode() for i in range(20)}
    m = _run(rows, blobs, tmp_path, workers=8)
    written = {r.output_path for r in m.records if r.status is Status.OK}
    assert written == {f"f{i}.txt" for i in range(20)}
