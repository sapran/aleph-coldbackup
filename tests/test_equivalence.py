import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aleph_coldbackup.client import make_api
from aleph_coldbackup.export import export_collection
from tests.equivalence import compare

pytestmark = pytest.mark.integration

EXAMPLE_DIR = os.environ.get("ALEPH_EXAMPLE_DIR")
EXAMPLE_COLLECTION = os.environ.get("ALEPH_EXAMPLE_COLLECTION", "example")


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    if not os.environ.get("ALEPHCLIENT_HOST") or not os.environ.get("ALEPHCLIENT_API_KEY"):
        pytest.skip("ALEPHCLIENT_HOST/API_KEY not set")
    if not EXAMPLE_DIR:
        pytest.skip("set ALEPH_EXAMPLE_DIR to the ground-truth source directory")
    example_dir = Path(EXAMPLE_DIR)
    if not example_dir.exists():
        pytest.skip(f"ALEPH_EXAMPLE_DIR not found: {example_dir}")
    out = tmp_path_factory.mktemp("backup")
    api = make_api()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    export_collection(api, EXAMPLE_COLLECTION, out, generated_at=now)
    return compare(example_dir, out / EXAMPLE_COLLECTION / "files")


def test_no_bytes_lost(report):
    # Every distinct file content in example/ must be present in the backup.
    assert report["content_only_in_example"] == []


def test_no_byte_mismatch(report):
    assert report["byte_mismatch"] == []


def test_no_missing_after_nfc_normalization(report):
    # With NFC normalization, every example/ regular file maps to a backup file.
    assert report["missing_in_backup"] == []


def test_extras_are_only_symlink_targets(report):
    # The only legitimate extras are symlinks that Aleph ingested as real files.
    # ANY other extra would mean compound-extraction leakage (e.g. an email's
    # attachment materialized as a separate file) — that must be zero.
    print("extra_in_backup:", report["extra_in_backup"][:50])
    print("unexplained_extra:", report["unexplained_extra"])
    assert report["unexplained_extra"] == []
