# RFC: публичный сайт Agent Harness Next

**Статус:** ACCEPTED, реализован в #972–#978 (закрыты 2026-11-06): сайт в `site/` на MkDocs
Material, публикация — `.github/workflows/pages.yml`. Сверка с Harness Next 2.0.0 (2026-11-10):
статус проекта `beta` (раздел 8, пункт 7) пересматривается при выпуске 2.0.0 в #1063;
раздел «Настройки» и промпты быстрого старта — #1013.
**Дата:** 2026-11-05.
**Связанные документы:** `docs/design/docs-site-mockups/`; дизайн-токены веб-консоли.
**Целевой URL:** `https://pvmalove.github.io/agent-harness-next/`.

## 1. Контекст

Agent Harness Next — новый проект: портативный harness для Claude Code и Codex, который
разворачивает в целевой проект скиллы, hooks и контекстные документы, а оркестрацию ведёт через
Rust runtime и локальный runtime-store.

Сейчас у проекта нет публичной точки входа, кроме GitHub-репозитория. README и `docs/` писались
как внутренние материалы: в них смешаны лендинг, установка, справочник, ADR, task-архивы и
описания для агентов. Человеку, который впервые открывает проект, трудно понять, что это, зачем
нужен Rust runtime, как установить harness и как выглядит работа.

При этом у проекта уже есть визуальная база: интерактивные макеты веб-консоли, дизайн-токены,
диаграммы и маскот. Их нужно использовать как основу публичного сайта, а не строить ещё один
несвязанный интерфейс.

## 2. Цели

1. Сделать публичный сайт `Agent Harness Next` на GitHub Pages.
2. Сократить `README.md` до лендинга: что это, для кого, быстрый старт, ссылки.
3. Убрать из публичной навигации внутренние `docs/harness-guide.md` и `docs/ARCHITECTURE.md`,
   перенеся их содержание в страницы сайта.
4. Объяснить текущую архитектуру: Python policy, Rust runtime, runtime-store, supervisor,
   инкрементальные проверки, hooks и веб-консоль.
5. Показать интерактивную демонстрацию веб-консоли.
6. Использовать маскота как часть публичного бренда.
7. Сохранить `docs/agents/`, `docs/adr/`, `docs/hooks/`, `docs/skills/` как источник для агентов;
   сайт ссылается на них, а не дублирует.
8. Не добавлять зависимость в основной Python-пакет.

## 3. Не входит в цели

- Замена внутренних ADR, task-архивов и агентских руководств.
- Публикация приватных терминов, внутренних blocker-списков и незавершённых обещаний.
- Автоматическая генерация сайта из всех Markdown-файлов `docs/`.
- Полный английский перевод в первой версии: русский — основной, английский — вторая фаза.
- Изменение CLI, runtime, coordinator или hooks ради сайта.
- Собственный домен в первой версии.
- Переименование репозитория без отдельного подтверждения владельца.

## 4. Аудитория

| Аудитория | Что ищет | Что получает |
| --- | --- | --- |
| Разработчик, впервые увидевший проект | «Что это и зачем» | Лендинг, 30-секундное объяснение, демо, quick start |
| Разработчик, устанавливающий harness | Команды и требования | Getting started, install, health, troubleshooting |
| Пользователь `/implement` | Как устроен workflow | Concepts + Guides: architect → developer → review → QA → publish |
| Мейнтейнер проекта-потребителя | Конфигурация и hooks | Reference: CLI, config, hooks, labels, agents |
| Архитектор | Границы и гарантии | Architecture: policy, runtime, store, IPC, supervisor, security |
| Человек, оценивающий проект | Как это выглядит | Demo веб-консоли, статус beta, roadmap |

## 5. Идентичность и URL

**Имя:** `Agent Harness Next`.
**Короткое имя:** `Harness Next`.
**Версия на сайте:** `beta` (без мажорной нумерации до стабильного релиза).
**Целевой URL:** `https://pvmalove.github.io/agent-harness-next/`.

