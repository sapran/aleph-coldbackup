import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aleph_coldbackup.archive_fs import FsArchive
from aleph_coldbackup.client import make_api
from aleph_coldbackup.export import export_collection, export_collection_direct
from aleph_coldbackup.pgmeta import PgMetadata
from tests.equivalence import compare, scan_tree

pytestmark = pytest.mark.integration

EXAMPLE_DIR = os.environ.get("ALEPH_EXAMPLE_DIR")
EXAMPLE_COLLECTION = os.environ.get("ALEPH_EXAMPLE_COLLECTION", "example")
ARCHIVE_PATH = os.environ.get("COLDBACKUP_ARCHIVE_PATH")
DB_URI = os.environ.get("COLDBACKUP_DB_URI") or os.environ.get("ALEPH_DATABASE_URI")


def _written(manifest):
    return {(f["output_path"], f["content_hash"]) for f in manifest["files"]
            if f["status"] in ("ok", "collision-renamed")}


@pytest.fixture(scope="module")
def both(tmp_path_factory):
    if not os.environ.get("ALEPHCLIENT_HOST") or not os.environ.get("ALEPHCLIENT_API_KEY"):
        pytest.skip("ALEPHCLIENT_HOST/API_KEY not set")
    if not ARCHIVE_PATH or not Path(ARCHIVE_PATH).is_dir():
        pytest.skip("set COLDBACKUP_ARCHIVE_PATH to a readable archive root")
    if not DB_URI:
        pytest.skip("set COLDBACKUP_DB_URI (or ALEPH_DATABASE_URI)")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    api_out = tmp_path_factory.mktemp("api")
    direct_out = tmp_path_factory.mktemp("direct")
    api = make_api()
    api_manifest = export_collection(api, EXAMPLE_COLLECTION, api_out,
                                     verify_hashes=True, generated_at=now)
    pg = PgMetadata.connect(DB_URI)
    try:
        direct_manifest = export_collection_direct(
            api, FsArchive(Path(ARCHIVE_PATH)), EXAMPLE_COLLECTION, direct_out,
            fetch_documents=pg.fetch_documents, verify_hashes=True, generated_at=now)
    finally:
        pg.close()
    return {
        "api_files": api_out / EXAMPLE_COLLECTION / "files",
        "direct_files": direct_out / EXAMPLE_COLLECTION / "files",
        "api_manifest": api_manifest,
        "direct_manifest": direct_manifest,
    }


def test_cross_mode_trees_identical(both):
    assert scan_tree(both["api_files"]) == scan_tree(both["direct_files"])


def test_cross_mode_written_records_match(both):
    assert _written(both["direct_manifest"]) == _written(both["api_manifest"])


def test_direct_no_mismatch_no_not_walked(both):
    counts = both["direct_manifest"]["summary"]["counts"]
    assert counts.get("hash-mismatch", 0) == 0
    assert counts.get("not-walked", 0) == 0


@pytest.mark.skipif(not EXAMPLE_DIR, reason="set ALEPH_EXAMPLE_DIR for ground-truth check")
def test_direct_matches_ground_truth(both):
    report = compare(Path(EXAMPLE_DIR), both["direct_files"])
    assert report["content_only_in_example"] == []
    assert report["byte_mismatch"] == []
    assert report["missing_in_backup"] == []
    assert report["unexplained_extra"] == []
