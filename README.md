# Hachi · 小八

![Hachi, a Shiba Inu wagging its tail](docs/assets/hachi-logo.gif)

Hachi (ハチ) is a little watchdog for macOS. The menu-bar dog continuously wags its tail while running and stays still with macOS Reduce Motion. The animation is decorative, not a network health indicator. [Read the market research and sources](docs/market-research.md).

Private development prototype. A native macOS menu-bar app; it observes macOS network-path availability and optionally invokes already-installed `claude-safe` / `codex-safe` preflight adapters on demand. It does **not** enforce runtime network policy or cover browser authorization or MCP. It has no login-item registration, telemetry, automatic credential use, runtime blocking or third-party dependency. Network availability is not proof of a verified egress IP.

## Build / test

Requirements: macOS, Apple command-line tools, and Python 3.9+.

```sh
python3 build.py
python3 tests/lab.py
python3 tests/branding.py
python3 tests/acceptance.py   # all of the above + gate report in build/acceptance/
open 'build/Hachi.app'
```

The test harness starts a real HTTP observer on loopback. It never runs an official provider client, reads a provider credential or sends traffic off-device. `tests/check.py` is an optional manual preflight smoke test for machines with the two local adapters, not part of acceptance or CI. Neither test represents a provider risk or ban outcome.

## Release gate (not met)

The gate is also kept in machine-readable form in [`release-gate.json`](release-gate.json). `tests/acceptance.py` evaluates each item from evidence files under [`evidence/`](evidence/README.md) on every CI run and reports it in the job summary; missing evidence counts as not met, evidence must match git history (tested commit is an ancestor of the release, product files unchanged since), the 95% success rate is judged on the Wilson 95% lower bound, not the point estimate. CI checks evidence format, thresholds and git history only (for G2–G5 that is little more than format: per-scenario counts, case results, client lists and extension flags are taken as stated); that runs happened at an independent observer is the maintainer's claim, made by committing the evidence (see [`evidence/README.md`](evidence/README.md)). Declared workflows cannot be waived by their evidence, except MCP ("where supported"): only it may be marked unsupported, and then its G3 lab cases may be `not_supported` too; narrowing any other workflow means removing it from the gate. Evidence may only use `none` or `synthetic` credentials; the gate has no path for authorized test credentials, and adding one is a separate maintainer decision. The `Acceptance backlog` workflow keeps one `acceptance` issue open per unmet item. A stable tag (`v0.2`) on a commit already on `main` only releases when every item is met; a suffixed tag (`v0.2-dev.1`) publishes a prerelease marked as not meeting the gate.


- Require at least 95% successful end-to-end operations in each declared workflow (desktop, CLI, browser authorization, MCP where supported), on a preregistered held-out scenario matrix spanning supported OS/architectures. Record counts, environments, repeated seeds, timing and uncertainty. Do not pool easy scenarios to hide a failing workflow.
- Critical failures block release independent of the percentage: zero observed direct or wrong-route egress for protected flows in the failure matrix, and no interruption or route change for unrelated control workloads. Verify at an independent network observer; app logs alone do not count. Missing coverage is not a pass.
- Initial lab cases: TCP/TLS streams including reconnect and token-like refresh, system/browser redirect and loopback callback, DNS IPv4/IPv6/UDP, MCP stdio child isolation and remote streaming. Inject route change, tunnel/core loss, already-open flows, sleep/wake, interface switch, update and extension disable/restart. Use isolated machines and synthetic credentials, never the user's provider accounts.
- Transfer evidence: exercise the same final OS enforcement mechanism across fixture clients and real signed client binaries in isolated homes. First validate process/signature identity and helpers by credential-free runs; only include official supported test endpoints or dedicated explicitly authorized test credentials if independently available. Match transport, process ownership, redirects and DNS behavior, and document gaps. Fixtures cannot establish vendor authentication UX, compatibility of unobserved flows, account eligibility, or provider enforcement outcomes. Do not claim those are validated or release an unverified surface as covered.
- Key blocker: signed Network Extension feasibility and independent test of behavior when extensions are unavailable. No launch-time status or synthetic canary substitutes for a data-plane test.

Scope: compliant network reliability only, not altering provider account eligibility or bypassing platform enforcement. No private IP/config, account tokens, device paths, or live test credentials belong in the repo.

Contributing: all changes go through pull requests, including the maintainer's own; merges are manual. See [AGENTS.md](AGENTS.md) for the merge gate and what runs automatically (CI and acceptance, Codex and Claude PR review, and Claude implementation for issues labeled `claude` or comments starting with `@claude`).
