# Budget Tracker
Local-first personal finance app: FastAPI + SQLite + vanilla JS (ApexCharts from a CDN). It reads bank alert emails
(BAC, Promerica - Costa Rica) from the owner's Gmail with read-only OAuth. Used by the owner and a few non-technical friends
on macOS; delivered as one pasted Terminal command (see `GUIA_DE_USO.md`) plus `Instalar.command`, `Abrir.command`,
`Actualizar.command` and the `finance-app` CLI. Spanish guide, English README.

## Working rules
- CI is advisory: never add required checks; keep the per-PR run fast; read it before merging (a red `main` happened twice).
- Suggest, don't build: if you notice a portability / CI / delivery improvement, mention it to the owner instead of
  implementing it. The owner keeps those suggestions, the lessons log and CI/installer templates in their own playbook repo
  (`vortizleon/claude-playbooks`: `backlogs/budget-tracker.md`, `.claude/skills/ship-small-apps/`), not here. It isn't
  attached to every session; if it is, read the skill before delivery/CI/security work, and offer to append new lessons.
- Say what you couldn't test. The cloud sandbox is Linux: no macOS, no real Gmail login. Headless Chromium is available
  for browser checks.
- Verify before you claim: "unused / not installed / never read" needs a whole-repo search. Docs that describe Google's
  console come from real screenshots or official docs and are dated - Google changes that UI.
- The owner opens PRs from the UI (squash merges). Before pushing to a branch, check whether its PR already merged; if so,
  restart the branch from `main` and say so.

## Delivery rules (each one came from a real failure)
- Assume nothing is installed on a friend's Mac: no Homebrew, git, Xcode tools or Python. The installer provides everything
  (uv + a managed Python). Don't suggest `git clone` or a browser ZIP: both trigger blocks/prompts on a fresh Mac.
- Scripts must exit 0 with stdin closed (`read ... || true`); CI runs the installer that way.
- Every import must be in `requirements.txt`; CI installs only that, imports every module and requests every page.
  Pin dependencies and CDN scripts, and note licenses (ApexCharts v5+ is not MIT).
- Updates never touch user data (`credentials.json`, `token.json`, `*.db`); back the database up first.
- Logins die (Google "Testing" mode: about 7 days; revoked access). Keep the auto re-login + banner working.

## Run / test
```
uv venv --python 3.13 venv
uv pip install --python venv/bin/python -r requirements.txt -r requirements-dev.txt
venv/bin/python -m pytest tests -q          # fresh database per test, never touches real data
venv/bin/python -m uvicorn backend.api:app --port 8000
```

## Conventions
- UI text: the English source string is the translation key. Wrap text built in JS with `_t('...')` (`_tp` plurals,
  `_tc` default category names) and add the Spanish to `frontend/static/js/locales/es.js`; `tests/test_i18n.py` fails
  otherwise. Spanish is neutral Latin American: no tu/vos/usted (infinitives, impersonal phrasing) - the test lints it.
- Never commit secrets or data: `credentials.json`, `client_secret*.json`, `token.json`, `*.db`, `backups/`, `.server.log*`.
- Request handlers that block (database, network, waiting for a login) are plain `def`, not `async def`.
- Local server binds `127.0.0.1`; CORS is localhost-only; escape quotes in HTML built in JS; validate colors as hex.
