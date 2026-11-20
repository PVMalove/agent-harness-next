# Жизненный цикл issue worktree в runtime

**Статус: ACCEPTED (2026-11-16).** Тикет #1180. Документ дополняет ADR 0021 (протокол
`harness-runtime`) и ADR 0022 (runtime работает вне песочницы агента): он фиксирует, кто создаёт и
удаляет управляемые worktree и как сессия координатора получает в них право записи.

## Контекст системы

Координатор `/implement` работает в основном checkout и до `batch create` создаёт worktree задачи.
Песочница агентского приложения монтирует `.git/worktrees` репозитория только для чтения, и
настройка разрешённых путей это не отменяет. Поэтому в песочнице:

- `git worktree add` останавливается на полпути: ветка создана, worktree нет;
- `git worktree remove` не удаляет ничего или удаляет только рабочий каталог;
- коммит в worktree, которое создала не эта сессия, падает на `index.lock` в
  `.git/worktrees/<name>`.

Проверка 2026-11-16 в Claude Code показала два работающих механизма:

- `harness-runtime serve` работает вне песочницы и выполняет те же команды git без ограничений;
- сессия получает запись в существующее worktree и в его каталог git-метаданных после пары
  вызовов `EnterWorktree` с `path` и `ExitWorktree` с `action: keep`. Сессия возвращается в
  основной checkout, запись сохраняется до конца сессии и действует для её in-process исполнителей.

Субагент с `isolation: worktree` войти в существующее worktree не может. `git worktree move` в
песочнице падает с `Invalid cross-device link`.

## Действующий контракт

### 1. Операции runtime

Minor 8 протокола добавляет две операции. Обе перечислены в `features` ответа `hello`, пока runtime
store — источник истины.

