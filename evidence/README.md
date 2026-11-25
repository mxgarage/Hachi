# Release-gate evidence

One JSON file per item in [`release-gate.json`](../release-gate.json), named by its `evidence` field. `python3 tests/acceptance.py` evaluates them; a missing or malformed file counts as not met.

Rules (see [AGENTS.md](../AGENTS.md)):
- Evidence comes from real lab runs measured at an independent network observer. App logs alone do not count.
- Only the maintainer commits files here. Agents build the harnesses that produce evidence; they never hand-write or edit these files.
- No private IPs, account tokens, device paths or live credentials. Use documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) where an address is needed, and link raw logs instead of pasting them.

What CI can and cannot check: `tests/acceptance.py` checks format, thresholds, and consistency with git history (`tested_commit` exists and is an ancestor of what is evaluated or released, `main.swift`/`build.py` unchanged since, the scenario matrix was committed before the test, raw records are in `evidence/` or pinned by SHA-256). It cannot prove that a run happened or that the observer was independent. Those are the maintainer's claims, made by committing the file. A PR from an agent branch or with agent-authored commits that touches `evidence/` fails CI.

Fields every file needs: `tested_commit` (40-character SHA), `environments` (OS/architecture list), `credentials` (`none`, `synthetic` or `authorized_test`), `raw_results` (a file under `evidence/`, or `{"url": "https://…", "sha256": "…"}`). The per-item fields are checked in `tests/acceptance.py`; `tests/gate_selftest.py` shows a complete example for each item.
