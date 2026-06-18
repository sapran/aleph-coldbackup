from __future__ import annotations

from typing import Any

import psycopg

from .directwalk import DocRow

_DOCS_SQL = (
    "SELECT id, content_hash, parent_id, meta, schema "
    "FROM document WHERE collection_id = %s"
)


def _file_name(meta: Any) -> str | None:
    if not meta:
        return None
    value = meta.get("file_name")
    if isinstance(value, list):
        return max(value, key=len) if value else None
    return value


class PgMetadata:
    """Read-only PostgreSQL access to Aleph's `document` tree."""

    def __init__(self, conn) -> None:
        self._conn = conn

    @classmethod
    def connect(cls, dsn: str) -> "PgMetadata":
        conn = psycopg.connect(dsn, autocommit=True)
        # Enforce SELECT-only at the server. In autocommit mode psycopg3 does not
        # emit SET TRANSACTION per statement, so the read_only attribute alone is
        # not propagated; set the session GUC explicitly to make it effective.
        conn.execute("SET default_transaction_read_only = on")
        conn.read_only = True
        return cls(conn)

    def fetch_documents(self, collection_id: int | str) -> list[DocRow]:
        with self._conn.cursor() as cur:
            cur.execute(_DOCS_SQL, (int(collection_id),))
            rows = cur.fetchall()
        out: list[DocRow] = []
        for rid, content_hash, parent_id, meta, schema in rows:
            out.append(
                DocRow(
                    id=str(rid),
                    content_hash=content_hash or None,
                    file_name=_file_name(meta),
                    parent_id=(str(parent_id) if parent_id is not None else None),
                    schema=schema,
                )
            )
        return out

    def close(self) -> None:
        self._conn.close()
