/* Справка: тексты взяты из справки реальной консоли (harness/console/kernel/help_text.py) и разложены по вкладкам.
   Клавиши — только те, что работают в этом макете. Справка статична: данные демо не нужны. */
const HELP_KEYS_NAV = { home: 'h', diagnostics: 'd', 'update-harness': 'u', orchestration: 'o', reports: 'r', board: 'b', publish: 'p' };
const HELP_SECTION_TEXT = {
  home: 'Проблемы проекта, рабочие сессии, проверки и контекст проекта.',
  diagnostics: 'Отчёт harness health, онлайн-проверки, исправление --fix и экспорт в Markdown.',
  'update-harness': 'Установленная и доступная версии, дрейф, diff, режим обновления и подтверждённый запуск.',
  'open-project': 'Путь, проверка Git-проекта и план init/adopt/update перед подтверждением.',
  board: 'Спеки, тикеты по статусам, фильтры и карточка тикета с промптом. Трекер только читается.',
  'agent-activity': 'Сессии worker, наблюдаемые шаги и доступы без запуска нового процесса.',
  orchestration: 'Статистика пайплайна, история batch по состояниям и команды coordinator.',
  reports: 'Стадии и отчёты ролей из леджера с фильтрами, хронология batch и QA-логи.',
  publish: 'Пакеты, PR/MR, кандидат и preflight. PR и merge остаются человеку.',
  harness: 'Установка и команды CLI: init, update, diff, adopt, очистка soft/hard, удаление, registry, health, Repo Map, ledger.',
  'repo-map': 'Карта для HEAD: сводка, файлы со статусом парсера, символы, связи и хабы.',
  configuration: 'Шаги project.json и orchestration.json, черновик, проверка и diff, версии и откат, необязательные ИИ-подсказки.',
  help: 'Окно консоли, разделы, клавиши, статусы, безопасность и документация.',
};
const HELP_STEPS = [['Главная', 'что требует внимания.'], ['Доска задач', 'какие задачи в работе.'], ['Ход работы', 'что делают агенты прямо сейчас.'], ['Публикация', 'когда можно создать PR.']];
const HELP_WINDOW = [
  ['Верхняя панель', 'Версия консоли, проект и ветка. Справа: состояние связи, язык, справка.'],
  ['Меню слева', '13 разделов в трёх группах. Текущий раздел отмечен линией слева.'],
  ['Рабочая область', 'Содержимое раздела. Выбор пункта меню, вкладки или сессии не запускает команду.'],
  ['Баннер связи', 'Если связь потеряна, данные только для чтения, а действия отключены.'],
  ['Нижняя строка', 'Клавиши текущего экрана и название раздела.'],
];
const HELP_KEYS = [
  ['Общие', [['Поиск по разделам и командам', ['Ctrl', 'K']], ['Открыть справку', ['?']], ['Закрыть панель, меню или окно', ['Esc']]]],
];
const HELP_STATUS = [
  ['ok', 'Принято', 'check', 'Принято или успешно. «Отчёт получен» ещё не означает, что он принят.'],
  ['info', 'Выполняется', 'refresh', 'Работа идёт сейчас.'],
  ['skip', 'Пауза', 'pause', 'Приостановлено, запускается, отменено или завершено — смотрите подпись.'],
  ['skip', 'Не начато', 'dot', 'Не начато или готово к запуску.'],
  ['err', 'Ошибка', 'x', 'Ошибка или работа заблокирована. Причина доступна в деталях.'],
  ['warn', 'Внимание', 'alert', 'Предупреждение, нет подтверждения или требуется разрешение.'],
];
const HELP_CHECKS = [
  ['ok', 'ok', 'check', 'Проверка прошла успешно.'],
  ['warn', 'warn', 'alert', 'Предупреждение: работать можно, но стоит разобраться.'],
  ['err', 'fail', 'x', 'Ошибка: проверка не пройдена.'],
  ['skip', 'skipped', 'pause', 'Проверка пропущена, а не завершилась успешно. Она ничего не доказала.'],
];
const HELP_SAFETY = [
  ['Команды', 'terminal', [
    'Команды из «Как исправить» консоль только показывает: запускайте их вручную.',
    '«Исправить» в Диагностике выполняет только <code>health --fix</code> и требует повторного нажатия.',
    'Предложенные команды никогда не запускаются автоматически.',
  ]],
  ['Необратимые действия', 'lock', [
    'Перед необратимыми действиями консоль переспрашивает. Отмена ничего не запускает.',
    '<code>ledger reset</code>, hard cleanup и удаление харнесса требуют ввести <code>RESET</code>, <code>HARD</code> или <code>UNINSTALL</code>.',
    'Harness показывает фактический план очистки: размер и число файлов по категориям, пропуски и дополнения hard. Набор, изменившийся после подтверждения, требует нового просмотра.',
    'Строки worktree показывают dirty counts и причины защиты. Удаление перепроверяет активные batch, возраст, Git и сохранность коммитов на origin; ветка и PR остаются.',
  ]],
  ['Данные и версии', 'db', [
    'Экспорты сохраняются в <code>docs/tasks/</code> и никогда не перезаписываются.',
    'Мастер пишет JSON только после итогового подтверждения и сохраняет предыдущую версию.',
    'Версии лежат в <code>.harness/config_versions/</code> и переживают cleanup. Откат восстанавливает оба файла, включая отсутствие файла.',
    'Вывод команд Harness поступает по мере чтения. Уход со страницы не останавливает команду: повторное открытие покажет тот же запуск и полный результат. Новый запуск допускается только после физического завершения.',
  ]],
  ['ИИ-подсказки', 'spark', [
    'ИИ по умолчанию выключен. Проверка CLI не обращается к модели, запрос выполняется отдельной кнопкой через существующий login Codex или Claude Code CLI.',
    'Недоступный CLI не блокирует мастер. Рекомендация ИИ принимается только в черновик.',
  ]],
  ['Что показывает консоль', 'eye', [
    'Только наблюдаемые факты: то, что агент сообщил, а не его рассуждения.',
    'Stale не значит «остановлен»: устаревший сигнал не доказывает, что процесс завершён.',
    'Evidence — основание для решения, а не само решение.',
  ]],
];
const HELP_FAQ = [
  ['Почему «пропущено» не считается успехом?', 'Пропущенная проверка не выполнялась и ничего не доказала. Консоль показывает её отдельно и не засчитывает как пройденную.'],
  ['Что такое stale?', 'Факт старше своего срока: heartbeat воркера, аренда QA lane или кэш снимка. Stale означает «перепроверьте», а не «сломано».'],
  ['Почему офлайн- и онлайн-проверки разные?', 'Офлайн-проверки читают только локальные файлы. Онлайн-проверки обращаются к трекеру и GitHub и запускаются отдельно.'],
  ['Что считается evidence?', 'Записанный результат команды: отчёт воркера в ledger, прогон QA, проверка CI. Текст в чате evidence не является.'],
  ['Нет событий — процесс остановился?', 'Не обязательно. Отсутствие события не доказывает остановку: смотрите давность последнего сигнала и состояние сессии.'],
  ['Почему у Codex нет шагов?', 'Codex не отдаёт структуру шагов, поэтому показывается хвост журнала без разбивки.'],
];
const HELP_DOCS = [
  ['harness --help', 'Команды и флаги CLI.'],
  ['.harness/orchestration/playbook.md', 'Контракт оркестрации и роли.'],
  ['.harness/orchestration/README.md', 'Настройки orchestration.json.'],
];