### 5.1. Ограничение GitHub Pages

GitHub Pages для project site строит путь из имени репозитория:
`https://<owner>.github.io/<repo>/`. Сейчас репозиторий называется
`claude-agent-harness`, поэтому без переименования сайт будет доступен по
`https://pvmalove.github.io/claude-agent-harness/`, а не по желаемому
`https://pvmalove.github.io/agent-harness-next/`.

| Вариант | Плюсы | Минусы |
| --- | --- | --- |
| **A. Переименовать репозиторий в `agent-harness-next`** | Желаемый URL; бренд совпадает; GitHub делает redirect старых URL | Меняются clone URL, badges, внешние ссылки; нужен отдельный шаг |
| B. Оставить `claude-agent-harness`, сайт называть «Agent Harness Next» | Ничего не ломается | URL не совпадает с брендом |
| C. Собственный домен | Полный контроль URL | DNS, TLS и решение владельца |
| D. Зеркальный репозиторий только для Pages | Желаемый URL | Дублирование CI и поддержки |

**Рекомендация:** вариант A отдельным шагом после проверки сайта на текущем URL.
До переименования `site_url` указывает на текущий Pages URL; после — меняется одна константа
в `site/mkdocs.yml`, старые ссылки продолжают работать через GitHub redirect.

### 5.2. Маскот

Публичный бренд использует воксельного маскота из `docs/assets/harness-banner.svg`:
тёплый оранжево-песочный персонаж с пиксельными акцентами. Маскот нужен:

- в hero лендинга — как проводник по продукту, с короткой репликой;
- в футере — как небольшой знак бренда;
- в пустых состояниях демо и на странице 404 — как дружелюбный помощник, без инфантильности.

Отдельный `mascot.svg` с прозрачным фоном лежит в `docs/design/docs-site-mockups/`.
Маскот не заменяет логотип `H›`: логотип — навигационный знак, маскот — персонаж.

## 6. Стек

**Решение:** MkDocs Material в отдельном `site/`, сборка в GitHub Actions, публикация через
GitHub Pages Actions.

Почему:

- Python-стек, не добавляет зависимость в основной пакет;
- статический HTML, без runtime Node и внешних CDN;
- поиск, навигация, тёмная/светлая тема, мобильная вёрстка;
- Markdown-источники удобны для ревью и будущего перевода;
- можно встроить существующие HTML-макеты консоли.

Альтернативы: чистый HTML/CSS/JS (больше ручной поддержки), Astro Starlight (ещё один
фронтенд-стек), Jekyll (Ruby-зависимость).

### 6.1. Структура

```text
site/
  mkdocs.yml
  requirements.txt
  docs/
    index.md
    getting-started/
    concepts/
    guides/
    reference/
    architecture/
    demo/
    assets/
      docs-site.css
      docs-site.js
      mascot.svg
      img/
  overrides/
```

Сборка: `mkdocs build -f site/mkdocs.yml -d site_build`.
Публикация: `.github/workflows/pages.yml`, permissions `pages: write`, `id-token: write`,
`actions/upload-pages-artifact` + `actions/deploy-pages`.
Ветка публикации: `master`, плюс `workflow_dispatch`.

## 7. Информационная архитектура

### 7.1. Верхнее меню

`Docs` · `Guides` · `Reference` · `Архитектура` · `Demo` · `GitHub` · поиск · тема · `beta`.

### 7.2. Боковая навигация

| Группа | Страницы |
| --- | --- |
| Начало | Обзор, Требования, Установка, Быстрый старт |
| Концепции | Capabilities, Skills, Hooks, Context Package, Orchestration, Runtime store, Verification, Approvals, Worktrees |
| Руководства | `/implement`, `/fast-implement`, TDD и test-author, Code review, QA gate, Release Gate, Console, Web console, Containers, Memory, Repo Map, Troubleshooting |
| Справочник | CLI, Configuration, Hooks reference, Labels, Agents, ADR, Changelog |
| Архитектура | Обзор, Python policy, Rust runtime, Store, IPC, Supervisor, Security |
| Проект | Roadmap/status, Contributing, License |

