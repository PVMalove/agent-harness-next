/* Обновление: список изменений · diff и решение · режим, seed, план и миграция в виде конвейера. */
'use strict';

const UL = { upd: ['info', 'Обновится', 'refresh'], add: ['ok', 'Добавится', 'plus'], local: ['warn', 'Локальные правки', 'alert'], conflict: ['err', 'Конфликт', 'x'] };
const MODES = [
  ['normal', 'Обычное', 'Обновляет управляемые файлы и не трогает ваши правки.', ['ok', 'Безопасно']],
  ['force', 'С перезаписью управляемых файлов', 'Приводит все managed-файлы к версии 2.0.0, локальные правки в них пропадут.', ['warn', 'Перезапись']],
  ['seed', 'С перезаписью выбранных seed-файлов', 'Вы сами выбираете, какие стартовые файлы заменить.', ['warn', 'Выборочно']],
];
const MIG = [['Backup', 'копия runtime-store', '2,1 с'], ['Schema 3 → 6', 'миграции схемы', '4,8 с'], ['Cutover', 'переключение на новый store', '1,2 с'], ['Health', 'итоговая проверка', '3,0 с']];
{ const q = new URLSearchParams(location.search); if (q.get('rtab')) S.upd.rtab = q.get('rtab'); if (q.get('mode')) S.upd.mode = q.get('mode'); if (q.get('sel')) S.upd.sel = q.get('sel'); if (q.get('ftab')) S.upd.ftab = q.get('ftab'); }
const resolved = (f) => S.upd.res[f];
const unresolved = () => UPD.filter((x) => x.s === 'conflict' && !resolved(x.f)).length;
const updCmd = () => { const u = S.upd; const picked = SEEDS.filter((p) => u.seeds[p]); return `harness update .${u.mode === 'force' ? ' --overwrite-managed' : ''}${u.mode === 'seed' ? picked.map((p) => ` --overwrite-seed ${p}`).join('') : ''}`; };
const updBlock = () => { const u = S.upd; const picked = SEEDS.filter((p) => u.seeds[p]).length; const c = unresolved(); return c ? `Решите конфликты: ${c}` : u.mode === 'seed' && !picked ? 'Выберите seed-файлы' : ''; };