const helpModel = () => { const h = S.help; h.q ||= ''; return h; };
const helpKbd = (keys) => keys.map((k) => `<kbd>${k}</kbd>`).join(' ');
const helpNavGroups = () => NAV.map(([group, items]) => [group, items.map(([id, name, icon]) => [id, name, icon])]);
const helpSectionRow = ([id, name, icon]) => `<a class="help-sec" href="#/${id}"><span class="help-sec-i">${ic(icon, 'sm')}</span><span><b>${name}</b><small>${HELP_SECTION_TEXT[id]}</small></span>${HELP_KEYS_NAV[id] ? `<span class="help-sec-k">${helpKbd(['g', HELP_KEYS_NAV[id]])}</span>` : id === 'help' ? `<span class="help-sec-k">${helpKbd(['?'])}</span>` : ''}</a>`;

function helpIndex() {
  const rows = [];
  helpNavGroups().forEach(([, items]) => items.forEach(([id, name]) => rows.push(['sections', name, HELP_SECTION_TEXT[id]])));
  HELP_STEPS.forEach(([n, t]) => rows.push(['start', n, t]));
  HELP_WINDOW.forEach(([n, t]) => rows.push(['start', n, t]));
  HELP_KEYS.forEach(([, items]) => items.forEach(([t, k]) => rows.push(['keys', t, k.join(' + ')])));
  Object.entries(HELP_KEYS_NAV).forEach(([id, k]) => rows.push(['keys', 'Перейти: ' + TITLES[id], 'g ' + k]));
  HELP_STATUS.forEach(([, n, , t]) => rows.push(['status', n, t]));
  HELP_CHECKS.forEach(([, n, , t]) => rows.push(['status', 'Проверка: ' + n, t]));
  HELP_SAFETY.forEach(([g, , rules]) => rules.forEach((r) => rows.push(['safety', g, r.replace(/<[^>]+>/g, '')])));
  HELP_FAQ.forEach(([q, a]) => rows.push(['faq', q, a]));
  HELP_DOCS.forEach(([p, t]) => rows.push(['docs', p, t]));
  HARNESS_CMDS.forEach(([c, d]) => rows.push(['docs', c, d]));
  return rows;
}
const HELP_TAB_NAMES = { start: 'Начало', sections: 'Разделы', keys: 'Клавиши', status: 'Статусы', safety: 'Безопасность', faq: 'Вопросы', docs: 'Документация' };

