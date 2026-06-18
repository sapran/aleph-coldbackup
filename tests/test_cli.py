import psycopg

from aleph_coldbackup import cli
from tests.conftest import FakeAPI, FakeArchive, make_doc, make_entity


def test_export_command_runs(tmp_path, monkeypatch, capsys):
    api = FakeAPI(top=[make_entity("e1", content_hash="h1", file_name="a.txt")],
                  children={})
    monkeypatch.setattr(cli, "make_api", lambda: api)
    monkeypatch.setattr(
        "aleph_coldbackup.cli.http_fetch",
        lambda url, dest: (dest.write_bytes(b"x"), (1, "0" * 40))[1],
    )
    rc = cli.main(["export", "example", "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "example" / "manifest.json").exists()
    assert "files_written" in capsys.readouterr().out


def test_missing_collection_returns_2(tmp_path, monkeypatch):
    api = FakeAPI(top=[], children={})
    monkeypatch.setattr(cli, "make_api", lambda: api)
    rc = cli.main(["export", "nope", "--out", str(tmp_path)])
    assert rc == 2


class _FakePg:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    @classmethod
    def make(cls, rows):
        return cls(rows)

    def fetch_documents(self, cid):
        return self._rows

    def close(self):
        self.closed = True


def _wire_direct(monkeypatch, rows, blobs):
    api = FakeAPI(top=[], children={},
                  collection={"id": "1", "foreign_id": "example", "label": "example"},
                  stream=[make_entity("e1", content_hash="h1", file_name="a.txt")])
    monkeypatch.setattr(cli, "make_api", lambda: api)
    monkeypatch.setattr(cli, "PgMetadata",
                        type("PG", (), {"connect": staticmethod(lambda dsn: _FakePg(rows))}))
    monkeypatch.setattr(cli, "FsArchive", lambda path, mode="copy": FakeArchive(blobs))


def test_direct_requires_archive_path(tmp_path, monkeypatch):
    _wire_direct(monkeypatch, [], {})
    monkeypatch.setenv("COLDBACKUP_DB_URI", "postgresql://x")
    rc = cli.main(["export", "example", "--out", str(tmp_path), "--direct"])
    assert rc == 2


def test_direct_requires_db_uri(tmp_path, monkeypatch):
    _wire_direct(monkeypatch, [], {})
    monkeypatch.delenv("COLDBACKUP_DB_URI", raising=False)
    monkeypatch.delenv("ALEPH_DATABASE_URI", raising=False)
    rc = cli.main(["export", "example", "--out", str(tmp_path),
                   "--direct", "--archive-path", "/tmp/archive"])
    assert rc == 2


def test_direct_export_runs(tmp_path, monkeypatch):
    rows = [make_doc("d1", content_hash="h1", file_name="a.txt")]
    _wire_direct(monkeypatch, rows, {"h1": b"A"})
    monkeypatch.setenv("COLDBACKUP_DB_URI", "postgresql://x")
    rc = cli.main(["export", "example", "--out", str(tmp_path),
                   "--direct", "--archive-path", "/tmp/archive"])
    assert rc == 0
    assert (tmp_path / "example" / "manifest.json").exists()
    assert (tmp_path / "example" / "files" / "a.txt").read_bytes() == b"A"


def test_direct_db_connection_failure_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "make_api", lambda: FakeAPI(top=[], children={}))

    class _BoomPg:
        @staticmethod
        def connect(dsn):
            raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(cli, "PgMetadata", _BoomPg)
    monkeypatch.setattr(cli, "FsArchive", lambda path, mode="copy": FakeArchive({}))
    monkeypatch.setenv("COLDBACKUP_DB_URI", "postgresql://x")
    rc = cli.main(["export", "example", "--out", str(tmp_path),
                   "--direct", "--archive-path", "/tmp/archive"])
    assert rc == 2
