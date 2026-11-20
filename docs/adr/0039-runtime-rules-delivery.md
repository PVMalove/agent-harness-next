# Доставка runtime rules в Claude Code и Codex

**Статус: ACCEPTED (2026-11-20).** Тикет #1160, эпик #1154. Документ выполняет срез «Runtime
rules» карты владельцев (ADR 0037 §10) и закрывает вопрос §8: поддерживает ли Codex правила по
путям.

## Контекст системы

Обязательные правила проекта лежат в `harness/project/rules/` и ставятся seed-копиями в
`.claude/rules/`. Claude Code грузит этот каталог автоматически; файл без frontmatter `paths:`
действует всегда. Codex этот каталог не читает: до этого решения правила `karpathy-guidelines.md` и
`token-efficiency.md` до Codex не доходили, а шаблон `AGENTS.md.tmpl` на них не ссылался.

Часть правил при этом жила внутри процедур: `git-workflow.md` §1 (Fundamental Constraints) и
обязательные пункты `worktrees.md` → Conventions. Агент получал их, только если сам открывал
процедуру. ADR 0037 отнёс эти пункты к классу mandatory rule и передал их перенос в #1160.

## Действующий контракт

### 1. Codex: правил по путям нет

Решение принято по официальной документации Codex (проверено 2026-11-20):

- [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) (переадресация на
  `learn.chatgpt.com/docs/agent-configuration/agents-md`): «Codex builds an instruction chain when
  it starts (once per run…)», «Starting at the project root (typically the Git root), Codex walks
  down to your current working directory», «Codex includes at most one file per directory».
  Размер цепочки ограничивает `project_doc_max_bytes` (32 KiB). Frontmatter, `paths` и glob-областей
  нет. Вложенный `AGENTS.md` выбирается по рабочему каталогу при старте, а не по файлам, которые
  агент меняет.
- [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules): Codex Rules — политика
  выполнения команд (файлы `.rules` на Starlark, `prefix_rule`, решения allow/prompt/forbidden), а не
  инструкции в контексте модели.

Вывод: у Codex нет механизма правил по путям. Вложенные `AGENTS.md` harness не использует: они
зависят от каталога запуска, а не от затронутых путей. `.claude/rules/` Codex сам не читает.

### 2. Механизм доставки

| Runtime | Как правило попадает в контекст |
| --- | --- |
| Claude Code | Автоматически: `.claude/rules/*.md`; без `paths:` — всегда |
| Codex | Явное чтение: раздел Runtime `AGENTS.md` требует в начале каждой сессии прочитать каждый файл `.claude/rules/` и выполнять его как обязательное правило |

Указатель — текст инструкции, а не механизм загрузки. Harness не обещает для Codex
автоматическую загрузку, `paths:` или enforcement правил из `.claude/rules/`. Процедуры по запросу
(`docs/agents/*.md`, `.harness/instructions/*.md`) остаются по ссылкам.

### 3. Новые runtime rules

| Источник | Установка | Что содержит | Старый путь |
| --- | --- | --- | --- |
| `harness/project/rules/git-delivery.md` | seed → `.claude/rules/git-delivery.md` | `git-workflow.md` §1 дословно: Zero Direct Commits, CLI Only, Body via File, Project-Only Metadata, Issue First, Zero Auto-Merge, PR Confirmation Required | `docs/agents/git-workflow.md` §1 — указатель с именами правил |
| `harness/project/rules/worktree-conventions.md` | seed → `.claude/rules/worktree-conventions.md` | три обязательных пункта `worktrees.md` → Conventions: provisioning-сессия не входит в worktree, конфигурация инструментов не меняется ради worktree, `git-workflow.md` действует в worktree | `docs/agents/worktrees.md` → Conventions — пункт-указатель |

Оба файла без `paths:`: delivery-правила действуют всегда, а «работа в worktree» — состояние
сессии, а не путь файла. Имена не совпадают с `docs/agents/*.md`, чтобы копию правила не путали с
процедурой. Новые файлы ставит существующий `SEED_FOLDERS` и записывает им baseline в
`.harness/harness.lock`.

Заголовок `### 1. Fundamental Constraints & Tooling` в `git-workflow.md` остаётся: на него и на имена
правил ссылаются hooks и skills. Под заголовком — указатель на runtime rule и список имён правил.

### 4. Существующие проекты

- `AGENTS.md` и `CLAUDE.md` проекта CLI не переписывает. `harness diff` и `harness update`
  предлагают вставку указателя в `AGENTS.md`, если активный текст (без fenced code) не упоминает
  `.claude/rules`. Обе вставки одного файла (Technical English и указатель) — одно предложение с
  одним diff.
- Изменённая проектом seed-копия `docs/agents/git-workflow.md` или `docs/agents/worktrees.md`
  остаётся по политике `SeedInstall`. Предупреждение `update` и подсказка `harness diff` для неё
  говорят, что источник правил переехал в `.claude/rules/…`, и локальный текст старого раздела
  больше не грузится как правило.
- Снапшоты закреплённых batch не меняются; перенос действует на следующие dispatch.

## Операционные последствия

- Новое обязательное правило добавляется в `harness/project/rules/`; Codex получает его без правки
  `AGENTS.md`, потому что указатель называет каталог, а не файлы.
- Тикет, который меняет загрузку правил, проверяет Claude Code по `.claude/rules/`, а Codex — по
  указателю в `AGENTS.md`.
- Перенос проверяют сценарии clean-room `scripts/clean_room/install_and_update.py`: свежая
  установка, старый путь, изменённый проектом файл и закреплённый batch.
- Если Codex добавит правила по путям, это решение пересматривается отдельным ADR.
