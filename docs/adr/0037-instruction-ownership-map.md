# Карта владельцев правил, инструкций и совместимости

**Статус: ACCEPTED (2026-11-16).** Эпик #1154, тикет #1155. Карта описывает состояние ветки
`integration/harness-runtime-reliability` на коммите `6729c976`. Она задаёт владельца каждого
раздела инструкций до переноса и правила совместимости для тикетов эпика #1160, #1162, #1156,
#1161, #1157, #1158 и #1159. Ссылки `путь:строка` верны на этом коммите; при расхождении ищите
названный рядом символ.

## Контекст системы

Агент получает инструкции из нескольких мест: постоянного контекста (`AGENTS.md`, `CLAUDE.md`,
глобальный профиль), правил Claude Code в `.claude/rules/`, общих процедур в `docs/agents/` и
`.harness/instructions/`, `SKILL.md`, ролей оркестрации и hooks. Одно и то же правило иногда
записано в нескольких файлах, а Claude Code и Codex загружают эти файлы по-разному. Установленные
копии могут отставать от исходников. Перед переносом нужно знать для каждого раздела один
редактируемый источник, область применения, потребителей и маршрут установки. Тогда перенос не
сломает существующие установки и не перезапишет правки проекта.

## Действующий контракт

### 1. Классы владельцев

Каждый раздел относится ровно к одному классу. Раздел, который смешивает классы, записан в
инвентаре несколькими строками.

| Класс | Смысл | Владелец |
| --- | --- | --- |
| mandatory rule | Короткое правило, действующее всегда или для набора путей | Постоянный контекст или runtime rules; где runtime не грузит rules, — явное чтение из `AGENTS.md` |
| shared procedure | Процедура для нескольких skills или ролей, читается по запросу | Шаблоны `harness/project/instructions/` |
| skill-specific procedure | Процедура одного skill | `SKILL.md` этого skill или его ресурсы |
| orchestration contract | Бриф, роль, отчёт, маршрут dispatch | `harness/orchestration/` (роли, playbook, код coordinator) |
| automatic enforcement | Правило, которое проверяет hook, health или CI | Hook или скрипт проверки; текст инструкции только ссылается на него |

### 2. Колонки инвентаря

Каждый файл описан строкой-заголовком и таблицей разделов.

- **Строка-заголовок файла:** источник (единственный редактируемый файл), режим установки,
  установленная точка входа, старый путь и поведение совместимости.
- **Таблица разделов:** раздел; класс; область (всегда, по путям, по skill, по роли, по запросу);
  потребители (runtime, skill, роль, hook, код с `путь:строка`); срез миграции (тикет эпика или
  «без переноса»).

Гранулярность — раздел `##`, а для смешанных разделов — группа пунктов одного класса. Соседние
разделы одного класса, области и среза объединены в одну строку: так записаны трекеры в
`issue-tracker.md`, разделы оператора в `container-executor.md` и разделы playbook.

Режимы установки определены кодом:

- **seed** — `SEED_FOLDERS` в `harness/uninstall.py:41`: `harness/project/instructions/*.md` →
  `docs/agents/`, `harness/project/rules/*.md` → `.claude/rules/`, `harness/project/agents/*.md` →
  `.claude/agents/`, `harness/project/hooks/*` → `.claude/hooks/`. Обновление — класс `SeedInstall`
  (`harness/bin/harness.py:988`): файл, совпадающий с baseline в `.harness/harness.lock`,
  заменяется с бэкапом; изменённый локально файл и файл без baseline остаются, пока пользователь
  не выбрал `--force-seed-file` или `--force-seed-files`.
- **managed** — `MANAGED_INSTRUCTIONS` в `harness/uninstall.py:50` и `package_files` в
  `harness/bin/harness.py:352`: `technical-english.md` ставится в каждую установку,
  `project-memory.md` — с engineering-suite, `container-executor.md` — с backend-orchestration;
  цель — `.harness/instructions/`. `update` перезаписывает файл; отличие показывает `harness diff`.
- **resource** — ресурсы capability в `harness/CAPABILITIES.json`, например каталог
  `orchestration` → `.harness/orchestration/`. Режим тот же, что у managed.
- **skill** — `.harness/skills/<name>/`, обнаружение через ссылки `.claude/skills` и
  `.agents/skills` (`DISCOVERY_LINKS`, `harness/health/project_files.py:32`).
- **render-once** — `AGENTS.md` и `CLAUDE.md` проекта создаются, только если их нет
  (`harness/bin/harness.py:1414-1421`). Дальше файлы принадлежат проекту; `update` их не трогает.
- **global** — `bin/install-global.py:224-262`: профиль и global skills в домашнем каталоге.
- **repo-only** — файл этого репозитория, в проекты не ставится.

### 3. Инвентарь: постоянный контекст и rules