### 7.3. Карта страниц

| Маршрут | Источник | Приоритет |
| --- | --- | --- |
| `/` | новый лендинг | P0 |
| `/getting-started/` | README + установка | P0 |
| `/getting-started/quick-start/` | harness-guide §0–3 | P0 |
| `/concepts/capabilities/` | README + CAPABILITIES | P1 |
| `/concepts/skills/` | docs/skills/README | P1 |
| `/concepts/hooks/` | docs/hooks/README + ADR 0024 | P1 |
| `/concepts/orchestration/` | backend-orchestration + playbook | P1 |
| `/concepts/runtime-store/` | ADR 0020/0021 | P1 |
| `/concepts/verification/` | ADR 0023 | P1 |
| `/guides/implement/` | harness-guide §4 + docs/skills/implement | P0 |
| `/guides/fast-implement/` | harness-guide §4 + docs/skills/fast-implement | P0 |
| `/guides/tdd/` | docs/skills/tdd + ADR 0014 | P1 |
| `/guides/code-review/` | docs/skills/code-review | P1 |
| `/guides/qa-gate/` | docs/skills/qa-gate + ADR 0023 | P1 |
| `/guides/release-gate/` | ADR 0026 §4 | P1 |
| `/guides/console/` | ADR 0009/0028/0029 | P1 |
| `/guides/web-console/` | ADR 0028/0029 + mockups | P0 |
| `/guides/containers/` | ADR 0022/0025 | P2 |
| `/guides/memory/` | ADR 0010 | P2 |
| `/guides/repo-map/` | ADR 0008 | P2 |
| `/reference/cli/` | harness-guide §0 CLI | P0 |
| `/reference/configuration/` | project.schema + orchestration.schema | P1 |
| `/reference/hooks/` | docs/hooks + ADR 0024 | P1 |
| `/reference/labels/` | triage-labels | P2 |
| `/reference/agents/` | docs/agents/README | P2 |
| `/reference/adr/` | docs/adr/ | P2 |
| `/reference/changelog/` | CHANGELOG | P2 |
| `/architecture/` | ARCHITECTURE | P0 |
| `/architecture/runtime/` | ADR 0019–0022 | P1 |
| `/architecture/security/` | ADR 0022/0024/0025 | P1 |
| `/demo/` | web-console mockups | P0 |
| `/project/status/` | GitHub milestones | P2 |
| `/project/contributing/` | AGENTS + git-workflow | P2 |
| `/project/license/` | LICENSE | P2 |

## 8. Контент

Публичный текст пишется с нуля, а не копируется из внутренних черновиков.

1. **Текущая архитектура.** Python policy + Rust `harness-runtime` + SQLite WAL store.
   Python не является вторым writer-ом operational state.
2. **Store.** `ledger.json` version 4, `AUTHORITY.json`, schema store, audit-цепочка,
   leases и reconcile. Без описания старых форматов.
3. **Verification.** ChangeImpact, `VerificationPlan`, focused/failed-only, full clean-room QA
   на финальном SHA, Release Gate по паре `{candidate, target}` и дереву.
4. **Hooks.** `minimal`/`standard`/`strict`, critical guards, `hook_policy_sha256`, второй runtime.
5. **Console.** TUI и веб-консоль — клиенты одного Сервера консоли; веб — FastAPI + React/TS.
6. **Containers.** Rust supervisor, OCI, Docker/Podman, SELinux, запрет монтирования сокетов.
7. **Статус.** `beta`; никаких обещаний стабильного API до отдельного решения.
8. **Никаких внутренних issue-номеров** в публичных текстах, кроме Changelog/Roadmap.
9. **Единый словарь.** `CONTEXT.md` — источник терминов; сайт использует те же термины.
10. **Маскот.** Присутствует в hero, футере и пустых состояниях; не перегружает чтение.

## 9. Дизайн

