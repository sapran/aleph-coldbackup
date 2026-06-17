from __future__ import annotations

import json
from pathlib import Path

from .manifest import Manifest

_RESTORE_TEMPLATE = """# Restoring `{foreign_id}` from this cold backup

## Primary — clean re-ingest (recommended)

Re-ingest the reconstructed originals into a NEW collection. Aleph re-extracts and
regenerates all entities. New entity IDs; xref/profiles are not preserved.

```
aleph crawldir {backup_dir}/files -f {foreign_id}-restored
```

## Advanced — ID-preserving restore (insurance path, needs server-side archive access)

Recreate the collection with the SAME foreign_id, restore the original blobs into the
archive, then load the bundled entities. `--unsafe` is MANDATORY (the default `--safe`
strips contentHash and orphans every blob):

```
aleph load-entities {foreign_id} -i {backup_dir}/entities.ijson --unsafe --immutable
```

Note: on a client-only deployment you cannot write blobs into the server archive, so the
clean re-ingest path above is the practical restore.
"""


def write_entities_ijson(api, collection: dict, path: Path) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as fh:
        for entity in api.stream_entities(collection=collection):
            fh.write(json.dumps(entity, ensure_ascii=False))
            fh.write("\n")
            count += 1
    return count


def write_collection_json(collection: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(collection, fh, ensure_ascii=False, indent=2, sort_keys=True)


def write_manifest(manifest: Manifest, path: Path, **summary_kwargs) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest.to_dict(**summary_kwargs), fh,
                  ensure_ascii=False, indent=2)


def write_restore_md(collection: dict, path: Path) -> None:
    text = _RESTORE_TEMPLATE.format(
        foreign_id=collection.get("foreign_id", "COLLECTION"),
        backup_dir=".",
    )
    path.write_text(text, encoding="utf-8")
