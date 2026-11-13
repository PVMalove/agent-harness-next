"""Why each `harness health` check matters: one sentence per check id, in Russian and English.

The Diagnostics detail shows it under «Почему важно». The table covers every id of
`harness/health/registry.py` `REGISTRY`, including each `directories.*` id of
`harness/health/checks/directories.py` `DIRECTORY_PATHS`; `tests/console/test_check_rationale.py`
fails when a check is added without a rationale. An id outside the table keeps the explicit
no-data state on the screen. `web_catalog.render` ships the table to the SPA as `rationales`."""

from __future__ import annotations

# check id -> (Russian, English)
RATIONALES: dict[str, tuple[str, str]] = {
    "files.lock": (
        "По harness.lock харнесс знает установленную версию, capability и управляемые файлы; без него update и diff не работают.",
        "harness.lock tells the harness its installed version, capabilities and managed files; without it update and diff cannot work.",
    ),
    "files.seed_baseline": (
        "По baseline seed-файлов update заменяет устаревшие файлы сам и не трогает изменённые локально; без него каждый отличающийся файл остаётся старым.",
        "The seed baseline lets update replace outdated seed files itself and keep locally modified ones; without it every differing file stays old.",
    ),
    "files.agents_md": (
        "AGENTS.md — первая инструкция агентам; плейсхолдеры шаблона дают им неверные правила проекта.",
        "AGENTS.md is the agents' first instruction; template placeholders give them wrong project rules.",
    ),
    "files.discovery_links": (
        "Через discovery-ссылки runtime находит навыки проекта; битая ссылка скрывает навыки от агента.",
        "Runtimes find the project's skills through the discovery links; a broken link hides skills from the agent.",
    ),
    "files.project_json": (
        "project.json задаёт трекер, ветки и QA-команды; некорректный файл ломает рабочий процесс задач.",
        "project.json sets the tracker, branches and QA commands; an invalid file breaks the task workflow.",
    ),
    "files.sandboxes": (
        "В .harness/.sandboxes харнесс пишет кэш, логи и рабочие копии; без доступа на запись команды падают.",
        "The harness writes caches, logs and worktrees to .harness/.sandboxes; without write access its commands fail.",
    ),
    "files.orchestration_config": (
        "Координатор читает роли, лимиты и политики из orchestration.json; ошибка в нём останавливает оркестрацию.",
        "The coordinator reads roles, limits and policies from orchestration.json; an error there stops orchestration.",
    ),
    "files.skill_snapshot": (
        "Расхождение снэпшота навыков с пакетом ломает воспроизводимость навыков между машинами.",
        "A skill snapshot that differs from the package breaks skill reproducibility across machines.",
    ),
    "files.skill_registry": (
        "Устаревший реестр навыков ведёт агента к несуществующим или старым навыкам.",
        "A stale skill registry points the agent to missing or outdated skills.",
    ),
    "files.overlay_locks": (
        "Overlay-локи фиксируют локальные правки поверх пакета; рассогласованный лок теряет правки при update.",
        "Overlay locks record local edits over the package; an inconsistent lock loses those edits on update.",
    ),
    "files.integrations": (
        "Неучтённые файлы интеграций (MCP, хуки) меняют поведение агентов в обход инвентаря харнесса.",
        "Unlisted integration files (MCP, hooks) change agent behaviour outside the harness inventory.",
    ),
    "files.verification_routing": (
        "Без verification_commands роли не получают проверок, и результат задачи не подтверждён тестами.",
        "Without verification_commands roles get no checks, and a task result is not confirmed by tests.",
    ),
    "directories.harness": (
        "Каталог .harness хранит всё состояние харнесса; без прав на запись любая команда упадёт.",
        "The .harness directory holds all harness state; without write access every command fails.",
    ),
    "directories.sandboxes": (
        "Каталог .harness/.sandboxes — корень одноразовых данных; без прав на запись сессия упадёт при первой записи.",
        "The .harness/.sandboxes directory is the root of disposable data; without write access a session fails on its first write.",
    ),
    "directories.cache": (
        "В кэш пишутся parser bundle и результаты Repo Map; без записи их приходится строить заново или нельзя построить.",
        "The cache stores the parser bundle and Repo Map results; without write access they are rebuilt each time or cannot be built.",
    ),
    "directories.logs": (
        "В logs пишутся журналы QA и команд; без записи evidence прогона теряется.",
        "QA and command logs go to logs; without write access the evidence of a run is lost.",
    ),
    "directories.scratch": (
        "Scratch — рабочая область временных файлов команд; без записи команды падают на промежуточных шагах.",
        "Scratch is the commands' temporary work area; without write access commands fail mid-way.",
    ),
    "directories.pr_body": (
        "Тексты PR и комментариев готовятся в pr_body и проверяются хуком; без записи публикация не подготовить.",
        "PR and comment texts are drafted in pr_body and checked by the hook; without write access a publication cannot be prepared.",
    ),
    "directories.runs": (
        "В runs хранятся данные запусков worker; без записи dispatch не сохранит результат.",
        "Worker run data lives in runs; without write access a dispatch cannot save its result.",
    ),
    "directories.reports": (
        "В reports пишутся отчёты ролей; без записи координатор не получит отчёт о завершении.",
        "Role reports are written to reports; without write access the coordinator gets no completion report.",
    ),
    "directories.worktrees": (
        "Рабочие копии задач создаются в worktrees; без записи задачу нельзя изолировать от основного checkout.",
        "Task worktrees are created in worktrees; without write access a task cannot be isolated from the main checkout.",
    ),
    "directories.orchestration_state": (
        "Здесь лежит ledger координатора; без записи ни один batch или dispatch не будет записан.",
        "The coordinator ledger lives here; without write access no batch or dispatch can be recorded.",
    ),
    "repo_map.tier": (
        "Dispatch получает контекст из Repo Map; неполная карта даёт роли неверное представление о коде.",
        "Dispatches get their context from the Repo Map; an incomplete map gives roles a wrong picture of the code.",
    ),
    "memory.index": (
        "Без индекса памяти поиск по ADR и глоссарию недоступен, и агент опирается на случайные файлы.",
        "Without the memory index search over ADRs and the glossary is unavailable, and the agent relies on random files.",
    ),
    "memory.model": (
        "Показывает, каким срезом поиска (FTS5 или векторным) отвечает память, чтобы не переоценивать её ответы.",
        "Shows which search slice (FTS5 or vector) answers memory queries, so its answers are not overrated.",
    ),
    "environment.os": (
        "Часть правил и проверок зависит от ОС; без этого контекста результаты других проверок трудно трактовать.",
        "Some rules and checks depend on the OS; without this context other results are hard to read.",
    ),
    "environment.git": (
        "Ветки, worktree и проверки целостности опираются на git; без нужной версии рабочий процесс не работает.",
        "Branches, worktrees and integrity checks rely on git; without a suitable version the workflow does not work.",
    ),
    "environment.git_identity": (
        "Без user.name и user.email коммиты не создаются или получают чужое авторство.",
        "Without user.name and user.email commits fail or get the wrong author.",
    ),
    "environment.gitattributes": (
        "Без .gitattributes переводы строк не нормализуются, и сравнение снэпшотов даёт ложные расхождения.",
        "Without .gitattributes line endings are not normalized, and snapshot comparisons report false drift.",
    ),
    "environment.line_endings": (
        "Переводы строк, не совпадающие с gitattributes, дают шумные diff и ложный drift управляемых файлов.",
        "Line endings that disagree with gitattributes produce noisy diffs and false drift of managed files.",
    ),
    "environment.python": (
        "Харнесс и его проверки требуют минимальной версии Python; старый интерпретатор падает на синтаксисе и API.",
        "The harness and its checks need a minimum Python; an older interpreter fails on syntax and APIs.",
    ),
    "environment.uv": (
        "uv ставит зависимости и запускает QA; без него окружение не воспроизводится.",
        "uv installs dependencies and runs QA; without it the environment is not reproducible.",
    ),
    "environment.glab": (
        "Для GitLab-трекера операции с задачами и MR идут через glab; старая версия ломает команды трекера.",
        "With a GitLab tracker issue and MR operations go through glab; an old version breaks tracker commands.",
    ),
    "environment.dev_env": (
        ".harness/.venv, не совпадающий с uv.lock, даёт тесты на других версиях зависимостей, чем в CI.",
        "A .harness/.venv that differs from uv.lock runs tests on other dependency versions than CI.",
    ),
    "environment.qa_executables": (
        "Если исполняемого файла QA-команды нет в среде агента, обязательный QA падает уже после запуска.",
        "If a QA command's executable is missing from the agent environment, required QA fails only after it starts.",
    ),
    "environment.c_linker": (
        "Без C-компоновщика cc cargo не собирает Rust-бинарники, и Rust-тесты в QA падают.",
        "Without the cc C linker cargo cannot link Rust binaries, and Rust tests in QA fail.",
    ),
    "environment.runtime_socket_path": (
        "Путь сокета длиннее 100 байт не принимается: runtime и тесты, которые его запускают, падают.",
        "A socket path over 100 bytes cannot be created: the runtime and the tests that start it fail.",
    ),
    "environment.output_encoding": (
        "Без UTF-8 вывода русский текст и символы статусов искажаются или вызывают ошибки кодировки.",
        "Without UTF-8 output Russian text and status symbols are garbled or raise encoding errors.",
    ),
    "environment.codex_sandbox": (
        "Без записи в рабочую область и нужной сети sandbox Codex не даст агенту выполнить задачу.",
        "Without workspace write access and the needed network the Codex sandbox stops the agent from doing the task.",
    ),
    "environment.claude_sandbox": (
        "Без файлового sandbox и разрешения на локальные Unix-сокеты Claude не достучится до runtime харнесса.",
        "Without the filesystem sandbox and local Unix socket permission Claude cannot reach the harness runtime.",
    ),
    "environment.codex_uv_cache": (
        "Если sandbox Codex не может писать в кэш uv, установка зависимостей и QA внутри него падают.",
        "If the Codex sandbox cannot write the uv cache, dependency installs and QA inside it fail.",
    ),
    "environment.claude_uv_cache": (
        "Если sandbox Claude Code не может писать в кэш uv, установка зависимостей и QA внутри него падают.",
        "If the Claude Code sandbox cannot write the uv cache, dependency installs and QA inside it fail.",
    ),
    "environment.long_paths": (
        "Без длинных путей Windows не открывает файлы глубже 260 символов, и checkout или тесты падают.",
        "Without long paths Windows cannot open files deeper than 260 characters, and checkouts or tests fail.",
    ),
    "environment.path_length": (
        "Длинный путь к репозиторию съедает запас до MAX_PATH, и вложенные файлы перестают открываться в Windows.",
        "A long repository path eats the headroom under MAX_PATH, and nested files stop opening on Windows.",
    ),
    "environment.pytest_temp": (
        "Если временный каталог pytest не записываем или чужой, тесты падают ещё до запуска.",
        "If pytest's temp directory is not writable or belongs to another user, tests fail before they start.",
    ),
    "environment.symlinks": (
        "Без права создавать symlink discovery-ссылки навыков и часть тестов не работают.",
        "Without the right to create symlinks the skill discovery links and some tests do not work.",
    ),
    "environment.hook_bash": (
        "Хуки проекта запускаются через bash; без Git Bash или с заглушкой WSL они не выполняются как задумано.",
        "Project hooks run through bash; without Git Bash or with the WSL stub they do not run as intended.",
    ),
    "hooks.policy": (
        "Без записанной политики хуков критичные проверки могут расходиться между runtime или не работать вовсе.",
        "Without a recorded hook policy critical checks may differ between runtimes or not run at all.",
    ),
    "hooks.test_author": (
        "Test-author пишет тесты через защищённый адаптер; без него шаг Red в TDD недоступен или не изолирован.",
        "The test author writes tests through a protected adapter; without it the TDD Red step is unavailable or not isolated.",
    ),
    "tracker.project": (
        "Все операции с задачами идут в трекер, который определён здесь; ошибка направит их не в тот проект.",
        "Every issue operation goes to the tracker resolved here; a mistake sends them to the wrong project.",
    ),
    "tracker.auth": (
        "Без авторизации CLI трекера задачи, PR и комментарии не создаются.",
        "Without tracker CLI authentication issues, PRs and comments cannot be created.",
    ),
    "tracker.reachability": (
        "Если origin недостижим, push и проверка веток не работают.",
        "If origin is unreachable, pushes and branch checks do not work.",
    ),
    "tracker.permissions": (
        "Без прав на PR, комментарии и метки рабочий процесс останавливается на публикации.",
        "Without rights for PRs, comments and labels the workflow stops at publication.",
    ),
    "tracker.labels": (
        "Доска и маршрутизация задач опираются на канонические метки; без них задачи теряют статус и приоритет.",
        "The board and issue routing rely on the canonical labels; without them issues lose status and priority.",
    ),
    "tracker.git_base": (
        "Задача без верной Git base начинается не от той ветки, и PR попадает не в ту integration-ветку.",
        "A task without the right Git base starts from the wrong branch, and its PR targets the wrong integration branch.",
    ),
    "orchestration.runtime": (
        "Без запущенного harness-runtime serve оркестрация и очистка worktree не работают.",
        "Without a running harness-runtime serve, orchestration and worktree cleanup do not work.",
    ),
    "orchestration.ledger_summary": (
        "Ledger — источник состояния оркестрации; недоступный или не мигрированный ledger скрывает работу.",
        "The ledger is the source of orchestration state; an unavailable or unmigrated ledger hides the work.",
    ),
    "orchestration.unfinished_batches": (
        "Незавершённые batch держат ветки и worktree; список показывает, что ещё ждёт решения.",
        "Unfinished batches hold branches and worktrees; the list shows what still waits for a decision.",
    ),
    "orchestration.blocked_batches": (
        "Заблокированный batch не движется без решения человека.",
        "A blocked batch does not move without a human decision.",
    ),
    "orchestration.stale_dispatches": (
        "Dispatch без heartbeat, скорее всего, завис или потерял worker и держит слот.",
        "A dispatch without a heartbeat has likely hung or lost its worker and holds the slot.",
    ),
    "orchestration.orphaned_worktrees": (
        "Осиротевшие worktree занимают место и могут содержать несохранённую работу.",
        "Orphaned worktrees take space and may hold unsaved work.",
    ),
    "orchestration.disposable_data": (
        "Показывает объём одноразовых данных, которые освободит harness cleanup.",
        "Shows how much disposable data harness cleanup would free.",
    ),
    "orchestration.adapters": (
        "Устаревший или отсутствующий адаптер запускает worker не так, как ждёт runtime, и dispatch блокируется.",
        "An outdated or missing adapter starts the worker other than the runtime expects, and the dispatch gets blocked.",
    ),
    "orchestration.worker_binaries": (
        "Runtime запускает worker в окружении serve; без claude или codex в его PATH внешний worker не стартует.",
        "The runtime starts workers in the serve environment; without claude or codex on its PATH an external worker does not start.",
    ),
}