**`AGENTS.md`** — repo-only; точка входа Codex и, через `CLAUDE.md`, Claude Code в этом
репозитории. Старого пути и совместимости нет.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Вступление, Language and output | mandatory rule | всегда, этот репозиторий | Claude Code, Codex | без переноса |
| Project index | mandatory rule | всегда, этот репозиторий | Claude Code, Codex | без переноса |
| Search and skill routing | mandatory rule | всегда, этот репозиторий | Claude Code, Codex | без переноса |
| Required boundaries: Git, vendor, root `docs/`, QA, schema | mandatory rule | всегда, этот репозиторий | Claude Code, Codex | без переноса |
| Required boundaries: metadata коммитов и PR | automatic enforcement | всегда | `block-public-attribution.sh`, `scripts/check_public_metadata.py` (CI этого репозитория) | без переноса |
| Required boundaries: порядок delivery | shared procedure (ссылка на `docs/agents/git-workflow.md`) | по запросу | все skills delivery | без переноса |
| Subagents | mandatory rule | всегда, этот репозиторий | Claude Code, Codex | без переноса |

**`CLAUDE.md`** — repo-only; импортирует `@AGENTS.md` и ссылается на `.claude/rules/`. Указатель,
собственных правил нет; срез — без переноса. В этом репозитории `.claude/rules/*.md` — seed-копии
`harness/project/rules/`, которые в Git не хранятся (`.gitignore`: `/.claude/*`). Редактируемый
источник правил — `harness/project/rules/`.

**`harness/project/AGENTS.md.tmpl`** — render-once → `AGENTS.md` проекта; плейсхолдеры
заполняет `start-project` или `integrate-project`. Совместимость: существующий `AGENTS.md`
проекта не меняется; новый текст шаблона доходит только до новых проектов.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Project, Commands, Repository map, Boundaries, Definition of Done, Known pitfalls | mandatory rule, project-owned | всегда | Claude Code, Codex; `harness/health/checks/files.py:154` | без переноса |
| Delivery: checkout, worktrees | mandatory rule | всегда | Claude Code, Codex | без переноса |
| Delivery: metadata коммитов и PR | automatic enforcement | всегда | `block-public-attribution.sh` | без переноса |
| Runtime: Technical English | mandatory rule (триггер обязательного чтения) | перед первой английской передачей | `harness/seed_links.py:29` | без переноса |
| Runtime: skills, REGISTRY, Repo Map, integrations | mandatory rule | всегда | Claude Code, Codex | #1160 |

Шаблон не ссылается на `.claude/rules/`, поэтому правила из `harness/project/rules/` до Codex не
доходят. Это проверено командой
`rg -n 'rules|karpathy|token-eff' harness/project/AGENTS.md.tmpl` — совпадений нет. Пробел
закрывает #1160: указатель в разделе Runtime или другой поддерживаемый способ.

**`CLAUDE.md` проекта** — render-once из `CLAUDE_MD_SEED` (`harness/uninstall.py:36`): строка
`@AGENTS.md`. Указатель; срез — без переноса.

