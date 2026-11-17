/* Обзор: Главная, Диагностика, Обновление, Проект */
'use strict';

const ATT_ACTS = {
  a1: () => confirmBtn('Назначить ревьюера', 'Назначить второго ревьюера для #555?', 'Ревьюер получит уведомление в трекере. QA запустится после его подтверждения.', 'Назначить', 'Ревьюер назначен', { cls: 'sm primary' }) + btn('Ход работы', 'go:agent-activity', { cls: 'sm' }),
  a2: () => confirmBtn('Offline worker', 'Продолжить #704 в offline worker?', 'Запуск перейдёт на изолированный worker без доступа к Docker daemon.', 'Продолжить', '#704 продолжен в offline worker', { cls: 'sm primary' }) + btn('Отчёт', 'go:reports', { cls: 'sm' }),
  a3: () => cmdBtn('Повторить QA', 'qa run --full', 'Повторить QA для #716?', 'Полный прогон QA с записью exit-кода для bounded restart.', { cls: 'sm primary' }) + btn('К воротам', 'go:publish', { cls: 'sm' }),
  a4: () => btn('Исправить', 'go:diagnostics', { cls: 'sm primary' }),
};
function attRow(a) {
  const kind = { decision: 'Решение', blocker: 'Блокер', health: 'Проверка' }[a.kind];
  return `<li class="row att"><span class="badge-ic ${a.sev}">${ic(sevIcon[a.sev])}</span><div class="grow"><div class="t">${esc(a.title)} <span class="tag" style="margin-left:8px">${kind}</span></div><div class="d">${esc(a.detail)}</div></div><div class="acts">${ATT_ACTS[a.id]()}</div></li>`;
}
const checkBar = () => `<div class="bar" role="img" aria-label="24 пройдено, 1 внимание, 3 ошибки, 29 пропущено"><i class="ok" style="flex:24"></i><i class="warn" style="flex:1"></i><i class="err" style="flex:3"></i><i class="skip" style="flex:29"></i></div>`;

const ctxCol = (icon, title, rowsArr) => `<div><h3>${ic(icon)} ${title}</h3>${rowsArr.map(([k, v, t]) => `<div class="r"><span>${k}</span><b class="${t || ''}" title="${esc(String(v))}">${v}</b></div>`).join('')}</div>`;
/* ---- Контур: анимация привязана к активности ----
   Связь «живая», если по ней за последние 15 с прошло хотя бы одно событие; скорость точек и штрихов
   растёт с числом событий в минуту. Нет событий — линия серая и неподвижна. Нет связи с сервером —
   данные устарели, всё неподвижно. В консоли счётчики берутся из снимка runtime (см. audit.md). */
