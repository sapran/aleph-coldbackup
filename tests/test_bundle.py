import json

from aleph_coldbackup.bundle import (
    write_entities_ijson, write_collection_json, write_manifest, write_restore_md,
)
from aleph_coldbackup.manifest import Manifest, FileRecord, Status
from tests.conftest import FakeAPI, make_entity


def test_entities_ijson_one_line_per_entity(tmp_path):
    stream = [make_entity("e1", content_hash="h1", file_name="a.txt"),
              make_entity("e2", content_hash="h2", file_name="b.txt")]
    api = FakeAPI(top=[], children={}, stream=stream)
    out = tmp_path / "entities.ijson"
    n = write_entities_ijson(api, api.get_collection("1"), out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert n == 2 and len(lines) == 2
    assert json.loads(lines[0])["id"] == "e1"


def test_collection_json_roundtrips(tmp_path):
    out = tmp_path / "collection.json"
    write_collection_json({"id": "1", "foreign_id": "example", "label": "Пример"}, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["foreign_id"] == "example" and data["label"] == "Пример"


def test_manifest_written(tmp_path):
    m = Manifest("example", "1")
    m.add(FileRecord("e1", "h1", "a.txt", "a.txt", None, Status.OK, bytes=3))
    out = tmp_path / "manifest.json"
    write_manifest(m, out, tool_version="0.1.0", alephclient_version="2.4.0",
                   host="http://h", generated_at="2026-06-17T00:00:00Z")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["files_written"] == 1


def test_restore_md_has_crawldir_recipe(tmp_path):
    out = tmp_path / "RESTORE.md"
    write_restore_md({"foreign_id": "example", "label": "example"}, out)
    text = out.read_text(encoding="utf-8")
    assert "aleph crawldir" in text
    assert "-f example-restored" in text
    assert "--unsafe" in text  # advanced path documented too
