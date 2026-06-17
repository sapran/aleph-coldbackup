from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from enum import Enum


class Status(str, Enum):
    OK = "ok"
    MISSING = "missing"
    COLLISION_RENAMED = "collision-renamed"
    NOT_WALKED = "not-walked"
    HASH_MISMATCH = "hash-mismatch"


_WRITTEN = {Status.OK, Status.COLLISION_RENAMED}


@dataclass
class FileRecord:
    entity_id: str
    content_hash: str | None
    file_name: str | None
    output_path: str | None
    parent: str | None
    status: Status
    bytes: int | None = None
    note: str | None = None


class Manifest:
    def __init__(self, foreign_id: str, collection_id: str) -> None:
        self.foreign_id = foreign_id
        self.collection_id = collection_id
        self.records: list[FileRecord] = []

    def add(self, record: FileRecord) -> None:
        self.records.append(record)

    def to_dict(
        self,
        *,
        tool_version: str,
        alephclient_version: str,
        host: str,
        generated_at: str,
    ) -> dict:
        counts = Counter(r.status.value for r in self.records)
        files_written = sum(1 for r in self.records if r.status in _WRITTEN)
        total_bytes = sum(r.bytes or 0 for r in self.records if r.status in _WRITTEN)
        files = []
        for r in self.records:
            d = asdict(r)
            d["status"] = r.status.value
            files.append(d)
        return {
            "collection": {
                "foreign_id": self.foreign_id,
                "collection_id": self.collection_id,
            },
            "summary": {
                "counts": dict(counts),
                "files_written": files_written,
                "total_bytes": total_bytes,
                "tool_version": tool_version,
                "alephclient_version": alephclient_version,
                "host": host,
                "generated_at": generated_at,
            },
            "files": files,
        }