Основа — дизайн-токены веб-консоли, но с более свободной типографикой для чтения.

| Токен | Значение |
| --- | --- |
| `--bg` | `#161a20` |
| `--surface` | `#1b1f26` |
| `--panel` | `#232830` |
| `--row` | `#2a303a` |
| `--fg` | `#e8ebef` |
| `--muted` | `#9aa3af` |
| `--primary` | `#6fa8dc` |
| `--accent` | `#d97757` |
| `--ok` | `#8fbf7f` |
| `--warn` | `#e0a458` |
| `--err` | `#d96b6b` |
| `--rule` | `#353d49` |
| `--edge` | `#5a6675` |

Типографика: системный sans для тела, mono для кода, команд, меток и версий. Заголовки лендинга —
крупный sans; бренд `H›` — mono.

Компоненты: topbar, hero, install, status band, feature cards, architecture diagram, docs
layout, code block с copy, callouts, tabs, pager, demo frame, search modal, version badge,
mascot, footer.

Доступность: контраст AA, видимый focus, клавиатурная навигация, `prefers-reduced-motion`,
alt-тексты для диаграмм и маскота, семантические заголовки.

## 10. Макеты

`docs/design/docs-site-mockups/`:

- `index.html` — лендинг: hero с маскотом, install, статус, возможности, архитектура, demo.
- `docs.html` — документация: sidebar, «Быстрый старт», TOC, code blocks, callouts, pager.
- `architecture.html` — архитектура: ownership, Rust runtime, store, IPC, supervisor, security.
- `demo.html` — демо: веб-консоль во фрейме и переключатель экранов.
- `console.html` — самостоятельная демонстрация консоли (4 экрана).
- `site.css`, `site.js` — общие стили и поведение; `mascot.svg` — маскот.

Макеты статические, без внешних ресурсов, данных и сети. Тема, поиск, копирование, мобильное
меню и переключатель экранов работают в памяти.

## 11. Миграция внутренних документов

### 11.1. `docs/harness-guide.md`

Разбить по страницам:

- §0–3 → `/getting-started/` и `/reference/cli/`;
- §4–6 → `/guides/implement/`, `/guides/fast-implement/`, `/guides/tdd/`, `/guides/code-review/`,
  `/guides/qa-gate/`;
- §7–9 → `/reference/labels/`, `/reference/hooks/`, `/concepts/hooks/`;
- §10–11 → `/concepts/worktrees/`, `/concepts/context/`;
- §12–13 → `/reference/skills/`, `/project/structure/`;
- §14 → `/guides/examples/`;
- troubleshooting → `/guides/troubleshooting/`.

После переноса файл удаляется. На время beta можно оставить 3-строчный redirect-stub, чтобы
внешние ссылки не ломались; удалить после стабилизации.

### 11.2. `docs/ARCHITECTURE.md`

Переносится в `/architecture/` и `/architecture/runtime/`; файл удаляется. Ссылки в
`docs/backend-orchestration.md`, `docs/README.md`, README и проверках обновляются.

### 11.3. `README.md`

Сокращается до 60–80 строк:

1. Баннер и badge.
2. Одно предложение: что такое Agent Harness Next.
3. 4 capability в двух строках.
4. Quick start: клонирование, `install-global.py`, `harness init`, `harness health`.
5. Ссылки: сайт, getting started, architecture, demo, ADR, contributing, changelog.
6. Лицензия.

Каталог скиллов и длинные примеры уходят на сайт. README не дублирует справочник.

### 11.4. Проверки, которые нужно обновить

- `scripts/verification/paths.py` — `HARNESS_GUIDE`;
- `scripts/verification/docs_sync.py` — `HARNESS_GUIDE`, `ARCHITECTURE.md`, перечисление
  `docs/agents/{...}.md`;
- `scripts/clean_room/backend_orchestration.py`, `scripts/clean_room/install_and_update.py`;
- `tests/orchestration/test_ci_scenarios.py`;
- `skills/first-party/engineering/implement/SKILL.md`;
- `docs/agents/README.md`, `docs/README.md`, `docs/backend-orchestration.md`, `README.md`.

