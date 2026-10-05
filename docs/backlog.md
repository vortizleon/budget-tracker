# Backlog (suggestions, not commitments)

One line each: **what** - why - effort (S/M/L) - added date. Claude adds items here instead of building unrequested
improvements; the owner decides what to pick up. Move finished items to "Done" with the PR number.

## Open
- [ ] **Pin or ship the chart library.** The page loads ApexCharts "latest" from a CDN; v5+ is not MIT (OEM license applies to
  products used by other people). 4.7.0 is the last MIT release and works in both languages. Needs the owner's call on the license. - S - 2026-10-05
- [ ] **Duplicate protection between hand-entered and emailed transactions.** Sync can add one the owner already typed in.
  Match on date + amount + merchant. - M - 2026-10-05
- [ ] **Establish and document the oldest supported macOS version.** Never checked. - S - 2026-10-05
- [ ] **Update from tagged releases instead of `main`,** so friends only get versions the owner chose. - S/M - 2026-10-05
- [ ] **Apply the advisory CI templates:** skip docs-only changes, cancel superseded runs, run the macOS installer job only when
  installer files change (`.claude/skills/ship-small-apps/templates/`). - S - 2026-10-05
- [ ] **Fresh-user-account run on a real Mac** whenever installer/download files change (about 5 minutes; covers the Gatekeeper
  warning CI can't). Habit, not automation. - S - 2026-10-05
- [ ] **Loosen the Python 3.13 pin.** The code ran on 3.11 in the sandbox; pin the oldest version CI exercises. - S - 2026-10-05
- [ ] **Browser smoke test in CI** (headless Chromium over every view, both languages). Valuable but heavier; optional. - M - 2026-10-05
- [ ] **IMAP + app-password mode** as an alternative to the Google Cloud setup (personal Gmail only; full-mailbox access). - L - 2026-10-05
- [ ] **Windows / Linux support.** README says not planned; macOS-only bits are `lsof`, the Chrome `open` call, the Darwin check. - L - 2026-10-05

## Done
- Installer without Homebrew/Xcode tools, clean-install CI, credentials upload, updater, Spanish UI, manual transactions,
  token auto re-login, dependency upgrade and hardening (#1-#14).
