/* Демонстрационные данные макета. Источники и формы повторяют реальный снимок консоли. */
// Пятое поле steps — демонстрационная длительность в секундах; null — источник её не передал.
// Значения заданы для проверки интерфейса, не вычислены по расстоянию между событиями.
const RUNS = [
  { id: '#716', title: 'Ранний сбой worker и наблюдение за запуском', state: 'running', stage: 1, role: 'Архитектор', agent: 'Claude Code', started: '21:58', elapsed: '2 мин', beat: '12 с назад', branch: 'issue/716-worker-early-failure', container: 'harness-716',
    steps: [
      ['21:58:02', 'start', 'Запущен worker в контейнере harness-716', '', 3],
      ['21:58:14', 'read', 'Прочитан docs/agents/git-workflow.md', '412 строк', 8],
      ['21:58:40', 'search', 'Поиск «early_exit» по native/harness-runtime', '7 совпадений в 3 файлах', 24],
      ['21:59:21', 'edit', 'Изменён native/harness-runtime/src/worker.rs', '+18 −3', 32],
      ['21:59:58', 'cmd', 'cargo test -p harness-runtime', '41 пройден · 0 упало', 11],
      ['22:00:10', 'wait', 'Ждёт решения: ограничить число перезапусков?', 'контрольная точка архитектора', null],
    ],
    reports: [] },
  { id: '#704', title: 'Offline worker в rootful Docker', state: 'blocked', stage: 2, role: 'Разработчик', agent: 'Codex', started: '21:44', elapsed: '14 мин', beat: '4 мин назад', branch: 'feature/offline-worker', container: 'harness-704',
    structured: false,
    tail: '[21:50:11] docker: permission denied while trying to connect to the Docker daemon socket\n[21:50:11] worker: executor start failed (rootful=true)\n[21:50:12] worker: retry 1/3 in 20s\n[21:50:32] docker: permission denied while trying to connect to the Docker daemon socket\n[21:50:32] worker: retry 2/3 in 40s',
    steps: [],
    reports: [{ id: 'r-704-dev', type: 'Разработчик', title: 'Rootful Docker daemon не стартовал', state: 'err', created: '21:46', conclusion: 'Нужно решение по окружению: rootful или offline worker.', evidence: [['daemon.log', 'err', 'permission denied'], ['env.json', 'warn', 'rootful = true'], ['receipt.json', 'warn', 'отсутствует']] }] },
  { id: '#555', title: 'Полный цикл red → green → refactor', state: 'wait', stage: 3, role: 'Ревью', agent: 'Claude Code', started: '21:28', elapsed: '31 мин', beat: '31 с назад', branch: 'feature/refactor-cycle', container: 'harness-555',
    steps: [
      ['21:50:03', 'read', 'Прочитан diff: 14 файлов', '+412 −188', 125],
      ['21:52:31', 'cmd', 'make test-fast', '1 284 пройдено', 148],
      ['21:55:09', 'msg', 'Ревью завершено, критичных замечаний нет', 'нужен независимый ревьюер', 1],
      ['21:55:10', 'wait', 'Ждёт назначения второго ревьюера', '', null],
    ],
    reports: [{ id: 'r-555-review', type: 'Ревью', title: 'Ревью · refactor cycle', state: 'warn', created: '21:36', conclusion: 'Изменения готовы; нужен второй ревьюер для независимого подтверждения.', evidence: [['review.md', 'warn', 'нужен второй ревьюер'], ['tests.log', 'ok', 'red → green']] }] },
  { id: '#787', title: 'Harness Next — Rust runtime, recovery, QA', state: 'attention', stage: 5, role: 'PR', agent: 'Claude Code', started: '20:12', elapsed: '1 ч 46 мин', beat: '9 мин назад', branch: 'integration/harness-runtime-reliability', container: 'harness-787',
    steps: [
      ['21:40:00', 'cmd', 'qa run', 'QA полный · 2 прогона', 244],
      ['21:44:12', 'fail', 'Нет exit-кода для bounded restart', 'evidence неполный', null],
      ['21:44:13', 'wait', 'Публикация заблокирована', '', null],
    ],
    reports: [
      { id: 'r-716-qa', type: 'QA', title: 'QA · worker readiness', state: 'warn', created: '22:00', conclusion: 'Нужен повторный прогон с записью exit-кода; публикация заблокирована.', evidence: [['qa-report.json', 'warn', 'readiness ok · exit evidence missing'], ['worker.log', 'warn', 'restart bounded · last exit unknown'], ['receipt.json', 'ok', 'attempt 2 accepted']] },
      { id: 'r-716-review', type: 'Ревью', title: 'Код-ревью', state: 'ok', created: '21:59', conclusion: 'Соответствует стандартам и спецификации; критичных замечаний нет.', evidence: [['review.md', 'ok', 'standards + spec'], ['diff.patch', 'ok', 'только управляемые файлы']] },
    ] },
  { id: '#701', title: 'Восстановление журнала команд после сбоя', state: 'done', stage: 6, role: 'PR', agent: 'Claude Code', started: 'вчера', elapsed: '2 ч 10 мин', beat: '—', branch: 'issue/701-command-journal', container: '—', steps: [], reports: [] },
  { id: '#698', title: 'Лимит токенов в памяти проекта', state: 'done', stage: 6, role: 'PR', agent: 'Codex', started: 'вчера', elapsed: '58 мин', beat: '—', branch: 'issue/698-memory-limit', container: '—', steps: [], reports: [] },
];