**`global/AGENTS.md`** — global → `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
`~/.kimi-code/AGENTS.md`, `~/.config/opencode/AGENTS.md`; Hermes профиль не получает и читает
`AGENTS.md` проекта. Файл помечен `managed-by: agent-harness`. Один раздел без заголовков:
mandatory rule, всегда, все проекты пользователя; срез — без переноса.

**`harness/project/rules/karpathy-guidelines.md`** — seed → `.claude/rules/karpathy-guidelines.md`.
Frontmatter `paths:` нет, поэтому Claude Code грузит файл всегда. Совместимость — политика
`SeedInstall`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Вступление, Tradeoff, 1. Think before coding, 2. Simplicity first, 3. Surgical changes, 4. Goal-driven execution | mandatory rule | всегда | Claude Code; Codex — нет | #1160 |

**`harness/project/rules/token-efficiency.md`** — seed → `.claude/rules/token-efficiency.md`, без
`paths:`. Совместимость — политика `SeedInstall`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Operational Principles | mandatory rule | всегда | Claude Code; Codex — нет | #1160 |
| Protocol | mandatory rule | всегда | Claude Code; Codex — нет | #1160 |

### 4. Инвентарь: общие процедуры

Источник — `harness/project/instructions/<file>.md`. Корневой `docs/agents/<file>.md` — собственная
seed-копия этого репозитория. `scripts/verification/docs_sync.py:78` требует, чтобы копия совпадала
с источником, кроме `PROJECT_FILLED_TEMPLATES` (`agent-prompt.md`). Проверено командой
`diff docs/agents/<f> harness/project/instructions/<f>`: отличается только
`docs/agents/agent-prompt.md` — в нём заполнены проектные блоки (Rust/Python ownership, Fedora и
Windows, правила тестов и QA). Это допустимое отличие, не дрейф. Остальные копии —
`docs/agents/artifacts.md`, `docs/agents/git-workflow.md`, `docs/agents/issue-tracker.md`,
`docs/agents/test-author.md`, `docs/agents/triage-labels.md`, `docs/agents/worktrees.md` — байт в
байт совпадают с источником.

**`harness/project/instructions/agent-prompt.md`** — seed → `docs/agents/agent-prompt.md`; проект
заполняет блоки. Путь читает код, поэтому его нельзя менять без переходного указателя.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Agent prompt blocks, Architecture invariants, Implementation discipline | shared procedure, project-owned | по запросу | `harness/console/backend/domain/task_board.py:141`, `skills/first-party/engineering/to-tickets/SKILL.md`, `scripts/verification/docs_sync.py:64` | без переноса |

**`harness/project/instructions/artifacts.md`** — seed → `docs/agents/artifacts.md`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Artifacts & Scratchpads: каталоги, имена, `docs/tasks/` | shared procedure | по запросу | skills grilling, to-spec, to-tickets, to-guide; `harness/console/kernel/export.py:7` | #1162 |
| Artifacts & Scratchpads: запись вне `docs/tasks/` и имена файлов в `pr_body/` | automatic enforcement | Write/Edit | `block-scratch-outside-docs-tasks.sh` | без переноса |
| Local runtime storage | shared procedure | по запросу | coordinator, cleanup, QA | без переноса |

**`harness/project/instructions/git-workflow.md`** — seed → `docs/agents/git-workflow.md`. Путь
назван в сообщениях hooks (`harness/project/hooks/direct_commits.py:39`,
`harness/project/hooks/tracker-issue.py:31`).

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| 1. Fundamental Constraints: issue first, ветка, без auto-merge, project-only metadata | mandatory rule | всегда при delivery | все skills delivery, `pr-composer` | #1160 |
| 1. Fundamental Constraints: части, которые проверяют hooks | automatic enforcement | Bash | `check-branch-name.sh`, `tracker-issue.py`, `block-direct-master.sh`, `block-pr-merge.sh`, `block-public-attribution.sh` | без переноса |
| 2. Workflow Sequence | shared procedure | по запросу | skills implement, fast-implement, to-guide, to-pull-requests, to-spec, to-tickets, triage, wayfinder; `require-qa-gate.sh` | #1162 |
| 3. PR Body Template (русский и английский шаблоны) | shared procedure | по запросу | `harness/project/agents/pr-composer.md`, `to-pull-requests` | без переноса |

**`harness/project/instructions/issue-tracker.md`** — seed → `docs/agents/issue-tracker.md`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| GitHub, GitLab, Local markdown | shared procedure | по трекеру проекта | skills code-review, fast-implement, setup-labels, to-guide, to-pull-requests, to-spec, to-tickets, triage, wayfinder | без переноса |
| Wayfinding operations | shared procedure | по запросу | wayfinder; `harness/reporting/delivery_stats.py:258,430` | без переноса |

**`harness/project/instructions/project-memory.md`** — managed → `.harness/instructions/project-memory.md`
(engineering-suite).

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Project memory in interactive skills, Explicit tracker sync, Completion report, Offline retrieval quality gate | shared procedure | по skill | skills architect, diagnosing-bugs, grilling; `scripts/clean_room/install_and_update.py` | без переноса |

**`harness/project/instructions/technical-english.md`** — managed → `.harness/instructions/technical-english.md`
в каждой установке.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Вступление, Scope, Clear instructions, Exact tokens, Examples | shared procedure | перед английской передачей | `AGENTS.md.tmpl` Runtime, `harness/orchestration/roles/common.md`, `harness/orchestration/playbook.md`, `harness/orchestration/adapters/claude_code.py:136`, `harness/seed_links.py:29` | без переноса |

**`harness/project/instructions/test-author.md`** — seed → `docs/agents/test-author.md`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| 1. Purpose, 2. Configuration, 4. Call contract, 5. Red → Green → Refactor, 8. Diagnostics | shared procedure | по запросу | skill tdd, агент test-author, `harness/health/project_files.py:96`, `harness/health/checks/hooks.py` | без переноса |
| 3. Protection | automatic enforcement | агент test-author | `test-author-guard.py`, `run-test.sh`, `test-author-preflight.sh` | без переноса |
| 6. The short `/fast-implement` route | skill-specific procedure (fast-implement) | по skill | fast-implement, tdd | #1162 |
| 7. The full `/implement` route | orchestration contract; дублирует `roles/developer.md` → Red-Green-Refactor with the optional test author | по роли | implement, developer | #1162 (один источник — роль) |

**`harness/project/instructions/triage-labels.md`** — seed → `docs/agents/triage-labels.md`.
Таблицу меток разбирает код, поэтому путь и формат таблиц — машинный контракт.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| The taxonomy, все подразделы меток | shared procedure | по трекеру проекта | `harness/health/checks/tracker.py:57`, `harness/health/labels_table.py`, skills setup-labels, triage, to-spec, to-tickets, to-guide, fast-implement, wayfinder | без переноса |
| State machine, Local markdown tracker, Adapting this taxonomy per project | shared procedure | по запросу | те же | без переноса |

**`harness/project/instructions/worktrees.md`** — seed → `docs/agents/worktrees.md`.

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Вступление, When to use it; Conventions: Base ref, Cleanup, Managed harness worktrees | shared procedure | по запросу | skills implement, fast-implement | без переноса |
| Conventions: provisioning-сессия не входит в worktree; не менять конфигурацию инструментов ради worktree; git-workflow действует в worktree | mandatory rule | при работе в worktree | Claude Code, Codex | #1160 |
| Conventions: Branch naming still applies | automatic enforcement | EnterWorktree | `check-worktree-branch-name.sh` (только Claude Code) | без переноса |
| Coordinator issue worktree | skill-specific procedure (implement) | по skill | implement | #1162 |

**`harness/project/instructions/container-executor.md`** — managed →
`.harness/instructions/container-executor.md` (backend-orchestration).

| Раздел | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| Agent adapter in a container → Project hooks | shared procedure; фиксирует, что managed hooks в issue worktree не доставляются, — enforcement там не обещан | по запросу | оператор, coordinator | без переноса |
| Остальные разделы (окружения, prerequisites, конфигурация, образы, кеши, сеть, blockers, cleanup, отчёты, адаптер, distrobox) | shared procedure для оператора | по запросу | `harness/health/checks/orchestration.py:790`, `harness/container/Dockerfile.qa`, `scripts/clean_room/backend_orchestration.py` | без переноса |

### 5. Инвентарь: orchestration и агенты

Роли, playbook, README и pilot — resource → `.harness/orchestration/` (backend-orchestration).
Класс — orchestration contract. Immutable бриф, манифест роли и схема отчёта остаются
единственным источником контракта роли; второй источник не создаётся. Каждый новый dispatch
закрепляет снапшот конфигурации, проекта и ролей в approval digest (`harness/orchestration/playbook.md`,
Configuration validation and pinned evidence), поэтому перенос файла не меняет уже запущенные batch.

| Файл | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| `harness/orchestration/roles/common.md` (без разделов `##`) | orchestration contract | каждая роль | `harness/orchestration/adapters/claude_code.py:137`, `harness/orchestration/workflow/context_package.py:172` | #1161 (только ссылка на developer skill, если нужна общая) |
| `harness/orchestration/roles/developer.md`: манифест и основной контракт | orchestration contract | роль developer | coordinator, implement | #1161 |
| `harness/orchestration/roles/developer.md`: Red-Green-Refactor with the optional test author | orchestration contract; единственный источник маршрута test-author в `/implement` (см. `test-author.md` §7) | роль developer | developer, test-author | #1162 |
| `harness/orchestration/roles/developer.md`: Rerunning only the failed tests | orchestration contract | роль developer | developer | без переноса |
| `harness/orchestration/roles/rebaser.md` | orchestration contract | маршрут `rebase` | `harness/orchestration/workflow/rebaser.py:54`, `harness/orchestration/core/constants.py:299` | #1158 |
| `harness/orchestration/roles/conflict-resolver.md` | orchestration contract | маршрут `resolve-conflict` | `harness/orchestration/core/constants.py:297`, `harness/orchestration/workflow/resolver_state.py:37` | #1158 (сохранить маршрут) |
| `harness/orchestration/roles/database-migrations.md` | orchestration contract без маршрута | — | `harness/orchestration/runtime_attestation.py:29` | #1159 |
| `harness/orchestration/roles/messaging-integration.md` | orchestration contract без маршрута | — | `harness/orchestration/runtime_attestation.py:30` | #1159 |
| `harness/orchestration/roles/architect.md` | orchestration contract | роль architect | coordinator | без переноса |
| `harness/orchestration/roles/code-review.md` | orchestration contract | роль code-review | coordinator | без переноса |
| `harness/orchestration/roles/qa.md` | orchestration contract | роль qa | coordinator | без переноса |
| `harness/orchestration/roles/verification.md` | orchestration contract | роль verification | coordinator | без переноса |
| `harness/orchestration/playbook.md`: Immutable handoff brief, Developer-retry handoff, Role order, liveness, and transport | orchestration contract | coordinator | implement, coordinator | #1161 (чтение, без нового источника) |
| `harness/orchestration/playbook.md`: остальные разделы — Authority and invariants; Configuration validation and pinned evidence; Lifecycle; Retry routing and abandon; Recovery route table; Automatic path; Operator recovery; Approvals bound to the transition digest; Explicit Context Package inputs; Read-only retry idempotency; Context pressure; Attention state; Pluggable operational interfaces; Versioned lifecycle ledger; Observable external workers; Delivering a worker report after a tool refusal; Completion report; Parallel work and quality gates; Integration accounting; Baseline metrics | orchestration contract | coordinator | implement, coordinator | без переноса |
| `harness/orchestration/README.md` | orchestration contract (справочник оператора, русский) | по запросу | оператор | без переноса |
| `harness/orchestration/pilot.md` | orchestration contract (процедура пилота) | по запросу | оператор | без переноса |

