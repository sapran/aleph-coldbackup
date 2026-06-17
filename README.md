# aleph-coldbackup

Export one [Aleph](https://github.com/alephdata/aleph) investigation into a
self-contained, **re-ingestable cold backup** — the original ingested files
reconstructed in their folder structure, plus the full entity graph and metadata.

**Client-side only.** It talks to Aleph purely over the HTTP API: all it needs is a
host URL and an API key. No shell access to the Aleph containers, no archive volume,
no database. This is the whole point — you can back up a hosted/managed Aleph you
don't operate.

It exists for one scenario: you ingested data into Aleph, **lost the original source
files**, and want them back out — in their original layout — as a durable archive you
can re-ingest if you ever lose the data or the Aleph instance itself.

## How Aleph stores your data (the 30-second model)

Aleph keeps ingested data in three tiers:

| Tier | Holds | In the backup? |
|------|-------|----------------|
| **Elasticsearch** | the search index | No — it's derived, rebuilt on re-ingest |
| **PostgreSQL** | entity/collection metadata, folder tree | Yes — as `entities.ijson` + `collection.json` |
| **servicelayer archive** | the **raw original bytes**, content-addressed by SHA-1 | Yes — downloaded into `files/` |

The original bytes live **only** in the archive, addressed by each document's
`contentHash`. This tool walks the collection's folder tree (the `Document` entities
linked by `parent`), downloads each file's original bytes, and rebuilds the directory
structure on disk — while also capturing the entity stream and collection metadata so
the backup is a faithful, re-ingestable record.

## Install

Requires Python ≥ 3.11 and [`uv`](https://github.com/astral-sh/uv).

```bash
uv venv && uv pip install -e .
```

## Usage

```bash
export ALEPHCLIENT_HOST=https://your-aleph          # the Aleph base URL
export ALEPHCLIENT_API_KEY=...                       # a key with READ access to the collection

uv run aleph-coldbackup export <foreign_id> --out ./backups --verify-hashes
```

`<foreign_id>` is the collection's stable identifier (visible in the UI / API, e.g.
`example`). Flags:

| Flag | Effect |
|------|--------|
| `--out <dir>` | output root (required); the backup lands in `<out>/<foreign_id>/` |
| `--verify-hashes` | re-compute each downloaded file's SHA-1 and check it equals its `contentHash` |
| `--overwrite` | re-download files even if a same-size file already exists (otherwise existing files are skipped, making re-runs resumable) |

On completion it prints a one-line summary, e.g.:

```
exported example: files_written=379 bytes=47066373 missing=0 collisions=0 not_walked=0 hash_mismatch=0
```

## What it produces

```
<out>/<foreign_id>/
  files/            the original files, in their original folder tree, with true
                    (Unicode-faithful) names
  entities.ijson    the complete FollowTheMoney entity stream (JSON-lines, uncapped)
  collection.json   collection metadata (foreign_id, label, category, languages, …)
  manifest.json     per-file records + a run summary
  RESTORE.md        restore recipes (generated per backup)
```

### The manifest

`manifest.json` records every file the walker touched, plus a summary (counts, total
bytes, tool/alephclient versions, host, timestamp). Each file gets a `status`:

| Status | Meaning |
|--------|---------|
| `ok` | downloaded successfully |
| `collision-renamed` | two files shared a name in the same folder; the later one got a `-<hash[:8]>` suffix |
| `missing` | the blob could not be downloaded (a dangling `contentHash`, after retries) — recorded, never silently dropped |
| `hash-mismatch` | `--verify-hashes` was on and the bytes didn't match the `contentHash` |
| `not-walked` | a folder had more direct children than the search window could return; the count is recorded so you know coverage was incomplete |

The manifest is the backup's self-description: it tells you exactly what was captured
and flags anything that wasn't.

## Restore