const SIM = { mode: 'normal', base: { pi: 41, ir: 128, rw: 96, rs: 12, ra: 18 }, rate: { pi: 41, ir: 128, rw: 96, rs: 12, ra: 18 }, ago: { pi: 3, ir: 1, rw: 2, rs: 4, ra: 6 }, records: 306, beat: 4, up: 11520, queue: 0, wal: 14.0 };
{ const q = new URLSearchParams(location.search).get('act'); if (q) { SIM.mode = q; const r = document.querySelector(`input[name=act][value=${q}]`); if (r) r.checked = true; } }
const LK = { pi: 'lk-pi', ir: 'lk-ir', rw: 'lk-rw', rs: 'lk-rs', ra: 'lk-ra' };
const LOOP = [
  ['shield', 'Python policy', 'pol', 'политика', ['41', 'решений/мин', 'pi'], [['профили', '4'], ['approval', 'human'], ['правил', '38']]],
  ['plug', 'IPC', 'ipc', 'транспорт', ['128', 'сообщений/мин', 'ir'], [['сокет', 'unix'], ['клиентов', '2'], ['p95', '3 мс']]],
  ['cpu', 'Rust runtime', 'rt', 'ядро', ['3 ч 12 мин', 'uptime', 'up'], [['версия', '2.0.0'], ['worker', '2'], ['очередь', '0', 'q']]],
  ['db', 'SQLite WAL', 'wal', 'хранилище', ['96', 'записей/мин', 'rw'], [['schema', '6'], ['generation', '36'], ['WAL', '14,0 МБ', 'wal']]],
  ['eye', 'Supervisor', 'sup', 'надзор', ['4 с', 'с последнего сигнала', 'beat'], [['под наблюдением', '2'], ['рестартов', '1'], ['heartbeat/мин', '12', 'rs']]],
  ['link', 'Audit chain', 'aud', 'журнал', ['306', 'записей', 'rec'], [['добавлений/мин', '18', 'ra'], ['цепочка', 'цела'], ['разрывов', '0']]],
];
const lnode = (n, cls = '') => `<div class="ln ${cls}" id="nd-${n[2]}" data-s="ok"><div class="ln-h"><span class="ico">${ic(n[0])}</span><div class="tt"><b>${n[1]}</b><small>${n[3]}</small></div><span class="ss"><i class="dot"></i><em>работает</em></span></div><div class="big"><b data-lv="${n[4][2]}">${n[4][0]}</b><span>${n[4][1]}</span></div>${n[5].map(([k, v, key]) => `<div class="m"><span>${k}</span><b ${key ? `data-lv="${key}"` : ''}>${v}</b></div>`).join('')}</div>`;
const lcell = (id) => `<i class="lc" id="${LK[id]}" data-live="0" data-sp="1" aria-hidden="true"><b class="fl"></b><span class="lr"></span></i>`;
const loopHtml = () => `<div class="loop" id="loop" role="group" aria-label="Схема контура">${lnode(LOOP[0])}${lcell('pi')}${lnode(LOOP[1])}${lcell('ir')}${lnode(LOOP[2], 'live')}<div class="bus" id="bus" data-live="0" aria-hidden="true"><i class="bv" data-live="0"><b class="fl"></b></i><i class="bh" data-live="0"><b class="fl"></b></i><i class="bt t1" id="lk-rw" data-live="0" data-sp="1"><b class="fl"></b><span class="lr"></span></i><i class="bt t2" id="lk-rs" data-live="0" data-sp="1"><b class="fl"></b><span class="lr"></span></i><i class="bt t3" id="lk-ra" data-live="0" data-sp="1"><b class="fl"></b><span class="lr"></span></i></div>${lnode(LOOP[3])}<span></span>${lnode(LOOP[4])}<span></span>${lnode(LOOP[5])}</div>`;
const fmtUp = (s) => `${Math.floor(s / 3600)} ч ${Math.floor((s % 3600) / 60)} мин`;
const fmtAgo = (s) => (s < 120 ? `${s} с` : `${Math.floor(s / 60)} мин`);
function simTick() {
  const off = S.conn !== 'online'; const m = SIM.mode;
  if (off) return;
  SIM.up += 1;
  Object.keys(SIM.base).forEach((k) => {
    const dead = m === 'idle' || (m === 'fault' && k === 'rs');
    SIM.rate[k] = dead ? 0 : Math.max(1, Math.round(SIM.base[k] * (0.9 + Math.random() * 0.2)));
    SIM.ago[k] = SIM.rate[k] ? Math.floor(Math.random() * Math.max(2, (60 / SIM.rate[k]) * 2)) : SIM.ago[k] + 1;
  });
  if (SIM.rate.ra && Math.random() < SIM.rate.ra / 60) SIM.records += 1;
  SIM.beat = SIM.rate.rs ? Math.floor(Math.random() * 12) : SIM.beat + 1;
  SIM.queue = m === 'normal' ? Math.floor(Math.random() * 3) : 0;
  SIM.wal += SIM.rate.rw ? 0.002 : 0;
}
const setText = (el, t) => { if (el && el.textContent !== String(t)) el.textContent = t; };
const setData = (el, k, v) => { if (el && el.dataset[k] !== v) el.dataset[k] = v; };
const speedLevel = (r) => (r >= 100 ? '3' : r >= 30 ? '2' : '1');
function updateLoop() {
  const root = document.getElementById('loop'); if (!root) return;
  if (!root._io && 'IntersectionObserver' in window) { root._io = new IntersectionObserver(([e]) => root.classList.toggle('paused', !e.isIntersecting)); root._io.observe(root); }
  const off = S.conn !== 'online'; const live = {};
  Object.keys(SIM.rate).forEach((k) => {
    live[k] = !off && SIM.rate[k] > 0 && SIM.ago[k] <= 15;
    const el = document.getElementById(LK[k]); if (!el) return;
    setData(el, 'live', live[k] ? '1' : '0'); setData(el, 'sp', speedLevel(SIM.rate[k]));
    setText(el.querySelector('.lr'), off ? '—' : live[k] ? `${SIM.rate[k]}/мин` : `нет ${fmtAgo(SIM.ago[k])}`);
  });
  const anyBus = live.rw || live.rs || live.ra;
  setData(document.getElementById('bus'), 'live', anyBus ? '1' : '0');
  $$('.bv, .bh', root).forEach((e) => setData(e, 'live', anyBus ? '1' : '0'));
  const vals = { pi: SIM.rate.pi, ir: SIM.rate.ir, rw: SIM.rate.rw, rs: SIM.rate.rs, ra: SIM.rate.ra, rec: SIM.records, beat: `${SIM.beat} с`, up: fmtUp(SIM.up), q: SIM.queue, wal: `${SIM.wal.toFixed(1).replace('.', ',')} МБ` };
  $$('[data-lv]', root).forEach((e) => setText(e, vals[e.dataset.lv]));
  const dead = SIM.beat > 15;
  const st = { pol: live.pi ? 'ok' : 'idle', ipc: live.ir ? 'ok' : 'idle', rt: live.ir || anyBus ? 'ok' : 'idle', wal: live.rw ? 'ok' : 'idle', sup: dead ? 'err' : live.rs ? 'ok' : 'idle', aud: live.ra ? 'ok' : 'idle' };
  Object.entries(st).forEach(([k, s]) => { const n = document.getElementById(`nd-${k}`); if (!n) return; const ss = off ? 'idle' : s; setData(n, 's', ss); n.classList.toggle('live', k === 'rt' && s === 'ok' && !off); setText(n.querySelector('em'), { ok: 'работает', idle: 'нет обмена', err: 'не отвечает' }[ss]); });
  const sum = Object.values(SIM.rate).reduce((x, y) => x + y, 0);
  const tag = document.getElementById('loop-tag'); const pl = document.getElementById('loop-pill');
  const idleFor = Math.min(...Object.values(SIM.ago));
  const [tk, tt] = off ? ['', 'данные устарели'] : dead ? ['err', `сбой · ${sum} соб/мин`] : sum ? ['info', `live · ${sum} соб/мин`] : ['', 'нет обмена'];
  if (tag) { const cls = `st ${tk}`; if (tag.className !== cls) tag.className = cls; setText(tag.lastChild, tt); }
  if (pl) { const [k, t, i] = off ? ['warn', 'данные устарели — показан последний снимок', 'clock'] : dead ? ['err', `Supervisor: нет сигнала ${SIM.beat} с`, 'x'] : sum ? ['ok', 'все компоненты на месте', 'check'] : ['warn', `нет обмена ${fmtAgo(idleFor)}`, 'pause']; const key = `${k}|${t}`; if (pl.dataset.k !== key) { pl.dataset.k = key; pl.className = `st ${k}`; pl.innerHTML = `${ic(i)}${t}`; } }
}
setInterval(() => { if (!document.hidden) { simTick(); updateLoop(); } }, 1000);
$$('input[name=act]').forEach((i) => i.addEventListener('change', () => { SIM.mode = i.value; if (i.value === 'normal') SIM.beat = 4; simTick(); updateLoop(); }));

