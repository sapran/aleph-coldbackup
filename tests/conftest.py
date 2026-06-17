from __future__ import annotations

from typing import Any

import pytest


def make_entity(eid, *, schema="Document", content_hash=None, file_name=None,
                parent=None, has_file=True):
    props: dict[str, Any] = {}
    if content_hash is not None:
        props["contentHash"] = [content_hash]
    if file_name is not None:
        props["fileName"] = [file_name]
    if parent is not None:
        props["parent"] = [parent]
    links = {}
    if content_hash is not None and has_file:
        links["file"] = f"/api/2/archive?token=tok-{eid}"
    return {"id": eid, "schema": schema, "properties": props, "links": links}


class FakeResultSet(list):
    """A list that also reports a `total` (may exceed len to simulate truncation)."""
    def __init__(self, items, total=None):
        super().__init__(items)
        self._total = len(items) if total is None else total

    def __len__(self):  # mimics alephclient APIResultSet.__len__ == total
        return self._total

    def __iter__(self):
        return list.__iter__(self)


class FakeAPI:
    base_url = "http://test/api/2/"

    def __init__(self, top, children, collection=None, stream=None):
        self._top = top                # list[entity]
        self._children = children      # dict[parent_id -> FakeResultSet|list]
        self._collection = collection or {"id": "1", "foreign_id": "example",
                                          "label": "example"}
        self._stream = stream or []

    def search(self, query, schema=None, schemata=None, filters=None, params=None):
        filters = filters or {}
        fdict = dict(filters)
        params = params or {}
        if params.get("empty:properties.parent") == "true":
            return FakeResultSet(self._top)
        parent = fdict.get("properties.parent")
        res = self._children.get(parent, [])
        return res if isinstance(res, FakeResultSet) else FakeResultSet(res)

    def get_collection_by_foreign_id(self, fid):
        return self._collection if fid == self._collection["foreign_id"] else None

    def get_collection(self, cid):
        return self._collection

    def stream_entities(self, collection=None):
        return iter(self._stream)


@pytest.fixture
def make_entity_fixture():
    return make_entity
