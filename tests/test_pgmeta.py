from aleph_coldbackup.directwalk import DocRow
from aleph_coldbackup.pgmeta import PgMetadata


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.cursor_obj = _FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def test_fetch_documents_maps_rows():
    rows = [
        (10, None, None, {"file_name": "dir"}, "Folder"),
        (11, "abc", 10, {"file_name": ["short", "longer.txt"]}, "Document"),
        (12, "def", 10, None, "Document"),
    ]
    pg = PgMetadata(_FakeConn(rows))
    docs = pg.fetch_documents(1)
    assert docs[0] == DocRow(id="10", content_hash=None, file_name="dir",
                             parent_id=None, schema="Folder")
    assert docs[1] == DocRow(id="11", content_hash="abc", file_name="longer.txt",
                             parent_id="10", schema="Document")
    assert docs[2].file_name is None and docs[2].content_hash == "def"


def test_fetch_documents_passes_int_collection_id():
    conn = _FakeConn([])
    PgMetadata(conn).fetch_documents("7")
    assert conn.cursor_obj.executed[1] == (7,)


def test_close_closes_connection():
    conn = _FakeConn([])
    PgMetadata(conn).close()
    assert conn.closed is True
