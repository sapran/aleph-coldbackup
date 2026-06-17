import hashlib
import os
from datetime import datetime, timezone

import pytest

from aleph_coldbackup.client import make_api
from aleph_coldbackup.export import export_collection

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    if not os.environ.get("ALEPHCLIENT_HOST") or not os.environ.get("ALEPHCLIENT_API_KEY"):
        pytest.skip("ALEPHCLIENT_HOST/API_KEY not set")
    out = tmp_path_factory.mktemp("backup")
    api = make_api()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = export_collection(api, "example", out, verify_hashes=True, generated_at=now)
    return out / "example", manifest


def test_top_level_matches_five_entries(exported):
    base, _ = exported
    entries = {p.name for p in (base / "files").iterdir()}
    assert ".DS_Store" in entries
    assert {"protei", "mashtab", "lin_vmUnitek2_005056011d30",
            "win_DESKTOP-HD67VA2_1c1b0d363880"}.issubset(entries)


def test_no_hash_mismatches_and_no_not_walked(exported):
    _, manifest = exported
    counts = manifest["summary"]["counts"]
    assert counts.get("hash-mismatch", 0) == 0
    assert counts.get("not-walked", 0) == 0


def test_entities_stream_is_complete(exported):
    base, _ = exported
    lines = (base / "entities.ijson").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1100  # ~1156 entities in the example collection


def test_downloaded_bytes_match_content_hash(exported):
    base, manifest = exported
    ok = [f for f in manifest["files"] if f["status"] in ("ok", "collision-renamed")]
    assert ok, "expected downloaded files"
    sample = ok[0]
    blob = (base / "files" / sample["output_path"]).read_bytes()
    assert hashlib.sha1(blob).hexdigest() == sample["content_hash"]
