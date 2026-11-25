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

- Require at least 95% successful end-to-end operations in each declared workflow (desktop, CLI, browser authorization, MCP where supported), on a preregistered held-out scenario matrix spanning supported OS/architectures. Record counts, environments, repeated seeds, timing and uncertainty. Do not pool easy scenarios to hide a failing workflow.
- Critical failures block release independent of the percentage: zero observed direct or wrong-route egress for protected flows in the failure matrix, and no interruption or route change for unrelated control workloads. Verify at an independent network observer; app logs alone do not count. Missing coverage is not a pass.
- Initial lab cases: TCP/TLS streams including reconnect and token-like refresh, system/browser redirect and loopback callback, DNS IPv4/IPv6/UDP, MCP stdio child isolation and remote streaming. Inject route change, tunnel/core loss, already-open flows, sleep/wake, interface switch, update and extension disable/restart. Use isolated machines and synthetic credentials, never the user's provider accounts.
- Transfer evidence: exercise the same final OS enforcement mechanism across fixture clients and real signed client binaries in isolated homes. First validate process/signature identity and helpers by credential-free runs; only include official supported test endpoints or dedicated explicitly authorized test credentials if independently available. Match transport, process ownership, redirects and DNS behavior, and document gaps. Fixtures cannot establish vendor authentication UX, compatibility of unobserved flows, account eligibility, or provider enforcement outcomes. Do not claim those are validated or release an unverified surface as covered.
- Key blocker: signed Network Extension feasibility and independent test of behavior when extensions are unavailable. No launch-time status or synthetic canary substitutes for a data-plane test.
- UX acceptance: CI renders every menu-bar, menu and alert state in light and dark appearance (`tests/ux_screens.py`, in the CI artifact under `acceptance/ux/`), and the maintainer walks through [`docs/ux-checklist.md`](docs/ux-checklist.md) on a real Mac at the released commit and signs off. The screenshots draw the real menu items rather than capturing the system menu bar, so the walkthrough is what covers the actual interaction.

Automated checking: the gate is kept in machine-readable form in [`release-gate.json`](release-gate.json) and evaluated by `tests/acceptance.py` on every CI run from evidence under [`evidence/`](evidence/README.md); missing evidence is not met, the 95% rate is judged on its Wilson lower bound (at least 73 all-successful runs per workflow), and CI checks format, thresholds and git history only, not that the runs really happened (details and limits in [`evidence/README.md`](evidence/README.md)). The `Acceptance backlog` workflow is designed to keep one `acceptance` issue per item (its issue sync is not covered by automated tests): open while unmet, marked when the format check passes so the maintainer can close it, and reopened if the item regresses. `release.yml` is written so that a stable tag (`v0.2`) at the head of `main` releases only when every item is met, and a suffixed tag (`v0.2-dev.1`) publishes a prerelease marked as not meeting the gate; both still require the baseline checks to pass. Because this private repository's plan has no environment approvals, a tag currently produces a draft release (with the app attached) that the maintainer publishes by hand; publish that draft rather than creating a new release. If a release for the tag already exists, the workflow is written to attach the app and acceptance report to it instead, and running the Release workflow by hand with an existing tag rebuilds and re-attaches them; these two paths have not yet run with a real tag. The draft path ran once, with `v0.2-dev.1`. G6 is met only by the maintainer's own sign-off; agents can fix the problems it finds but cannot sign it. The G2/G3 lab cases do not have runners yet: CI runs the existing loopback lab, not the gate's cases, so those items are judged only from committed evidence. "Met" here means the maintainer's evidence claim passed the format and history checks; it is not independent verification that the runs happened.

Scope: compliant network reliability only, not altering provider account eligibility or bypassing platform enforcement. No private IP/config, account tokens, device paths, or live test credentials belong in the repo.

Contributing: all changes go through pull requests, including the maintainer's own; merges are manual. See [AGENTS.md](AGENTS.md) for the merge gate and what runs automatically (CI and acceptance, Codex and Claude PR review, and Claude implementation for issues labeled `claude` or comments starting with `@claude`).