function helpStart() {
  const wm = HELP_WINDOW;
  const diagram = `<div class="help-win" role="img" aria-label="Схема окна консоли: верхняя панель, меню слева, рабочая область, баннер связи, нижняя строка"><div class="hw-top"><i>1</i><span>Harness next · проект · ветка</span><em>online</em></div><div class="hw-mid"><div class="hw-rail"><i>2</i><s></s><s></s><s></s><s></s></div><div class="hw-main"><div class="hw-ban"><i>4</i><span>Связь потеряна</span></div><div class="hw-body"><i>3</i><s></s><s></s><s></s><s></s></div></div></div><div class="hw-foot"><i>5</i><span>Ctrl K Поиск</span></div></div>`;
  const left = panel('Как читать консоль', `<ol class="help-steps">${HELP_STEPS.map(([n, t]) => `<li><b>${n}</b><span>${t}</span></li>`).join('')}</ol><p class="help-note">Консоль — оболочка над CLI <code>harness</code> и coordinator оркестрации. Рядом с каждым действием показан CLI-эквивалент: консоль запускает тот же процесс и не повторяет его логику.</p>`);
  const right = panel('Окно консоли', `<div class="help-window">${diagram}<ol class="help-legend">${wm.map(([n, t], i) => `<li><i>${i + 1}</i><span><b>${n}</b><small>${t}</small></span></li>`).join('')}</ol></div>`);
  return `<div class="help-cols help-cols-start">${left}${right}</div>`;
}
function helpSections() {
  return `<div class="help-cols help-cols-3">${helpNavGroups().map(([g, items]) => panel(g, `<div class="help-secs">${items.map(helpSectionRow).join('')}</div>`, { count: items.length, flush: true })).join('')}</div>`;
}
function helpKeys() {
  const nav = Object.entries(HELP_KEYS_NAV).map(([id, k]) => `<div class="help-key"><span>${TITLES[id]}</span><span>${helpKbd(['g', k])}</span></div>`).join('');
  const gen = HELP_KEYS.flatMap(([, items]) => items).map(([t, k]) => `<div class="help-key"><span>${t}</span><span>${helpKbd(k)}</span></div>`).join('');
  return `<div class="help-cols">${panel('Переход между разделами', `<div class="help-keys">${nav}</div><p class="help-note">Нажмите <kbd>g</kbd>, затем букву раздела (до 1,2 с). В поле ввода сочетания не срабатывают.</p>`)}${panel('Общие', `<div class="help-keys">${gen}</div><p class="help-note">Нижняя строка окна показывает клавиши текущего экрана. Выбор пункта меню, вкладки или сессии не запускает команду.</p>`)}</div>`;
}
function helpStatus() {
  const row = ([k, label, icon, text]) => `<div class="help-st">${pill(k, label, icon)}<span>${text}</span></div>`;
  return `<div class="help-cols">${panel('Сессии и действия', HELP_STATUS.map(row).join(''), { count: HELP_STATUS.length })}${panel('Проверки', HELP_CHECKS.map(row).join('') + '<p class="help-note">Статус всегда показан значком и подписью, цвет только дополняет их. Отсутствие данных не заменяется нулём.</p>', { count: HELP_CHECKS.length })}</div>`;
}
function helpSafety() {
  const card = ([g, icon, rules]) => panel(`<span class="help-ph">${ic(icon, 'sm')}${g}</span>`, `<ul class="help-rules">${rules.map((r) => `<li>${r}</li>`).join('')}</ul>`, { count: rules.length });
  const col = (ids) => `<div class="help-stack">${ids.map((i) => card(HELP_SAFETY[i])).join('')}</div>`;
  return `<div class="help-cols help-cols-3">${col([0, 3])}${col([1, 4])}${col([2])}</div>`;
}
function helpFaq() {
  const item = ([q, a]) => `<article class="help-q"><h3>${q}</h3><p>${a}</p></article>`;
  const half = Math.ceil(HELP_FAQ.length / 2);
  return `<div class="help-cols">${panel('Частые вопросы', `<div class="help-qs">${HELP_FAQ.slice(0, half).map(item).join('')}</div>`, { count: half, flush: true })}${panel('Ещё вопросы', `<div class="help-qs">${HELP_FAQ.slice(half).map(item).join('')}</div>`, { count: HELP_FAQ.length - half, flush: true })}</div>`;
}
function helpDocs() {
  const copy = (v) => `<button type="button" class="btn sm ghost" data-act="help-copy" data-v="${esc(v)}" aria-label="Скопировать ${esc(v)}" title="Скопировать">${ic('copy', 'sm')}</button>`;
  const docs = HELP_DOCS.map(([p, t]) => `<div class="help-doc"><span><code>${p}</code><small>${t}</small></span>${copy(p)}</div>`).join('');
  const cmds = HARNESS_CMDS.map(([c, d, m]) => `<div class="help-doc"><span><code>${c}</code><small>${d} · <em>${m}</em></small></span>${copy(c)}</div>`).join('');
  return `<div class="help-cols">${panel('Где искать подробности', docs, { count: HELP_DOCS.length, flush: true })}${panel('Безопасные команды', cmds + '<p class="help-note help-pad">Команды только читают или показывают план. Консоль их не запускает: скопируйте и выполните в терминале.</p>', { count: HARNESS_CMDS.length, flush: true })}</div>`;
}
function helpResults(q) {
  const needle = q.trim().toLowerCase(), found = helpIndex().filter(([, t, d]) => `${t} ${d}`.toLowerCase().includes(needle));
  if (!found.length) return `<section class="panel">${empty('Ничего не найдено', 'Проверьте написание или поищите по другому слову: раздел, клавиша, статус, команда.', btn('Сбросить поиск', 'help-reset', { cls: 'sm' }))}</section>`;
  const hl = (s) => esc(s).replace(new RegExp(esc(needle).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), (m) => `<mark>${m}</mark>`);
  return panel('Найдено', `<ul class="help-found">${found.map(([tab, t, d]) => `<li><button type="button" data-act="help-open:${tab}"><span class="tag">${HELP_TAB_NAMES[tab]}</span><span><b>${hl(t)}</b><small>${hl(d)}</small></span>${ic('chev', 'sm')}</button></li>`).join('')}</ul>`, { count: found.length, flush: true });
}