const STATE = {
  running: ['info', 'Идёт', 'dot'], blocked: ['err', 'Заблокирован', 'x'], wait: ['warn', 'Ждёт решения', 'clock'],
  attention: ['warn', 'Нужно внимание', 'alert'], done: ['ok', 'Завершён', 'check'],
};

const ATTENTION = [
  { id: 'a1', kind: 'decision', sev: 'warn', run: '#555', title: 'Назначить второго ревьюера для #555', detail: 'Ревью без критичных замечаний, но политика требует независимого подтверждения. QA не запускается.',
    actions: [['Назначить ревьюера', 'primary', 'assign'], ['Открыть запуск', '', 'run:#555']] },
  { id: 'a2', kind: 'decision', sev: 'err', run: '#704', title: 'Выбрать окружение для #704', detail: 'Rootful Docker не стартовал: permission denied на сокете. Продолжить можно только в другом окружении.',
    actions: [['Offline worker', 'primary', 'choose-offline'], ['Rootful', '', 'choose-rootful'], ['Журнал', 'ghost', 'run:#704']] },
  { id: 'a3', kind: 'blocker', sev: 'warn', run: '#787', title: 'Публикация #787 ждёт QA evidence', detail: 'Нет exit-кода для bounded restart; свежих checks нет. PR создать нельзя.',
    actions: [['Повторить QA', 'primary', 'rerun-qa'], ['К воротам', '', 'go:publish']] },
  { id: 'a4', kind: 'health', sev: 'err', title: 'Нет файла .harness/harness.lock', detail: 'Без него неизвестно, какая версия Harness управляет проектом. Это одна из 3 ошибок состояния.',
    actions: [['Исправить', 'primary', 'fix:lock'], ['Все проверки', 'ghost', 'go:health']] },
];

const FEED = [
  ['22:01', 'Публикация #787 заблокирована: нет checks evidence'],
  ['22:00', 'QA по #787: readiness ok, exit evidence missing'],
  ['21:59', 'Ревью #787 пройдено'],
  ['21:55', '#555 ждёт второго ревьюера'],
  ['21:50', '#704: Rootful Docker не стартовал'],
  ['21:44', '#704 передан разработчику (Codex)'],
];

