# Параллельная работа: git worktree { #parallel-work-git-worktrees }

Руководство описывает параллельные worktree, которыми управляет пользователь, и worktree задачи, который coordinator готовит перед `batch create`. Протокол coordinator описан в `.harness/orchestration/playbook.md`.

Чтобы вести несколько feature-веток одновременно и не допускать, чтобы грязное рабочее дерево одной сессии мешало другой, используйте нативные инструменты Claude Code `EnterWorktree` / `ExitWorktree`, а не ручной `git worktree add` с отдельным терминальным мультиплексором. Если установлен `tmux`, `EnterWorktree` сам подключает к worktree сессию `tmux`, а `ExitWorktree` управляет её жизненным циклом (`keep` оставляет её работать, `remove` завершает), и настраивать ничего не нужно. Если `tmux` нет (например, в WSL без полноценного дистрибутива Linux), `EnterWorktree` даёт ту же изоляцию без него.

## Когда использовать { #when-to-use-it }

Только по явной просьбе разработчика или этого документа. Для обычной задачи в одной ветке worktree не нужен: её покрывает обычный поток «ветка задачи + PR» из [git-workflow.md](git-workflow.md). Worktree нужен, когда разработчик хочет вести (или поручить агенту) больше одной задачи параллельно, чтобы у каждой был собственный рабочий каталог и ветка, а не общие.

Чтобы subagent, запущенный через инструмент `Agent`, работал над независимой задачей параллельно, передайте в вызов `isolation: "worktree"` вместо ручного создания worktree: механизм тот же, но ограничен этим subagent.

## Соглашения { #conventions }

Три обязательных пункта ниже — «Сессия, которая лишь готовит worktree…», «Не меняйте конфигурацию инструментов…» и «Всё остальное из git-workflow.md…» — поставляются как runtime rule `.claude/rules/worktree-conventions.md` (источник `harness/project/rules/worktree-conventions.md`). Claude Code загружает его автоматически, Codex читает по указателю из раздела Runtime в `AGENTS.md`. В установленном `docs/agents/worktrees.md` вместо них стоит один пункт-указатель.


