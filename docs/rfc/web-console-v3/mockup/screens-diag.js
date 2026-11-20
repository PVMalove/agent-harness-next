/* Диагностика: вкладки «Функции» (вкл/выкл и готовность каждой функции Harness) и «Проверки» (57 проверок). */
'use strict';

const AREAS = [['Файлы Harness', 'file', { err: 3, ok: 6 }], ['Окружение', 'branch', { warn: 1, ok: 5 }], ['Конфигурация', 'sliders', { ok: 6 }], ['Runtime', 'cpu', { ok: 7 }], ['Сеть', 'plug', { skip: 14 }], ['Контейнеры', 'box', { skip: 15 }]];
const CHK_X = {
  lock: { aff: ['.harness/harness.lock'], hist: ['ok', 'ok', 'err', 'err', 'err'], dur: '42 мс', rel: ['agents', 'links'] },
  agents: { aff: ['AGENTS.md', 'CLAUDE.md'], hist: ['ok', 'ok', 'ok', 'err', 'err'], dur: '18 мс', rel: ['lock', 'links'] },
  links: { aff: ['.agents/skills', '.claude/skills'], hist: ['ok', 'ok', 'err', 'err', 'err'], dur: '27 мс', rel: ['lock'] },
  gitattr: { aff: ['.gitattributes'], hist: ['warn', 'warn', 'warn', 'warn', 'warn'], dur: '9 мс', rel: [] },
  git: { aff: ['.git'], hist: ['ok', 'ok', 'ok', 'ok', 'ok'], dur: '31 мс', rel: [] },
  pjson: { aff: ['.harness/project.json'], hist: ['ok', 'ok', 'ok', 'ok', 'ok'], dur: '12 мс', rel: [] },
  store: { aff: ['.harness/runtime-store'], hist: ['ok', 'ok', 'ok', 'ok', 'ok'], dur: '64 мс', rel: [] },
  registry: { aff: ['реестр навыков'], hist: ['skip', 'skip', 'skip', 'skip', 'skip'], dur: '—', rel: [] },
  docker: { aff: ['docker.sock'], hist: ['skip', 'skip', 'skip', 'skip', 'skip'], dur: '—', rel: ['containers'] },
};
const SLAB = { err: 'Ошибка', warn: 'Внимание', ok: 'Пройдено', skip: 'Пропущено' };
const FLAB = { err: 'Не работает', warn: 'Частично', ok: 'Работает', skip: 'Выключено' };

