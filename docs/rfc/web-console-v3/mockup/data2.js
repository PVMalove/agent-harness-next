/* Данные для 13 экранов v3.1 (дополняют data.js). Демонстрационные. */
const REPORTS = [
  { id: 'r-716-qa', type: 'QA', title: 'QA · worker readiness', s: 'warn', ses: '#716', created: '22:00', sum: 'Второй прогон worker дошёл до readiness, но evidence неполный: нет exit-кода для bounded restart.', concl: 'Нужен повторный прогон с записью exit-кода; публикация заблокирована.', ev: [['qa-report.json', 'warn', 'readiness ok · exit evidence missing'], ['worker.log', 'warn', 'restart bounded · last exit unknown'], ['receipt.json', 'ok', 'attempt 2 accepted']], att: [['попытка 1', 'err'], ['попытка 2', 'ok'], ['текущая', 'warn']] },
  { id: 'r-716-review', type: 'Review', title: 'Код-ревью · #716', s: 'ok', ses: '#716', created: '21:59', sum: 'Изменения соответствуют стандартам и спецификации; критичных замечаний нет.', concl: 'Можно передавать в QA; evidence ревью сохранён.', ev: [['review.md', 'ok', 'standards + spec'], ['diff.patch', 'ok', 'только управляемые файлы']] },
  { id: 'r-704-dev', type: 'Developer', title: 'Developer · #704 · offline Docker', s: 'err', ses: '#704', created: '21:46', sum: 'Rootful Docker daemon не стартовал; контейнер не создан.', concl: 'Нужно решение по окружению: rootful или offline worker.', ev: [['daemon.log', 'err', 'permission denied'], ['env.json', 'warn', 'rootful = true']] },
  { id: 'r-555-review', type: 'Review', title: 'Review · #555 · refactor cycle', s: 'warn', ses: '#555', created: '21:36', sum: 'Изменения готовы, но нужен второй ревьюер для независимого подтверждения.', concl: 'Назначить ревьюера; QA пока не запускать.', ev: [['review.md', 'warn', 'нужен второй ревьюер'], ['tests.log', 'ok', 'red → green']] },
  { id: 'r-health', type: 'Health', title: 'Health snapshot · 22:01', s: 'err', ses: '—', created: '22:01', sum: '24 пройдено, 1 внимание, 3 ошибки, 29 пропущено.', concl: 'Ошибки блокируют установку Harness; исправьте файлы Harness.', ev: [['health.json', 'err', '3 errors'], ['checks.log', 'warn', '29 skipped offline']] },
  { id: 'r-publish', type: 'Publish', title: 'Publish evidence · #716', s: 'err', ses: '#716', created: '22:01', sum: 'PR не создан: QA report требует внимания, candidate SHA не закреплён.', concl: 'Сначала закрыть QA evidence, затем готовить PR/MR.', ev: [['publish.json', 'err', 'qa evidence missing']] },
];

const UPD = [
  { f: 'skills/implement/SKILL.md', s: 'upd', note: '+12 −4', d: ['@@ -18,7 +18,15 @@', ' ## Шаги', '-1. Создай ветку от master.', '+1. Создай ветку от integration-ветки эпика.', '+2. Проверь, что рабочее дерево чистое.', ' 2. Напиши тест.'] },
  { f: 'skills/review/SKILL.md', s: 'add', note: 'новый файл', d: ['@@ -0,0 +1,4 @@', '+# Review', '+Проверяет изменения по стандартам и спецификации.', '+Результат — отчёт review.md.'] },
  { f: 'docs/agents/git-workflow.md', s: 'conflict', note: 'изменён и у вас', d: ['<<<<<<< ваш файл', 'Ветки называем issue/<ID>-<slug>.', '=======', 'Ветки называем <тип>/<ID>-<slug>.', '>>>>>>> 2.0.0'] },
  { f: 'AGENTS.md', s: 'local', note: 'локальные правки', d: ['@@ -3,3 +3,5 @@', ' Язык ответов — русский.', '+Дополнительно: тесты запускать через make verify.'] },
  { f: 'harness/CAPABILITIES.json', s: 'upd', note: '+3 −0', d: ['@@ -41,3 +41,6 @@', '+  "runtime-store": { "schema": 6 },'] },
  { f: 'scripts/verify.py', s: 'upd', note: '+22 −9', d: ['@@ -10,6 +10,19 @@', '+def check_runtime_store(): ...'] },
  { f: 'skills/qa-gate/SKILL.md', s: 'upd', note: '+2 −2', d: ['@@ -5,4 +5,4 @@', '-Запусти make test', '+Запусти make verify'] },
  { f: 'docs/agents/artifacts.md', s: 'local', note: 'локальные правки', d: ['@@ -1,2 +1,3 @@', '+Артефакты задач — в docs/tasks/.'] },
];
const SEEDS = ['AGENTS.md', 'CLAUDE.md', '.harness/project.json', '.harness/orchestration.json', 'docs/agents/git-workflow.md', 'docs/agents/artifacts.md', 'docs/agents/triage-labels.md', 'docs/agents/issue-tracker.md', 'docs/agents/worktrees.md', 'docs/agents/domain.md', '.claude/rules/token-efficiency.md', '.claude/rules/karpathy-guidelines.md', '.claude/settings.json', '.gitattributes', '.github/pull_request_template.md'];