Наблюдения, проверенные 2026-11-16:

1. **rebaser.** Источник `harness/orchestration/roles/rebaser.md` есть, маршрут `rebase` → `rebaser`
   есть (`harness/orchestration/core/constants.py:299`), назначение есть в
   `harness/orchestration.example.json:216`. В main checkout этого репозитория установленный
   `.harness/orchestration/roles/` не содержит `rebaser.md`, а `assignment_plans` в
   `.harness/orchestration.json` не содержит `rebaser`. Проверено командами
   `ls .harness/orchestration/roles/` и чтением ключей `assignment_plans`. Это дрейф одной
   установки, а не доказанный дефект установщика. Разбор — #1158.
2. **Специалисты.** `database-migrations` и `messaging-integration` есть в манифестах, в
   `harness/orchestration.example.json` и в `WORKER_ROLES_REQUIRING_ISSUE_WORKTREE`, но в
   `NEXT_ACTION_DISPATCH_ROLE` (`harness/orchestration/core/constants.py:289`) для них нет маршрута,
   и в `ISSUE_WORKTREE_WRITER_ROLES` их нет. Проверено командой
   `rg -n 'database-migrations' harness -g '!**/tests/**'`. Модель dispatch проектирует #1159;
   регистрация имён требование не закрывает.
