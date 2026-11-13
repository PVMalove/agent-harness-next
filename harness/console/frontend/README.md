# Фронтенд консоли

SPA веб-консоли на React и TypeScript (ADR 0029). Vite собирает её в `dist/`, а
`harness.console.backend.api` отдаёт `dist/` по корню сервера, если там есть `dist/index.html`.
Без сборки сервер отвечает простой текстовой страницей. Node нужен только для сборки и тестов:
серверу консоли он не нужен. Python-пакета в этом каталоге нет.

## Команды

Все команды запускаются в `harness/console/frontend`:

```bash
npm ci                 # точные версии из package-lock.json
npm run build          # проверка типов и сборка в dist/
npm test               # Vitest: tests/web/**/*.test.ts(x), включая проверки dist/
npm run typecheck      # tsc для src/ и tests/web/
npx playwright install chromium   # один раз: браузер для Playwright
npm run test:e2e       # Playwright: tests/web/*.spec.ts против настоящего сервера консоли
```

Из корня репозитория те же шаги запускают `make web-install`, `make web-build`, `make web-test`,
`make web-typecheck` и `make web-e2e`.

`npm test` проверяет и готовую сборку (`tests/web/dist.test.ts`), поэтому сначала выполните
`npm run build`.

## Playwright

`tests/web/global-setup.ts` запускает `python -m tests.web.serve_console`: настоящий
`ConsoleServer` над временным пустым Git-проектом со сборкой из `dist/`, с настоящими CSP, cookie и
WebSocket. Интерпретатор задаёт `HARNESS_PYTHON` (по умолчанию `<repo>/.harness/.venv/bin/python`,
его создаёт `make bootstrap`). Нужна свежая сборка: `npm run build`.

Сценарии Playwright проверяют поведение: данные, фильтры, команды, диалоги подтверждения и
отсутствие горизонтального переполнения на 1440 и 390 px. Скриншоты не сравниваются, эталонных
снимков в репозитории нет: отрисовку шрифтов и пиксели владелец проверяет вручную по макетам.

## Устройство

- `index.html` подключает `/execution-console.css` первым. Плагин в `vite.config.ts` берёт этот
  файл побайтно из `docs/design/web-console-mockups/execution-console.css` и выпускает как
  `dist/execution-console.css`; копии в репозитории нет.
- `src/styles/app.css` содержит только правила, которых нет в стилях макета.
- Дизайн-система v3 (`docs/rfc/web-console-v3.md`) лежит в `src/styles/ds-*.css` и подключается
  после `app.css`: `ds-tokens.css` (токены `--ds-*`, шкала шрифта 11/13/16/20/28, reduced-motion),
  `ds-shell.css` (верхняя панель, рельса, баннер, подвал), `ds-components.css` (кнопки, панель
  с единым заголовком, сводка, вкладки-конвейер, значки статуса, плитки, переключатель 34x20) и
  `ds-screens.css` (раскладка экранов). Все классы и переменные начинаются с `ds-`, поэтому они
  не пересекаются со старой таблицей: `tests/web/ds-css.test.ts` проверяет префикс,
  `unslop-css.test.ts` и `palette-contrast.test.ts` - шкалу, сетку 4 px, веса, движение и контраст.
- Общие компоненты экранов v3 - `src/ds/` (`Panel`, `PageHeader`/`Summary`, `PipeTabs`,
  `StatusIcon`, `RelatedTiles`, `Switch`). Экраны Справка, Harness и Repo Map уже на них
  (`DS_ROUTES` в `src/navigation.ts`); остальные десять рисуются в `main` с классом
  `ds-main--legacy` и старыми стилями, пока их срезы эпика #1090 не перенесут. Общие панели
  команд и подтверждения стоят внутри `.ds-legacy-island`.
- Английские строки экранов v3, которых ещё нет в `catalog.json`, лежат в `src/i18n/ds.en.json`
  (ключи не пересекаются с каталогом); их свёртка в таблицы kernel идёт срезами с бэкендом.
- Окно: `tests/web/console-fit.spec.ts` измеряет Справку (7 вкладок), Harness (5) и Repo Map (3) на
  1920x1080, 1920x1010, 1920x950, 1680x950 и 1440x900; с `CONSOLE_FIT_OUT=<каталог>` пишет
  `fit-measurements.json` и PNG.
- Шрифт JetBrains Mono (латиница и кириллица, 400/600/700) берётся из `@fontsource` и попадает
  в `dist/` файлами woff2. `assetsInlineLimit: 0` запрещает `data:` URL, которые нарушили бы
  `font-src 'self'`.
- Переводы берутся из `src/i18n/catalog.json`. Его генерирует
  `python -m harness.console.kernel.web_catalog` из таблиц TUI. Новую строку интерфейса сначала
  добавьте в `harness/console/kernel/i18n_strings.py`, затем перегенерируйте каталог.
- Маршруты hash-based (`#/`, `#/diagnostics`): серверу не нужен SPA-fallback.
- Тесты лежат в `tests/web/`. `vitest.config.ts` разрешает пакеты для них из этого каталога
  (`resolve.dedupe`), а `tests/web/tsconfig.json` — через `paths`.