| Операция | Payload | Результат |
|---|---|---|
| `worktree.create` | `path`, `branch`, `base` | `path`, `branch`, `head`, `created` |
| `worktree.remove` | `path` | `path`, `removed` |
| `worktree.commit` (minor 9, #1246) | `path`, `message`, необязательный `pathspecs` | `path`, `branch`, `head`, `committed` |
| `worktree.rebase` (minor 9, #1246) | `path`, `action` (`start` с `onto` и `upstream`, `continue`, `skip`, `abort`) | `path`, `branch`, `head`, `in_progress`, `conflicts`, `git_output` |
| `worktree.merge` (minor 9, #1246) | `path`, `action` (`start` с `revision` и необязательным `message`, `continue`, `abort`) | то же |

`worktree.create` выполняет `git worktree add --no-track -b <branch> <path> <base>`. Повтор запроса
для уже созданного worktree отвечает `created: false`. Если ветка уже есть, указывает на `base` и
нигде не извлечена, runtime добавляет worktree для неё: так запрос доводит до конца прерванную
ручную команду. `worktree.remove` выполняет `git worktree remove <path>` без `--force` и ветку не
удаляет.

### 2. Граница доверия

Запрос приходит из песочницы, а runtime работает вне её. Поэтому runtime сам проверяет запрос и не
полагается на клиента.

- Создание разрешено только внутри `<repo>/.harness/.sandboxes/worktrees`. Удаление разрешено там же
  и внутри `<repo>/.claude/worktrees`, каталога worktree агентского приложения. Путь вне этих
  каталогов — `policy_denied`.
- Путь абсолютный и без компонента `..`; существующий предок пути внутри управляемого каталога не
  может быть символической ссылкой.
- `branch` и `base` не начинаются с `-`; `branch` проходит `git check-ref-format --branch`.
- Git запускается без оболочки, с `-c core.hooksPath=/dev/null -c core.fsmonitor=false`: hook или
  монитор, записанный из песочницы в `.git`, не исполняется вне её.
- Опции принудительного удаления нет. Worktree с незакоммиченными изменениями и заблокированное
  worktree git удалять отказывается, и runtime возвращает `invariant_violation` с `git_stderr`.

### 3. Клиенты

- `coordinator.py worktree create --branch <branch> --base <ref> [--path <path>]` и
  `coordinator.py worktree remove --path <path>` только запрашивают runtime. Локальной команды git
  взамен они не выполняют. Путь по умолчанию — `.harness/.sandboxes/worktrees/<последний сегмент
  ветки>`.
- Ответ `worktree create` содержит `session_write_access`: может ли сессия писать в worktree и в его
  git-метаданные. При `writable: false` координатор открывает запись парой вызовов из раздела
  «Контекст системы» до `batch create`.
- `harness cleanup` удаляет worktree через `worktree.remove`, пока runtime store — источник истины.
  Если runtime отвечает `protocol_unsupported` или `unknown_operation`, удаляет локальный git.
  Любой другой отказ runtime оставляет worktree на месте и попадает в отчёт.
- `harness cleanup` считает управляемыми прямых потомков `.harness/.sandboxes/worktrees`,
  `.harness/worktrees` и `.claude/worktrees`. Условия удаления прежние, к ним добавлено одно:
  заблокированное worktree (`git worktree lock`) остаётся с причиной `worktree is locked`.

### 4. Коммит через runtime (#1246)

Сессия может писать в файлы worktree, но не в его каталог `.git/worktrees/<name>`. Тогда
in-process исполнитель не выполнит `git add` и `git commit`. Подход взят из qf-studio/pilot
(`agent-isolation-design.md` §4.2): git-операции над рабочей копией агента выполняет доверенный
процесс вне песочницы.

- `worktree.commit` выполняет `git add --all -- [:(literal)<pathspec>...]` и
  `git commit --no-verify --file=-` в worktree. Сообщение передаётся через stdin, а не аргументом.
  Пустое сообщение, сообщение длиннее 64 КиБ и управляющие символы, кроме перевода строки и
  табуляции, — `malformed_request`. Pathspec — непустая строка, относительная и без `..`.
- Путь проверяется как у `worktree.remove`, worktree должно быть в `git worktree list`. Detached
  HEAD и worktree без изменений — `invariant_violation`. Hooks и fsmonitor выключены, как у
  остальных операций.
- Агент не может подложить runtime filter или hook через конфигурацию: песочница не даёт писать
  `.git/config` (проверка 2026-11-20: `could not lock config file .git/config`), глобальный конфиг
  и служебный каталог worktree.
- `coordinator.py worktree commit --path <worktree> (--message <text> | --message-file <file>)
  [--pathspec <path>...]` до запроса к runtime отклоняет detached HEAD, базовую ветку и ветки
  `integration/*`. Hooks агентского приложения, которые охраняют `git commit`, эту команду не видят.
- `batch create`, `dispatch preflight` и `dispatch send` для роли на запись больше не отказывают
  при read-only каталоге git, если сессия может писать в worktree, а runtime отвечает по
  протоколу 1.9 и перечисляет `worktree.commit` в `features`. Если token-файла runtime нет,
  проверка отвечает сразу, без повторов подключения.
- Пока rebase или merge остановлен, `worktree.commit` отказывает: разрешение завершает `continue`
  своей операции.

### 5. Rebase и merge через runtime (#1246)

- `worktree.rebase` `start` выполняет `git rebase --no-autostash --no-update-refs --onto <onto>
  <upstream>` в ветке worktree: другие ветки не сдвигаются, незакоммиченные изменения не прячутся.
  `continue` выполняет `git add --all` и `git rebase --continue`, `skip` и `abort` — одноимённые
  действия git.
- `worktree.merge` `start` выполняет `git merge --no-edit --no-autostash [-m <message>] <revision>`;
  `continue` — `git add --all` и `git merge --continue`; `abort` — `git merge --abort`.
- `onto`, `upstream` и `revision` не начинаются с `-` и разрешаются в коммит до запуска git.
  Сообщение merge — одна непустая строка. Редактор не открывается (`GIT_EDITOR=:`), сообщение,
  подготовленное git, сохраняется.
- Конфликт — успешный ответ: `in_progress: true`, `conflicts` — неслитые пути из
  `git diff --name-only --diff-filter=U`, `git_output` — вывод git (до 2000 символов). Ошибка git без
  остановленной операции — `invariant_violation` с `git_stderr`.
- `start` отказывает, если в worktree уже остановлен rebase или merge. `continue`, `skip` и `abort`
  отказывают, если их операция не остановлена. `start` требует ветку, а не detached HEAD.
- `coordinator.py worktree rebase --path <worktree> (--onto <target> --upstream <old base> |
  --continue | --skip | --abort)` и `coordinator.py worktree merge --path <worktree> (--revision
  <commit> [--message <title>] | --continue | --abort)` проверяют ветку до запроса. Во время
  остановленного rebase веткой считается `head-name` из `rebase-merge` или `rebase-apply`.
- Интерактивный rebase по-прежнему требует записи в каталог git.

## Операционные последствия

- Runtime старше minor 8 операций не знает. Клиент передаёт `requires_minor=8` и получает
  `protocol_unsupported` до отправки запроса. Выход — обновить и перезапустить `harness-runtime`
  либо выполнить ручную команду из `docs/agents/worktrees.md` в терминале вне песочницы.
- Проверки записи в `batch create`, `dispatch preflight` и `dispatch send` (#1126) отказывают до
  запуска пишущей роли и называют каталог, если ни git, ни runtime (раздел 4) не может коммитить.
  Их remedy называет пару вызовов и runtime 1.9.
- Запись, открытая парой вызовов, принадлежит сессии. Новая сессия координатора повторяет оба
  вызова для того же worktree.
- Тесты: `native/harness-runtime/crates/ipc/src/worktree.rs`, `tests/orchestration/test_worktree_lifecycle.py`,
  `tests/core/test_cleanup.py`.
