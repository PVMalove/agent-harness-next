/* Harness Console · макет v3.1: оболочка и общие компоненты. Экраны — в screens*.js. */
'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const ic = (n, c = '') => `<svg class="ic ${c}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
const sevIcon = { err: 'x', warn: 'alert', ok: 'check', info: 'dot', skip: 'pause' };
const pill = (k, text, icon) => `<span class="st ${k === 'skip' ? '' : k}">${ic(icon || sevIcon[k] || 'dot')}${esc(text)}</span>`;
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* без хранилища */ } } };
const plural = (n, a, b, c) => (n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? b : c);

const S = {
  conn: 'online', empty: false,
  home: { mode: 'offline', q: '' },
  diag: { tab: 'feat', mode: 'offline', filter: 'all', area: 'all', q: '', sel: 'lock', run: null, last: '22:01 · 1,8 с' },
  feat: { sel: 'containers', filter: 'all', cat: 'all', q: '', on: {} },
  upd: { mode: 'normal', sel: 'skills/implement/SKILL.md', seeds: {}, filter: 'all', rtab: 'mode', ftab: 'diff', res: {}, run: null, done: false, checked: '22:03' },
  proj: { sel: 'harness', comp: 'workflow', mode: 'offline', path: '', step: 2, rtab: 'comp', dtab: 'ready', run: null, installed: {} },
  board: { spec: '862', q: '', pri: 'all', free: false, sel: null, tab: 'context', demo: 'ok' },
  act: { sel: '#716', status: 'all', role: 'all', q: '', tab: 'overview', side: 'context' },
  orch: { tab: 'map', role: 'all', status: 'all', stage: 'all', q: '', sel: '#704', side: 'action', execution: 'b-closed', scope: 'active', result: 'all', environment: 'offline', reviewer: '', proposal: null, decisions: {}, containerView: 'logs', logStream: 'all', logQuery: '' },
  rep: { sel: 'r-716-qa', type: 'all', status: 'all', q: '', tab: 'list' },
  pub: { tab: 'overview', cand: '#716' },
  har: { tab: 'overview' },
  repo: { tab: 'overview', q: '', sel: 'Supervisor::spawn_worker', mod: 'all' },
  cfg: { tab: 'overview', group: 0, param: 0, file: 'project.json', enabled: {} },
  help: { tab: 'start' },
};

