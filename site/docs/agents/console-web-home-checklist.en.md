# Manual acceptance of the web console SPA Home page

Basis: ADR 0029 and the accepted
[mockup](../demo/console.html). The Home page is a React SPA from
`harness/console/frontend`. The console server serves it as the static `dist/` build, and the facts
arrive only over the authenticated WebSocket `/ws`.

Check the real `harness console --web` in an isolated project. Do not put the token, the sign-in URL with `?token=`, cookies, or the content of the discovery file in screenshots,
reports, or logs.

## What is checked automatically

- `tests/console/test_console_admission.py` checks the parsing of the Cookie header and the sign-in rule:
  the URL `/?token=` answers 303; a wrong token, extra parameters, HEAD, a repeated cookie, and a
  cookie of another port are rejected.
- Playwright `tests/web/home.spec.ts` against a real server checks that the sign-in URL opens the
  clean `/#/?lang=ru` and sets the cookie `console_token_<port>` (HttpOnly, SameSite=Strict, Path=/),
  that with this cookie Home gets a snapshot over `/ws`, and that a wrong token gets 401 without a cookie.
- `tests/console/test_web_catalog.py` compares `src/i18n/catalog.json` with the TUI translation tables.
- Vitest in `tests/web/*.test.ts(x)` checks the shell (13 sections in three groups,
  `aria-current`, collapsing, the mobile menu, Esc, the keys g/d/o/?), ru/en without a reload,
  the Home blocks, the WebSocket client (reconnect, backoff, cursor, `cursor_expired`), the five
  connection states, `protocol.gen.ts` drift, and the build: byte-for-byte equality of
  `dist/execution-console.css` with the mockup styles, and no external URLs.
- Playwright in `tests/web/*.spec.ts` checks in Chromium the sign-in by link, the cookie, language
  switching without a reload, no CSP violations, no console errors, and no requests to other origins, all
  five states, and the structure of the shell and Home at 1440 and 390 px. These are DOM checks without
  screenshot comparison (ADR 0029): the owner accepts the appearance by hand against the mockup.

Automated tests do not replace a human review: 200 % zoom, a real tracker, and a long
connection loss are checked by hand.

## Commands

```bash
cd harness/console/frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

From the repository root: `make web-install`, `make web-build`, `make web-test`, `make web-e2e`.
The Python part: `.harness/.venv/bin/python -m pytest tests/console/test_console_admission.py
tests/console/test_web_catalog.py`.

## Manual checklist for the PR

In the PR, give the browser, viewport, zoom, commit SHA, the result for each item, and links to the screenshots
without credentials. A partial observation does not close an item.

- [ ] Wide screen (≥ 1440 px), narrow screen (390 px), and 200 % zoom: no horizontal scrolling
  of the page, the menu collapses to icons and expands again, the state is remembered after a
  reload, and on a narrow screen the menu opens as a drawer and closes by the backdrop and Esc.
- [ ] All 13 sections open from the menu and with the keys g/d/o/?. The sections other than Home honestly
  say that they are not available yet and show no demo data.
- [ ] Home shows the blocks "Requires attention", "Context" (above "Recent tasks"),
  "Recent tasks", "Health", and "Harness 2.0.0 outline". Facts that are not in the snapshot (project
  name, branch, tracker, tasks, roles, runtime store) are marked as unavailable, not invented.
  `null` is not shown as `0`.
- [ ] RU/EN switch without a reload: headings, navigation, labels, and `lang` on `<html>`.
  Check messages stay data and are not translated.
- [ ] DevTools: the Console has no errors and no CSP violations. In Network, all requests go to
  `127.0.0.1:<port>`, the fonts and icons are local, and there are no external URLs.
- [ ] Connection loss: after the server stops, a reconnect banner appears with the attempt number,
  the delay, and a note that the snapshot is stale. After a restart (a new link), Home
  gets a snapshot again without a page reload.
- [ ] Five connection states: connected, reconnecting, no server, error (for example,
  opening the port without a cookie), no data. Each has its own chip, banner, or page and a retry
  action.
- [ ] Sign-in: after the link from `harness console --web`, the URL is clean (`/#/?lang=…`, no token).
  The cookie `console_token_<port>` has the HttpOnly and SameSite=Strict flags. Two consoles of different
  projects in one browser work at the same time and do not knock each other out.
- [ ] The screenshots show no token, cookie, or sign-in URL.