После удаления файлов `make verify` должен оставаться зелёным. Для сайта добавляется
`mkdocs build --strict` в `pages.yml` и проверка ссылок.

## 12. Проверка и приёмка

- [ ] `mkdocs build --strict` проходит локально и в CI.
- [ ] GitHub Pages workflow публикует сайт; `workflow_dispatch` работает.
- [ ] README ≤ 80 строк и не содержит ссылок на удалённые файлы.
- [ ] `docs/harness-guide.md` и `docs/ARCHITECTURE.md` удалены или заменены redirect-stub.
- [ ] `make verify` зелёный после правки проверок.
- [ ] Нет внешних CDN/шрифтов/скриптов; сайт работает офлайн после загрузки.
- [ ] Мобильная вёрстка 390px, 768px, 1280px; меню, поиск, TOC, copy работают.
- [ ] Тема dark/light, контраст AA, focus visible, `prefers-reduced-motion`.
- [ ] Маскот присутствует в hero, футере и пустых состояниях; alt-текст осмысленный.
- [ ] Demo-страница открывает веб-консоль; 4 ключевых экрана переключаются.
- [ ] Нет приватных терминов, внутренних blocker-списков и незавершённых обещаний.
- [ ] Старые ссылки на `docs/harness-guide.md` и `docs/ARCHITECTURE.md` не дают 404.
- [ ] Репозиторий переименован только после подтверждения владельца; `site_url` обновлён.

## 13. Этапы

| Этап | Результат |
| --- | --- |
| 0 | RFC + макеты |
| 1 | Каркас MkDocs, Pages workflow, лендинг, README |
| 2 | Архитектура, getting started |
| 3 | Guides + reference, перенос harness-guide |
| 4 | Demo + web console |
| 5 | Удаление внутренних docs, проверки, redirects |
| 6 | Repo rename + URL switch + content QA |

## 14. Риски

| Риск | Влияние | Мера |
| --- | --- | --- |
| Переименование репозитория ломает ссылки/CI | Высокое | Отдельный шаг; GitHub redirect; обновить badges, clone URL, docs |
| Удаление harness-guide ломает `make verify` | Высокое | Сначала обновить проверки, потом удалять; stub |
| Сайт дублирует docs и расходится | Среднее | Ссылки на ADR/agents, а не копии; единый словарь |
| MkDocs-зависимость и supply chain | Низкое | Отдельный `site/requirements.txt`, pin, без CDN |
| Pages не включён | Низкое | Включить `build_type=workflow` до первого деплоя |
| Большой объём harness-guide | Среднее | Страницы по разделам, ревью по частям |

## 15. Открытые вопросы

1. Переименовывать ли репозиторий в `agent-harness-next` сейчас или после проверки сайта?
2. Оставлять ли redirect-stub для внутренних руководств на beta или удалять сразу?
3. Нужен ли английский лендинг в первой версии?
4. Публиковать ли `/project/status/` с текущим статусом beta?
5. Включать ли `docs/backend-orchestration.md` в сайт как deep-dive?

## 16. Решения

| Дата | Решение | Статус |
| --- | --- | --- |
| 2026-11-05 | Стек: MkDocs Material, отдельный `site/`, GitHub Actions Pages | ПРИНЯТО |
| 2026-11-05 | Визуальная основа: дизайн-токены веб-консоли | ПРИНЯТО |
| 2026-11-05 | Публичный бренд: `Agent Harness Next`, версия `beta` | ПРИНЯТО |
| 2026-11-05 | Целевой URL: `https://pvmalove.github.io/agent-harness-next/` | ПРИНЯТО, зависит от переименования |
| 2026-11-05 | Маскот: в hero, футере и пустых состояниях | ПРИНЯТО |
| 2026-11-05 | Сначала RFC и макеты, затем тикеты | ПРИНЯТО |
