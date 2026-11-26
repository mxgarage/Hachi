# Hachi UX acceptance checklist (G6)

The maintainer walks through every item on a real Mac, on the commit being released, and records the result in
`evidence/G6-ux-signoff.json` (see `evidence/README.md`). CI renders every menu-bar, menu and alert state in light
and dark appearance (`tests/ux_screens.py`, artifact `hachi-<sha>` → `acceptance/ux/index.html`); use those
screenshots to compare against what you see. CI also compares every screenshot pixel for pixel with the stored
baseline in `tests/ux-baseline/` (`tests/ux_baseline.py`) and fails on any difference, with diff images in
`acceptance/ux-diff/index.html`. That only proves nothing changed by accident since the baseline was accepted; it
does not prove the screens are right, and it does not replace this walkthrough or the maintainer's sign-off. Two things in the screenshots are not what the running app does: the alert icon is drawn directly from the
artwork (the app shows its app icon, built from the same artwork), and the precheck text in alerts is a hand-written
example, not output from a real `claude-safe` / `codex-safe`. Every screenshot sits on the plain window background,
so menus show no translucent material. Check the real alert icon and menu background during UX-08 to UX-12. CI
draws the menu from the real menu items, so it cannot show how the system menu bar itself looks or behaves. That
part is only covered by this walkthrough.

Each item has an ID; the evidence needs a `pass` for every ID below. If an item fails, open an issue for it (it can
be labelled `claude`) and sign off again once it is fixed. Changing this file after `tested_commit` makes the
sign-off stale.

## Install and first launch

- **UX-01** The ad-hoc signed, not notarized zip (release asset or CI artifact) unpacks, and Hachi opens after allowing it in System Settings → Privacy & Security. No Dock icon and no window appear; only the menu-bar icon.
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
- **UX-10** With a synthetic `claude-safe` / `codex-safe` that exits 0 (pass) and one that exits non-zero (fail), each provider shows `预检通过` or `预检未通过` with its output, and every alert ends with the note that this is a precheck only (the client was not started, which is not the failure reason) and that browser OAuth, MCP and in-flight interception are not covered. A failed result also says that Hachi only relays the entry's output and that the failure is not necessarily about the IP (for example `observed_route=NOT OBSERVED`).
  A synthetic entry for this test (it refuses to overwrite an existing file; if you have a real `claude-safe`, move it aside first and restore it afterwards): `f=~/.local/bin/claude-safe; [ -e "$f" ] && echo "exists, move it aside first" || { mkdir -p ~/.local/bin && printf '#!/bin/sh\necho synthetic check\nexit 0\n' > "$f" && chmod +x "$f"; }` (use `exit 1` for the fail case, and delete the file when done).
- **UX-11** The alert comes to the front and is dismissed with Return or the OK button; focus returns to the previous app.

## Appearance and quitting

- **UX-12** Menu and alerts are readable in light mode, dark mode and with Increase contrast on; nothing is clipped at the default text size.
- **UX-13** `退出` and ⌘Q from the open menu quit Hachi; the icon disappears and no process is left behind.
