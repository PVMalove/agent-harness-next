/* Схема пайплайна во вкладке «Поток». Узлы, связи и правила состояний повторяют PipelineMap реальной консоли
   (harness/console/frontend/src/orchestration/Charts.tsx, format.ts): роль держит открытые этапы леджера,
   тон err — блокировка, active — живой шаг, warn — открыт, но не живой; Approve QA ждёт, если есть запуски на решении.
   Геометрия сжата: 1200×270 вместо 1200×416, без пустых полос под узлами. */
const OM_ROLE_NODE = { 1: 'Архитектор', 2: 'Разработчик', 3: 'Code review', 4: 'QA · clean-room' };
const OM_NODES = [
  // [id, x, y, w, тип, заголовок, подпись, роль (этап запуска) | null]
  ['plan', 24, 36, 192, 'human', 'Approve плана', 'гейт человека', null],
  ['arch', 268, 36, 228, 'role', 'Архитектор', 'разбор задачи', 1],
  ['dev', 268, 90, 228, 'role', 'Разработчик', 'контекст + TDD', 2],
  ['rev', 268, 144, 228, 'role', 'Code review', 'свежесть базы', 3],
  ['qa', 268, 198, 228, 'role', 'QA · clean-room', 'закреплённый SHA', 4],
  ['frev', 540, 144, 240, 'exception', 'Находки review', 'возврат в Developer', null],
  ['fqa', 540, 198, 240, 'exception', 'Находки QA', 'повтор или дефект', null],
  ['aqa', 868, 36, 308, 'human', 'Approve QA', 'гейт человека', null],
  ['rep', 868, 90, 308, 'coord', 'Итоговый отчёт', 'evidence + решение', null],
  ['pub', 868, 144, 308, 'coord', 'Публикация', 'принятый SHA', null],
  ['pr', 868, 198, 308, 'human', '/to-pull-requests', 'передача человеку', null],
];
const OM_H = 42;
const OM_GROUPS = [['01 · План и approve', 8, 224], ['02 · Сборка и review с находками', 252, 580], ['03 · Evidence и публикация', 852, 340]];
// [путь, цвет, узел-приёмник для «active», пунктир]
const OM_EDGES = [
  ['M216 57H268', 'flow', 'arch'], ['M382 78V90', 'flow', 'dev'], ['M382 132V144', 'flow', 'rev'], ['M382 186V198', 'flow', 'qa'],
  ['M496 165H540', 'back'], ['M496 219H540', 'back'],
  ['M540 165H518V111H496', 'back', null, 1], ['M540 219H508V138H434V132', 'back', null, 1],
  ['M382 240V252H800V57H868', 'flow', 'aqa'], ['M780 219H820V111H868', 'gate', null, 1],
  ['M1022 78V90', 'flow', 'rep'], ['M1022 132V144', 'flow'], ['M1022 186V198', 'flow'],
];

function orchSchemeModel() {
  const live = S.empty ? [] : orchAll().filter((r) => !r.archived);
  const at = (stage) => live.filter((r) => r.stage === stage);
  const place = (stage) => {
    const open = at(stage);
    if (!open.length) return { tone: 'idle', chip: '', count: 0 };
    const tone = open.some((r) => ['blocked', 'failed'].includes(r.state)) ? 'err' : open.some((r) => r.state === 'running') ? 'active' : 'warn';
    return { tone, chip: open.at(-1).id, count: open.length };
  };
  const places = Object.fromEntries(Object.entries(OM_ROLE_NODE).map(([stage, name]) => [name, place(Number(stage))]));
  const working = live.filter((r) => r.state === 'running').length, blocked = live.filter((r) => ['blocked', 'failed'].includes(r.state)).length, awaiting = live.filter((r) => r.state === 'wait').length;
  const steps = live.filter((r) => r.state === 'running' && OM_ROLE_NODE[r.stage]).map((r) => `${r.id} · ${OM_ROLE_NODE[r.stage]}`);
  return { places, working, blocked, awaiting, steps, gate: awaiting > 0 ? 'wait' : 'idle' };
}

function orchScheme() {
  const m = orchSchemeModel();
  const tone = (n) => (n[4] === 'role' ? m.places[n[5]] : n[0] === 'aqa' ? { tone: m.gate, chip: '', count: 0 } : { tone: n[4] === 'exception' ? (n[0] === 'frev' ? 'review' : 'qa') : 'idle', chip: '', count: 0 });
  const nodeTone = Object.fromEntries(OM_NODES.map((n) => [n[0], tone(n)]));
  const node = (n) => {
    const [id, x, y, w, type, title, sub] = n, t = nodeTone[id], c = t.count || 0;
    return `<g class="om-node ${type} ${t.tone}"><title>${esc(title)}${c ? ` · запусков: ${c}` : ''}</title><rect class="om-bg" x="${x}" y="${y}" width="${w}" height="${OM_H}" rx="8"/><rect class="om-bar" x="${x}" y="${y + 9}" width="3" height="${OM_H - 18}" rx="1.5"/><text class="om-t" x="${x + 14}" y="${y + 18}">${esc(title)}</text><text class="om-s" x="${x + 14}" y="${y + 34}">${t.chip ? esc(t.chip) + ' · ' : ''}${esc(sub)}</text><g class="om-count ${c ? 'on' : ''}"><circle cx="${x + w - 14}" cy="${y + 14}" r="9"/><text x="${x + w - 14}" y="${y + 18}" text-anchor="middle">${c}</text></g></g>`;
  };
  const edge = ([d, kind, into, dashed]) => `<path class="om-edge ${kind}${into && nodeTone[into]?.tone === 'active' ? ' active' : ''}${dashed ? ' dashed' : ''}" d="${d}" marker-end="url(#om-${kind})"/>`;
  const groups = OM_GROUPS.map(([label, x, w]) => `<g class="om-group"><rect x="${x}" y="4" width="${w}" height="262" rx="10"/><text x="${x + 16}" y="21">${label}</text><line x1="${x}" y1="28" x2="${x + w}" y2="28"/></g>`).join('');
  const desc = Object.entries(m.places).map(([name, p]) => `${name}: ${p.count || 'нет запусков'}`).join('; ');
  const total = m.working + m.blocked + m.awaiting;
  const bar = `<div class="om-status"><span class="ok"><b>${m.working}</b> в работе</span><span class="err"><b>${m.blocked}</b> заблокировано</span><span class="warn"><b>${m.awaiting}</b> ждёт</span><span>${total} ${plural(total, 'задача', 'задачи', 'задач')} в конвейере</span><span class="om-live">${m.steps.length ? 'живой шаг: ' + esc(m.steps.join('; ')) : 'живого шага нет'}</span></div>`;
  return `<section class="panel om-panel" aria-label="Схема пайплайна оркестрации"><div class="ph"><h2 title="сгруппированный поток · текущие задачи в узлах">Пайплайн</h2>${bar}</div><svg class="om" viewBox="0 0 1200 270" role="img" aria-label="Схема ролей оркестрации. ${esc(desc)}"><defs>${['flow', 'back', 'gate'].map((k) => `<marker id="om-${k}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" class="om-mk ${k}"/></marker>`).join('')}</defs>${groups}${OM_EDGES.map(edge).join('')}${OM_NODES.map(node).join('')}</svg></section>`;
}

/* Предустановка для снимков и ревью: ?orchtab=map|flow|quality|runtime|container|gates. */
(() => { const t = new URLSearchParams(location.search).get('orchtab'); if (t) S.orch.tab = t; })();
