# Contributing

Thanks for considering a contribution. This is a small, focused tool: it exports one
Aleph investigation into a re-ingestable cold backup. Changes that keep it small and
predictable are easier to accept than changes that broaden its remit.

## Setting up

Requires Python ≥ 3.11 and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/sapran/aleph-coldbackup
cd aleph-coldbackup
uv venv && uv pip install -e ".[dev]"
```

## Checks a pull request must pass

These three run in CI on every push and pull request, across Python 3.11–3.14. Run them
locally first:

```bash
uv run pytest                  # unit tests — fast, no network, no Aleph needed
uv run ruff check src tests
uv run mypy src tests
```

The unit suite is self-contained: `pyproject.toml` sets `addopts = "-m 'not integration'"`,
so the tests that need a live Aleph are deselected by default.

## Integration and equivalence tests

The strongest check in the repository is the equivalence suite, which exports a real
collection and asserts the reconstructed tree matches the original source directory
byte for byte. It cannot run in CI, because it needs an Aleph instance and ground-truth
data that only you have:

```bash
export ALEPHCLIENT_HOST=https://your-aleph
export ALEPHCLIENT_API_KEY=...
export ALEPH_EXAMPLE_DIR=/path/to/source-tree        # ground truth for the equivalence test
uv run pytest -m integration -s
```

**`--direct` mode needs two more variables.** Without them the direct-mode tests
*skip* rather than fail, so the run still reports success and you can easily believe
you tested code you did not touch at all:

```bash
export COLDBACKUP_ARCHIVE_PATH=/path/to/servicelayer/archive   # must be a readable directory
export COLDBACKUP_DB_URI=postgresql://user:pass@host/aleph     # read-only role recommended
```

Check the output for `skipped` before claiming a run: `tests/test_direct_integration.py`
skips when either is unset, and the equivalence suite skips without
`ALEPH_EXAMPLE_DIR`.

If your change touches the walker, the archive reader (`archive_fs.py`, `directwalk.py`)
or name allocation, please run this against your own Aleph and say so in the pull
request — the archive reader is reachable only through `--direct`, so it needs the two
variables above. Never paste real host names, API keys, or investigation data into an
issue or pull request — `.env` and `.env.*` are gitignored, keep credentials there.

## Style and commits

- Match the surrounding code: type annotations throughout, `from __future__ import annotations`
  at the top of every module that declares them, comments only where the logic is not
  obvious.
- One logical change per commit, with a [Conventional Commits](https://www.conventionalcommits.org/)
  prefix — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:` — matching the
  existing history.
- New behaviour needs a test. For a bug fix, the most useful thing you can do is write
  the test first and confirm it fails with the reported symptom before you fix it.

## Reporting bugs

Open an issue describing what you ran, what you expected, and what happened — including
the summary line the export printed and the relevant `manifest.json` statuses. Redact
host names and collection identifiers if they are sensitive.

For **security** issues, do not open a public issue; follow [SECURITY.md](SECURITY.md)
instead.

## Licensing

By contributing you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE), the same terms as the project.