const CHECKS = [
  { id: 'lock', s: 'err', area: 'Файлы Harness', title: 'Файл harness.lock', what: 'Файл .harness/harness.lock отсутствует.', why: 'В нём записаны версия, capabilities и управляемые файлы. Без него обновление не знает, что можно менять.', fix: 'harness install .', time: '22:01' },
  { id: 'agents', s: 'err', area: 'Файлы Harness', title: 'Инструкция AGENTS.md', what: 'Файл AGENTS.md отсутствует.', why: 'Агенты берут из него правила проекта. Без файла они работают по общим умолчаниям.', fix: 'harness install . --only agents', time: '22:01' },
  { id: 'links', s: 'err', area: 'Файлы Harness', title: 'Ссылки обнаружения навыков', what: '.agents/skills и .claude/skills не указывают на ../.harness/skills.', why: 'Runtime не находит навыки проекта.', fix: 'harness repair links', time: '22:01' },
  { id: 'gitattr', s: 'warn', area: 'Окружение', title: 'Файл .gitattributes', what: 'Нет правил переводов строк: поведение зависит от core.autocrlf каждой машины.', why: 'На Windows и Linux один и тот же файл может получать разные переводы строк.', fix: 'harness repair gitattributes', time: '22:01' },
  { id: 'git', s: 'ok', area: 'Окружение', title: 'Git-репозиторий', what: 'Репозиторий найден, ветка integration/harness-runtime-reliability.', why: 'Нужен для задач, веток и публикации.', fix: '', time: '22:01' },
  { id: 'pjson', s: 'ok', area: 'Конфигурация', title: 'project.json', what: 'Файл найден и проходит схему.', why: 'Из него берутся QA-команды и трекер.', fix: '', time: '22:01' },
  { id: 'store', s: 'ok', area: 'Runtime', title: 'runtime-store', what: 'schema 6 · generation 36 · audit 306.', why: 'Журнал запусков и решений.', fix: '', time: '22:01' },
  { id: 'registry', s: 'skip', area: 'Сеть', title: 'Реестр навыков (онлайн)', what: 'Пропущено в офлайн-режиме.', why: 'Пропуск — не успех: актуальность навыков не проверена.', fix: 'harness health --online', time: '—' },
  { id: 'docker', s: 'skip', area: 'Контейнеры', title: 'Docker daemon', what: 'Пропущено: нет прав на сокет.', why: 'Без него не запускаются изолированные worker.', fix: 'harness health --containers', time: '—' },
];

const TICKETS = [
  { n: 912, col: 'backlog', pri: 'mid', t: 'Миграция схемы runtime-store 6 → 7', lab: ['runtime'], free: true },
  { n: 905, col: 'backlog', pri: 'lo', t: 'Документировать профили approval-политики', lab: ['docs'], free: true },
  { n: 899, col: 'backlog', pri: 'hi', t: 'Журнал команд: отбрасывает записи при переполнении', lab: ['runtime', 'bug'], free: true },
  { n: 893, col: 'ready', pri: 'hi', t: 'Windows: путь сокета превышает лимит длины', lab: ['windows', 'bug'], free: true },
  { n: 887, col: 'ready', pri: 'mid', t: 'TUI «Настройка» принимает снимок сервера с каталогом мастера', lab: ['tui'], free: true },
  { n: 716, col: 'doing', pri: 'hi', t: 'Ранний сбой worker и наблюдение за запуском', lab: ['runtime'], run: '#716', stage: 'Архитектор' },
  { n: 704, col: 'doing', pri: 'mid', t: 'Offline worker в rootful Docker', lab: ['containers'], run: '#704', stage: 'Разработчик', blocked: true },
  { n: 555, col: 'review', pri: 'mid', t: 'Полный цикл red → green → refactor', lab: ['skills'], run: '#555', stage: 'Ревью' },
  { n: 787, col: 'review', pri: 'hi', t: 'Harness Next — Rust runtime, recovery, QA', lab: ['epic'], run: '#787', stage: 'QA / PR', blocked: true },
  { n: 701, col: 'done', pri: 'mid', t: 'Восстановление журнала команд после сбоя', lab: ['runtime'] },
  { n: 698, col: 'done', pri: 'lo', t: 'Лимит токенов в памяти проекта', lab: ['memory'] },
];
const COLS = [['backlog', 'Бэклог'], ['ready', 'Готово к работе'], ['doing', 'В работе'], ['review', 'Ревью и QA'], ['done', 'Готово']];

const GATES = [
  { s: 'ok', t: 'Дерево совпадает', d: 'HEAD ветки issue/716-worker-early-failure совпадает с кандидатом, расхождений нет.' },
  { s: 'ok', t: 'Ревью пройдено', d: 'Код-ревью: стандарты и спецификация, критичных замечаний нет.' },
  { s: 'err', t: 'QA: полный прогон с evidence', d: 'Есть readiness, но нет exit-кода для bounded restart. Фокусный прогон не считается evidence.', fix: 'Повторить QA', act: 'rerun-qa' },
  { s: 'err', t: 'Свежие checks', d: 'Результаты checks устарели относительно последнего коммита.', fix: 'Запустить checks', act: 'rerun-checks' },
  { s: 'warn', t: 'Текст PR готов', d: 'Тело PR ещё не подготовлено. Его можно составить по шаблону после QA.', fix: 'Подготовить текст', act: 'prep-pr' },
];

