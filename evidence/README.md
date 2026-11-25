# Release-gate evidence

One JSON file per item in [`release-gate.json`](../release-gate.json), named by its `evidence` field. `python3 tests/acceptance.py` evaluates them; a missing or malformed file counts as not met.

Rules (see [AGENTS.md](../AGENTS.md)):
- Evidence comes from real lab runs measured at an independent network observer. App logs alone do not count.
- Only the maintainer commits files here. Agents build the harnesses that produce evidence; they never hand-write or edit these files.
- No private IPs, account tokens, device paths or live credentials. Use documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) where an address is needed, and link raw logs instead of pasting them.

Fields every file needs: `tested_commit` (40-character SHA), `environments` (OS/architecture list), `credentials` (`none`, `synthetic` or `authorized_test`), `raw_results` (link to the raw records). The per-item fields are checked in `tests/acceptance.py`; `tests/gate_selftest.py` shows a complete example for each item.