**Primary — clean re-ingest (recommended).** Re-feed the reconstructed files into a
**new** collection; Aleph re-extracts and regenerates all entities:

```bash
aleph crawldir <out>/<foreign_id>/files -f <foreign_id>-restored
```

Robust and version-independent. Entity IDs and any cross-reference/profile decisions
are *not* preserved (they're regenerated from scratch).

**Advanced — ID-preserving (insurance path).** Recreate the collection with the
**same** `foreign_id`, restore the blobs into the archive, then load the bundled
entity stream:

```bash
aleph load-entities <foreign_id> -i <out>/<foreign_id>/entities.ijson --unsafe --immutable
```

> `--unsafe` is **mandatory** — the default `--safe` strips `contentHash` and orphans
> every blob. This path also requires server-side archive access to place the blobs,
> so on a client-only deployment the clean re-ingest above is the practical route.

Each backup's `RESTORE.md` carries these commands with its own paths filled in.

## What counts as an "original file"

The tool walks the `Document` folder tree and downloads a node's bytes **iff it has a
`contentHash`** (folders have none). It deliberately does **not** descend into a
file's children — so an email's `.eml` is saved whole rather than exploded into its
extracted attachments, and derived `Page`/`PlainText` artifacts (which aren't real
uploads) are excluded. The result mirrors what you originally ingested.

## Known-acceptable differences from the source tree

When comparing a backup against the original directory it was ingested from, a few
benign differences are expected (they're not data loss):

- **Filename normalization.** macOS stores names in NFD; Aleph returns NFC. Same name,
  same bytes — but compare with Unicode normalization or identical Cyrillic names look
  "different".
- **Symlinks become real files.** Aleph ingests a symlink's *target bytes* as a normal
  file, so symlinks reappear as regular file copies, not links.
- **Empty directories vanish.** A directory with no files has no entity in Aleph, so it
  can't be reconstructed.
- **POSIX metadata isn't preserved.** Aleph stores bytes only — no permissions, owners,
  or mtimes.

## Robustness & security

- **No silent data loss.** Downloads retry transient errors (HTTP 429/5xx, dropped
  connections) with backoff, honoring `Retry-After`. A file is only marked `missing`
  after retries are exhausted — and that's recorded in the manifest, never swallowed.
  A genuine 404 (dangling blob) fails fast.
- **Credential scoping.** The API key is sent only to the configured Aleph host
  (matched by network location); it is never attached to an off-host (e.g. presigned
  CDN) download URL. TLS verification is always on. Keep your key in an env var or a
  gitignored env file — never on a command line or in a commit.

## Development

```bash
uv venv && uv pip install -e ".[dev]"

uv run pytest                  # unit tests (fast, no network)
uv run ruff check src tests
uv run mypy src tests

# live integration + equivalence tests (need a running Aleph + credentials):
export ALEPHCLIENT_HOST=https://your-aleph
export ALEPHCLIENT_API_KEY=...
export ALEPH_EXAMPLE_DIR=/path/to/the/original/source/dir   # ground truth for equivalence
export ALEPH_EXAMPLE_COLLECTION=example                     # its collection foreign_id
uv run pytest -m integration -s
```

The equivalence suite is the strongest check: it exports a known collection and
asserts the reconstructed tree is byte-for-byte equivalent to the original source
directory (modulo the known-acceptable differences above) — set `ALEPH_EXAMPLE_DIR`
to that source directory and `ALEPH_EXAMPLE_COLLECTION` to its `foreign_id`.

## Limitations

- Reconstructs the **document tree** (files + folders). User-curated cross-reference /
  profile decisions are not exported (the clean re-ingest path regenerates entities
  anyway); `entities.ijson` preserves the entity graph for the advanced restore path.
- A single folder with more direct children than Aleph's search window can page
  through is reported as `not-walked` rather than silently truncated.
- Built against Aleph 4.1.x. Upstream Aleph is end-of-life; pin to your deployment's
  version.