{ const q = new URLSearchParams(location.search); if (q.get('tab')) S.diag.tab = q.get('tab'); if (q.get('f')) S.feat.sel = q.get('f'); }
const featOn = (f) => (S.feat.on[f.id] !== undefined ? S.feat.on[f.id] : f.on);
const featState = (f) => { if (!featOn(f)) return 'skip'; const r = f.reqs.map((x) => x[1]); return r.includes('err') ? 'err' : r.includes('warn') ? 'warn' : 'ok'; };
const fCounts = (arr = FEATURES) => { const t = { err: 0, warn: 0, ok: 0, skip: 0 }; arr.forEach((f) => { t[featState(f)] += 1; }); return t; };
const checkCounts = () => { const t = { err: 0, warn: 0, ok: 0, skip: 0 }; AREAS.forEach((a) => Object.entries(a[2]).forEach(([k, v]) => { t[k] += v; })); return t; };
const dIcon = (s, cls = '', label = '') => `<span class="badge-ic ${s === 'skip' ? '' : s}" style="${s === 'skip' ? 'background:var(--hover);color:var(--muted);' : ''}${cls}"${label ? ` role="img" aria-label="${esc(label)}" title="${esc(label)}"` : ''}>${ic(sevIcon[s])}</span>`;
const sw = (f) => `<button type="button" class="sw" role="switch" aria-checked="${featOn(f)}" aria-label="Функция «${esc(f.name)}»" data-act="feat-toggle:${f.id}"></button>`;
const fchip = (path, cur, key, label, n, st) => `<button type="button" class="fchip ${cur === key ? 'on' : ''} ${st || ''}" data-act="set" data-k="${path}" data-v="${key}" aria-pressed="${cur === key}">${st ? ic(sevIcon[st], 'sm') : ''}<b>${n}</b> ${label}</button>`;
const countParts = (cnt, labels) => [['err', labels.err], ['warn', labels.warn], ['ok', labels.ok], ['skip', labels.skip]].filter(([k]) => cnt[k]).map(([k, t]) => `<span class="ac ${k}" title="${cnt[k]} ${t}"><i></i>${cnt[k]}</span>`).join('');
const runLine = (txt) => { const run = S.diag.run; return `<div class="runline"><div class="runtrack ${run ? 'on' : ''}"><i id="run-fill" style="transform:scaleX(${run ? run.p : 1})"></i></div><span id="run-txt" class="muted" title="${esc(txt)}">${run ? `Проверяю… ${Math.round(run.p * 100)}%` : txt}</span></div>`; };
const tileBtn = (name, icon, parts, on, k, idx) => `<button type="button" class="atile ${on ? 'on' : ''}" id="ar-${idx}" data-act="set" data-k="${k}" data-v="${on ? 'all' : name}" aria-pressed="${on}"><span class="ai">${ic(icon)}</span><span class="an">${name}</span><span class="acs">${parts}</span></button>`;
const logBlock = (lines) => `<pre class="log dlog" tabindex="0" aria-label="Вывод проверки">${lines.map((l) => esc(l)).join('\n')}</pre>`;
/* Переключатели в виде конвейера: узел (номер, число или значок) — подпись — линия к следующему шагу */
const pipeTabs = (key, opts, cur, size = 'sm') => { const at = Math.max(0, opts.findIndex((o) => o[0] === cur)); return `<div class="pl ${size}" role="tablist">${opts.map(([v, label, node], i) => `${i ? `<i class="pc ${i <= at ? 'on' : ''}" aria-hidden="true"></i>` : ''}<button type="button" role="tab" class="pl-i" aria-selected="${v === cur}" data-act="set" data-k="${key}" data-v="${v}" title="${esc(label)}"><span class="pl-n">${node != null ? node : i + 1}</span><span class="pl-l">${label}</span></button>`).join('')}</div>`; };
const subTabs = pipeTabs;
const statePipe = (path, cur, items) => `<div class="pl st" role="group" aria-label="Фильтр по состоянию">${items.map(([key, label, n, st], i) => `${i ? '<i class="pc" aria-hidden="true"></i>' : ''}<button type="button" class="pl-i" aria-pressed="${cur === key}" data-act="set" data-k="${path}" data-v="${key}"><span class="pl-n s-${st || 'all'}">${n}</span><span class="pl-l">${label}</span></button>`).join('')}</div>`;
const sumPanel = (chips, bar, tiles, idle) => `<section class="panel dsum compact" aria-label="Сводка"><div class="dsum-row">${chips}${runLine(idle)}</div>${bar}<div class="atiles compact">${tiles}</div></section>`;
const segBar = (t, label) => `<div class="bar thin" role="img" aria-label="${label}"><i class="ok" style="flex:${t.ok}"></i><i class="warn" style="flex:${t.warn}"></i><i class="err" style="flex:${t.err}"></i><i class="skip" style="flex:${t.skip}"></i></div>`;
const changeList = (steps) => { const seen = [...new Set(steps.map(([x]) => x.id))].map((id) => FEATURES.find((x) => x.id === id)); if (!seen.length) return ''; return `<h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Что изменится после плана</h3><ul class="chg">${seen.map((x) => { const left = x.reqs.filter((r) => r[1] !== 'ok' && !r[3]).map((r) => r[1]); const after = left.includes('err') ? 'err' : left.includes('warn') ? 'warn' : 'ok'; return `<li><span class="clamp1">${esc(x.name)}</span>${pill(featState(x), FLAB[featState(x)])}${ic('chev', 'sm')}${pill(after, FLAB[after])}</li>`; }).join('')}</ul>`; };
const evList = () => `<ul class="feed">${DIAG_EVENTS.map(([t, x]) => `<li><time>${t}</time><span>${esc(x)}</span></li>`).join('')}</ul>`;