screens.help = () => {
  const h = helpModel(), tab = HELP_TAB_NAMES[h.tab] ? h.tab : 'start', q = h.q.trim();
  const sections = NAV.flatMap(([, i]) => i).length, keys = Object.keys(HELP_KEYS_NAV).length + HELP_KEYS.flatMap(([, i]) => i).length, rules = HELP_SAFETY.reduce((n, [, , r]) => n + r.length, 0);
  const summary = `<section class="panel cfg-summary help-summary" aria-label="Сводка справки"><div class="cfg-metrics">${[['Разделов', sections], ['Сочетаний клавиш', keys], ['Правил безопасности', rules], ['Вопросов', HELP_FAQ.length]].map(([k, v]) => `<div><span>${k}</span><b>${v}</b></div>`).join('')}</div><div class="cfg-summary-foot"><span>${ic('check', 'sm')} Справка консоли Harness next 1.5.1</span><span>${S.conn === 'reconnect' ? 'Кэш 22:01 · может быть устаревшим' : 'Текст передаёт сервер консоли'}</span><span>Справка ничего не запускает</span></div></section>`;
  const tools = `<div class="panel cfg-tools">${search('help.q', h.q, 'Поиск по справке: раздел, клавиша, статус, команда')}${btn('Сбросить', 'help-reset', { cls: 'sm ghost', dis: !h.q })}</div>`;
  const nav = `<div class="cfg-tabs">${pipeTabs('help.tab', [['start', 'Начало', ic('help', 'sm')], ['sections', 'Разделы', sections], ['keys', 'Клавиши', keys], ['status', 'Статусы', HELP_STATUS.length + HELP_CHECKS.length], ['safety', 'Безопасность', ic('shield', 'sm')], ['faq', 'Вопросы', HELP_FAQ.length], ['docs', 'Документация', ic('file', 'sm')]], tab)}</div>`;
  const body = q ? helpResults(q) : { start: helpStart, sections: helpSections, keys: helpKeys, status: helpStatus, safety: helpSafety, faq: helpFaq, docs: helpDocs }[tab]();
  return `<div class="page help-screen fit">${head('Справка', 'Как устроена консоль: разделы, клавиши, статусы и правила безопасности.')}${summary}${tools}${q ? '' : nav}${body}${q ? '' : helpNext(tab)}</div>`;
};
Object.assign(actions, {
  'help-open': (tab) => { if (!HELP_TAB_NAMES[tab]) return; Object.assign(S.help, { tab, q: '' }); render(); },
  'help-reset': () => { S.help.q = ''; render(); },
  'help-copy': async (_, el) => { const v = el?.dataset?.v; if (!v) return; try { await navigator.clipboard.writeText(v); toast('Скопировано'); } catch { toast('Не удалось скопировать. Выделите текст вручную.'); } },
});
/* Предустановка для снимков и ревью: ?helptab=sections|keys|status|safety|faq|docs, ?helpq=текст поиска. */
(() => {
  const q = new URLSearchParams(location.search), tab = q.get('helptab'), text = q.get('helpq');
  if (tab && HELP_TAB_NAMES[tab]) S.help.tab = tab;
  if (text) S.help.q = text;
})();
