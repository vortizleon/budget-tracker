# Lessons log

Append-only. Format: **symptom** - cause - prevention. `Ref` points at where it happened in the
Budget Tracker project (PR numbers) so the fix can be read in context.

## Delivery and install

1. **Mac refused to open the installer; needed `sudo xattr -rd com.apple.quarantine`.**
   Cause: files downloaded through a browser/AirDrop get the quarantine flag and unsigned scripts are blocked;
   the developer's own files never have it. Prevention: deliver with a Terminal `curl | tar` command (no flag),
   have the installer clear the flag on its own folder, and check browser-download behaviour by hand on a real
   machine - CI cannot reproduce Gatekeeper. Ref: first install report; fixed in #1, #3.
2. **Installer demanded Xcode Command Line Tools and a macOS update.** Cause: it installed Homebrew, which needs them;
   the developer's Mac already had both. Prevention: remove heavyweight prerequisites (uv: one binary, managed Python,
   no sudo). CI runners have the tools preinstalled, so CI can't reveal this - reduce the prerequisites instead. Ref: #1.
3. **`git clone` suggested as the "simple" way to fetch the app.** Cause: on a fresh Mac `/usr/bin/git` is a stub that
   triggers the same Xcode-tools prompt. Prevention: `curl | tar`; don't assume git, brew or python exist. Ref: #3.
4. **Page failed with "jinja2 must be installed".** Cause: imported by the code, missing from `requirements.txt`,
   installed by hand on the dev machine. Prevention: CI installs only `requirements.txt` into a fresh venv, imports every
   module, starts the server and requests every page. Ref: fixed in #4; the clean-install test arrived in #9.
5. **Setup stopped waiting for a credentials file placed by hand with an exact name.** Cause: required, manual,
   order-dependent step. Prevention: auto-detect the downloaded file, allow upload from inside the app, never block
   the installer on an optional secret. Ref: #9.
6. **Installer "failed" in CI after succeeding.** Cause: the closing "press any key" `read` returns non-zero when stdin is
   closed. Prevention: `|| true`, explicit `exit 0`, and run the installer in CI with stdin closed. Ref: #10.
7. **First update had to be manual.** Cause: the updater didn't exist in copies already delivered. Prevention: ship the
   updater in the first version people get; document the one-time manual step for older copies. Ref: #5.
8. **Updates must not endanger data.** Prevention: updater copies code only (excludes credentials, tokens, `*.db`, env, venv),
   backs up the database first, restarts the server so migrations run. Ref: #5.

## Documentation

9. **Setup guide for a third-party console didn't match the real screens.** Cause: written from memory; the vendor
   changed its UI. Prevention: build from screenshots/official docs, date it, keep it short, prefer designs that avoid
   the steps entirely (shared project + invited test users), and expect drift. Ref: #4, #6.
10. **"X is never read" asserted from a partial search.** Cause: grepped only part of the repo. Prevention: whole-repo
    search before claiming absence; list what was not checked.

## Security and robustness

11. **Server reachable from the whole network.** Cause: bound to `0.0.0.0` for convenience. Prevention: bind `127.0.0.1`.
12. **Any website could call the local API.** Cause: CORS allowed every origin. Prevention: allow only localhost origins;
    test it, including look-alike hosts. Ref: #14.
13. **XSS holes.** Cause: HTML escaping that didn't escape quotes; colors interpolated into style attributes.
    Prevention: escape quotes too, validate hex colors server-side, escape every interpolated field. Ref: #14.
14. **The whole server froze during a browser login / slow query.** Cause: blocking work inside `async def` handlers
    (event loop blocked). Prevention: plain `def` handlers for blocking work (thread pool), time limits on logins,
    one-at-a-time lock returning 409 for long jobs. Ref: #13, #14.
15. **Sync failed with a 500 when the login token died.** Cause: OAuth refresh tokens expire (7 days for apps in Google's
    Testing mode) or get revoked. Prevention: drop the dead token, start a fresh login, show a banner that says what to
    do. Ref: #13.
16. **Log file grew forever.** Prevention: rotating log (size cap, a few backups), capture stdout/stderr. Ref: #14.

## Dependencies

17. **A CDN script loaded "latest"; a new major version changed its license (no longer MIT).** Prevention: pin or ship the
    file, record the license when adding a dependency. Open item for this project.
18. **Upgrading to the latest packages broke every page** (Starlette 1.x changed `TemplateResponse` arguments; startup
    hooks deprecated). Caught by the every-page smoke test. Prevention: pin, upgrade deliberately, let the smoke test
    judge. Ref: #14.
19. **A strict language-version pin nobody verified** (code ran on an older Python). Prevention: pin the oldest version
    CI actually exercises; don't demand a newer one for its own sake.

## Testing

20. **Tests interfered with each other.** Cause: one shared test database. Prevention: fresh database per test. Ref: #12.
21. **A browser-only bug in the English page** (custom chart locale replaced the library's built-in one). Prevention: a
    real-browser pass (headless Chromium) over every view in every language for UI work. Ref: #11.
22. **A local variable shadowed the global translation function.** Prevention: distinctive helper names (`_t`). Ref: #11.
23. **A chart ignored the date filter and a shared axis hid one currency.** Prevention: test data views with filters on
    and with mixed currencies. Ref: #13.
24. **Spanish copy used forms the owner wanted avoided.** Prevention: a test that lints the translations for them. Ref: #11, #14.

## Process

25. **Commits pushed after a PR merged were stranded, repeatedly** (#2 -> #3, #3 -> #4, #5 -> #6, #6 -> #7, #9 -> #10).
    Prevention: before pushing, check whether the PR merged; if so, restart the branch from the default branch and say so.
    Squash merges mean "already merged" must be judged by content (diff against main), not commit ids.
26. **Main went red.** Cause: merged mid-run, before the CI fix landed. Prevention: look at CI before merging; it doesn't
    gate, it informs. Ref: #9, #10.

## Known open (this project)

- Manual entry vs. email sync can duplicate a transaction.
- Oldest supported macOS version never established.
- Pin or vendor the chart library (license), pending the owner's decision.
