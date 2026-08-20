# Implementation notes

Findings parked during other work. Each entry says what, where, and why it was
not fixed at the time.

## ruff 0.16 flags 22 pre-existing violations

**What.** ruff 0.16 widened its default rule set. Running `ruff check src tests`
under 0.16.4 reports 22 errors that 0.15.17 does not: 7 `I001` (unsorted
imports), 5 `RUF059` (unused unpacked variable), 4 `UP017` (`datetime.timezone.utc`
→ `datetime.UTC`), 2 `UP037` (quoted annotation), and one each of `BLE001`,
`RUF015`, `RUF100`, `UP035`. 15 are auto-fixable.

**Where.** Across `src/aleph_coldbackup/` and `tests/`. The four non-auto-fixable
ones are worth reading before any bulk fix:

- `archive_fs.py:13` `BLE001` — the `except Exception` guarding the optional
  `fcntl` import. Deliberate: platforms without `fcntl` must fall back to a plain
  copy. Needs a targeted suppression, not a rewrite.
- `client.py:111` `RUF100` — the existing `# noqa: BLE001` is now *unused*, because
  0.16 no longer considers that handler blind. Removing the directive is correct,
  but the comment beside it still documents real intent and should stay.
- `walker.py:5` `UP035` — import `Callable` from `collections.abc`.
- `tests/test_directwalk.py:19` `RUF015` — prefer `next(...)` over a single-element
  slice.

**Why parked.** Found while adding CI during the open-sourcing change (2026-08-20).
Fixing it means touching most files in the project for style reasons unrelated to
that change, which would inflate a diff whose purpose is licensing and release
scaffolding. Instead `pyproject.toml` caps ruff at `<0.16`, and Dependabot is set
`versioning-strategy: lockfile-only` so it cannot quietly widen that cap. Lifting it
is therefore a deliberate act, to be done together with the fixes below.

**To pick up.** Bump the cap, run `ruff check src tests --fix` for the 15
auto-fixable ones, then hand-fix the four listed above.

## Dev tooling ships in published package metadata

**What.** `[project.optional-dependencies] dev` puts the dev toolchain into the
wheel: `METADATA` carries `Requires-Dist: ruff<0.16,>=0.15.17; extra == 'dev'`.
Anyone installing `aleph-coldbackup[dev]`, or resolving alongside a project needing
ruff >=0.16, inherits a constraint that exists only for this repo's CI. PEP 735
`[dependency-groups]` (supported by uv via `uv sync --group dev`) keeps dev tooling
out of the distribution entirely.

**Where.** `pyproject.toml`, the `dev` extra.

**Why parked.** Raised in review of the open-sourcing PR (2026-08-20). The `dev`
extra predates that change, which only tightened one version inside it. Converting
to dependency-groups changes the documented install command in both `README.md` and
`CONTRIBUTING.md` plus the CI install step — a toolchain migration, not release
scaffolding.

## mypy and pytest are unpinned while ruff is capped

**What.** The argument for capping ruff — a tool release reddening CI on a day with
no code change — applies equally to mypy and pytest, which float. `uv.lock` records
mypy 2.1.0 while the install path resolves 2.3.1 today.

**Where.** `pyproject.toml`, the `dev` extra.

**Why parked.** Ruff had a demonstrated, reproduced failure; mypy 2.3.1 and pytest
9.1.1 both pass. Pinning them now would be speculative. The real fix is for CI to
install from `uv.lock` (`uv sync --extra dev --locked`) rather than resolving fresh,
which would pin all three at once; CI currently only asserts the lock is *in sync*
via `uv lock --check`, it does not install from it.

## CONTRIBUTING.md duplicates setup instructions from README.md

**What.** The setup command, the three check commands, and the integration exports
appear in both files. Two copies drift: the CONTRIBUTING copy was already missing
`COLDBACKUP_ARCHIVE_PATH` and `COLDBACKUP_DB_URI` when first written.

**Where.** `CONTRIBUTING.md` vs `README.md` (Development section).

**Why parked.** Raised in review of the open-sourcing PR (2026-08-20). The accuracy
gap is fixed; collapsing to one authoritative copy means restructuring the README's
Development section, which is pre-existing content outside that PR's scope.