- **Правило имени ветки действует и здесь.** Параметр `name` в `EnterWorktree` задаёт имя новой ветки, но копируется не дословно: runtime добавляет префикс и заменяет `/`, так что `feature/issue-366-checkout-quote` превращается в `worktree-feature+issue-366-checkout-quote`. Такое имя не удовлетворяет `branch_pattern` из `.harness/project.json` (см. [git-workflow.md](git-workflow.md#2-workflow-sequence)). Проверьте имя ветки, которую создал инструмент, и переименуйте её до первого коммита. Для задач не оставляйте случайное имя по умолчанию.
- **Сессия, которая лишь готовит worktree для другого исполнителя, в него не входит.** `EnterWorktree` предназначен для сессии, которая сама работает в этой ветке. Сессия coordinator, управляющая `coordinator.py`, к таким не относится: её состояние лежит в `.harness/orchestration/state/` относительно корня репозитория, который она передаёт как `--repo`. Если войти в worktree, состояние раздвоится, а batch станет невидим из корня. Такая сессия создаёт дерево командой `worktree create` (см. [процедуру worktree задачи](../skills/implement.md#issue-worktree)), остаётся в основном checkout и передаёт batch только путь. Единственное исключение — пара вызовов, которая открывает запись (см. «Право записи сессии» в [процедуре worktree задачи](../skills/implement.md#issue-worktree)): `EnterWorktree` с `path`, затем `ExitWorktree` с `action: keep`. Пара возвращает сессию в основной checkout до следующей команды coordinator.
- **Не меняйте конфигурацию инструментов ради worktree.** Правка `.claude/settings.local.json` (в том числе `worktree.baseRef`) ради одной задачи меняет проект для всех последующих сессий. Если базовая ссылка по умолчанию не подходит задаче, создайте дерево явно от нужной ссылки.
- **Базовая ссылка.** Новое worktree для дочерней задачи создаётся от записанной в эпике `origin/<integration-branch>`; задача без эпика использует `origin/<base_branch>` из `.harness/project.json`. Текущий локальный `HEAD` берите, только если задача этого требует (настройка `worktree.baseRef`).
- **Всё остальное из [git-workflow.md](git-workflow.md) действует и внутри worktree:** TDD, `qa-gate` перед открытием PR, подтверждение перед PR, запрет на merge. Worktree меняет только то, *где* идёт работа, но не процесс.
- **Очистка.** Когда задача в worktree готова и её PR слит (или задача заброшена), выйдите через `ExitWorktree`. `remove` выбирайте для завершённой или заброшенной задачи, `keep` только если разработчик хочет вернуться к ней позже. Не оставляйте worktree копиться в `.claude/worktrees/`.
- **Управляемые worktree harness.** Checkout задач, которыми владеют coordinator и CLI, создавайте в `.harness/.sandboxes/worktrees/` основного checkout. Устаревшие чистые worktree показывает `harness cleanup <repo> --mode hard`; `--apply --confirm HARD` удаляет подходящие каталоги и их локальные ветки. Под очистку подпадают и worktree на ветках `integration/*`, и чистые worktree с отсоединённым HEAD (например, для code review), если их коммиты уже в `origin`; у отсоединённых worktree нет ветки, которую можно удалить. Worktree из ledger, грязные, текущие и с неотправленными коммитами остаются на месте. Удалённые ветки остаются.

## Worktree задачи для coordinator { #coordinator-issue-worktree }

Процедурой worktree задачи владеет coordinator (`/implement`): `worktree create`,
`harness worktree-venv`, право записи сессии, auto-gc, восстановление после частичного сбоя и выбор
checkout для worker. Её источник для агентов — `.harness/skills/implement/references/issue-worktree.md`
(ставится с `engineering-suite`), перевод — в [описании скила implement](../skills/implement.md#issue-worktree).

## Окружение worker checkout { #worker-checkout-environment }

Worker готовит issue worktree, не меняя окружение основного checkout:

- **Python-проверки** (`make lint` и pytest-команды brief): coordinator один раз выполняет `harness worktree-venv <repo> <worktree>`. Checkout worktree, rebase или merge дают `pyproject.toml` и `uv.lock` новый mtime без изменения содержимого; из-за этого связанный venv не синхронизируют заново и mtime файлов не сдвигают. В репозитории harness `make` вызывает `scripts/sync_dev_venv.py` вместо `uv sync`: для связанного venv он сравнивает оба файла с основным checkout и не синхронизирует, а если файлы различаются — отказывает и называет remedy (собственный venv worktree).
- **Браузерные e2e (Playwright):** в песочнице домашний кэш (`~/.cache/ms-playwright`) доступен только на чтение, и `playwright install` там падает. Задайте `PLAYWRIGHT_BROWSERS_PATH` в `.harness/.sandboxes/cache/ms-playwright` основного checkout; для `npm ci` `~/.npm` тоже только для чтения, поэтому передайте `npm_config_cache=<main>/.harness/.sandboxes/cache/npm`. Собирайте фронтенд перед каждым прогоном e2e: спека на старой сборке показывает старые падения. В репозитории harness `npm run test:e2e` в `harness/console/frontend` делает всё это сам: собирает `dist`, выбирает каталог браузеров, ставит Chromium (без действий, если он уже есть) и запускает Playwright с аргументами после `--`.
- **Сеть для первой установки:** `registry.npmjs.org` для `npm ci`; `cdn.playwright.dev` и `storage.googleapis.com` (Chrome for Testing) для Chromium. Добавьте их в разрешённые домены песочницы для этой команды. Без них worker отмечает e2e-проверку как `not_run` и называет заблокированный хост.
