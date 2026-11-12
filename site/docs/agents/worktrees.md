# Параллельная работа: git worktree { #parallel-work-git-worktrees }

Руководство описывает параллельные worktree, которыми управляет пользователь, и worktree задачи, который coordinator готовит перед `batch create`. Протокол coordinator описан в `.harness/orchestration/playbook.md`.

Чтобы вести несколько feature-веток одновременно и не допускать, чтобы грязное рабочее дерево одной сессии мешало другой, используйте нативные инструменты Claude Code `EnterWorktree` / `ExitWorktree`, а не ручной `git worktree add` с отдельным терминальным мультиплексором. Если установлен `tmux`, `EnterWorktree` сам подключает к worktree сессию `tmux`, а `ExitWorktree` управляет её жизненным циклом (`keep` оставляет её работать, `remove` завершает) — настраивать ничего не нужно. Если `tmux` нет (например, в WSL без полноценного дистрибутива Linux), `EnterWorktree` даёт ту же изоляцию без него.

## Когда использовать { #when-to-use-it }

Только по явной просьбе — разработчика или этого документа. Для обычной задачи в одной ветке worktree не нужен: её покрывает обычный поток «ветка задачи + PR» из [git-workflow.md](git-workflow.md). Worktree нужен, когда разработчик хочет вести (или поручить агенту) больше одной задачи параллельно, чтобы у каждой был собственный рабочий каталог и ветка, а не общие.

Чтобы subagent, запущенный через инструмент `Agent`, работал над независимой задачей параллельно, передайте в вызов `isolation: "worktree"` вместо ручного создания worktree: механизм тот же, но ограничен этим subagent.

## Соглашения { #conventions }