screens.home = () => {
  const h = S.home;
  const att = ATTENTION.length;
  const sess = RUNS.filter((r) => r.state !== 'done' && (!h.q || r.id.includes(h.q.replace('#', ''))));
  const health = `${checkBar()}<div style="display:flex;justify-content:space-between;gap:12px;margin:12px 0 12px;flex-wrap:wrap;align-items:center"><span>24 пройдено · 1 внимание · 3 ошибки</span>${seg('home.mode', [['offline', 'Офлайн'], ['online', 'Онлайн']], h.mode, 'Режим проверки')}</div>
      <div class="hb"><span>Файлы Harness</span><span class="tr"><i class="err" style="width:100%"></i></span><b>3 ош.</b></div><div class="hb"><span>Окружение</span><span class="tr"><i class="warn" style="width:50%"></i></span><b>1 вним.</b></div><div class="hb"><span>Конфигурация</span><span class="tr"><i class="ok" style="width:100%"></i></span><b>ок</b></div><div class="hb"><span>Runtime</span><span class="tr"><i class="ok" style="width:100%"></i></span><b>ок</b></div><div class="hb"><span>Сеть и контейнеры</span><span class="tr"><i style="width:0"></i></span><b>29 пропущ.</b></div>
      <p class="muted hh-note" style="font-size:var(--fs-2);margin-top:12px">${h.mode === 'offline' ? 'Онлайн-проверки пропущены, пропуск не считается успехом.' : 'Онлайн-режим в макете не выполняется и не превращает пропуски в успех.'}</p><h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">Что исправить в первую очередь</h3>${CHECKS.filter((c) => c.s === 'err').map((c) => `<a class="row click" href="#/diagnostics" data-act="set" data-k="diag.sel" data-v="${c.id}" style="padding:8px 0;text-decoration:none;color:inherit;border-top:1px solid var(--line)"><span class="badge-ic err" style="width:24px;height:24px">${ic('x', 'sm')}</span><span class="grow">${esc(c.title)}</span>${ic('chev', 'sm')}</a>`).join('')}<div class="hh-chips">${CHECKS.filter((c) => c.s === 'err').map((c) => `<a class="tag" href="#/diagnostics" data-act="set" data-k="diag.sel" data-v="${c.id}">${esc(c.title)}</a>`).join('')}</div><p class="faint hh-note" style="font-size:var(--fs-2);margin-top:auto;padding-top:12px">Последняя проверка 22:01 · всего 57 проверок</p>`;
  const context = `<div class="ctx">
    ${ctxCol('folder', 'Проект', [['Имя', 'claude-agent-harness'], ['Ветка', 'integration/harness-runtime-reliability'], ['Трекер', 'github']])}
    ${ctxCol('box', 'Harness', [['Пакет', '1.5.1', 'ok'], ['Установлено', '1.5.1'], ['Capability', '1 установлена'], ['Скиллы', '32 · drift 1', 'warn']])}
    ${ctxCol('db', 'Runtime store', [['Authority', 'runtime-store', 'ok'], ['Schema', '6'], ['Generation', '36'], ['Audit', '306'], ['Cutover', '27.10.2026']])}
    ${ctxCol('map', 'Repo Map', [['Уровень', 'full'], ['Файлы', '1 284'], ['Связи', '3 912'], ['Объём', '≈184k токенов'], ['HEAD', '47d465ce']])}
    ${ctxCol('file', 'Память', [['Состояние', 'пропущена', 'warn'], ['Источники', '3'], ['Лимит', '5 · 1 800 токенов']])}
  </div>`;
  const loopFoot = `<div class="loop-foot"><span id="loop-pill" class="st ok">${ic('check')}все компоненты на месте</span><span class="tag">${ic('clock', 'sm')} cutover 27.10.2026</span><span class="tag">${ic('check', 'sm')} цепочка аудита цела</span><span class="legend">Линия движется, если по ней за последние 15 с шли события; скорость — число событий в минуту. Нет событий — линия неподвижна.</span></div>`;
  const feed = `<ol class="feed">${FEED.map(([t, x]) => `<li><time class="mono">${t}</time><span>${esc(x)}</span></li>`).join('')}</ol>`;
  const tasks = sess.length ? sess.map((r) => `<a class="tl" href="#/agent-activity" data-act="set" data-k="act.sel" data-v="${r.id}"><b class="mono">${r.id}</b><span class="ttl" title="${esc(r.title)}">${esc(r.title)}</span><span class="who">${r.agent} · ${r.role}</span>${lane(r.stage, r.state, true)}${stateOf(r)}<span class="el">${r.elapsed}</span></a>`).join('') : empty('Нет задач', 'По этому номеру ничего не найдено.');
  return `<div class="page fit home">
  ${head('Главная', 'Состояние Harness в проекте claude-agent-harness: версия, контекст, контур и последние задачи.', btn('Проверить', 'toast:Снимок перечитан', { icon: 'refresh' }) + btn('Диагностика', 'go:diagnostics') + btn('Обновление', 'go:update-harness', { cls: 'primary' }))}
  ${strip([['Здоровье', '24 пройдено', '<span style="color:var(--warn)">1 внимание</span> · <span style="color:var(--err)">3 ошибки</span> · 29 пропущено'], ['Версия', '1.5.1 → 2.0.0', 'pre-release · есть обновление'], ['Навыки', '32', '259 managed files · 1 расхождение'], ['Runtime store', 'schema 6', 'generation 36 · audit 306 · cutover 27.10.2026']])}
  <div class="stack">
    <div class="home-top">
      ${S.empty ? panel('Требует внимания', empty('Всё спокойно', 'Нет решений, блокеров и ошибок проверок.'), { flush: true }) : panel('Требует внимания', rows(ATTENTION.map(attRow)), { flush: true, count: att, cls: 'attn home-attn', actions: '<span class="muted" style="font-size:var(--fs-2)">3 ошибки · 1 предупреждение</span>' })}
      ${panel('Здоровье', health, { cls: 'home-health', actions: btn('Все проверки', 'go:diagnostics', { cls: 'sm' }) })}
    </div>
    ${panel('Контекст', context, { flush: true, cls: 'home-ctx', actions: '<span class="muted" style="font-size:var(--fs-2)">project</span>' })}
    ${panel('Контур Harness Next 2.0', loopHtml() + loopFoot, { flush: true, cls: 'home-loop', actions: `<span id="loop-tag" class="st info" title="Линия движется, если по ней за последние 15 с шли события; скорость — число событий в минуту. Нет событий — линия неподвижна.">${ic('dot')}<span>live</span></span>${btn('Harness', 'go:harness', { cls: 'sm' })}` })}
    <div class="home-side">${panel('Последние задачи', tasks, { flush: true, cls: 'home-tasks', count: sess.length, actions: `<label class="field" style="min-height:30px;width:150px">${ic('search', 'sm')}<input type="search" data-bind="home.q" value="${esc(h.q)}" placeholder="Номер" aria-label="Номер тикета"></label>${btn('Ход работы', 'go:agent-activity', { cls: 'sm' })}` })}${panel('Последние события', feed, { flush: true, cls: 'home-feed', count: FEED.length })}</div>
  </div></div>`;
};