/* ---------- Навигация: 13 разделов в 3 группах (вариант A) ---------- */
const NAV = [
  ['Обзор', [['home', 'Главная', 'home'], ['diagnostics', 'Диагностика', 'health'], ['update-harness', 'Обновление', 'refresh'], ['open-project', 'Проект', 'project']]],
  ['Работа', [['board', 'Доска задач', 'board'], ['agent-activity', 'Ход работы', 'runs'], ['orchestration', 'Оркестрация', 'flow'], ['reports', 'Отчёты', 'file'], ['publish', 'Публикация', 'publish']]],
  ['Контекст', [['harness', 'Harness', 'box'], ['repo-map', 'Repo Map', 'map'], ['configuration', 'Настройки', 'sliders'], ['help', 'Справка', 'help']]],
];
const TITLES = Object.fromEntries(NAV.flatMap(([, i]) => i.map(([id, t]) => [id, t])));
const screens = {};
const route = () => (location.hash.replace(/^#\/?/, '').split('/')[0] || 'home');
const badges = () => ({
  home: [ATTENTION.length, 'err'],
  diagnostics: [CHECKS.filter((c) => c.s === 'err').length, 'err'],
  'agent-activity': [RUNS.filter((r) => r.state !== 'done').length, 'calm'],
  reports: [REPORTS.filter((r) => r.s !== 'ok').length, 'calm'],
  publish: [S.empty ? 0 : Object.values(PCAND).filter((c) => c.verdict !== 'ready').length, 'err'],
});
function renderNav() {
  const b = badges(); const cur = route();
  $('#nav').innerHTML = NAV.map(([g, items]) => `<div class="nav-group"><div class="nav-label">${g}</div>${items.map(([id, label, icon]) => {
    const bd = b[id] && b[id][0] ? b[id] : null;
    return `<a href="#/${id}" ${cur === id ? 'aria-current="page"' : ''} ${bd && bd[1] === 'err' ? 'data-badge' : ''} title="${label}">${ic(icon)}<span class="grow">${label}</span>${bd ? `<span class="count ${bd[1] === 'calm' ? 'calm' : ''}"><span class="sr"> — </span>${bd[0]}</span>` : ''}</a>`;
  }).join('')}</div>`).join('');
}

/* ---------- Общие компоненты ---------- */
const head = (title, sub, actions = '') => `<div class="page-head"><div><h1>${title}</h1>${sub ? `<p class="sub">${/\.\s/.test(sub) ? sub : sub.replace(/\.$/, '')}</p>` : ''}</div><div class="head-actions">${actions}</div></div>`;
const btn = (label, act, o = {}) => `<button type="button" class="btn ${o.cls || ''}" data-act="${esc(act)}" ${o.dis ? 'disabled' : ''} ${o.title ? `title="${esc(o.title)}"` : ''} ${o.data || ''}>${o.icon ? ic(o.icon, 'sm') : ''}${label}</button>`;
const cmdBtn = (label, cmd, title, effect, o = {}) => btn(label, 'cmd', { ...o, data: `data-c="${esc(cmd)}" data-t="${esc(title)}" data-m="${esc(effect)}" data-done="${esc(o.done || 'Команда запущена')}"` });
const confirmBtn = (label, title, msg, ok, done, o = {}) => btn(label, 'confirm', { ...o, data: `data-t="${esc(title)}" data-m="${esc(msg)}" data-ok="${esc(ok)}" data-done="${esc(done)}"` });
const seg = (key, opts, cur, label) => `<div class="seg" role="group" aria-label="${label}">${opts.map(([v, t]) => `<button type="button" data-act="set" data-k="${key}" data-v="${v}" aria-pressed="${cur === v}">${t}</button>`).join('')}</div>`;
const tabs = (key, opts, cur) => `<div class="tabs" role="tablist">${opts.map(([v, t]) => `<button role="tab" type="button" data-act="set" data-k="${key}" data-v="${v}" aria-selected="${cur === v}">${t}</button>`).join('')}</div>`;
const search = (key, val, ph) => `<label class="field">${ic('search', 'sm')}<span class="sr">${ph}</span><input type="search" data-bind="${key}" value="${esc(val)}" placeholder="${ph}"></label>`;
const empty = (h, p, actions = '') => `<div class="empty"><h3>${h.replace(/\.$/, '')}</h3><p>${p}</p>${actions}</div>`;
const strip = (cells) => `<div class="strip">${cells.map(([k, v, s]) => `<div><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`).join('')}</div>`;
const panel = (title, body, o = {}) => `<section class="panel ${o.cls || ''}" ${o.id ? `id="${o.id}"` : ''}><div class="ph"><h2>${title}</h2>${o.count != null ? `<span class="tag">${o.count}</span>` : ''}<div class="push">${o.actions || ''}</div></div><div class="${o.flush ? '' : 'pb'}">${body}</div></section>`;
const table = (cols, rows, clickFn) => `<div class="tw"><table class="table"><thead><tr>${cols.map((c) => `<th scope="col">${c}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr ${clickFn ? `class="click" ${clickFn(r)}` : ''}>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const bars = (rows, unit = '') => rows.map(([l, v, max, tone]) => `<div class="hb"><span>${l}</span><span class="tr"><i class="${tone || ''}" style="width:${Math.round((v / max) * 100)}%"></i></span><b>${v}${unit}</b></div>`).join('');
const STAGES = ['План', 'Architect', 'Developer', 'Review', 'QA', 'PR'];
const lane = (stage, state, mini) => `<ol class="lane ${mini ? 'mini' : ''}" aria-label="Этапы запуска">${STAGES.map((s, i) => {
  const st = stage > i ? 'done' : stage === i ? ({ blocked: 'blocked', wait: 'wait', attention: 'wait', done: 'done' })[state] || 'current' : 'todo';
  const glyph = st === 'done' ? ic('check') : st === 'blocked' ? ic('x') : st === 'wait' ? ic('pause') : '';
  return `<li data-s="${st}"><span class="node">${glyph}</span><span>${s}<span class="sr"> — ${{ done: 'готово', current: 'сейчас', todo: 'впереди', blocked: 'заблокировано', wait: 'ждёт' }[st]}</span></span></li>`;
}).join('')}</ol>`;
const stateOf = (r) => { const [k, t, i] = STATE[r.state]; return pill(k, t, i); };
const rows = (items) => `<ul class="rows">${items.join('')}</ul>`;
const row = (icon, t, d, act = '') => `<li class="row"><span class="badge-ic ${icon[0]}">${ic(icon[1])}</span><div class="grow"><div class="t">${t}</div>${d ? `<div class="d">${d}</div>` : ''}</div>${act ? `<div class="acts">${act}</div>` : ''}</li>`;

/* ---------- Рендер и состояния соединения ---------- */
function render() {
  const r = route(); const view = screens[r] ? r : 'home';
  const main = $('#content'); const top = main.scrollTop; const ae = document.activeElement;
  const focus = ae && ae.dataset && ae.dataset.bind ? { k: ae.dataset.bind, s: ae.selectionStart } :
    ae && ae.matches('input[type="checkbox"][data-act]') ? { act: ae.dataset.act, v: ae.dataset.v } : null;
  const app = $('#app'); app.dataset.conn = S.conn;
  main.innerHTML = S.conn === 'offline' ? offlineView() : screens[view]();
  $$('.clamp1, .seedlist .mono, .dlist .row .t, .vt > b, .vt > small, .runline > span', main).forEach((el) => { if (!el.hasAttribute('title')) el.title = el.textContent.trim(); });
  document.title = `${TITLES[view]} · Harness Console`;
  renderNav();
  $('#where').textContent = `2.0.0 · claude-agent-harness · ${TITLES[view]}`;
  $('#banner').classList.toggle('on', S.conn === 'reconnect');
  $('#banner').innerHTML = S.conn === 'reconnect' ? `${ic('clock')}<span style="flex:1">Связь с сервером потеряна. Показаны данные от 22:01, действия отключены. Переподключаюсь…</span>${btn('Повторить сейчас', 'conn:online', { cls: 'sm' })}` : '';
  $('#conn').dataset.s = S.conn; $('#conn-text').textContent = { online: 'online', reconnect: 'reconnect', offline: 'offline' }[S.conn];
  main.scrollTop = top;
  if (typeof updateLoop === 'function') updateLoop();
  if (focus) { const el = focus.k ? $(`[data-bind="${focus.k}"]`) : $$('input[type="checkbox"][data-act]').find((i) => i.dataset.act === focus.act && i.dataset.v === focus.v); if (el) { el.focus(); if (focus.k) { try { el.setSelectionRange(focus.s, focus.s); } catch { /* select, switch */ } } } }
}
const offlineView = () => `<div class="page">${empty('Нет связи с сервером консоли', 'Сервер остановлен или перезапускается. Данные не обновляются, действия недоступны. Запустите консоль командой ниже и повторите подключение.', `<div class="codebox" style="max-width:360px;margin:0 auto 16px"><code>harness console</code>${btn('', 'copy:harness console', { cls: 'sm icon ghost', icon: 'copy', title: 'Скопировать' })}</div>${btn('Повторить подключение', 'conn:online', { cls: 'primary', icon: 'refresh' })}`)}</div>`;
function toast(t) { const el = $('#toast'); el.textContent = t; el.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('on'), 2600); }
function setPath(k, v) { const p = k.split('.'); let o = S; p.slice(0, -1).forEach((x) => { o = o[x]; }); o[p[p.length - 1]] = v === 'true' ? true : v === 'false' ? false : v; }

/* ---------- Диалоги, панель, палитра ---------- */
function dialog(html, onYes, yesLabel = 'Подтвердить', wide) {
  const d = $('#dlg'); d.className = wide ? 'wide' : '';
  d.innerHTML = `<form method="dialog" class="dlg">${html}<div class="dlg-foot"><button class="btn" value="cancel" type="submit">Отмена</button><button class="btn primary" value="yes" type="submit">${yesLabel}</button></div></form>`;
  d.onclose = null;
  d.querySelector('form').addEventListener('submit', (e) => { if (e.submitter && e.submitter.value === 'yes') setTimeout(onYes, 0); });
  d.showModal();
}
let drawerOpener = null;
function openDrawer(html) { if (!$('#drawer').classList.contains('on')) drawerOpener = document.activeElement; $('#drawer').innerHTML = html; $('#drawer').classList.add('on'); $('#drawer-back').classList.add('on'); const f = $('#drawer .btn'); if (f) f.focus(); }
function closeDrawer() { const wasOpen = $('#drawer').classList.contains('on'); $('#drawer').classList.remove('on'); $('#drawer-back').classList.remove('on'); if (wasOpen && drawerOpener && drawerOpener.isConnected) drawerOpener.focus(); }
let palSel = 0;
function palItems() { const q = $('#pal-q').value.toLowerCase(); return COMMANDS.filter(([t]) => t.toLowerCase().includes(q)); }
function palRender() {
  const items = palItems(); palSel = Math.min(palSel, Math.max(items.length - 1, 0));
  $('#pal-list').innerHTML = items.length ? items.map(([t, a, k], i) => `<li role="option" id="pal-${i}" aria-selected="${i === palSel}" data-a="${a}"><span>${t}</span><span class="hint">${k}</span></li>`).join('') : '<li class="muted" style="cursor:default">Ничего не найдено</li>';
  $('#pal-q').setAttribute('aria-activedescendant', items.length ? `pal-${palSel}` : '');
}
function palOpen() { $('#pal-q').value = ''; palSel = 0; palRender(); $('#palette').showModal(); $('#pal-q').focus(); }
const COMMANDS = [...NAV.flatMap(([, i]) => i.map(([id, t]) => [`Перейти: ${t}`, `go:${id}`, ''])), ['Проверить состояние проекта', 'toast:Проверка запущена', ''], ['Переключить тему', 'theme', '']];

/* ---------- Действия ---------- */
const actions = {
  set: (_, el) => { setPath(el.dataset.k, el.dataset.v); render(); },
  go: (a) => { closeDrawer(); location.hash = `#/${a}`; },
  toast: (a) => toast(a),
  conn: (a) => { S.orch.proposal = null; S.conn = a; $$('input[name=conn]').forEach((i) => { i.checked = i.value === a; }); render(); },
  refresh: () => toast('Снимок обновлён в 22:03'),
  copy: (a, el) => { try { navigator.clipboard.writeText(a || el.dataset.v); } catch { /* буфер недоступен */ } toast('Скопировано'); },
  confirm: (_, el) => dialog(`<h2 id="dlg-title">${esc(el.dataset.t)}</h2><p class="muted">${esc(el.dataset.m)}</p>`, () => { toast(el.dataset.done); }, el.dataset.ok),
  cmd: (_, el) => dialog(`<h2 id="dlg-title">${esc(el.dataset.t)}</h2><p class="muted">${esc(el.dataset.m)}</p><div class="codebox"><code>${esc(el.dataset.c)}</code></div><p class="muted" style="font-size:var(--fs-2)">Команда запускается на этом компьютере только после подтверждения.</p>`, () => { toast(el.dataset.done); }, 'Запустить'),
  theme: () => cycleTheme(),
  rail: () => { const a = $('#app'); a.classList.toggle('rail-min'); store.set('rail', a.classList.contains('rail-min') ? '1' : '0'); $('[data-act=rail]').setAttribute('aria-label', a.classList.contains('rail-min') ? 'Развернуть меню' : 'Свернуть меню'); },
  'nav-open': () => $('#app').classList.add('nav-open'), 'nav-close': () => $('#app').classList.remove('nav-open'),
  'drawer-close': () => closeDrawer(),
  palette: () => palOpen(),
  pop: () => { const p = $('#pop'); const o = !p.classList.contains('open'); p.classList.toggle('open', o); $('#conn').setAttribute('aria-expanded', String(o)); },
};
function exec(a) { const [name, ...rest] = a.split(':'); if (actions[name]) actions[name](rest.join(':'), document.body); }
document.addEventListener('click', (e) => {
  const li = e.target.closest('#pal-list li[data-a]'); if (li) { $('#palette').close(); exec(li.dataset.a); return; }
  const el = e.target.closest('[data-act]');
  if (!el) { if (!e.target.closest('.pop')) { $('#pop').classList.remove('open'); $('#conn').setAttribute('aria-expanded', 'false'); } return; }
  const [name, ...rest] = el.dataset.act.split(':');
  if (actions[name]) actions[name](rest.join(':'), el);
  if (el.closest('.rail') && window.innerWidth <= 860) $('#app').classList.remove('nav-open');
});
document.addEventListener('input', (e) => { const k = e.target.dataset && e.target.dataset.bind; if (!k) return; setPath(k, e.target.type === 'checkbox' ? String(e.target.checked) : e.target.value); render(); });

/* клавиатура */
let gSeq = 0;
document.addEventListener('keydown', (e) => {
  if (e.key === 'Tab' && $('#drawer').classList.contains('on') && !document.querySelector('dialog[open]')) {
    const items = $$('button:not(:disabled), a[href], select:not(:disabled), input:not(:disabled), textarea:not(:disabled), [tabindex="0"]', $('#drawer')).filter((el) => el.getClientRects().length);
    if (items.length && ((!e.shiftKey && document.activeElement === items.at(-1)) || (e.shiftKey && document.activeElement === items[0]) || !$('#drawer').contains(document.activeElement))) { e.preventDefault(); (e.shiftKey ? items.at(-1) : items[0]).focus(); }
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); palOpen(); return; }
  if (e.key === 'Escape') { closeDrawer(); $('#pop').classList.remove('open'); $('#app').classList.remove('nav-open'); }
  if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || document.querySelector('dialog[open]')) return;
  if (e.key === '?') { location.hash = '#/help'; return; }
  if (e.key === 'g') { gSeq = Date.now(); return; }
  if (Date.now() - gSeq < 1200) { const m = { h: 'home', d: 'diagnostics', u: 'update-harness', o: 'orchestration', r: 'reports', b: 'board', p: 'publish' }[e.key]; if (m) { location.hash = `#/${m}`; gSeq = 0; } }
});
$('#pal-q').addEventListener('input', () => { palSel = 0; palRender(); });
$('#pal-q').addEventListener('keydown', (e) => {
  const n = palItems().length;
  if (e.key === 'ArrowDown') { e.preventDefault(); palSel = (palSel + 1) % Math.max(n, 1); palRender(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); palSel = (palSel - 1 + n) % Math.max(n, 1); palRender(); }
  else if (e.key === 'Enter') { const it = palItems()[palSel]; if (it) { $('#palette').close(); exec(it[1]); } }
});

/* тема */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $$('[data-theme-set]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.themeSet === t))); store.set('theme', t);
}
function cycleTheme() { applyTheme((store.get('theme') || 'dark') === 'dark' ? 'light' : 'dark'); }
$$('[data-theme-set]').forEach((b) => b.addEventListener('click', () => applyTheme(b.dataset.themeSet)));
$$('input[name=conn]').forEach((i) => i.addEventListener('change', () => actions.conn(i.value)));
$('#demo-empty').addEventListener('change', (e) => { S.empty = e.target.checked; S.orch.proposal = null; render(); });
function boot() {
  applyTheme(store.get('theme') === 'light' ? 'light' : 'dark');
  if (store.get('rail') === '1') $('#app').classList.add('rail-min');
  window.addEventListener('hashchange', () => { closeDrawer(); render(); });
  /* для ревью и снимков: ?set=rep.tab=quality,repo.tab=links задаёт состояние до первого рендера */
  (new URLSearchParams(location.search).get('set') || '').split(',').filter(Boolean).forEach((kv) => { const [k, v] = kv.split('='); try { setPath(k, v); } catch { /* неизвестный ключ */ } });
  render();
}
