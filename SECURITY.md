# Security Policy

## Supported versions

Only the latest `0.1.x` release receives fixes. This project is pre-1.0; there are no
long-term support branches.

## Reporting a vulnerability

Please report security issues **privately** through GitHub's private vulnerability
reporting: open the repository's
[Security tab](https://github.com/sapran/aleph-coldbackup/security/advisories/new) and
file a draft advisory. This keeps the report confidential until a fix is available.

Do not open a public issue for a security problem, and do not include real credentials,
real host names, or data from a live investigation in a report — a redacted reproduction
is enough.

Expect an acknowledgement within a week. This is a small, unfunded project: there is no
bug bounty, and fixes are best-effort.

## What is in scope

This tool handles two secrets and writes an archive of potentially sensitive material,
so the interesting areas are:

- **Credential leakage.** `ALEPHCLIENT_API_KEY` and the PostgreSQL DSN in
  `COLDBACKUP_DB_URI` must never reach disk, the process table, a log line, or a host
  other than the configured Aleph instance. The API key is deliberately scoped by
  network location in `src/aleph_coldbackup/client.py` so it is not attached to
  off-host (for example presigned CDN) download URLs.
- **Path traversal.** File and folder names come from a remote Aleph instance and are
  attacker-influenced. `src/aleph_coldbackup/names.py` sanitizes each path component;
  anything that escapes the output directory is a vulnerability.
- **Silent data loss.** A backup that reports success while dropping files is a safety
  bug, not just a correctness one. Every file the walker touches must appear in
  `manifest.json` with an accurate status.
- **SQL injection** in `--direct` mode, and any path that escalates beyond the
  read-only database session.

## What is out of scope

- Vulnerabilities in [Aleph](https://github.com/alephdata/aleph) itself — report those
  to the Aleph maintainers.
- Vulnerabilities in third-party dependencies without a demonstrated impact on this
  tool; report those upstream.
- The `--hardlink` copy mode sharing inodes with the live archive. This is documented
  behaviour, not a defect: that mode is for staging, not for an independent backup.
