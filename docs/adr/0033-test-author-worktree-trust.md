# Тест-автор в worktree developer: корень проекта из Git и доверие worktree

**Статус: ACCEPTED (2026-11-13).** Тикет #1122. Документ заменяет три решения ADR 0035:
обязательный `CLAUDE_PROJECT_DIR` и доверие только к точному пути проекта (абзац «Активация и fallback»
и раздел «Автор в worker worktree: вариант A»), а также отказ `checkout_mismatch` как штатный исход для
in-process developer (тот же раздел). Guard, runner, цикл Red → Green и выбор исполнителя ADR 0035
не меняются.

## Контекст системы

Тест-автор — помощник developer: он работает в worktree developer, пишет новый тест или правит
подходящий старый и передаёт developer только упавший (Red) тест. Developer делает его Green.

В issue worktree preflight отказывал, хотя worktree и его developer уже доверены:

- Claude Code не всегда передаёт `CLAUDE_PROJECT_DIR` в Bash, а preflight требовал эту переменную
  (`project_untrusted`). Корень проекта уже известен Git, и preflight его проверял.
- В `~/.claude.json` нет записи `hasTrustDialogAccepted` для точного пути нового worktree. Claude
  Code доверяет worktree через основной checkout, а preflight принимал только точный путь, поэтому
  каждый новый worktree требовал отдельного диалога доверия (`project_untrusted`).
- In-process developer — субагент сессии coordinator в основном checkout. Scoped guard нативного
  `Agent(test-author)` читает `${CLAUDE_PROJECT_DIR}` этой сессии, то есть основной checkout, поэтому
  preflight основного checkout с `--worktree <worker>` отвечал `checkout_mismatch`, и автор не
  запускался совсем.

## Действующий контракт

### 1. Корень проекта — из Git

- Корень — канонический каталог на два уровня выше hook (`<checkout>/.claude/hooks/`).
  `git -C <checkout> rev-parse --show-toplevel` обязан совпасть с ним, а checkout — быть рабочим
  деревом Git: основной checkout или linked worktree, одинаково в Claude Code и Codex. Иначе —
  `project_untrusted`.
- `CLAUDE_PROJECT_DIR` необязателен: отсутствие или пустое значение не ошибка. Если переменная
  задана, её канонический путь обязан совпасть с корнем Git, иначе отказ `project_dir_mismatch`.
  Причина отдельна от `checkout_mismatch`, который относится к аргументу `--worktree`. Сравнение
  нужно, потому что scoped guard нативного Agent берёт проект из этой же переменной: другой путь
  привязал бы автора к другому checkout.
- Корень проекта не дублируется в `.harness/project.json`, настройках Claude Code или конфиге
  Codex: единственный источник — Git.

### 2. Доверие к worktree доверенного репозитория

Preflight читает `~/.claude.json` (или `$CLAUDE_CONFIG_DIR/.claude.json`) и разрешает автора, если
`hasTrustDialogAccepted: true` стоит:

- у точного пути checkout, как раньше;
- или у основного checkout репозитория, когда checkout — его linked worktree. Основной checkout —
  родитель каталога `git rev-parse --git-common-dir` с именем `.git`. Он обязан быть собственным
  корнем Git и перечислять checkout в `git worktree list --porcelain`.

Доверие не отменено: человек принимает диалог один раз для репозитория. Доверие только к
родительскому каталогу не считается. Каталог, который заимствует `.git`-файл чужого worktree,
не зарегистрирован в репозитории и получает `project_untrusted`. Любая ошибка чтения состояния
доверия или вызова Git — тоже `project_untrusted`.

### 3. Автор у in-process developer

- `--worktree` по-прежнему обязан назвать checkout, где лежит preflight. Preflight основного
  checkout не ручается за другой checkout (`checkout_mismatch`): его guard и runner привязаны к
  основному checkout.
- In-process developer вызывает автора через launcher своего worktree:
  `python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree>
  --brief <brief> --prompt-file <файл>`. Launcher проверяет preflight этого worktree с
  `CLAUDE_PROJECT_DIR=<worker_worktree>` и запускает отдельный процесс `claude --print --agent
  test-author` с тем же рабочим каталогом и той же переменной. Scoped guard и runner этого процесса
  обслуживают worktree developer.
- Действие `preflight --brief` для нативного Agent не подставляет идентичность: переданная родителем
  переменная сравнивается с корнем Git (`project_dir_mismatch`), отсутствующая не мешает.
- Условия вызова те же, что у external developer: исполнитель из утверждённого brief, разрешение
  `Agent(test-author)` или `Agent` в brief, иначе обычный TDD с причиной. Отказ не создаёт blocker,
  dispatch или запись ledger.
- Два правила TDD сохраняются: автор пишет только в `test_paths` своего checkout (scoped guard) и
  передаёт тест только после Red, подтверждённого runner.

### 4. Отклонённые варианты

| Вариант | Решение |
| --- | --- |
| Preflight основного checkout принимает `--worktree` linked worktree того же репозитория | Отклонён: guard и runner основного checkout привязаны к нему, автор не смог бы писать в worker или запускал бы тесты основного checkout. |
| Доверие через любой родительский каталог | Отклонён: шире, чем «worktree доверенного репозитория». |
| Корень проекта в `.harness/project.json` или настройках runtime | Отклонён: второй источник рядом с Git. |

## Операционные последствия

- Для нового worktree доверенного репозитория отдельный диалог доверия и ручной `export` не нужны.
  Запись для точного пути worktree по-прежнему действует.
- Харнесс устанавливается в worker worktree, как и раньше, вместе с `test_paths` и `test_runner`.
- Список отказов preflight: `checkout_mismatch`, `runner_unavailable`, `selector_unavailable`,
  причины выбора исполнителя, `project_untrusted`, `project_dir_mismatch`,
  `claude_code_unsupported`, `agent_missing`, `guard_hook_unavailable`, причины конфигурации и
  изоляции; формат ответа и порядок остальных проверок не меняются.
- `harness health` сверяет доверие по этому же правилу: проверка `hooks.test_author` и строка
  `hooks.test_author_trust`, которая называет путь для диалога доверия. Корень проекта по Git и
  `CLAUDE_PROJECT_DIR` проверяет строка `hooks.test_author_root`.
- Тесты `tests/test_author/test_preflight.py` закрепляют: ответ `ok` без `CLAUDE_PROJECT_DIR` и
  без записи доверия для linked worktree, отказ `project_dir_mismatch`, отказ для незарегистрированного
  каталога и запуск автора launcher-ом in-process developer в его worktree. Живой вызов автора
  in-process developer на настоящем Claude Code `make test-author-probe` не проверяет.