const MODULES = [
  { id: 'harness', n: 214, kids: ['console', 'health', 'orchestration', 'project'] },
  { id: 'native/harness-runtime', n: 96, kids: ['supervisor', 'worker', 'audit', 'ipc'] },
  { id: 'skills', n: 312, kids: [] }, { id: 'scripts', n: 41, kids: [] }, { id: 'tests', n: 588, kids: [] },
];
const SYMBOLS = [
  { n: 'Supervisor::spawn_worker', kind: 'fn', mod: 'native/harness-runtime', file: 'src/supervisor.rs', line: 142, sig: 'pub async fn spawn_worker(&self, spec: WorkerSpec) -> Result<WorkerHandle>', used: ['runtime::serve · src/lib.rs:88', 'Supervisor::restart · src/supervisor.rs:201', 'tests::spawn_ok · tests/worker.rs:12'] },
  { n: 'runtime::serve', kind: 'fn', mod: 'native/harness-runtime', file: 'src/lib.rs', line: 61, sig: 'pub async fn serve(config: ServeConfig) -> Result<()>', used: ['main · src/main.rs:9'] },
  { n: 'AuditChain::append', kind: 'fn', mod: 'native/harness-runtime', file: 'src/audit.rs', line: 77, sig: 'pub fn append(&mut self, entry: Entry) -> Result<Hash>', used: ['Supervisor::spawn_worker · src/supervisor.rs:171', 'decisions::record · src/decisions.rs:44'] },
  { n: 'ConsoleServer', kind: 'class', mod: 'harness', file: 'console/backend/server.py', line: 38, sig: 'class ConsoleServer', used: ['tests/web/serve_console.py:30'] },
  { n: 'validate_project_json', kind: 'fn', mod: 'harness', file: 'health/project_files.py', line: 120, sig: 'def validate_project_json(data: dict) -> list[Problem]', used: ['harness health · health/runner.py:55'] },
];

const UPDATE_FILES = [
  { f: 'skills/implement/SKILL.md', s: 'changed', note: '+12 −4', diff: ['@@ -18,7 +18,15 @@', ' ## Шаги', '-1. Создай ветку от master.', '+1. Создай ветку от integration-ветки эпика.', '+2. Проверь, что рабочее дерево чистое.', ' 2. Напиши тест.'] },
  { f: 'skills/review/SKILL.md', s: 'new', note: 'новый файл', diff: ['@@ -0,0 +1,6 @@', '+# Review', '+Проверяет изменения по стандартам и спецификации.', '+Результат — отчёт review.md.'] },
  { f: 'docs/agents/git-workflow.md', s: 'conflict', note: 'изменён и у вас', diff: ['<<<<<<< ваш файл', 'Ветки называем issue/<ID>-<slug>.', '=======', 'Ветки называем <тип>/<ID>-<slug>.', '>>>>>>> обновление 2.0.0'] },
  { f: 'skills/qa-gate/SKILL.md', s: 'same', note: 'без изменений', diff: [] },
];

const PROJECTS = [
  { id: 'harness', name: 'claude-agent-harness', path: '/home/user/projects/claude-agent-harness', current: true, state: 'warn', note: '3 ошибки состояния' },
  { id: 'site', name: 'harness-docs-site', path: '/home/user/projects/harness-docs-site', state: 'ok', note: 'Готов' },
];
const SETUP = [
  ['ok', 'Git-репозиторий', 'ветка integration/harness-runtime-reliability'],
  ['err', 'Конфигурация Harness', 'нет .harness/harness.lock'],
  ['ok', 'Capabilities', 'установлена 1 из 1'],
  ['warn', 'Снимок навыков', '32 навыка · 1 расхождение'],
  ['warn', 'Локальные файлы', 'нет AGENTS.md и ссылок обнаружения'],
];
const CONFIG_FILES = {
  'project.json': '{\n  "name": "claude-agent-harness",\n  "tracker": "github",\n  "qa": { "command": "make verify" },\n  "branch_pattern": "issue/<ID>-<slug>"\n}',
  'orchestration.json': '{\n  "roles": ["architect", "developer", "review", "qa"],\n  "stale_seconds": 120,\n  "approval": "human"\n}',
  'hook-policy.json': '{\n  "metadata": "project-only",\n  "reject_agent_signature": true\n}',
};