3. **developer-worker.** Сейчас worker получает инструкции из брифа, `roles/common.md` и
   `roles/developer.md` (адаптер Claude Code требует прочитать `common.md` и манифест роли —
   `harness/orchestration/adapters/claude_code.py:136-137`). Developer skill нет. #1156 добавляет
   skill, #1161 подключает его к dispatch без изменения брифа, scope и схемы отчёта.

**Агенты Claude Code** — seed → `.claude/agents/<file>.md`. У Codex эквивалента в установке нет:
для Codex нужно явное чтение файла, автоматической загрузки нет.

| Файл | Класс | Область | Потребители | Срез |
| --- | --- | --- | --- | --- |
| `harness/project/agents/code-review-spec.md` | skill-specific procedure (code-review) | по skill | code-review | без переноса |
| `harness/project/agents/code-review-standards.md` | skill-specific procedure (code-review) | по skill | code-review | без переноса |
| `harness/project/agents/pr-composer.md` | shared procedure (исполнитель `git-workflow.md` §3) | по запросу | to-pull-requests, to-guide | без переноса |
| `harness/project/agents/test-author.md` | skill-specific procedure (tdd); frontmatter подключает `test-author-guard.py` | по skill | tdd, fast-implement, `harness/health/checks/hooks.py:56`, `harness/seed_links.py` | без переноса |

### 6. Инвентарь: skills

First-party skills — skill → `.harness/skills/<name>/`; в engineering-suite они заменяют vendor
skills с тем же именем (`overrides`) или добавляются (`additions`, `harness/CAPABILITIES.json`).
Класс — skill-specific procedure. Совместимость: `update` перезаписывает каждый файл снапшота
без проверки локальных правок (`write_snapshot`, `harness/bin/harness.py:476-512`); правки проекта
внутри `.harness/skills/` не сохраняются.

Кроме `SKILL.md` skill может содержать файлы, которые тоже принадлежат ему:

- `agents/openai.yaml` — метаданные Codex; есть у 13 из 19 first-party skills. У ask-matt,
  to-spec, delivery-stats, to-tickets, implement, wayfinder, triage и fast-implement стоит
  `policy.allow_implicit_invocation: false`. В Claude Code тот же запрет задаёт
  `disable-model-invocation: true` во frontmatter `SKILL.md`; у 14 skills он есть, и наборы не
  совпадают (например, у architect, to-guide и to-pull-requests запрет есть только для Claude Code).
  Выравнивание наборов — вне эпика; карта фиксирует различие.
- `scripts/` — исполняемые части qa-gate и diagnosing-bugs.
- Ресурсы `ask-matt/PHASE-BOUNDARIES.md`, `tdd/examples.md`, `triage/OUT-OF-SCOPE.md`,
  `triage/AGENT-BRIEF.md`.

