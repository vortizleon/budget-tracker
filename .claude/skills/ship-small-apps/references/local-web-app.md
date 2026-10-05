# Local web apps (FastAPI + browser UI) - defaults worth having from day one

## Network and browser security
- Bind `127.0.0.1`, not `0.0.0.0`: financial data must not be reachable from the Wi-Fi.
- CORS: allow only `http://localhost:<port>` and `http://127.0.0.1:<port>`; test that look-alike hosts
  (`http://localhost.evil.example`) are refused. Otherwise any website open in the browser can read the local API.
- Escape every interpolated value in HTML built in JavaScript, **including quotes** (`"` and `'`), not just `<` `>` `&`.
- Values that end up in style/attribute contexts (colors) are validated server-side (hex only) and passed through a
  safe-color helper client-side.
- Validate input at the endpoint with clear messages (positive amounts, allowed enums, referenced rows exist).

## Server behaviour
- Route handlers that do blocking work (database, network, waiting for a browser login) are plain `def`, so they run
  in the thread pool; an `async def` that blocks freezes the whole server.
- Long jobs (sync) are single-flight: a lock, and HTTP 409 if one is already running.
- Anything waiting on a human (OAuth browser login) has a timeout.
- Log to a rotating file (about 1 MB x 3), capturing `print()` and tracebacks; unbounded logs eventually bite.
- Start-up creates tables and adds missing columns idempotently, so an update plus a restart migrates data.

## External logins / OAuth
- Refresh tokens die: revoked access, password change, and in Google's "Testing" publishing mode they expire after about
  7 days. On a dead token delete the stored token, fall back to a fresh login, and show a banner explaining what to click.
  Never surface it as a bare 500.
- Desktop-app client files identify the app, not a person; they grant no mailbox access. Tokens do - never share or commit them.
- Shared-project model for a few friends: the owner keeps one project in Testing mode, adds each friend as a test user and
  sends the client file privately (limit 100 test users). Each friend's token stays on their own machine.

## Dependencies and upgrades
- Pin direct dependencies; pin CDN scripts too (or ship the file). Record each new dependency's license.
- Upgrades can break every page at once (Starlette 1.x changed `TemplateResponse(request, name)`; `on_event` deprecated in
  favour of lifespan). A smoke test that imports every module and requests every page is what makes upgrades cheap.
- Prefer the oldest language version CI actually runs over the newest one available.

## Tests that earned their keep
- Clean install -> import every module -> serve every page (catches missing deps and upgrade breaks).
- A fresh database per test.
- CORS, validation, lock behaviour, auto-categorization: small API-level tests with the real app and a throwaway database.
- A headless-browser pass over every view in every language for UI work (Chromium is available in the cloud sandbox);
  assert no console errors and no untranslated text.

## Internationalization (English / Spanish here)
- English source text is the key; a missing translation falls back to English, so partial work never breaks the UI.
- Translate static HTML in place; text built by JavaScript goes through the helper at render time; switching re-renders
  the current view. Never rewrite user data (merchant, category names) by matching it against the dictionary - give default
  data names their own key namespace and translate at display time only.
- Name the helper so it can't be shadowed by loop variables (`_t`, not `t`).
- A coverage test (every UI string has an entry, placeholders and HTML tags match, style lint) is what keeps translations honest.
- Numbers: keep the format users already know (`es-419` renders like English); dates/months follow the language.
- Spanish register: neutral, no tu/vos/usted - infinitives and impersonal phrasing - when the owner asks for it.
