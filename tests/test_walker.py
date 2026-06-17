import hashlib
from pathlib import Path

from aleph_coldbackup.manifest import Manifest, Status
from aleph_coldbackup.walker import walk_collection
from tests.conftest import FakeAPI, FakeResultSet, make_entity


def _fetch_ok(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = url.encode()
    dest.write_bytes(data)
    return len(data), hashlib.sha1(data).hexdigest()


def run(api, tmp_path, *, fetch=_fetch_ok, verify=False):
    m = Manifest("example", "1")
    walk_collection(api, api.get_collection("1"), tmp_path, m,
                    fetch=fetch, verify_hashes=verify, overwrite=True)
    return m


def test_single_top_level_file(tmp_path):
    api = FakeAPI(top=[make_entity("e1", content_hash="h1", file_name="a.txt")],
                  children={})
    m = run(api, tmp_path)
    assert (tmp_path / "a.txt").exists()
    rec = m.records[0]
    assert rec.status is Status.OK and rec.output_path == "a.txt"


def test_nested_folder(tmp_path):
    top = [make_entity("f1", content_hash=None, file_name="dir")]
    children = {"f1": [make_entity("e2", content_hash="h2", file_name="b.txt", parent="f1")]}
    api = FakeAPI(top=top, children=children)
    m = run(api, tmp_path)
    assert (tmp_path / "dir" / "b.txt").exists()
    paths = {r.output_path for r in m.records if r.status is Status.OK}
    assert paths == {"dir/b.txt"}


def test_collision_renamed(tmp_path):
    top = [
        make_entity("e1", content_hash="aaaaaaaa1111", file_name="x.txt"),
        make_entity("e2", content_hash="bbbbbbbb2222", file_name="x.txt"),
    ]
    api = FakeAPI(top=top, children={})
    m = run(api, tmp_path)
    names = sorted(r.output_path for r in m.records)
    assert names == ["x-bbbbbbbb.txt", "x.txt"]
    assert any(r.status is Status.COLLISION_RENAMED for r in m.records)


def test_dangling_blob_marked_missing(tmp_path):
    def boom(url, dest):
        from aleph_coldbackup.client import FetchError
        raise FetchError("404")
    api = FakeAPI(top=[make_entity("e1", content_hash="h1", file_name="a.txt")],
                  children={})
    m = run(api, tmp_path, fetch=boom)
    assert m.records[0].status is Status.MISSING
    assert not (tmp_path / "a.txt").exists()


def test_hash_mismatch_when_verify(tmp_path):
    def wrong(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x")
        return 1, "0000000000000000000000000000000000000000"
    api = FakeAPI(top=[make_entity("e1", content_hash="h1", file_name="a.txt")],
                  children={})
    m = run(api, tmp_path, fetch=wrong, verify=True)
    assert m.records[0].status is Status.HASH_MISMATCH


def test_truncated_folder_records_not_walked(tmp_path):
    # folder f1 reports total=5 but returns only 2 children
    kids = FakeResultSet(
        [make_entity("e2", content_hash="h2", file_name="b.txt", parent="f1"),
         make_entity("e3", content_hash="h3", file_name="c.txt", parent="f1")],
        total=5,
    )
    api = FakeAPI(top=[make_entity("f1", content_hash=None, file_name="dir")],
                  children={"f1": kids})
    m = run(api, tmp_path)
    not_walked = [r for r in m.records if r.status is Status.NOT_WALKED]
    assert len(not_walked) == 1
    assert not_walked[0].note == "3 of 5 children unreachable (search window)"
