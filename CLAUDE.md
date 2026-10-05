# Budget Tracker
Local-first personal finance app: FastAPI + SQLite + vanilla JS (ApexCharts from a CDN). It reads bank alert emails
(BAC, Promerica - Costa Rica) from the owner's Gmail with read-only OAuth. Used by the owner and a few non-technical friends
on macOS; delivered as one pasted Terminal command (see `GUIA_DE_USO.md`) plus `Instalar.command`, `Abrir.command`,
`Actualizar.command` and the `finance-app` CLI. Spanish guide, English README.

## Work rules
- Before touching installers, updates, dependencies, CI, server security defaults, logins/tokens, docs that describe
  Google's console, or translations: read `.claude/skills/ship-small-apps/SKILL.md` (lessons from real failures here).
- CI is advisory: never add required checks; keep the per-PR run fast; read it before merging.
- Suggest, don't build: ideas about portability / CI / delivery go in `docs/backlog.md` (what - why - effort) unless asked.
- Say what you couldn't test. The cloud sandbox is Linux: no macOS, no real Gmail login. Headless Chromium is available
  for browser checks.
- The owner opens PRs from the UI (squash merges). Before pushing to a branch, check whether its PR already merged; if so,
  restart the branch from `main` and say so.

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
  otherwise. Spanish is neutral Latin American: no tu/vos/usted (infinitives, impersonal phrasing).
- Never commit secrets or data: `credentials.json`, `client_secret*.json`, `token.json`, `*.db`, `backups/`, `.server.log*`.
- Request handlers that block (database, network, waiting for a login) are plain `def`, not `async def`.
- Local server binds `127.0.0.1`; CORS is localhost-only.