| Skill | Срез | Разделы, которые повторяют общий источник или противоречат правилу |
| --- | --- | --- |
| `skills/first-party/engineering/architect/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/ask-matt/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/code-review/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/delivery-stats/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/diagnosing-bugs/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/fast-implement/SKILL.md` | #1162, #1156 | Смена `status::*` и назначение повторяют `issue-tracker.md` и `triage-labels.md`; developer skill может взять реализацию, а delivery остаётся у fast-implement |
| `skills/first-party/engineering/grilling/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/grill-me/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/grill-with-docs/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/implement/SKILL.md` | #1161, #1162 | Coordinator worktree повторяет `worktrees.md` → Coordinator issue worktree; инструкции developer dispatch |
| `skills/first-party/engineering/qa-gate/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/setup-labels/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/tdd/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/to-guide/SKILL.md` | #1162 | Раздел 5 шаблона повторяет `git-workflow.md` §2: футер `Closes`/`Related to`, проверка закрытия issue, отчёт по задаче |
| `skills/first-party/engineering/to-pull-requests/SKILL.md` | #1162 | Правило `Closes`/`Related to` и проверка закрытия повторяют `git-workflow.md` §2 |
| `skills/first-party/engineering/to-spec/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/to-tickets/SKILL.md` | без переноса | — |
| `skills/first-party/engineering/triage/SKILL.md` | #1157 | Строка 16 требует пометку `> *This was generated by AI during triage.*`; это противоречит project-only metadata (`AGENTS.md`, `git-workflow.md` §1). Исправляется в first-party override; vendor snapshot не меняется |
| `skills/first-party/engineering/wayfinder/SKILL.md` | без переноса | — |

Вспомогательные файлы skills из списка выше принадлежат своему skill; срез — без переноса.

Global skills — global → `~/.claude/skills/`, `~/.agents/skills/` и другие каталоги из
`bin/install-global.py`.

| Skill | Срез | Замечание |
| --- | --- | --- |
| `global-skills/start-project/SKILL.md` | без переноса | Заполняет `AGENTS.md.tmpl`; затрагивается, если #1160 меняет раздел Runtime шаблона |
| `global-skills/integrate-project/SKILL.md` | без переноса | То же; ресурс `RECONSTRUCT-HISTORY.md` принадлежит skill |

Vendor skills (`skills/vendor/`, список — `mattpocock-suite` и `project-foundation` в
`harness/CAPABILITIES.json`): владелец — upstream. Изменения только заменой закреплённого
снапшота; эпик их не меняет.

### 7. Инвентарь: автоматическая проверка

Hooks — seed → `.claude/hooks/`. Claude Code подключает их через
`harness/project/settings.local.json.tmpl`, Codex — через `harness/project/codex-hooks.json.tmpl`.
Codex исполняет проектные hooks только после доверия слою `.codex/` и каждому hook по хэшу
(`harness/health/hook_settings.py:506-516`). Строгость задаёт `hook_policy` (ADR 0024).

| Hook | Правило | Событие | Claude Code | Codex |
| --- | --- | --- | --- | --- |
| `harness/project/hooks/protect-hook-policy.sh` | ADR 0024: hooks и `hook_policy` не меняет агент | PreToolUse Bash, Write/Edit | да | да (Bash, apply_patch) |
| `harness/project/hooks/block-public-attribution.sh` | `git-workflow.md` §1, `AGENTS.md.tmpl` Delivery | PreToolUse Bash | да | да |
| `harness/project/hooks/block-direct-master.sh` | `git-workflow.md` §1: без коммитов в base | PreToolUse Bash | да | да |
| `harness/project/hooks/block-pr-merge.sh` | `git-workflow.md` §1: без auto-merge | PreToolUse Bash | да | да |
| `harness/project/hooks/check-branch-name.sh` | `git-workflow.md` §1: issue first, `branch_pattern` | PreToolUse Bash | да | да |
| `harness/project/hooks/require-qa-gate.sh` | `git-workflow.md` §2: qa-gate перед PR | PreToolUse Bash | да | да |
| `harness/project/hooks/require-bounded-check.sh` | полный прогон QA только через ограниченный вывод | PreToolUse Bash | да | да |
| `harness/project/hooks/block-dangerous-git.sh` | спрашивать перед необратимыми действиями | PreToolUse Bash | да | да |
| `harness/project/hooks/block-scratch-outside-docs-tasks.sh` | `artifacts.md`: каталоги и имена файлов | PreToolUse Write/Edit | да | да (apply_patch) |
| `harness/project/hooks/targeted-check-reminder.sh` | напоминание о целевых проверках (advisory) | PreToolUse Write/Edit/MultiEdit/NotebookEdit, Stop, SubagentStop | да | да (apply_patch, Stop, SubagentStop) |
| `harness/project/hooks/runtime-autostart.sh` | ADR 0031: автозапуск runtime | PreToolUse Bash, Stop, SubagentStop | да | нет |
| `harness/project/hooks/impact-first-touch.sh` | ADR 0024: первое касание пути | PreToolUse Write/Edit/MultiEdit/NotebookEdit | да | да (apply_patch) |
| `harness/project/hooks/sensitive-path-recheck.sh` | ADR 0024: чувствительные пути | PreToolUse Write/Edit/MultiEdit/NotebookEdit | да | да (apply_patch) |
| `harness/project/hooks/check-worktree-branch-name.sh` | `worktrees.md`: имя ветки worktree | PreToolUse EnterWorktree | да | нет (события нет) |
| `harness/project/hooks/mark-qa-gate-passed.sh` | отметка пройденного qa-gate | PostToolUse Bash | да | нет; skill qa-gate вызывает `record-qa-gate-pass.sh` явно |
| `harness/project/hooks/count-skill-usage.sh` | статистика, правила нет | PreToolUse Skill | да | нет |
| `harness/project/hooks/test-author-guard.py` | `test-author.md` §3 | PreToolUse агента test-author (frontmatter) | да | нет (агента нет) |