screens.diagnostics = () => {
  const d = S.diag; const run = d.run; const feat = d.tab === 'feat';
  return `<div class="page fill dg">${head('Диагностика', 'Состояние проекта и всех функций Harness.', (feat ? '' : `<span class="muted">Режим</span>${seg('diag.mode', [['offline', 'Офлайн'], ['online', 'Онлайн']], d.mode, 'Режим проверки')}`) + btn(run ? 'Идёт проверка…' : 'Проверить заново', 'diag-run', { icon: 'refresh', cls: 'primary', dis: !!run }) + btn('Экспорт JSON', 'toast:Сохранено в health-report.json'))}
  <div class="dg-top">${pipeTabs('diag.tab', [['feat', 'Функции', FEATURES.length], ['checks', 'Проверки', 57]], d.tab, 'lg')}</div>${feat ? featView() : checksView()}</div>`;
};

/* ---------- Функции ---------- */
function featView() {
  const F = S.feat; F.dtab = F.dtab || 'ready'; const tot = fCounts(); const n = FEATURES.length;
  const list = FEATURES.filter((f) => (F.filter === 'all' || featState(f) === F.filter) && (F.cat === 'all' || f.cat === F.cat) && (!F.q || (`${f.name} ${f.desc}`).toLowerCase().includes(F.q.toLowerCase())));
  const f = FEATURES.find((x) => x.id === F.sel) || list[0];
  const groups = FCATS.map(([g]) => [g, list.filter((x) => x.cat === g)]).filter(([, a]) => a.length);
  const tiles = FCATS.map(([g, icon], k) => tileBtn(g, icon, countParts(fCounts(FEATURES.filter((x) => x.cat === g)), { err: 'не работают', warn: 'частично', ok: 'работают', skip: 'выключены' }), F.cat === g, 'feat.cat', k)).join('');
  const chips = statePipe('feat.filter', F.filter, [['all', 'Все', n], ['ok', 'Работают', tot.ok, 'ok'], ['warn', 'Частично', tot.warn, 'warn'], ['err', 'Не работают', tot.err, 'err'], ['skip', 'Выключены', tot.skip, 'skip']]);
  const summary = sumPanel(chips, segBar(tot, `Работают ${tot.ok}, частично ${tot.warn}, не работают ${tot.err}, выключены ${tot.skip}`), tiles, `Последний прогон ${S.diag.last} · выключенное не считается ошибкой`);
  const manual = []; const steps = [];
  FEATURES.filter((x) => featOn(x)).forEach((x) => x.reqs.forEach((r) => { if (r[1] === 'ok') return; (r[3] ? steps : manual).push([x, r]); }));
  const working = tot.ok + steps.filter(([x]) => x.reqs.filter((r) => r[1] !== 'ok' && !r[3]).length === 0).length;
  let pt = S.diag.ptab; if (!['plan', 'manual', 'events'].includes(pt)) pt = 'plan';
  const planBody = { plan: steps.length ? `<ol class="plan">${steps.map(([x, r]) => `<li><div><b>${esc(r[0])}</b><span class="faint"> · ${esc(x.name)}</span></div><div class="codebox"><code>${esc(r[3])}</code>${btn('', `copy:${r[3]}`, { cls: 'sm icon ghost', icon: 'copy', title: 'Скопировать' })}</div></li>`).join('')}</ol><div class="ba"><div class="ba-r"><span>Сейчас</span>${segBar(tot, 'Сейчас')}<b>${tot.ok} из ${n}</b></div><div class="ba-r"><span>После плана</span>${segBar({ ok: working, warn: Math.max(0, tot.warn - (working - tot.ok)), err: tot.err, skip: tot.skip }, 'После плана')}<b>${working} из ${n}</b></div></div>${changeList(steps)}` : '<p class="muted">Команд для исправления нет.</p>',
    manual: manual.length ? `<ul class="manual">${manual.map(([x, r]) => `<li>${ic(sevIcon[r[1]], 'sm')}<span><b>${esc(r[0])}</b><br><span class="muted">${esc(x.name)} · ${esc(r[2])}</span></span></li>`).join('')}</ul>` : '<p class="muted">Ручных шагов нет.</p>', events: evList() }[pt];
  const planFoot = pt === 'plan' && steps.length ? `<div class="dfoot">${confirmBtn('Выполнить по порядку', 'Выполнить план исправления?', steps.map(([, r]) => r[3]).join(' && '), 'Выполнить', 'План запущен: вывод появится в разделе Harness', { cls: 'primary sm' })}${btn('Скопировать всё', `copy:${steps.map(([, r]) => r[3]).join(' && ')}`, { cls: 'sm' })}</div>` : '';
  return `${summary}<div class="diag">
    <div class="panel dlist"><div class="dlist-top">${search('feat.q', F.q, 'Поиск функции')}</div><div role="list" class="dl-scroll">${groups.length ? groups.map(([g, items]) => `<div class="group-title">${g} · ${items.length}</div>${items.map((x) => { const st = featState(x); return `<div role="listitem" class="row cmp frow ${f && x.id === f.id ? 'sel' : ''}"><button type="button" class="frow-main" data-act="set" data-k="feat.sel" data-v="${x.id}" aria-pressed="${!!f && x.id === f.id}">${dIcon(st, 'width:24px;height:24px;')}<span class="grow"><span class="t" style="font-weight:500;display:block">${esc(x.name)}</span></span><span class="sr">${FLAB[st]}</span></button>${sw(x)}</div>`; }).join('')}`).join('') : empty('Нет функций', 'Измените фильтр, категорию или запрос.', btn('Сбросить', 'feat-reset'))}</div><div class="dl-foot muted">${list.length} из ${n} · переключатель включает и выключает</div></div>
    <section class="panel dd" aria-label="Функция">${f ? featDetail(f) : empty('Выберите функцию', 'Слева список, здесь подробности.')}</section>
    <aside class="panel dplan" aria-label="План исправления"><div class="ph"><h2>Исправление</h2></div>${pipeTabs('diag.ptab', [['plan', 'План', steps.length], ['manual', 'Вручную', manual.length], ['events', 'События', '↻']], pt)}<div class="scr">${planBody}</div>${planFoot}</aside></div>`;
}
function featDetail(f) {
  const s = featState(f); const on = featOn(f); const used = FEATURES.filter((x) => x.deps.includes(f.id));
  const dep = (id) => { const x = FEATURES.find((z) => z.id === id); return x ? `<button type="button" class="btn sm" data-act="set" data-k="feat.sel" data-v="${id}">${ic(sevIcon[featState(x)], 'sm')}${esc(x.name)}</button>` : ''; };
  const log = [`$ harness health --feature ${f.id}`, ...f.reqs.map((r) => `${{ ok: '✓', warn: '!', err: '✗' }[r[1]]} ${r[0]} — ${r[2]}`), `итог: ${FLAB[s].toLowerCase()}`];
  const nd = f.deps.length + used.length; const dt = F_TABS.includes(S.feat.dtab) ? S.feat.dtab : 'ready';
  const body = { ready: `${on ? '' : `<div class="note" style="margin-bottom:12px">${ic('pause')}<div><b>Функция выключена.</b> ${esc(f.off)} Требования показаны для справки, ошибкой это не считается.</div></div>`}<ul class="reqs">${f.reqs.map((r) => `<li class="req"><span class="badge-ic ${r[1]}" style="width:26px;height:26px">${ic(sevIcon[r[1]], 'sm')}</span><div class="grow"><div class="t" style="font-weight:500">${esc(r[0])}</div><div class="d">${esc(r[2])}</div></div>${r[3] ? cmdBtn('Исправить', r[3], `Исправить: ${r[0]}?`, r[2], { cls: 'sm' }) : ''}</li>`).join('')}</ul>`,
    cfg: `<div class="cfgs">${f.cfg.map(([k, v, src]) => `<div class="cfgrow"><code>${esc(k)}</code><span>${esc(v)}</span><span class="faint">${esc(src)}</span></div>`).join('')}</div>`,
    deps: nd ? `<div class="cols2" style="gap:24px"><div><h3 class="muted" style="font-size:var(--fs-2);margin-bottom:8px">Зависит от</h3><div class="chips">${f.deps.length ? f.deps.map(dep).join('') : '<span class="muted">ничего</span>'}</div></div><div><h3 class="muted" style="font-size:var(--fs-2);margin-bottom:8px">Нужна для</h3><div class="chips">${used.length ? used.map((x) => dep(x.id)).join('') : '<span class="muted">ничего</span>'}</div></div></div>` : '<p class="muted">Связей с другими функциями нет.</p>',
    log: logBlock(log) }[dt];
  return `<div class="dh">${dIcon(s, 'width:32px;height:32px;', FLAB[s])}<div style="flex:1;min-width:0"><h2 class="clamp1">${esc(f.name)}</h2><p class="muted clamp1 dsub" title="${esc(f.desc)}"><span>${f.cat} · ${esc(f.desc)}</span></p></div><span class="swl">${sw(f)}<span class="muted" style="font-size:var(--fs-2)">${on ? 'вкл' : 'выкл'}</span></span></div>
  ${pipeTabs('feat.dtab', [['ready', 'Готовность', f.reqs.length], ['cfg', 'Конфигурация', f.cfg.length], ['deps', 'Связи', nd], ['log', 'Вывод', '›']], dt)}<div class="scr">${body}</div>
  <div class="dfoot">${btn('Проверить функцию', 'feat-check:' + f.id, { cls: 'primary sm', icon: 'refresh' })}${btn('Настройки', 'go:configuration', { cls: 'sm' })}</div>`;
}
const F_TABS = ['ready', 'cfg', 'deps', 'log'];
Object.assign(actions, {
  'feat-reset': () => { Object.assign(S.feat, { filter: 'all', cat: 'all', q: '' }); render(); },
  'feat-check': (id) => toast(`Проверка «${FEATURES.find((x) => x.id === id).name}» выполнена в ${new Date().toTimeString().slice(0, 5)}`),
  'feat-toggle': (id) => {
    const f = FEATURES.find((x) => x.id === id); const on = featOn(f);
    const blockers = f.reqs.filter((r) => r[1] === 'err'); const dependants = FEATURES.filter((x) => x.deps.includes(id) && featOn(x));
    const body = `<h2 id="dlg-title">${on ? 'Выключить' : 'Включить'} «${esc(f.name)}»?</h2><p class="muted">${on ? esc(f.off) : 'Функция начнёт использоваться при следующем запуске.'}</p>${!on && blockers.length ? `<div class="note err">${ic('alert')}<div>Заработает не сразу. Нужно исправить: ${blockers.map((r) => esc(r[0])).join('; ')}.</div></div>` : ''}${on && dependants.length ? `<div class="note warn">${ic('alert')}<div>От неё зависят включённые функции: ${dependants.map((x) => esc(x.name)).join(', ')}.</div></div>` : ''}<p class="muted" style="font-size:var(--fs-2)">Изменение записывается в конфигурацию проекта после подтверждения.</p>`;
    dialog(body, () => { S.feat.on[id] = !on; render(); toast(`«${f.name}» ${on ? 'выключена' : 'включена'}`); }, on ? 'Выключить' : 'Включить');
  },
});

