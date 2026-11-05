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
```

`npm test` проверяет и готовую сборку (`tests/web/dist.test.ts`), поэтому сначала выполните
`npm run build`.

## Устройство

- `index.html` подключает `/execution-console.css` первым. Плагин в `vite.config.ts` берёт этот
  файл побайтно из `docs/design/web-console-mockups/execution-console.css` и выпускает как
  `dist/execution-console.css`; копии в репозитории нет.
- `src/styles/app.css` содержит только правила, которых нет в стилях макета.
- Шрифт JetBrains Mono (латиница и кириллица, 400/600/700) берётся из `@fontsource` и попадает
  в `dist/` файлами woff2. `assetsInlineLimit: 0` запрещает `data:` URL, которые нарушили бы
  `font-src 'self'`.
- Переводы берутся из `src/i18n/catalog.json`. Его генерирует
  `python -m harness.console.kernel.web_catalog` из таблиц TUI. Новую строку интерфейса сначала
  добавьте в `harness/console/kernel/i18n_strings.py`, затем перегенерируйте каталог.
- Маршруты hash-based (`#/`, `#/diagnostics`): серверу не нужен SPA-fallback.
- Тесты лежат в `tests/web/`. `vitest.config.ts` разрешает пакеты для них из этого каталога
  (`resolve.dedupe`), а `tests/web/tsconfig.json` — через `paths`.
