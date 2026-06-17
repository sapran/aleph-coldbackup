import json
from pathlib import Path

import pytest

from aleph_coldbackup.export import export_collection, CollectionNotFound
from tests.conftest import FakeAPI, make_entity


def _fetch_ok(url, dest: Path):
    import hashlib
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = url.encode()
    dest.write_bytes(data)
    return len(data), hashlib.sha1(data).hexdigest()


def _api():
    top = [
        make_entity("dsstore", content_hash="h0", file_name=".DS_Store"),
        make_entity("f1", content_hash=None, file_name="protei"),
    ]
    children = {"f1": [make_entity("e2", content_hash="h2", file_name="YMD РЖД.xlsx", parent="f1")]}
    stream = top + children["f1"]
    return FakeAPI(top=top, children=children, stream=stream)


def test_export_produces_full_bundle(tmp_path):
    api = _api()
    manifest = export_collection(api, "example", tmp_path,
                                 fetch=_fetch_ok, generated_at="2026-06-17T00:00:00Z")
    base = tmp_path / "example"
    assert (base / "files" / ".DS_Store").exists()
    assert (base / "files" / "protei" / "YMD РЖД.xlsx").exists()
    assert (base / "entities.ijson").read_text(encoding="utf-8").count("\n") == 3
    assert json.loads((base / "collection.json").read_text(encoding="utf-8"))["foreign_id"] == "example"
    assert (base / "manifest.json").exists()
    assert (base / "RESTORE.md").exists()
    assert manifest["summary"]["files_written"] == 2


def test_missing_collection_raises(tmp_path):
    api = FakeAPI(top=[], children={})
    with pytest.raises(CollectionNotFound):
        export_collection(api, "nope", tmp_path, fetch=_fetch_ok,
                          generated_at="2026-06-17T00:00:00Z")