- **Правило имени ветки действует и здесь.** Параметр `name` в `EnterWorktree` задаёт имя новой ветки, но копируется не дословно: runtime добавляет префикс и заменяет `/`, так что `feature/issue-366-checkout-quote` превращается в `worktree-feature+issue-366-checkout-quote`. Такое имя не удовлетворяет `branch_pattern` из `.harness/project.json` (см. [git-workflow.md](git-workflow.md#2-workflow-sequence)). Проверьте имя ветки, которую создал инструмент, и переименуйте её до первого коммита. Для задач не оставляйте случайное имя по умолчанию.
- **Сессия, которая лишь готовит worktree для другого исполнителя, в него не входит.** `EnterWorktree` предназначен для сессии, которая сама работает в этой ветке. Сессия coordinator, управляющая `coordinator.py`, к таким не относится: её состояние лежит в `.harness/orchestration/state/` относительно корня репозитория, который она передаёт как `--repo`. Если войти в worktree, состояние раздвоится, а batch станет невидим из корня. Такая сессия создаёт дерево обычным `git worktree add`, остаётся в основном checkout и передаёт batch только путь.
- **Не меняйте конфигурацию инструментов ради worktree.** Правка `.claude/settings.local.json` (в том числе `worktree.baseRef`) ради одной задачи меняет проект для всех последующих сессий. Если базовая ссылка по умолчанию не подходит задаче, создайте дерево явно от нужной ссылки.
- **Базовая ссылка.** Новое worktree для дочерней задачи создаётся от записанной в эпике `origin/<integration-branch>`; задача без эпика использует `origin/<base_branch>` из `.harness/project.json`. Текущий локальный `HEAD` берите, только если задача этого требует (настройка `worktree.baseRef`).
- **Всё остальное из [git-workflow.md](git-workflow.md) действует и внутри worktree:** TDD, `qa-gate` перед открытием PR, подтверждение перед PR, запрет на merge. Worktree меняет только то, *где* идёт работа, но не процесс.
- **Очистка.** Когда задача в worktree готова и её PR открыт (или заброшен), выйдите через `ExitWorktree`. `remove` — для завершённой или заброшенной задачи, `keep` — только если разработчик хочет вернуться к ней позже. Не оставляйте worktree копиться в `.claude/worktrees/`.
- **Управляемые worktree harness.** Checkout задач, которыми владеют coordinator и CLI, создавайте в `.harness/.sandboxes/worktrees/` основного checkout. Устаревшие чистые worktree показывает `harness cleanup <repo> --mode hard`; `--apply --confirm HARD` удаляет подходящие каталоги и их локальные ветки. Под очистку подпадают и worktree на ветках `integration/*`, и чистые worktree с отсоединённым HEAD (например, для code review), если их коммиты уже в `origin`; у отсоединённых worktree нет ветки, которую можно удалить. Worktree из ledger, грязные, текущие и с неотправленными коммитами остаются на месте. Удалённые ветки остаются.

## Worktree задачи для coordinator { #coordinator-issue-worktree }

Coordinator (`/implement`) обязан создать worktree задачи до `batch create`. `batch create` отказывает, если `git worktree list` не показывает worktree: `worktree '<path>' is not registered by git worktree`. Coordinator выполняет команды ниже в основном checkout и в новое worktree не входит:

```bash
git fetch origin <integration-branch>
git worktree add --no-track -b feature/issue-<ID>-<slug> .harness/.sandboxes/worktrees/issue-<ID>-<slug> origin/<integration-branch>
harness worktree-venv . .harness/.sandboxes/worktrees/issue-<ID>-<slug>
```

- `<integration-branch>` — значение раздела `## Integration Branch` задачи. Если раздела нет, берите значение `## Git base`, затем тот же раздел родительского эпика. Для задачи без эпика берите `base_branch` из `.harness/project.json`. Если у задачи с эпиком значения нет, остановитесь и сообщите о блокере. Не угадывайте его.
- `--no-track` обязателен. Без него `git worktree add -b` записывает upstream новой ветки в `.git/config`. В песочнице `.git/config` может быть защищён от записи, и тогда команда остановится на полпути: ветка есть, а worktree нет.
- `git push -u origin feature/issue-<ID>-<slug>` (см. [git-workflow.md](git-workflow.md#2-workflow-sequence), шаг 2) позже задаёт upstream. Он тоже пишет в `.git/config`, поэтому в песочнице может упасть так же. В таком случае выполните `git push origin feature/issue-<ID>-<slug>` и сообщите разработчику, что upstream не задан.
- `harness worktree-venv` делает `.harness/.venv` worktree символической ссылкой на venv основного checkout, поэтому проверки brief, например `make lint`, запускаются без `make bootstrap`. Ссылка создаётся, только если `uv.lock` и `pyproject.toml` worktree совпадают с основным checkout. Иначе команда отвечает `"status": "refused"`, называет расходящиеся файлы и remedy: отдельный venv в worktree (`UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`). Не запускайте `make bootstrap` в worktree со ссылкой на venv: через ссылку он пересинхронизирует venv основного checkout. После восстановительного `git worktree add` ниже выполните команду снова.
- В `batch create` передайте абсолютный путь worktree как `--worktree`, ветку как `--branch` и integration-ветку как `--integration-ref`. Для задачи без эпика `--integration-ref` не указывайте.

**Восстановление после частичного сбоя.** Если `git worktree add -b` упал, а `git branch --list feature/issue-<ID>-<slug>` показывает ветку, значит ветка есть, а worktree нет. Не создавайте ветку заново и не удаляйте её. Выполните:

```bash
git worktree add .harness/.sandboxes/worktrees/issue-<ID>-<slug> feature/issue-<ID>-<slug>
```

Перед этой командой убедитесь, что ветка указывает на коммит `origin/<integration-branch>`: `git rev-parse feature/issue-<ID>-<slug> origin/<integration-branch>`. Если в ветке есть другие коммиты, остановитесь и сообщите о блокере. Затем подтвердите worktree командой `git worktree list`.

Перед запуском worker передайте выбранный абсолютный checkout как `--worktree` в `dispatch preflight` и `dispatch send`. Для пишущих ролей это должен быть зарегистрированный worktree задачи batch на ветке задачи, на неизменяемом стартовом SHA. Code-review сохраняет явный `--checkout`; QA и publish используют собственные границы coordinator. `send` проверяет выбор ещё раз и возвращает `worker_worktree` и `worker_snapshot_commit` для prompt запуска. Runtime должен поддерживать запуск в этом готовом checkout; одного `isolation: worktree` для такого подключения недостаточно. В Claude Code инструмент Agent не умеет запускать subagent в существующем checkout (он стартует в основном checkout, и `EnterWorktree` там отказывает). Для worker, чей CWD — worktree, используйте транспорт `external` с `.harness/adapters/claude_worker.py`: `dispatch send --adapter <main-repo>/.harness/adapters/claude_worker.py` запускает его в `worker_worktree`, а он стартует там отсоединённый headless `claude -p`. Subagent `in-process` работает через абсолютные пути и `git -C <worker_worktree>`; его self-report доказывает checkout, в котором он работает, но не его CWD. Worker сам проверяет и сообщает свой фактический канонический Git top-level, ветку и HEAD. Основной checkout на том же SHA всё равно остаётся неверным путём для пишущей роли. Адрес репозитория и состояния для coordinator и его CLI держите в основном checkout. Не сбрасывайте candidate ради устаревшего brief.