screens['update-harness'] = () => {
  const u = S.upd; const run = u.run; const block = updBlock(); const picked = SEEDS.filter((p) => u.seeds[p]).length;
  const list = UPD.filter((x) => u.filter === 'all' || x.s === u.filter);
  const f = UPD.find((x) => x.f === u.sel) || list[0] || UPD[0];
  const groups = ['conflict', 'local', 'upd', 'add'].map((k) => [k, list.filter((x) => x.s === k)]).filter(([, g]) => g.length);
  const conf = unresolved();
  const filt = statePipe('upd.filter', u.filter, [['all', 'Все', 16], ['upd', 'Обновятся', 12, 'info'], ['add', 'Добавится', 1, 'ok'], ['local', 'Локальные', 2, 'warn'], ['conflict', 'Конфликты', conf, 'err']]);
  const summary = `<section class="panel dsum compact" aria-label="Сводка обновления"><div class="dsum-row"><div class="verline"><b>${u.done ? '2.0.0' : '1.5.1'}</b>${u.done ? '' : `<span class="muted">→</span><b>2.0.0</b>`}<span class="tag">pre-release</span><span class="muted">32 навыка · 259 managed files · schema ${u.done ? '6' : '3 → 6'}</span></div><div class="runline"><div class="runtrack ${run ? 'on' : ''}"><i id="upd-fill" style="transform:scaleX(${run ? (run.i + run.p) / 4 : u.done ? 1 : 1})"></i></div><span id="upd-txt" class="muted">${run ? runText(run) : u.done ? 'Обновление выполнено (демо)' : `Diff от ${u.checked} · файлы не меняются, пока вы не подтвердите`}</span></div></div>${segBar({ ok: 1, warn: 2, err: conf, skip: 12 }, 'Состав изменений')}<div class="dsum-row" style="margin:8px 0 0">${filt}</div></section>`;
  const modeTab = `<ul class="vpl" role="radiogroup" aria-label="Режим обновления">${MODES.map(([v, t, d, [rk, rt]], k) => { const sel = u.mode === v; const before = MODES.findIndex((m) => m[0] === u.mode) > k; return `<li class="${before ? 'pass' : ''}"><button type="button" role="radio" aria-checked="${sel}" class="vb" data-act="set" data-k="upd.mode" data-v="${v}"><span class="vn">${k + 1}</span><span class="vt"><b>${t}</b><small>${d}</small><span class="vp">${pill(rk, rt)}</span></span></button></li>`; }).join('')}</ul>`;
  const seedTab = u.mode === 'seed' ? `<div class="note warn" style="margin-bottom:12px">${ic('alert')}<div>Включено — «перезаписать», выключено — «оставить мой файл». Включено <b>${picked}</b> из ${SEEDS.length}.</div></div><div class="head-actions" style="margin-bottom:8px">${btn('Выбрать все', 'seed-all', { cls: 'sm' })}${btn('Снять выбор', 'seed-none', { cls: 'sm' })}</div><div class="seedlist">${SEEDS.map((p) => `<label class="chk"><input type="checkbox" role="switch" data-act="seed" data-v="${p}" ${u.seeds[p] ? 'checked' : ''}><span class="mono">${p}</span></label>`).join('')}</div>` : `<div class="note">${ic('dot')}<div>Seed-файлы выбираются только в режиме «С перезаписью выбранных seed-файлов».</div></div><div class="head-actions" style="margin-top:12px">${btn('Выбрать этот режим', 'upd-mode-seed', { cls: 'sm' })}</div>`;
  const warn = { normal: 'Ваши локальные правки сохранятся. Конфликты нужно решить до обновления.', force: 'Управляемые файлы будут перезаписаны версиями 2.0.0, локальные правки в них пропадут.', seed: picked ? `Будут перезаписаны выбранные seed-файлы: ${picked}. Остальные останутся.` : 'Seed-файлы не выбраны: перезаписывать нечего.' }[u.mode];
  const planTab = `<h3 class="muted" style="font-size:var(--fs-2);margin-bottom:8px">Команда</h3><div class="codebox"><code>${esc(updCmd())}</code>${btn('', `copy:${updCmd()}`, { cls: 'sm icon ghost', icon: 'copy', title: 'Скопировать' })}</div><div class="note ${u.mode === 'normal' ? '' : 'warn'}" style="margin-top:12px">${ic(u.mode === 'normal' ? 'dot' : 'alert')}<div>${warn}</div></div>
    <dl class="kv" style="margin-top:12px"><dt>Обновятся</dt><dd>12</dd><dt>Добавится</dt><dd>1</dd><dt>Локальные правки</dt><dd>2</dd><dt>Конфликты</dt><dd>${conf ? `<span style="color:var(--err)">${conf} не решён</span>` : 'решены'}</dd><dt>Миграция store</dt><dd>schema 3 → 6 при запуске</dd></dl>`;
  const done = (k) => u.done || (run && (k < run.i)); const act = (k) => run && k === run.i;
  const migTab = `<ul class="vpl mig" aria-label="Миграция runtime-store">${MIG.map(([t, d, dur], k) => `<li class="${done(k) || (run && k <= run.i) ? 'pass' : ''}" data-s="${done(k) ? 'done' : act(k) ? 'run' : 'wait'}"><div class="vb static"><span class="vn">${done(k) ? ic('check') : act(k) ? ic('refresh') : k + 1}</span><span class="vt"><b>${t}</b><small>${d}</small></span><span class="faint mig-d">${done(k) ? dur : act(k) ? 'идёт…' : 'ожидает'}</span></div></li>`).join('')}</ul><p class="muted" style="font-size:var(--fs-2);margin-top:12px">${run ? 'Шаги идут по очереди; движение — только пока шаг выполняется.' : u.done ? 'Все шаги выполнены (демо, файлы не менялись).' : 'Миграция стартует после подтверждения обновления. В макете файлы и store не меняются.'}</p>`;
  const rtab = ['mode', 'seed', 'plan', 'migr'].includes(u.rtab) ? u.rtab : 'mode';
  const rbody = { mode: modeTab, seed: seedTab, plan: planTab, migr: migTab }[rtab];
  const right = `<div class="ph"><h2>Как обновить</h2></div>${pipeTabs('upd.rtab', [['mode', 'Режим', MODES.findIndex((m) => m[0] === u.mode) + 1], ['seed', 'Seed', u.mode === 'seed' ? picked : '–'], ['plan', 'План', '3'], ['migr', 'Миграция', run ? `${Math.min(4, run.i + 1)}` : '4']], rtab)}<div class="scr">${rbody}</div><div class="dfoot">${block ? `<span class="muted blk">${ic('alert', 'sm')} ${block}</span>` : ''}${btn('Обновить…', 'upd-start', { cls: 'primary sm', dis: !!(block || run || u.done), title: block })}</div>`;
  const fsel = f; const st = UL[fsel.s]; const ftab = ['diff', 'decide'].includes(u.ftab) ? u.ftab : 'diff';
  const isSeed = SEEDS.includes(fsel.f) || /^(AGENTS|CLAUDE)\.md$/.test(fsel.f);
  const impact = fsel.f.startsWith('skills/') ? 'навык workflow: меняется описание шагов' : fsel.f.startsWith('docs/') ? 'документация агентов и правила процесса' : fsel.f.startsWith('scripts/') ? 'скрипты проверки и QA' : fsel.f.startsWith('harness/') ? 'каталог capabilities и установка' : 'инструкции проекта для агентов';
  const about = `<h3 class="muted" style="font-size:var(--fs-2);margin:16px 0 8px">О файле</h3><dl class="kv"><dt>Тип</dt><dd>${isSeed ? 'seed — стартовый файл проекта' : 'managed — под управлением Harness'}</dd><dt>Capability</dt><dd>${fsel.f.startsWith('skills/') ? 'engineering-suite' : 'project-foundation'}</dd><dt>Версия</dt><dd>1.5.1 → 2.0.0</dd><dt>Влияние</dt><dd>${impact}</dd></dl>`;
  const diffTab = fsel.d.length ? `<div class="diff" tabindex="0" role="region" aria-label="Diff ${esc(fsel.f)}">${fsel.d.map((l) => `<div class="${l[0] === '+' ? 'a' : l[0] === '-' ? 'd' : l[0] === '@' ? 'h' : ''}">${esc(l)}</div>`).join('')}</div>${about}` : `<p class="muted">Файл совпадает с версией 2.0.0.</p>${about}`;
  const r = resolved(fsel.f);
  const cmpSide = (title, lines, tone) => `<div class="cmpcol"><h3 class="muted" style="font-size:var(--fs-2);margin-bottom:8px">${title}</h3><div class="diff"><div class="${tone}">${lines.map(esc).join('\n') || ' '}</div></div></div>`;
  const mi = fsel.d.findIndex((l) => l.startsWith('<<<<<<<')); const ei = fsel.d.findIndex((l) => l.startsWith('=======')); const ti = fsel.d.findIndex((l) => l.startsWith('>>>>>>>'));
  const compare = fsel.s === 'conflict' && mi >= 0 ? `<div class="cols2" style="margin-top:16px;gap:12px">${cmpSide('Ваш файл', fsel.d.slice(mi + 1, ei), 'd')}${cmpSide('Версия 2.0.0', fsel.d.slice(ei + 1, ti), 'a')}</div><p class="muted" style="font-size:var(--fs-2);margin-top:8px">«Объединить вручную» оставит маркеры конфликта в файле: после правки проверьте его командой <code>harness diff</code>.</p>` : '';
  const decideTab = fsel.s === 'conflict' ? `<div class="note ${r ? '' : 'err'}">${ic(r ? 'check' : 'alert')}<div>${r ? `Решение: ${r === 'mine' ? 'оставить мой файл' : r === 'theirs' ? 'взять версию 2.0.0' : 'объединить вручную'}.` : 'Файл изменён и у вас, и в обновлении. Решите конфликт до применения.'}</div></div><div class="head-actions" style="margin-top:12px">${btn('Оставить мой', 'upd-res:mine', { cls: 'sm' + (r === 'mine' ? ' primary' : '') })}${btn('Взять из 2.0.0', 'upd-res:theirs', { cls: 'sm' + (r === 'theirs' ? ' primary' : '') })}${btn('Объединить вручную', 'upd-res:merge', { cls: 'sm' + (r === 'merge' ? ' primary' : '') })}</div>${compare}` : `<div class="note">${ic('check')}<div>${{ upd: 'Файл будет обновлён автоматически, ваших правок в нём нет.', add: 'Новый файл будет добавлен.', local: 'В файле есть ваши правки — они сохранятся, обновление их не затронет.' }[fsel.s]}</div></div>`;
  const mid = `<div class="dh"><span class="badge-ic ${st[0]}" role="img" aria-label="${st[1]}" title="${st[1]}">${ic(st[2])}</span><div style="flex:1;min-width:0"><h2 class="clamp1 mono" style="font-size:var(--fs-3)">${esc(fsel.f)}</h2></div>${diffCount(fsel)}</div>${pipeTabs('upd.ftab', [['diff', 'Изменения', '±'], ['decide', 'Решение', fsel.s === 'conflict' ? (r ? '✓' : '!') : '✓']], ftab)}<div class="scr">${ftab === 'diff' ? diffTab : decideTab}</div>`;
  return `<div class="page fill dg">${head('Обновление', 'Что изменится при переходе на Harness 2.0.0 и как применить обновление безопасно.', btn('', 'upd-recheck', { icon: 'refresh', cls: 'icon', dis: !!run, title: 'Проверить заново', data: 'aria-label="Проверить заново"' }))}
  ${summary}<div class="diag upd">
    <div class="panel dlist"><div class="dlist-top"><span class="muted" style="font-size:var(--fs-2)">Ключевые файлы · ${list.length} из 16</span></div><div role="list" class="dl-scroll">${groups.length ? groups.map(([k, g]) => `<div class="group-title">${UL[k][1]} · ${g.length}</div>${g.map((x) => `<button type="button" role="listitem" class="row click cmp ${x.f === fsel.f ? 'sel' : ''}" data-act="set" data-k="upd.sel" data-v="${esc(x.f)}"><span class="badge-ic ${UL[x.s][0]}">${ic(UL[x.s][2], 'sm')}</span><span class="grow" style="min-width:0"><span class="t clamp1" style="font-weight:500;display:block">${esc(x.f.split('/').pop())}</span><span class="faint mono clamp1" style="font-size:var(--fs-1);display:block">${esc(x.f.split('/').slice(0, -1).join('/') || 'корень проекта')}</span></span><span class="faint" style="font-size:var(--fs-2)">${x.note}</span></button>`).join('')}`).join('') : empty('Нет файлов', 'В этой категории ключевых файлов нет.', btn('Сбросить', 'upd-reset'))}</div><div class="dl-foot muted">Остальные 8 файлов обновятся без вопросов</div></div>
    <section class="panel dd" aria-label="Файл">${mid}</section><aside class="panel dplan" aria-label="Как обновить">${right}</aside></div></div>`;
};
const diffCount = (f) => { const m = /\+(\d+)\s*[−-]\s*(\d+)/.exec(f.note); return m ? `<span class="dcount" title="Добавлено ${m[1]}, удалено ${m[2]} строк"><b class="p">+${m[1]}</b><b class="m">−${m[2]}</b></span>` : `<span class="dcount"><span class="faint">${esc(f.note)}</span></span>`; };
const runText = (r) => `Миграция: ${MIG[Math.min(3, r.i)][0]} · ${Math.round(((r.i + r.p) / 4) * 100)}%`;
Object.assign(actions, {
  'upd-reset': () => { S.upd.filter = 'all'; render(); },
  'upd-recheck': () => { S.upd.done = false; S.upd.checked = new Date().toTimeString().slice(0, 5); render(); toast('Diff перечитан'); },
  'upd-res': (v) => { S.upd.res[S.upd.sel] = v; render(); },
  'upd-mode-seed': () => { S.upd.mode = 'seed'; render(); },
  seed: (a, el) => { const p = el.dataset.v; S.upd.seeds[p] = !S.upd.seeds[p]; render(); },
  'seed-all': () => { SEEDS.forEach((p) => { S.upd.seeds[p] = true; }); render(); },
  'seed-none': () => { S.upd.seeds = {}; render(); },
  'upd-start': () => dialog(`<h2 id="dlg-title">Применить обновление 2.0.0?</h2><p class="muted">Сначала будет сделана резервная копия store, затем миграция схемы 3 → 6, переключение и проверка.</p><div class="codebox"><code>${esc(updCmd())}</code></div><p class="muted" style="font-size:var(--fs-2)">В макете файлы и store не меняются.</p>`, () => actions['upd-run'](), 'Обновить'),
});
/* Миграция: каждый шаг идёт по очереди; прогресс — transform, значок вращается только у выполняемого шага */
let updTimer = null;
actions['upd-run'] = () => {
  if (S.upd.run) return;
  S.upd.run = { i: 0, p: 0 }; S.upd.rtab = 'migr'; S.upd.done = false; render();
  updTimer = setInterval(() => {
    const r = S.upd.run; if (!r) return;
    r.p += 0.07 + Math.random() * 0.05;
    if (r.p >= 1) { r.i += 1; r.p = 0; }
    if (r.i >= MIG.length) { clearInterval(updTimer); S.upd.run = null; S.upd.done = true; render(); toast('Обновление выполнено (демо)'); return; }
    const fill = document.getElementById('upd-fill'); const txt = document.getElementById('upd-txt');
    if (fill) fill.style.transform = `scaleX(${(r.i + r.p) / MIG.length})`;
    if (txt) txt.textContent = runText(r);
    $$('.mig li').forEach((li, k) => { const s = k < r.i ? 'done' : k === r.i ? 'run' : 'wait'; if (li.dataset.s !== s) { li.dataset.s = s; li.classList.toggle('pass', k <= r.i); const vn = li.querySelector('.vn'); vn.innerHTML = s === 'done' ? ic('check') : s === 'run' ? ic('refresh') : String(k + 1); li.querySelector('.mig-d').textContent = s === 'done' ? MIG[k][2] : s === 'run' ? 'идёт…' : 'ожидает'; } });
  }, 120);
};
