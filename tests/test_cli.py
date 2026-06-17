from aleph_coldbackup import cli
from tests.conftest import FakeAPI, make_entity


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