const PROJ5 = [
  { id: 'harness', name: 'claude-agent-harness', path: '~/Projects/Code/claude-agent-harness', st: 'warn', note: '3 ошибки состояния', br: 'integration/harness-runtime-reliability', v: '1.5.1' },
  { id: 'site', name: 'harness-docs-site', path: '~/Projects/Code/harness-docs-site', st: 'ok', note: 'Готов', br: 'main', v: '2.0.0' },
  { id: 'api', name: 'billing-api', path: '~/Work/billing-api', st: 'warn', note: 'нет capability', br: 'develop', v: '1.5.1' },
  { id: 'web', name: 'storefront', path: '~/Work/storefront', st: 'skip', note: 'Harness не установлен', br: 'main', v: '—' },
  { id: 'lab', name: 'lab-notes', path: '~/Lab/lab-notes', st: 'ok', note: 'Готов', br: 'main', v: '2.0.0' },
];
const COMPOSITION = [['workflow', 'Workflow', 'навыки процесса: implement, review, qa-gate', '12 навыков'], ['base', 'Основа', 'AGENTS.md, правила, хуки', '9 файлов'], ['upstream', 'Upstream', 'снимок навыков Matt Pocock', '11 навыков'], ['backend', 'Backend', 'оркестрация и runtime', '+ runtime-store']];

const PARAM_GROUPS = [
  ['Project', [['name', 'Имя проекта', 'claude-agent-harness', 'Используется в отчётах и заголовках.', 'Любое понятное имя.'], ['tracker', 'Трекер', 'github', 'Откуда берутся задачи и куда публикуются PR.', 'github, gitlab или local.']]],
  ['Orchestration', [['stale', 'Порог «нет сигнала», сек', '120', 'Через сколько секунд молчания запуск считается устаревшим.', '120 — безопасное значение: ложных тревог мало.'], ['approval', 'Одобрение', 'human', 'Кто подтверждает переходы между этапами.', 'human — единственный режим для публикации.']]],
  ['QA', [['qa_cmd', 'Команда QA', 'make verify', 'Полная проверка перед публикацией.', 'Фокусный прогон не считается evidence.']]],
  ['Dispatch', [['parallel', 'Параллельных запусков', '2', 'Сколько worker работают одновременно.', 'Больше 2 — только в контейнерах.']]],
  ['Hooks', [['hook_meta', 'Метаданные хука', 'project-only', 'Отклоняет подписи ассистентов в коммитах.', 'Рекомендуется оставить.']]],
];
const CFG_FILES = {
  'project.json': '{\n  "name": "claude-agent-harness",\n  "tracker": "github",\n  "qa": { "command": "make verify" },\n  "branch_pattern": "issue/<ID>-<slug>"\n}',
  'orchestration.json': '{\n  "roles": ["architect", "developer", "review", "qa"],\n  "stale_seconds": 120,\n  "approval": "human",\n  "parallel": 2\n}',
};

const REPO_TREE = [
  ['harness/', 214, [['console/', 63], ['health/', 28], ['orchestration/', 71], ['project/', 22]]],
  ['native/harness-runtime/', 96, [['src/supervisor.rs', 1], ['src/worker.rs', 1], ['src/audit.rs', 1], ['src/lib.rs', 1]]],
  ['skills/', 312, []], ['scripts/', 41, []], ['tests/', 588, []],
];
const FILE_VIEW = ['pub async fn serve(config: ServeConfig) -> Result<()> {', '    let store = RuntimeStore::open(&config.store)?;', '    let audit = AuditChain::open(&config.audit)?;', '    let supervisor = Supervisor::new(store.clone(), audit.clone());', '    ipc::listen(config.socket, supervisor).await', '}'];
const REL = [['harness/console', 'native/harness-runtime', 'ipc', 42], ['harness/orchestration', 'harness/console', 'import', 31], ['harness/health', 'harness/project', 'import', 18], ['tests', 'harness', 'import', 204], ['native/harness-runtime', 'SQLite WAL', 'storage', 12]];

const HARNESS_CMDS = [['harness health', 'Проверить состояние проекта', 'только чтение'], ['harness diff', 'Показать, что изменит обновление', 'только чтение'], ['harness update --plan', 'План обновления без применения', 'план'], ['harness cleanup --mode soft', 'Показать, что можно удалить', 'план'], ['harness repo-map status', 'Состояние индекса', 'только чтение'], ['harness runtime status', 'Состояние runtime', 'только чтение']];
