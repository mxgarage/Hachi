# Hachi UX acceptance checklist (G6)

The maintainer walks through every item on a real Mac, on the commit being released, and records the result in
`evidence/G6-ux-signoff.json` (see `evidence/README.md`). CI renders every menu-bar, menu and alert state in light
and dark appearance (`tests/ux_screens.py`, artifact `hachi-<sha>` → `acceptance/ux/index.html`); use those
screenshots to compare against what you see. CI draws the menu from the real menu items, so it cannot show how the
system menu bar itself looks or behaves. That part is only covered by this walkthrough.

Each item has an ID; the evidence needs a `pass` for every ID below. If an item fails, open an issue for it (it can
be labelled `claude`) and sign off again once it is fixed. Changing this file after `tested_commit` makes the
sign-off stale.

## Install and first launch

- **UX-01** The unsigned zip from CI unpacks, and Hachi opens after allowing it in System Settings → Privacy & Security. No Dock icon and no window appear; only the menu-bar icon.
- **UX-02** The menu-bar icon is the dog in profile, legible in both light and dark menu bars, and lines up with neighbouring icons.
- **UX-03** The tail wags continuously and smoothly from launch. With System Settings → Accessibility → Display → Reduce motion on, it stops at rest within a second; turning it off resumes the wag.
- **UX-04** Hovering the icon shows the tooltip `Hachi · 观察模式（不拦截）`. VoiceOver reads the icon as `Hachi 小八`.

## Menu

- **UX-05** Clicking the icon opens the menu. The first three rows (observation mode, system network, browser authorization / MCP) are grey and do nothing when clicked.
- **UX-06** The system network row changes from `等待状态` to `可用（不是出口验证）` within a few seconds; turning Wi-Fi off changes it to `不可用或待建立`, and back when Wi-Fi returns.
- **UX-07** The wording never implies more than Hachi does: no row or alert says traffic is protected, intercepted or routed.

## Egress checks

- **UX-08** `检查 Claude 出口` with no `claude-safe` installed shows an alert `Claude：预检未通过` explaining the entry could not be run; the app does not hang or crash.
- **UX-09** While a check runs, its row is greyed out and the tooltip reads `Hachi · 预检中`; afterwards the row is enabled again and the tooltip returns to normal.
- **UX-10** With a synthetic `claude-safe` / `codex-safe` that exits 0 (pass) and one that exits non-zero (fail), each provider shows `预检通过` or `预检未通过` with its output, and every alert ends with the note that the client was not started and browser OAuth, MCP and in-flight interception are not covered.
  A synthetic entry for this test: `mkdir -p ~/.local/bin && printf '#!/bin/sh\necho synthetic check\nexit 0\n' > ~/.local/bin/claude-safe && chmod +x ~/.local/bin/claude-safe` (use `exit 1` for the fail case). If you already have a real `claude-safe` there, move it aside first and restore it afterwards.
- **UX-11** The alert comes to the front and is dismissed with Return or the OK button; focus returns to the previous app.

## Appearance and quitting

- **UX-12** Menu and alerts are readable in light mode, dark mode and with Increase contrast on; nothing is clipped at the default text size.
- **UX-13** `退出` and ⌘Q from the open menu quit Hachi; the icon disappears and no process is left behind.
