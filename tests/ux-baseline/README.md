# UX screenshot baseline

`tests/ux_baseline.py` compares every screenshot that `tests/ux_screens.py` renders in CI with the PNG of the same
name here, pixel for pixel, and fails on any difference. `baseline.json` records the runner image, macOS version
and commit the baseline was rendered at.

These files always come from the CI runner (`macos-15`), never from a developer Mac: scale, fonts and OS version
differ, so a local render would never match.

## Accepting an intended change

1. Push the change. The `Account-free macOS verification` job fails at "UX screenshots match baseline" and uploads
   `acceptance/ux-diff/index.html` (baseline | this build | changed pixels) in the `hachi-<sha>` artifact.
2. Look at the diff images. Only continue if every change is intended.
3. Replace this folder's PNGs and `baseline.json` with `acceptance/ux-candidate-baseline/` from the same artifact,
   or, without downloading the artifact, save the failed job's log and run
   `python3 tests/ux_baseline.py --import-log <log file>` (it checks the bundle's checksum).
4. Commit in the same PR and say in the PR description which screenshots changed and why. Reviewers see the
   before/after images in the PR's file view.

Updating the baseline does not sign anything off: the maintainer's walkthrough in `docs/ux-checklist.md` still
decides G6.
