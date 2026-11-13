# test-author-preflight.sh: проверка активации test-author

## 1. Название и локализация

- **Исходный скрипт:** [`harness/project/hooks/test-author-preflight.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-preflight.sh)
- **Русский перевод:** проверка, что тест-автора можно включить без потери защиты.

## 2. Полное описание

`test-author-preflight.sh` проверяет, что тест-автора можно включить без потери защиты. Это не
hook события: установка копирует скрипт в `.claude/hooks/test-author-preflight.sh`, но не
подключает его в `settings.local.json`. Developer запускает его перед вызовом субагента
test-author, обычно через общую команду `.harness/health/test_author.py preflight`. Скрипт печатает
ровно одну строку JSON и всегда завершается кодом 0: `{"status":"ok"}` или
`{"status":"disabled","reason":"<причина>"}`. Отказ не создаёт состояния оркестрации, а developer
продолжает обычный маршрут.

**Аргументы.** Вызов: `test-author-preflight.sh [--worktree <путь>] [--brief <brief> | --planned]`.

- `--worktree <путь>`. Скрипт проверяет только тот checkout, в котором лежит сам, то есть
  checkout, откуда он запущен. Developer вызывает `test-author-preflight.sh --worktree <worktree из
  brief>` из того worktree, где работает; in-process developer делает это через launcher
  `.harness/health/test_author.py run` своего worktree. Ответ `{"status":"ok"}` возможен, только
  если канонический путь (после `cd` и `pwd -P`) совпадает с checkout скрипта; иначе скрипт
  отвечает `checkout_mismatch`. Путь из аргумента в ответ не попадает.
- `--brief <brief>` выбирает исполнителя автора из утверждённого brief developer. `--planned`
  проверяет план developer из orchestration (так делает `harness health`). Без этих флагов скрипт
  требует явный short-профиль `test_author` в `.harness/project.json`. Флаги взаимоисключающие.
- Повторный `--worktree`, отсутствующее, пустое или неразрешимое значение, `--brief` вместе с
  `--planned` и любые другие аргументы (неизвестный флаг, лишние аргументы) дают
  `checkout_mismatch`. Разбор аргументов идёт сразу после определения корня скрипта, раньше
  остальных проверок.

**Выбор исполнителя.** До проверок Claude Code скрипт запускает установленный селектор
`.harness/health/test_author.py check`. Если селектора нет или он оказался symlink, ответ
`selector_unavailable`. Селектор может отказать с причиной `test_paths_missing`,
`test_runner_missing`, `test_author_missing`, `test_author_config_invalid`, `runtime_unsupported`
или `orchestration_unavailable`; любой другой ответ даёт `selector_unavailable`. Настроенный
runtime без защищённого адаптера никогда не превращается в сессию Claude.

Дальше скрипт проверяет условия и на первом нарушении отвечает фиксированной причиной (таблица
условий и причин есть в [руководстве](../agents/test-author.md), раздел 3). Возможные причины:
`checkout_mismatch`, `selector_unavailable`, `test_author_missing`, `test_author_config_invalid`,
`runtime_unsupported`, `orchestration_unavailable`, `runner_unavailable`, `project_untrusted`,
`project_dir_mismatch`, `claude_code_unsupported`, `agent_missing`, `scoped_hook_unsupported`,
`test_paths_missing`, `test_runner_missing`, `config_invalid`, `write_zone_rejected`,
`guard_hook_unavailable`, `isolation_unavailable`. Ответы guard и runner скрипт пропускает через
список допустимых причин: любое другое значение он заменяет на `guard_hook_unavailable` или
`isolation_unavailable`, поэтому пути и текст чужих ошибок в ответ не попадают.

**Корень проекта.** Скрипт берёт корень из `git rev-parse --show-toplevel` своего checkout. Корень
обязан совпасть с checkout скрипта, иначе ответ `project_untrusted`. Так работают основной
checkout, любой worktree, Claude Code и Codex. `CLAUDE_PROJECT_DIR` не обязателен: Claude Code не
всегда передаёт его в Bash. Если переменная задана, скрипт сравнивает её канонический путь с
корнем Git, и несовпадение даёт `project_dir_mismatch`: scoped guard нативного субагента берёт
проект из этой переменной.

**Доверие проекту.** Нативный режим `claude --print` не показывает диалог доверия, поэтому скрипт
читает решение сам. В `~/.claude.json` (или `$CLAUDE_CONFIG_DIR/.claude.json`) должно стоять
`hasTrustDialogAccepted: true` для точного пути checkout или для основного checkout репозитория,
если checkout является его linked worktree. Основной checkout определяется как родитель
`git rev-parse --git-common-dir`, и он обязан перечислять checkout в `git worktree list`. Ответ
`project_untrusted` дают: отсутствие файла, битый JSON, чужие проекты, доверие только к
родительскому каталогу, незарегистрированный каталог и любое значение, кроме булева `true`. Так
ошибка уходит в безопасную сторону (ADR 0033).

**Режимы Claude Code.** Переменные `CLAUDE_CODE_SIMPLE` и `CLAUDE_CODE_SAFE_MODE` отключают
hooks, поэтому при значении `1` скрипт отвечает `claude_code_unsupported`. Обе переменные есть в
бинарнике Claude Code 2.1.300; при смене версии эту проверку стоит повторить.

**Статические проверки.** Скрипт не запускает Claude Code. Проверки agent, frontmatter и guard
статические, поэтому `guard_hook_unavailable` означает неисправный или неисполняемый guard, а не
доказательство срабатывания hook в живой сессии.

## 3. Проверка реальным Claude Code в clean-room

Срабатывание scoped hook подтверждает не preflight, а сценарий
[`scripts/clean_room/isolated_test_runner.py`](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/isolated_test_runner.py) с
модулем [`claude_probe.py`](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/claude_probe.py). Сценарием управляют переменные
окружения:

| Переменная | Эффект |
| --- | --- |
| не заданы | проба не запрашивается, в логе строка `confirmation not requested` |
| `HARNESS_VERIFY_CLAUDE_TEST_AUTHOR=1` | проба запрошена; без `claude` в `PATH` она пропускается с сообщением, любой другой сбой проваливает сценарий |
| `HARNESS_REQUIRE_CLAUDE_TEST_AUTHOR=1` | проба обязательна; отсутствие `claude` тоже проваливает сценарий |

`make verify` и CI эти переменные не задают: у CI нет учётных данных Claude Code, а проба тратит
квоту. Поэтому её запускают вручную перед PR:

```bash
make test-author-probe
```

Цель выставляет `HARNESS_REQUIRE_TEST_SANDBOX=1`, `HARNESS_VERIFY_CLAUDE_TEST_AUTHOR=1` и
`HARNESS_REQUIRE_CLAUDE_TEST_AUTHOR=1` и запускает весь clean-room (`scripts/test_clean_room.py`).
Нужны Linux с bubblewrap, `claude` в `PATH` и выполненный вход. Результат пробы приводят в теле PR.

Проба дважды запускает `claude --agent test-author` в доверенном clean-room проекте. Первый запуск
просит три вызова: запись `src/canary.txt`, команду `touch bash-probe.txt` и запись
`tests/allowed-probe.txt`. Hook обязан отказать в первых двух с причинами
`write_outside_test_paths` и `runner_only` (они есть только у guard, поэтому подтверждают его
срабатывание), а третий пропустить. Второй запуск отдаёт субагенту требование и сценарий: субагент
сам пишет один тест и запускает его через runner. Результат принимается, только если runner сообщил
`failed`, лог запуска содержит `AssertionError` без `TypeError`, `ImportError` и `SyntaxError`, а
production-код не изменён. Изолированный `HOME` с решением о доверии лежит рядом с проектом.
Ссылка на учётные данные пользователя существует только на время пробы, потом сценарий её удаляет.

Кроме пробы, сценарий без Claude Code проверяет, что preflight включается в доверенном проекте и
отвечает `project_untrusted` при трёх состояниях доверия: решение не принято, запись есть только для
другого проекта, `.claude.json` отсутствует.

## Источник

[test-author-preflight.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-preflight.sh),
[test_preflight.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_preflight.py),
[claude_probe.py](https://github.com/PVMalove/agent-harness-next/blob/master/scripts/clean_room/claude_probe.py),
[docs/agents/test-author.md](../agents/test-author.md),
ADR 0014, ADR 0033
