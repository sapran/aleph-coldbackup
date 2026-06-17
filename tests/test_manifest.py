from aleph_coldbackup.manifest import Status, FileRecord, Manifest


def test_summary_counts_by_status():
    m = Manifest(foreign_id="example", collection_id="1")
    m.add(FileRecord("e1", "h1", "a.txt", "a.txt", None, Status.OK, bytes=10))
    m.add(FileRecord("e2", "h2", "b.txt", "d/b.txt", "e9", Status.OK, bytes=20))
    m.add(FileRecord("e3", "h3", "c.txt", None, "e9", Status.MISSING))
    m.add(FileRecord("e4", "h4", "x.txt", "d/x-0011.txt", "e9", Status.COLLISION_RENAMED, bytes=5))

    doc = m.to_dict(
        tool_version="0.1.0",
        alephclient_version="2.4.0",
        host="http://localhost:8080",
        generated_at="2026-06-17T00:00:00Z",
    )
    assert doc["collection"] == {"foreign_id": "example", "collection_id": "1"}
    assert doc["summary"]["counts"] == {
        "ok": 2, "collision-renamed": 1, "missing": 1,
    }
    assert doc["summary"]["files_written"] == 3       # ok + collision-renamed
    assert doc["summary"]["total_bytes"] == 35        # 10 + 20 + 5
    assert doc["summary"]["host"] == "http://localhost:8080"
    assert len(doc["files"]) == 4
    assert doc["files"][0]["status"] == "ok"
