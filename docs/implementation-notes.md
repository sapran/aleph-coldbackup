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
scaffolding. Instead `pyproject.toml` caps ruff at `<0.16` so the toolchain is
reproducible for every contributor, and Dependabot will raise the 0.16 bump as its
own PR where the lint fixes can be reviewed as a single unit.

**To pick up.** Bump the cap, run `ruff check src tests --fix` for the 15
auto-fixable ones, then hand-fix the four listed above.
