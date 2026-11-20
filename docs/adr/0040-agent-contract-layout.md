# Раскладка контрактов агента: языковые правила и руководства в `.harness/`

**Статус: ACCEPTED (2026-11-20).** Тикет #1249, эпик #1154. Документ заменяет маршрут seed для
руководств из ADR 0037 §2 (`harness/project/instructions/*.md` → `docs/agents/`) и выводит старый
путь из обращения, что ADR 0037 §9.1 оставил отдельному решению.

## Контекст системы

Агент получает контракты из трёх мест: постоянного контекста (`AGENTS.md`, `CLAUDE.md`), runtime
rules в `.claude/rules/` и руководств, которые читает по ссылке. До этого решения руководства
ставились в `docs/agents/` проекта, а этот репозиторий держал их байтовую копию в своём `docs/agents/`.
Корневой `docs/` поэтому смешивал документацию проекта с установленными контрактами агента, хотя
остальные контракты (skills, rules, агенты, роли) уже жили в каталогах инструмента.

Языковые контракты доходили до агентов неравномерно. `technical-english.md` был managed-инструкцией
в `.harness/instructions/`, и агент получал его, только если сам открывал файл по ссылке «must read».
Промпт in-process воркера `/implement` эту ссылку не называл: её называл только внешний адаптер
Claude Code. Правила русского текста лежали в `docs/technical-russian.md` этого репозитория, в
проекты не попадали и не загружались ни одним runtime.

Проверка 2026-11-20 показала, что in-process subagent Claude Code получает в стартовом контексте
`.claude/rules/*.md` без `paths:`, текст `AGENTS.md` через `@AGENTS.md` в `CLAUDE.md` и глобальный
профиль пользователя. Файл, на который только ссылаются, в контекст не попадает.

## Действующий контракт

### 1. Классы и места установки

| Класс | Источник | Установка | Режим |
| --- | --- | --- | --- |
| Языковое правило | `harness/project/rules/technical-{english,russian}.md` | `.claude/rules/` | managed, в каждой установке |
| Runtime rule | `harness/project/rules/*.md` | `.claude/rules/` | seed, с engineering-suite |
| Руководство | `harness/project/instructions/*.md` | `.harness/instructions/` | seed, с engineering-suite |
| Managed-инструкция | `project-memory.md`, `container-executor.md` | `.harness/instructions/` | managed, со своей capability |
| Агент | `harness/project/agents/*.md` | `.claude/agents/` | seed |

Rule — короткий текст, который действует всегда и лежит в контексте каждой сессии. Руководство —
процедура, которую агент читает по ссылке, когда она нужна; часть руководств проект заполняет своими
данными (`issue-tracker.md`, `triage-labels.md`, `agent-prompt.md`). Поэтому руководства не
переносятся в rules: около 1700 строк процедур грузились бы в каждую сессию и в каждого воркера.

### 2. Языковые правила

`technical-english.md` задаёт английский текст между агентами: брифы, передачи, checkpoint, state
evidence. `technical-russian.md` задаёт русский текст для человека: ответы в чате, вопросы и
варианты, итоговые сводки, документацию, `CHANGELOG.md` и русские completion reports. Текст обоих
правил английский; примеры русского правила русские. Оба файла без `paths:`, поэтому Claude Code
грузит их в каждую сессию и в каждого subagent. Codex читает их по указателю на `.claude/rules/` из
раздела Runtime в `AGENTS.md` (ADR 0039).

Языковые правила — managed-файлы: их ставит каждая установка, включая `project-foundation`, где
seed-файлов нет, а `update` перезаписывает их как любой managed-файл. Правку проекта показывает
`harness diff`.

### 3. Промпт воркера

Промпт каждого воркера называет одну и ту же строку обязательных чтений: контракт `common.md`,
контракт роли и оба языковых правила. Литерал живёт в
`harness/orchestration/core/worker_contract.py`. Stdlib-адаптеры `claude_worker.py` и
`codex_worker.py` повторяют его, а шаблон промпта in-process воркера в `implement/SKILL.md` содержит
его с плейсхолдерами `<repo>` и `<role>`; тест сверяет все копии.

### 4. Перенос существующих проектов

`harness update` переносит руководства, которые harness ставил в `docs/agents/`, в
`.harness/instructions/` до обычного шага seed:

- руководство переезжает вместе с правками проекта, его baseline в `seed_files` lock — вместе с ним;
  дальше `SeedInstall` решает по обычным правилам, обновить файл или оставить;
- копию, равную файлу на новом месте, команда удаляет; отличающуюся оставляет и называет;
- файлы, которые harness не ставит (например, `domain.md` от вендорной настройки), остаются;
- пустые `docs/agents/` и `docs/` удаляются.

Старый managed-файл `.harness/instructions/technical-english.md` `update` удаляет как файл, выбывший
из снимка. Для `AGENTS.md`, `CLAUDE.md` и установленных agent seeds `update` и `diff` предлагают один
diff на файл: замену ссылок на переехавшие пути и, если его нет, указатель для Codex. Проектные
файлы команда не меняет.

### 5. Вендорная настройка

В engineering-suite скилл `setup-matt-pocock-skills` переопределён first-party версией с тем же
именем: трекер она записывает в `.harness/project.json`, руководства ведёт в `.harness/instructions/`,
метки создаёт `/setup-labels`. Вендорный снимок не меняется; в чистом `mattpocock-suite` вендорный
скилл по-прежнему пишет свои файлы в `docs/agents/`.

### 6. Этот репозиторий

Корневой `docs/` хранит только документацию разработчика: `adr/`, `tasks/`, `assets/`, `perf/`,
`rfc/`, `settings/` и отдельные документы. Копии `docs/agents/` и `docs/technical-russian.md` удалены;
`AGENTS.md`, `CLAUDE.md` и `CONTEXT.md` ссылаются на источники в `harness/project/`.

## Операционные последствия

- Новая установка не создаёт `docs/` в проекте. Clean-room проверяет это и сверяет
  `.harness/instructions/` с шаблонами.
- `scripts/verification/docs_sync.py` больше не сверяет копию `docs/agents/`; страница структуры
  сайта перечисляет `.harness/instructions/{...}.md`.
- Код, который читает руководства во время работы (`harness/health/checks/tracker.py`, доска задач
  консоли), читает `.harness/instructions/`; сообщения hooks называют новые пути.
- `uninstall` удаляет managed-файлы вне `.harness/` по одному и сохраняет в резервной копии
  изменённые проектом; seed-руководства внутри `.harness/` уходят вместе с каталогом, а изменённые
  попадают в резервную копию.