/* ---------- Проверки ---------- */
function checksView() {
  const d = S.diag; const tot = checkCounts(); const dtab = ['info', 'hist'].includes(d.dtab) ? d.dtab : 'info';
  const list = CHECKS.filter((c) => (d.filter === 'all' || c.s === d.filter) && (d.area === 'all' || c.area === d.area) && (!d.q || (`${c.title} ${c.area} ${c.what}`).toLowerCase().includes(d.q.toLowerCase())));
  const c = CHECKS.find((x) => x.id === d.sel) || list[0];
  const todo = CHECKS.filter((x) => x.fix && (x.s === 'err' || x.s === 'warn'));
  const groups = AREAS.map(([g]) => [g, list.filter((x) => x.area === g)]).filter(([, a]) => a.length);
  const tiles = AREAS.map(([name, icon, cnt], k) => tileBtn(name, icon, countParts(cnt, { err: 'ошибки', warn: 'внимание', ok: 'пройдено', skip: 'пропущено' }), d.area === name, 'diag.area', k)).join('');
  const chips = statePipe('diag.filter', d.filter, [['all', 'Все', 57], ['err', 'Ошибки', tot.err, 'err'], ['warn', 'Внимание', tot.warn, 'warn'], ['ok', 'Пройдено', tot.ok, 'ok'], ['skip', 'Пропущено', tot.skip, 'skip']]);
  const summary = sumPanel(chips, segBar(tot, `${tot.ok} пройдено, ${tot.warn} внимание, ${tot.err} ошибки, ${tot.skip} пропущено`), tiles, `Последний прогон ${d.last} · ${d.mode === 'offline' ? 'офлайн: пропуск не считается успехом' : 'онлайн в макете не выполняется'}`);
  const detail = c ? (() => {
    const x = CHK_X[c.id] || { aff: [], hist: [], dur: '—', rel: [] };
    const log = [`$ harness health --check ${c.id}${d.mode === 'online' ? ' --online' : ''}`, `${{ ok: '✓', warn: '!', err: '✗', skip: '–' }[c.s]} ${c.what}`, c.fix ? `подсказка: ${c.fix}` : 'подсказок нет', `exit ${c.s === 'err' ? 1 : 0}`];
    const info = `<div class="cols2" style="gap:24px"><div><h3 class="muted" style="font-size:var(--fs-2);margin-bottom:4px">Что проверено</h3><p>${esc(c.what)}</p></div><div><h3 class="muted" style="font-size:var(--fs-2);margin-bottom:4px">Почему это важно</h3><p>${esc(c.why)}</p></div></div>
      ${x.aff.length ? `<h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Затронуто</h3><div class="chips">${x.aff.map((fl) => `<span class="tag mono">${esc(fl)}</span>`).join('')}</div>` : ''}
      ${c.s === 'skip' ? `<div class="note warn" style="margin-top:12px">${ic('alert')}<div><b>Пропуск — не успех.</b> Проверка не выполнялась, результат неизвестен.</div></div>` : ''}
      ${c.fix ? `<h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Что сделать</h3><div class="codebox"><code>${esc(c.fix)}</code>${btn('', `copy:${c.fix}`, { cls: 'sm icon ghost', icon: 'copy', title: 'Скопировать' })}</div>` : `<div class="note" style="margin-top:12px">${ic('check')}<div>Действий не требуется: проверка пройдена.</div></div>`}`;
    const hist = `<h3 class="muted" style="font-size:var(--fs-2);margin-bottom:8px">Последние прогоны</h3><div class="hist" role="img" aria-label="История: ${x.hist.map((h) => SLAB[h]).join(', ')}">${x.hist.map((h) => `<span class="hd ${h}" title="${SLAB[h]}">${ic(sevIcon[h], 'sm')}</span>`).join('')}<span class="muted" style="font-size:var(--fs-2);margin-left:8px">от старых к новым</span></div>
      <h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Вывод проверки</h3>${logBlock(log)}
      ${x.rel.length ? `<h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Связанные</h3><div class="chips">${x.rel.map((r) => { const k = CHECKS.find((z) => z.id === r); if (k) return `<button type="button" class="btn sm" data-act="set" data-k="diag.sel" data-v="${r}">${ic(sevIcon[k.s], 'sm')}${esc(k.title)}</button>`; const ft = FEATURES.find((z) => z.id === r); return ft ? `<button type="button" class="btn sm" data-act="diag-to-feat:${r}">${ic(sevIcon[featState(ft)], 'sm')}Функция: ${esc(ft.name)}</button>` : ''; }).join('')}</div>` : ''}`;
    return `<div class="dh">${dIcon(c.s, 'width:32px;height:32px;', SLAB[c.s])}<div style="flex:1;min-width:0"><h2 class="clamp1">${esc(c.title)}</h2><p class="muted clamp1 dsub"><span>${c.area} · проверено ${c.time} · ${x.dur}</span></p></div></div>
    ${pipeTabs('diag.dtab', [['info', 'Обзор', 'i'], ['hist', 'Прогоны и вывод', '›']], dtab)}<div class="scr">${dtab === 'info' ? info : hist}</div>
    <div class="dfoot">${c.fix ? cmdBtn(c.s === 'skip' ? 'Запустить онлайн' : 'Исправить', c.fix, c.s === 'skip' ? 'Запустить проверку онлайн?' : 'Исправить проблему?', c.what, { cls: 'primary sm' }) : ''}${btn('Открыть Harness', 'go:harness', { cls: 'sm' })}</div>`;
  })() : empty('Выберите проверку', 'Слева список, здесь подробности.');
  let pt = S.diag.ptab; if (!['plan', 'events'].includes(pt)) pt = 'plan';
  const planBody = pt === 'plan' ? (todo.length ? `<ol class="plan">${todo.map((x) => `<li><div><b>${esc(x.title)}</b><span class="faint"> · ${x.area}</span></div><div class="codebox"><code>${esc(x.fix)}</code>${btn('', `copy:${x.fix}`, { cls: 'sm icon ghost', icon: 'copy', title: 'Скопировать' })}</div></li>`).join('')}</ol><div class="ba"><div class="ba-r"><span>Сейчас</span>${segBar(tot, 'Сейчас')}<b>${tot.ok} пройдено</b></div><div class="ba-r"><span>После плана</span>${segBar({ ok: tot.ok + todo.length, warn: 0, err: 0, skip: tot.skip }, 'После плана')}<b>${tot.ok + todo.length} пройдено</b></div></div>` : empty('Исправлять нечего', 'Ошибок и предупреждений нет.')) : evList();
  const planFoot = pt === 'plan' && todo.length ? `<div class="dfoot">${confirmBtn('Выполнить по порядку', 'Выполнить план исправления?', todo.map((x) => x.fix).join(' && '), 'Выполнить', 'План запущен: вывод появится в разделе Harness', { cls: 'primary sm' })}${btn('Скопировать всё', `copy:${todo.map((x) => x.fix).join(' && ')}`, { cls: 'sm' })}</div>` : '';
  return `${summary}<div class="diag">
    <div class="panel dlist"><div class="dlist-top">${search('diag.q', d.q, 'Поиск проверки')}</div><div role="list" class="dl-scroll">${groups.length ? groups.map(([g, a]) => `<div class="group-title">${g} · ${a.length}</div>${a.map((x) => `<button type="button" role="listitem" class="row click cmp ${c && x.id === c.id ? 'sel' : ''}" data-act="set" data-k="diag.sel" data-v="${x.id}">${dIcon(x.s, 'width:24px;height:24px;')}<span class="grow t" style="font-weight:500">${esc(x.title)}</span><span class="faint" style="font-size:var(--fs-2)">${SLAB[x.s]}</span></button>`).join('')}`).join('') : empty('Нет проверок', 'Измените фильтр, область или запрос.', btn('Сбросить', 'diag-reset'))}${list.length && d.filter === 'all' && d.area === 'all' && !d.q ? `<button type="button" class="row click cmp" data-act="toast:В макете показаны ключевые проверки; остальные 48 подгружаются из снимка health"><span class="badge-ic" style="width:24px;height:24px;background:var(--hover);color:var(--muted)">${ic('plus', 'sm')}</span><span class="grow t" style="font-weight:500">Показать остальные ${57 - list.length}</span></button>` : ''}</div><div class="dl-foot muted">${list.length} из 57</div></div>
    <section class="panel dd" aria-label="Детали проверки">${detail}</section>
    <aside class="panel dplan" aria-label="План исправления"><div class="ph"><h2>Исправление</h2></div>${pipeTabs('diag.ptab', [['plan', 'План', todo.length], ['events', 'События', '↻']], pt)}<div class="scr">${planBody}</div>${planFoot}</aside></div>`;
}
Object.assign(actions, {
  'diag-reset': () => { Object.assign(S.diag, { filter: 'all', area: 'all', q: '' }); render(); },
  'diag-to-feat': (id) => { S.diag.tab = 'feat'; S.feat.sel = id; render(); },
});

