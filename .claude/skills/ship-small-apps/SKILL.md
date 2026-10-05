---
name: ship-small-apps
description: Use when building or changing an app that other people (often non-technical friends) will install, run or update - installers, download/update flow, dependencies and version pins, CI, portability across machines, local-server security defaults, OAuth/login lifecycles, docs that depend on someone else's UI, translations. A checklist of lessons learned from real failures, so they are not repeated.
---

# Shipping small apps to people who aren't developers

Your own machine hides delivery problems: years of installed tools, hand-installed packages,
files that never carry a download flag. Almost every failure in the log was invisible to the
developer and obvious to the first friend who tried it. This skill is how to see them first
without turning a small app into a release process.

Lessons are in `references/lessons.md` (symptom -> cause -> prevention). Read it when you
touch anything in the checklist below. Platform detail: `references/macos.md` (installers,
Gatekeeper, prerequisites) and `references/local-web-app.md` (local servers, security
defaults, OAuth tokens, dependency upgrades, i18n).

## Principles

1. **Assume nothing is installed.** Every prerequisite is installed by the installer or removed.
   Prefer one self-contained tool over a chain of them (e.g. `uv` instead of Homebrew + Xcode tools + Python).
2. **One way in, one command.** A step a person must do by hand is a delivery bug: automate it
   or delete it before documenting it. Don't present two install paths when one has known traps.
3. **Test the delivery path from the user's side.** A clean install that imports everything and
   serves every page catches missing dependencies; a clean-machine run catches the rest.
4. **Say what you could not test.** A Linux sandbox can't run macOS, a headless browser isn't a
   friend's Mac, memory of a third-party UI isn't the UI. State the gap; don't paper over it.
5. **Verify before you assert.** "X is unused / never read / not installed" needs a whole-repo
   search, not a partial grep. Docs that depend on someone else's UI come from screenshots or
   official docs, dated, or are marked unverified.
6. **Safe by default.** Local servers bind to localhost, CORS is local-only, output is escaped,
   data and secrets never leave the machine or the repo.
7. **Pin what you load,** including CDN scripts, and check the license when adding a dependency.
8. **Updates never touch user data,** and the updater ships in the first version people get.

## Checklist - what did you change?

| If you touched... | Check |
|---|---|
| Installer / download / update scripts | Works with stdin closed (exit code 0 without a TTY); no quarantine/permission assumptions; no sudo; every prerequisite installed by the script; **tell the owner** a fresh-user-account run on a real machine is worth doing (see `references/macos.md`) |
| `requirements*`, CDN tags, library versions | Pinned; every module still imports; every page still served; license noted for new deps |
| Anything a server exposes | Localhost bind, CORS, escaping of every interpolated value, validated inputs, no blocking call in a request handler, one-at-a-time lock on long jobs |
| Login / tokens / external APIs | Expiry and revocation handled without a 500; the UI says what to do |
| Docs naming buttons/menus of another product | Verified against screens or official docs; dated; short |
| UI text | Goes through the translation helper; the coverage test passes |
| A branch whose PR may have merged | Check first; if merged, restart from the default branch and tell the owner |

## CI stance

CI is **advisory**: it informs, it never gates. Don't add required checks. Keep the per-PR run
under a minute (clean install + tests on one OS). Run slow, platform-specific jobs (clean-Mac
installer) only when their files change, on the default branch, or on demand. Read CI before
merging anyway - a red run on main is a problem somebody has to fix. Templates:
`templates/ci.yml`, `templates/installer-check.yml`.

## Suggestions

When you notice a portability / CI / delivery improvement that wasn't asked for: add one line
to `docs/backlog.md` (what - why - effort) and mention it; do not build it. Build it when the
owner picks it.

## Keeping this alive

After finishing a phase of work, append what broke and why to `references/lessons.md` (date,
symptom, cause, prevention). To reuse in another project: copy this folder to its
`.claude/skills/`, add the short `templates/CLAUDE.md.template` as `CLAUDE.md`, and start an
empty `docs/backlog.md`.