Скрипты, которые вызывают явно, а не событием runtime:
`harness/project/hooks/record-qa-gate-pass.sh` (skills qa-gate, to-pull-requests),
`harness/project/hooks/run-test.sh` и `harness/project/hooks/test-author-preflight.sh`
(`test-author.md`, skills tdd, fast-implement, implement).

Helpers без собственного события: `harness/project/hooks/hook-envelope.sh`,
`harness/project/hooks/hook_response.py`, `harness/project/hooks/apply_patch_payload.py`,
`harness/project/hooks/protect_hook_policy.py`, `harness/project/hooks/direct_commits.py`,
`harness/project/hooks/pr_commands.py`, `harness/project/hooks/qa-gate-state.py`,
`harness/project/hooks/tracker-issue.py`, `harness/project/hooks/change_impact_hooks.py`,
`harness/project/hooks/runtime_autostart.py`.

Проверки вне hooks:

- `harness health`: `harness/health/checks/tracker.py:57` читает таблицу меток из
  `docs/agents/triage-labels.md`; `harness/health/checks/hooks.py:56` проверяет
  `.claude/agents/test-author.md`; `harness/health/checks/orchestration.py:790` ссылается на
  `.harness/instructions/container-executor.md`.
- `harness diff` показывает отличия managed-файлов от снапшота и `seed_differing`
  (`harness/bin/harness.py:1438-1461`).
- CI этого репозитория: `scripts/check_public_metadata.py` (metadata коммитов и PR) и
  `scripts/verification/docs_sync.py` (копии `docs/agents/` против шаблонов). В целевой проект
  harness CI-проверок не ставит.

Правило без проверки в одном из runtime записано в таблице как «нет». Инструкции не должны
обещать для Codex enforcement, который даёт только Claude Code.

### 8. Загрузка в Claude Code и Codex

| Класс | Claude Code | Codex |
| --- | --- | --- |
| mandatory rule (проект) | `CLAUDE.md` → `@AGENTS.md`; `.claude/rules/*.md` автоматически, с `paths:` — по путям | `AGENTS.md` проекта; `.claude/rules/` не читает — нужно явное чтение по указателю из `AGENTS.md` |
| mandatory rule (глобально) | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| shared procedure | по ссылке из `AGENTS.md`, `SKILL.md` или роли; явное чтение | так же |
| skill-specific procedure | `.claude/skills` → `.harness/skills`; запрет неявного вызова — `disable-model-invocation`; агенты `.claude/agents/` | `.agents/skills` → `.harness/skills`; запрет неявного вызова — `agents/openai.yaml`; агентов нет, нужно явное чтение |
| orchestration contract | бриф и `.harness/orchestration/roles/`; адаптер требует чтения `common.md` и манифеста | бриф и роли; явное чтение |
| automatic enforcement | `.claude/settings.local.json`, hooks таблицы раздела 7 с колонкой «Claude Code: да»; строгость поведенческих hooks задаёт `hook_policy` | `.codex/hooks.json` после доверия; hooks с колонкой «Codex: да» |

Runtime без механизма загрузки получает требование явного чтения. Автоматическую загрузку или
enforcement для такого runtime карта не обещает. Поддерживает ли Codex правила по путям через
вложенные `AGENTS.md`, карта не утверждает: #1160 проверяет это по документации Codex до того, как
выбрать механизм.

### 9. Совместимость при миграции

1. Старые пути `docs/agents/*.md`, `.harness/instructions/*.md` и `.claude/rules/*.md` продолжают
   работать после переноса: остаётся сгенерированная копия или файл-указатель на новый источник.
   Вывод старого пути из обращения — отдельное решение после проверки всех потребителей.
2. Код, скрипты и тесты, которые читают переносимый путь, переводятся в том же тикете, что и
   перенос файла. Источник списка — колонка «Потребители» таблиц §3–§7; перед переносом тикет
   повторяет поиск `rg -n '<старый путь>' harness scripts tests skills global-skills`, потому что
   тесты и clean-room сценарии (`scripts/clean_room/*`) в карте перечислены не полностью.
3. Seed-файл, изменённый проектом, не перезаписывается молча: работают `SeedInstall`,
   `--force-seed-file`, `--force-seed-files` и `--record-seed-baseline`. Новый seed получает
   baseline в `.harness/harness.lock`.