/* ---------- Прогон: прогресс — transform; значок вращается только у проверяемой плитки ---------- */
let diagTimer = null;
actions['diag-run'] = () => {
  if (S.diag.run) return;
  const feat = S.diag.tab === 'feat'; const names = feat ? FEATURES.map((x) => x.name) : CHECKS.map((x) => x.title);
  S.diag.run = { p: 0 }; render();
  diagTimer = setInterval(() => {
    const r = S.diag.run; if (!r) return;
    r.p = Math.min(1, r.p + 0.035 + Math.random() * 0.03);
    const fill = document.getElementById('run-fill'); const txt = document.getElementById('run-txt'); const tiles = $$('.atile');
    if (fill) fill.style.transform = `scaleX(${r.p})`;
    const idx = Math.min(tiles.length - 1, Math.floor(r.p * tiles.length));
    tiles.forEach((t, k) => { t.classList.toggle('busy', k === idx && r.p < 1); t.classList.toggle('done', k < idx || r.p >= 1); });
    if (txt) txt.textContent = r.p < 1 ? `Проверяю: ${tiles[idx] ? tiles[idx].querySelector('.an').textContent : ''} · ${names[Math.min(names.length - 1, Math.floor(r.p * names.length))]} · ${Math.round(r.p * 100)}%` : 'Готово';
    if (r.p >= 1) { clearInterval(diagTimer); S.diag.run = null; S.diag.last = `${new Date().toTimeString().slice(0, 5)} · ${(3.2 + Math.random()).toFixed(1).replace('.', ',')} с`; setTimeout(() => { render(); toast('Проверки перечитаны'); }, 250); }
  }, 120);
};