def catalog() -> dict[str, dict[str, str]]:
    """The rationales as the SPA reads them: id -> {"ru": ..., "en": ...}."""
    return {check_id: {"ru": ru, "en": en} for check_id, (ru, en) in RATIONALES.items()}


# The short title of each check (the Home and Diagnostics lists show it instead of the id).
# check id -> (Russian title, English title)
TITLES: dict[str, tuple[str, str]] = {
    "files.lock": ("Файл harness.lock", "harness.lock file"),
    "files.seed_baseline": ("Baseline seed-файлов", "Seed file baseline"),
    "files.agents_md": ("Инструкция AGENTS.md", "AGENTS.md instructions"),
    "files.discovery_links": ("Ссылки обнаружения навыков", "Skill discovery links"),
    "files.project_json": ("Настройки project.json", "project.json settings"),
    "files.sandboxes": ("Каталог песочниц", "Sandboxes directory"),
    "files.orchestration_config": ("Настройки оркестрации", "Orchestration settings"),
    "files.skill_snapshot": ("Снимок навыков", "Skill snapshot"),
    "files.skill_registry": ("Реестр навыков", "Skill registry"),
    "files.overlay_locks": ("Блокировки оверлеев", "Overlay locks"),
    "files.integrations": ("Интеграции", "Integrations"),
    "files.verification_routing": ("Маршрутизация проверок", "Verification routing"),
    "directories.harness": ("Каталог .harness", "The .harness directory"),
    "directories.sandboxes": ("Каталог .sandboxes", "The .sandboxes directory"),
    "directories.cache": ("Каталог кэша", "Cache directory"),
    "directories.logs": ("Каталог журналов", "Logs directory"),
    "directories.scratch": ("Черновой каталог", "Scratch directory"),
    "directories.pr_body": ("Каталог описаний PR", "PR body directory"),
    "directories.runs": ("Каталог запусков", "Runs directory"),
    "directories.reports": ("Каталог отчётов", "Reports directory"),
    "directories.worktrees": ("Каталог рабочих копий", "Worktrees directory"),
    "directories.orchestration_state": ("Каталог состояния оркестрации", "Orchestration state directory"),
    "repo_map.tier": ("Уровень Repo Map", "Repo Map tier"),
    "memory.index": ("Индекс памяти", "Memory index"),
    "memory.model": ("Модель памяти", "Memory model"),
    "environment.os": ("Операционная система", "Operating system"),
    "environment.git": ("Программа Git", "Git binary"),
    "environment.git_identity": ("Подпись коммитов Git", "Git commit identity"),
    "environment.gitattributes": ("Файл .gitattributes", "The .gitattributes file"),
    "environment.line_endings": ("Окончания строк", "Line endings"),
    "environment.python": ("Интерпретатор Python", "Python interpreter"),
    "environment.uv": ("Менеджер пакетов uv", "uv package manager"),
    "environment.glab": ("Клиент glab", "glab client"),
    "environment.dev_env": ("Окружение разработки", "Development environment"),
    "environment.qa_executables": ("Исполняемые файлы QA-команд", "QA command executables"),
    "environment.c_linker": ("C-компоновщик для Rust", "C linker for Rust"),
    "environment.runtime_socket_path": ("Путь сокета runtime", "Runtime socket path"),
    "environment.output_encoding": ("Кодировка вывода", "Output encoding"),
    "environment.codex_sandbox": ("Песочница Codex", "Codex sandbox"),
    "environment.claude_sandbox": ("Песочница Claude Code", "Claude Code sandbox"),
    "environment.codex_uv_cache": ("Кэш uv для Codex", "uv cache for Codex"),
    "environment.claude_uv_cache": ("Кэш uv для Claude Code", "uv cache for Claude Code"),
    "environment.long_paths": ("Длинные пути", "Long paths"),
    "environment.path_length": ("Длина путей", "Path length"),
    "environment.pytest_temp": ("Временный каталог pytest", "pytest temporary directory"),
    "environment.symlinks": ("Символические ссылки", "Symbolic links"),
    "environment.hook_bash": ("Bash для хуков", "Bash for hooks"),
    "hooks.policy": ("Политика хуков", "Hook policy"),
    "hooks.test_author": ("Хук автора тестов", "Test author hook"),
    "tracker.project": ("Проект в трекере", "Tracker project"),
    "tracker.auth": ("Вход в трекер", "Tracker sign-in"),
    "tracker.reachability": ("Доступность трекера", "Tracker reachability"),
    "tracker.permissions": ("Права в трекере", "Tracker permissions"),
    "tracker.labels": ("Метки трекера", "Tracker labels"),
    "tracker.git_base": ("Базовая ветка Git", "Git base branch"),
    "orchestration.runtime": ("Процесс runtime", "Runtime process"),
    "orchestration.ledger_summary": ("Сводка ledger", "Ledger summary"),
    "orchestration.unfinished_batches": ("Незавершённые batch", "Unfinished batches"),
    "orchestration.blocked_batches": ("Заблокированные batch", "Blocked batches"),
    "orchestration.stale_dispatches": ("Зависшие dispatch", "Stale dispatches"),
    "orchestration.orphaned_worktrees": ("Брошенные рабочие копии", "Orphaned worktrees"),
    "orchestration.disposable_data": ("Временные данные", "Disposable data"),
    "orchestration.adapters": ("Адаптеры worker", "Worker adapters"),
    "orchestration.worker_binaries": ("Бинарники worker", "Worker binaries"),
}


def titles() -> dict[str, dict[str, str]]:
    """The check titles as the SPA reads them: id -> {\"ru\": ..., \"en\": ...}."""
    return {check_id: {"ru": ru, "en": en} for check_id, (ru, en) in TITLES.items()}