4. `AGENTS.md` и `CLAUDE.md` проекта не перезаписываются. Новый текст `AGENTS.md.tmpl` доходит до
   существующего проекта только ручной правкой. `propose_contract_links` (`harness/seed_links.py`)
   предлагает одну вставку — обязательное чтение Technical English — и другие изменения шаблона
   не доставляет. Если #1160 добавляет в раздел Runtime указатель на rules, он выбирает одно из
   двух: расширить предложения `harness diff` для этого указателя или явно оставить ручную правку и
   сообщить о ней в выводе `harness update`.
5. Смена способа установки seed-файла:
   - **seed заменяется указателем.** Если проект не менял файл, `SeedInstall` заменяет его
     указателем с бэкапом. Если менял, файл остаётся со старым текстом, а `update` печатает
     предупреждение о локальной правке. Тикет добавляет в это предупреждение, что источник
     переехал, чтобы старый и новый тексты не расходились незаметно.
   - **seed становится managed.** Managed-файл `update` перезаписывает без проверки правок
     (`write_snapshot`). Перевод разрешён только вместе с переносом пути: старый seed-путь
     остаётся под политикой `SeedInstall`, новый managed-путь получает новый файл. Перевести
     существующий seed-путь в `MANAGED_INSTRUCTIONS` без такого переноса нельзя.
   - **seed удалён из шаблонов.** `seed_sources` больше не видит файл, поэтому `update` его не
     трогает, а `harness uninstall` не удаляет. Тикет, который удаляет шаблон, либо оставляет его
     указателем до решения о выводе пути, либо документирует ручное удаление.
6. Снапшоты конфигурации, проекта и ролей в закреплённых batch не меняются; перенос действует на
   следующие dispatch.
7. Корневой `docs/` этого репозитория в целевые проекты не копируется. Копии `docs/agents/`
   этого репозитория обновляются вместе с шаблонами, иначе падает `docs_sync.py`.
8. Vendor snapshot не правится вручную.

### 10. Срезы миграции

| Срез | Тикет | Что забирает из карты | Зависит от | Параллельно |
| --- | --- | --- | --- | --- |
| Runtime rules | #1160 | `harness/project/rules/*`, Runtime в `AGENTS.md.tmpl`, `git-workflow.md` §1 (mandatory rule), правила из `worktrees.md` → Conventions, пробел Codex | — | да |
| Workflow rules и процедуры | #1162 | `git-workflow.md` §2, `artifacts.md` (процедура), `test-author.md` §6–§7 и `roles/developer.md` → Red-Green-Refactor, `worktrees.md` → Coordinator issue worktree, повторы в to-guide, to-pull-requests, fast-implement, implement | #1160 (граница правила и процедуры в `git-workflow.md`) | после #1160 |
| Developer skill | #1156 | новый first-party skill; fast-implement как потребитель | — | да |
| Developer dispatch | #1161 | `roles/developer.md`, `roles/common.md`, разделы playbook о брифе, implement | #1156 | после #1156 |
| Triage и attribution | #1157 | `skills/first-party/engineering/triage/SKILL.md:16` | — | да |
| Rebaser | #1158 | `roles/rebaser.md`, `roles/conflict-resolver.md`, дрейф установки и `assignment_plans` | — | да |
| Специалисты | #1159 | `roles/database-migrations.md`, `roles/messaging-integration.md`; только дизайн | — | да |

Строки с пометкой «без переноса» остаются на месте; эпик их не меняет.

### 11. Решение человека

Одобрено 2026-11-16, сопровождающий `lotsmanova`: карта принята целиком, без правок.

- [x] Классы спорных разделов: `git-workflow.md` §1, `worktrees.md` → Conventions,
  `test-author.md` §6–§7.
- [x] Единственный источник маршрута test-author в `/implement` — `roles/developer.md`, а
  `test-author.md` §7 ссылается на роль.
- [x] Правила совместимости §9, включая три случая смены способа установки (п. 5).
- [x] Доставка указателя на rules в существующие проекты (§9 п. 4): выбор между расширением
  `harness diff` и ручной правкой остаётся за #1160 по правилу п. 4.
- [x] Срезы §10: независимые — #1160, #1156, #1157, #1158, #1159; #1162 после #1160; #1161
  после #1156.

## Операционные последствия

- Тикет, который переносит раздел, обновляет строку этой карты в том же PR. Он же обновляет
  русские описания на сайте (`site/docs/agents/`, `site/docs/hooks/`, `site/docs/skills/`, файлы
  `*.md` и `*.en.md`), если они называют перенесённый путь или раздел.
- Перенос seed-файла проверяется сценариями install/update и clean-room: свежая установка,
  обновление, старый путь, изменённый проектом файл, закреплённый batch.
- Тикет, который меняет загрузку правил, проверяет оба runtime: Claude Code — через
  `.claude/rules/` или `AGENTS.md`, Codex — через `AGENTS.md`; для Codex проверяется указатель, а
  не автоматическая загрузка.
- `harness health` и `harness diff` остаются средствами обнаружения дрейфа установки; карта их
  не заменяет.
