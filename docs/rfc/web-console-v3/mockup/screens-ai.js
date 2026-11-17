/* Настройки: рекомендации консоли и ИИ-подсказки (демо). Поведение повторяет мастер настройки реальной консоли:
   ИИ работает через уже авторизованный CLI, запрос уходит только по кнопке, проверка CLI модель не вызывает,
   в запрос попадает короткое описание параметра, ответ проверяется как значение этого параметра и применяется только к черновику. */
const AI_PROV = [['codex', 'Codex CLI'], ['claude', 'Claude Code CLI']];
const AI_FALLBACK = ' Обычные подсказки мастера остаются доступны.';
const AI_NOTE = 'ИИ-подсказки используют существующую авторизацию CLI; запрос запускается только по кнопке, проверка CLI модель не вызывает.';
/* Демо-окружение: Codex авторизован, Claude Code нет — так виден и успешный путь, и деградация. */
const AI_ENV = {
  codex: { ok: true, text: 'Готов к запросу; сеть и лимит проверяются при запросе' },
  claude: { ok: false, text: 'Нет действующей авторизации Claude Code CLI.' + AI_FALLBACK },
};
const CFG_ADVICE = {
  name: {
    rec: { value: 'claude-agent-harness', why: 'Совпадает с именем каталога репозитория: под ним проект виден в заголовках и отчётах.' },
    ai: { value: 'claude-agent-harness', why: 'Имя каталога и репозитория уже совпадают, поэтому отдельное короткое имя только добавит путаницы в отчётах.', impact: 'Имя попадает в заголовки консоли и отчёты. На запуски и публикацию не влияет.', comparison: [['claude-agent-harness', 'Совпадает с репозиторием; длиннее в заголовках.'], ['harness', 'Короче, но совпадает с названием продукта и путает отчёты.']] },
  },
  tracker: {
    rec: { value: 'github', why: 'Удалённый origin указывает на github.com: задачи и PR создаются через gh.' },
    ai: { value: 'github', why: 'По признакам проекта (origin на github.com, каталог .github/workflows) трекером служит GitHub.', impact: 'Определяет, откуда берутся задачи и куда публикуется PR. Значение local отключит публикацию.', comparison: [['github', 'Задачи, PR и CI через gh; нужна авторизация gh.'], ['gitlab', 'MR через glab; признаков GitLab в проекте нет.'], ['local', 'Задачи в файлах; публикации PR и MR нет.']] },
  },
  stale: {
    rec: { value: 300, why: 'Полный QA может молчать дольше двух минут: при 120 с активный запуск ложно помечается «нет сигнала».' },
    ai: { value: 300, why: 'У проекта найден полный QA (qa_command_detected). Он минутами не пишет в журнал, поэтому порог в 2 минуты даёт ложные срабатывания.', impact: 'Запуск без событий дольше порога помечается устаревшим и попадает в «Требует внимания». Больший порог откладывает это предупреждение.', comparison: [['120 с', 'Быстро замечает зависание, но срабатывает ложно на длинном QA.'], ['300 с', 'Хватает для типичного полного QA; зависание видно через 5 минут.'], ['600 с', 'Ложных срабатываний почти нет; зависание видно только через 10 минут.']] },
  },
  qa_cmd: {
    rec: { value: 'make verify', why: 'В корне найден Makefile с целью verify; команда уже совпадает с найденной.' },
    ai: { value: 'make verify', why: 'Саму команду модель не получает: совет опирается на признак qa_command_detected и тип проекта. Текущее значение стоит проверить самостоятельно.', impact: 'Команду запускает гейт QA перед публикацией. Здесь меняется только текст настройки, проверка не запускается.', comparison: [['make verify', 'Один вход для всех проверок; нужна цель verify в Makefile.'], ['Отдельные команды тестов', 'Быстрее локально, но пропускают общие проверки.']] },
  },
  parallel: {
    rec: { value: 2, why: 'Больше двух worker без контейнеров конфликтуют за общий каталог: безопасное значение — 2.' },
    ai: { value: 4, why: 'В проекте много независимых задач, поэтому 4 worker быстрее разберут очередь.', impact: 'Больше worker — выше нагрузка на диск и риск конфликтов между ветками.', incompatible: 'Значение 4 требует функции «Контейнеры», а она выключена.', comparison: [['2', 'Безопасно без контейнеров.'], ['4', 'Быстрее очередь; нужны контейнеры.']] },
  },
};

const aiFmt = (f, v) => esc(String(v)) + (f?.unit ? ' ' + esc(f.unit) : '');
const aiField = () => CFG_FIELDS.find((x) => x.id === cfgAi().param);
function cfgAi() { const c = cfgModel(); return c.ai ||= { prov: 'none', status: null, phase: 'idle', adv: null, msg: '', detail: '', token: 0, param: null, ctxOpen: false }; }
function cfgSelected(group) { const c = cfgModel(); return group.fields.find((f) => f.id === c.param) || group.fields.find((f) => !f.readonly) || group.fields[0]; }

function cfgSetField(f, value) {
  const doc = cfgParse().docs[f.doc]; if (!doc) return false;
  let parent = doc;
  for (const key of f.path.slice(0, -1)) { if (!parent[key] || typeof parent[key] !== 'object' || Array.isArray(parent[key])) parent[key] = {}; parent = parent[key]; }
  parent[f.path.at(-1)] = f.type === 'number' ? Number(value) : value;
  S.cfg.texts[f.doc] = JSON.stringify(doc, null, 2);
  return true;
}
function cfgFieldError(f, v) {
  if (f.type === 'number') return Number.isInteger(Number(v)) && Number(v) >= 1 ? '' : 'ожидается целое число больше нуля';
  if (f.type === 'select') return f.options.includes(v) ? '' : 'значение вне списка: ' + f.options.join(', ');
  return String(v).trim() ? '' : 'пустое значение';
}
/* Всё, что уходит в запрос: короткое описание параметра. Команды, пути, имена моделей и текущие значения не передаются. */
function cfgAiContext(f, value) {
  const opts = f.options || [], rec = CFG_ADVICE[f.id].rec.value;
  return { file: cfgName(f.doc), parameter: f.path.join('.'), type: f.type === 'select' ? 'enum' : f.type === 'number' ? 'integer' : 'string', choices: opts.slice(0, 4), more_choices: Math.max(0, opts.length - 4), description: f.help, platform: 'linux', project_markers: ['pyproject.toml', 'Cargo.toml', 'Makefile'], qa_command_detected: true, value_already_set: value !== undefined, console_recommendation: opts.includes(rec) ? rec : null };
}

function cfgPickBtn(f, sel) {
  const on = sel?.id === f.id;
  return `<button type="button" class="btn sm ghost cfg-pick" data-act="cfg-pick:${f.id}" aria-pressed="${on}" title="Показать рекомендацию и ИИ-подсказки для параметра">${ic('spark', 'sm')}Подсказки</button>`;
}
function cfgRecRow(f, value) {
  const a = CFG_ADVICE[f.id]; if (!a || f.readonly) return '';
  const rec = a.rec.value, same = String(value) === String(rec);
  return `<div class="cfg-rec${same ? ' ok' : ''}">${ic(same ? 'check' : 'sliders', 'sm')}<span>${same ? 'Совпадает с рекомендацией' : 'Рекомендуется'} <code>${aiFmt(f, rec)}</code></span>${same ? '' : btn('Принять', 'cfg-rec-accept:' + f.id, { cls: 'sm ghost', dis: !cfgCanEdit() })}</div>`;
}

function aiProvRow(ai, key, label, text, state) {
  const off = state === 'bad' || ai.phase === 'checking' || ai.phase === 'asking';
  return `<button type="button" role="radio" class="ai-p" aria-checked="${ai.prov === key}" data-act="cfg-ai-prov:${key}" ${off ? 'disabled' : ''}><i class="ai-dot ${state}"></i><span><b>${label}</b>${text ? `<small>${esc(text)}</small>` : ''}</span></button>`;
}
function aiOutput(ai, f, cur) {
  const adv = ai.adv && ai.adv.fieldId === f.id ? ai.adv : null;
  if (ai.phase === 'checking') return `<div class="ai-busy">${ic('refresh', 'sm')}<span>Проверяется наличие, версия и текущая авторизация CLI…</span></div>`;
  if (ai.phase === 'asking') return `<div class="ai-busy">${ic('spark', 'sm')}<span>Запрашивается рекомендация через текущую авторизацию CLI… Лимит ожидания 90 с.</span></div>`;
  if (ai.phase === 'fail') return `<div class="ai-fail">${ic('alert', 'sm')}<span>${esc(ai.msg)}${ai.detail ? `<small>${esc(ai.detail)}</small>` : ''}</span></div>`;
  if (ai.phase === 'applied') return `<div class="ai-okmsg">${ic('check', 'sm')}<span>${esc(ai.msg)}</span></div>`;
  if (adv) {
    const same = String(cur) === String(adv.value), prov = AI_PROV.find(([k]) => k === adv.prov)?.[1];
    return `<div class="ai-adv"><div class="ai-adv-head"><span class="tag">Предложено</span><code>${aiFmt(f, adv.value)}</code>${same ? '<span class="rep-caption">совпадает с текущим</span>' : `<span class="rep-caption">сейчас <code>${aiFmt(f, cur ?? '—')}</code></span>`}</div><dl><dt>Почему</dt><dd>${esc(adv.why)}</dd><dt>Влияние</dt><dd>${esc(adv.impact)}</dd></dl><ul class="ai-cmp" aria-label="Сравнение вариантов">${adv.comparison.map(([o, t]) => `<li${String(o).startsWith(String(adv.value)) ? ' class="pick"' : ''}><b>${esc(o)}</b><span>${esc(t)}</span></li>`).join('')}</ul><p class="ai-src">${prov} · ответ проверен как значение этого параметра · файлы не изменены</p></div>`;
  }
  return `<p>${esc(ai.msg || 'Запрос к модели ещё не выполнялся.')}</p>`;
}
function cfgAiPanel(f, parsed) {
  if (!f) return '';
  const ai = cfgAi();
  if (ai.param !== f.id) Object.assign(ai, { param: f.id, token: ai.token + 1, phase: 'idle', adv: null, msg: '', detail: '' });
  const caption = f.doc ? `${cfgName(f.doc)} · ${f.path.join('.')}` : f.label;
  const head = `<div class="ph"><h2>${ic('spark', 'sm')}ИИ-подсказки</h2><span class="rep-caption mono" title="${esc(caption)}">${esc(caption)}</span></div>`;
  const a = CFG_ADVICE[f.id];
  if (f.readonly || !a) return `<aside class="panel cfg-ai" aria-label="ИИ-подсказки">${head}<div class="ai-sec"><p>Параметр доступен только для просмотра, поэтому рекомендации и запрос к ИИ для него не предлагаются. Значение берётся из снимка файла.</p></div></aside>`;
  const can = cfgCanEdit(), busy = ai.phase === 'checking' || ai.phase === 'asking', cur = cfgValue(f, parsed);
  const same = String(cur) === String(a.rec.value), adv = ai.adv && ai.adv.fieldId === f.id;
  const st = ai.status;
  const provs = aiProvRow(ai, 'none', 'Без ИИ — обычные подсказки', '', 'ok') + AI_PROV.map(([k, label]) => aiProvRow(ai, k, label, st ? st[k].text : 'доступность ещё не проверена', st ? (st[k].ok ? 'ok' : 'bad') : '')).join('');
  const reason = !can ? 'Нет связи с сервером или проект не выбран: запрос к ИИ недоступен.' : ai.prov === 'none' ? 'Выберите CLI, чтобы спросить ИИ. Без него работают обычные подсказки.' : !adv ? '«Принять совет ИИ»: сначала получите совет: «Спросить ИИ».' : '';
  return `<aside class="panel cfg-ai" aria-label="ИИ-подсказки">${head}
  <section class="ai-sec ai-rec"><div class="ai-sech"><h3>Рекомендация консоли</h3>${btn('Принять рекомендацию', 'cfg-rec-accept:' + f.id, { cls: 'sm', dis: !can || same })}</div><div class="ai-val"><code>${aiFmt(f, a.rec.value)}</code><span class="tag">${same ? 'уже выбрано' : 'сейчас: ' + aiFmt(f, cur ?? '—')}</span></div><p><b>Почему:</b> ${esc(a.rec.why)}</p></section>
  <section class="ai-sec ai-ask"><h3>Совет ИИ</h3><div class="ai-cols"><div class="ai-left"><p>${AI_NOTE}</p><div class="ai-prov" role="radiogroup" aria-label="Источник подсказок">${provs}</div>
  <div class="ai-actions">${btn('Проверить CLI', 'cfg-ai-check', { cls: 'sm', icon: 'refresh', dis: !can || busy })}${ai.phase === 'asking' ? btn('Отменить запрос', 'cfg-ai-cancel', { cls: 'sm', icon: 'x' }) : btn('Спросить ИИ', 'cfg-ai-ask', { cls: 'sm', icon: 'spark', dis: !can || busy || ai.prov === 'none' })}${btn('Принять совет ИИ', 'cfg-ai-accept', { cls: 'sm primary', icon: 'check', dis: !can || !adv })}</div>
  ${reason ? `<p class="ai-reason">${esc(reason)}</p>` : ''}</div><div class="ai-right"><div class="ai-out" role="status" aria-live="polite">${aiOutput(ai, f, cur)}</div>
  <details class="ai-ctx" data-ai-ctx ${ai.ctxOpen ? 'open' : ''}><summary>Что уходит в запрос</summary><pre class="mono">${esc(JSON.stringify(cfgAiContext(f, cur), null, 2))}</pre><p>Команды, пути, имена моделей и текущие значения не передаются. Ответ CLI не выполняется как команда и ничего не записывает в файлы.</p></details></div></div></section></aside>`;
}
function cfgAdviceDigest() {
  const parsed = cfgParse(), diff = CFG_FIELDS.filter((f) => CFG_ADVICE[f.id] && parsed.docs[f.doc] && String(cfgValue(f, parsed)) !== String(CFG_ADVICE[f.id].rec.value));
  const rows = diff.map((f) => `<button type="button" class="cfg-digest-row" data-act="cfg-advice-open:${f.id}"><span><b>${f.label}</b><small>сейчас <code>${aiFmt(f, cfgValue(f, parsed))}</code> → рекомендуется <code>${aiFmt(f, CFG_ADVICE[f.id].rec.value)}</code></small></span>${ic('chev', 'sm')}</button>`).join('');
  return `<div class="cfg-digest"><h3>${ic('spark', 'sm')}Советы по настройке</h3>${rows || `<p>Значения совпадают с рекомендациями консоли. По любому параметру можно спросить ИИ.</p>`}<div class="har-actions">${btn(diff.length ? 'Открыть первый совет' : 'Спросить ИИ', 'cfg-advice-open:' + (diff[0]?.id || 'stale'), { cls: 'sm', icon: 'spark' })}</div></div>`;
}

/* Ответ приходит позже запроса: устаревший (другой параметр, отмена, смена экрана) молча отбрасывается. */
function aiLater(ms, fn) {
  const ai = cfgAi(), token = ++ai.token;
  setTimeout(() => { if (cfgAi().token !== token) return; fn(); if (route() === 'configuration') { render(); $('.cfg-ai .ai-out')?.scrollIntoView({ block: 'nearest' }); } }, ms);
}
Object.assign(actions, {
  'cfg-pick': (id) => { const f = CFG_FIELDS.find((x) => x.id === id); if (!f || f.readonly) return; S.cfg.param = id; render(); $(`[data-act="cfg-pick:${id}"]`)?.focus(); },
  'cfg-rec-accept': (id) => {
    const f = CFG_FIELDS.find((x) => x.id === id), a = CFG_ADVICE[id]; if (!f || !a || !cfgCanEdit()) return;
    if (!cfgSetField(f, a.rec.value)) return toast('Файл с ошибкой JSON: сначала исправьте его.');
    render(); toast('Рекомендация принята в черновик');
  },
  'cfg-ai-prov': (key) => { const ai = cfgAi(); if (ai.phase === 'checking' || ai.phase === 'asking' || (ai.status && key !== 'none' && !ai.status[key]?.ok)) return; ai.prov = key; render(); $(`[data-act="cfg-ai-prov:${key}"]`)?.focus(); },
  'cfg-ai-check': () => {
    const ai = cfgAi(); if (!cfgCanEdit() || ai.phase === 'checking' || ai.phase === 'asking') return;
    Object.assign(ai, { phase: 'checking', adv: null, msg: '', detail: '' }); render();
    aiLater(1000, () => { ai.status = { codex: { ...AI_ENV.codex }, claude: { ...AI_ENV.claude } }; if (ai.prov !== 'none' && !ai.status[ai.prov].ok) ai.prov = 'none'; Object.assign(ai, { phase: 'idle', msg: 'Готовность CLI проверена; запрос к модели ещё не выполнялся.' }); });
  },
  'cfg-ai-ask': () => {
    const ai = cfgAi(), f = aiField(); if (!f || !CFG_ADVICE[f.id] || !cfgCanEdit() || ai.prov === 'none' || ai.phase === 'checking' || ai.phase === 'asking') return;
    Object.assign(ai, { phase: 'asking', adv: null, msg: '', detail: '' }); render();
    aiLater(1600, () => {
      const prov = ai.prov, a = CFG_ADVICE[f.id].ai, bad = (msg, detail = '') => Object.assign(ai, { phase: 'fail', msg, detail });
      if (!AI_ENV[prov].ok) return bad(AI_ENV[prov].text);
      const err = cfgFieldError(f, a.value);
      if (err) return bad('CLI вернул неподходящую рекомендацию: значение не проходит проверку поля (' + err + ').' + AI_FALLBACK);
      if (a.incompatible) return bad('Рекомендация несовместима со связанными параметрами.' + AI_FALLBACK, 'Предложено ' + a.value + '. ' + a.incompatible);
      Object.assign(ai, { phase: 'done', adv: { fieldId: f.id, prov, ...a } });
    });
  },
  'cfg-ai-cancel': () => { const ai = cfgAi(); if (ai.phase !== 'asking') return; ai.token++; Object.assign(ai, { phase: 'idle', adv: null, msg: 'Запрос ИИ отменён.' + AI_FALLBACK }); render(); $('[data-act="cfg-ai-ask"]')?.focus(); },
  'cfg-ai-accept': () => {
    const ai = cfgAi(), f = aiField(); if (!f || !ai.adv || ai.adv.fieldId !== f.id || !cfgCanEdit()) return;
    const same = String(cfgValue(f)) === String(ai.adv.value);
    if (!same && !cfgSetField(f, ai.adv.value)) return toast('Файл с ошибкой JSON: сначала исправьте его.');
    Object.assign(ai, { phase: 'applied', adv: null, msg: same ? 'Совет совпадает с текущим значением: черновик не изменился.' : 'Совет ИИ применён к черновику. Файл проекта не изменён: проверьте значение во вкладке «Изменения».' });
    render(); toast(same ? 'Совет совпадает с текущим значением' : 'Совет ИИ применён к черновику');
  },
  'cfg-advice-open': (id) => { const f = CFG_FIELDS.find((x) => x.id === id); if (!f) return; Object.assign(S.cfg, { tab: 'wizard', group: f.group, param: id, q: '', changedOnly: false }); render(); },
});
document.addEventListener('toggle', (e) => { if (e.target.matches?.('[data-ai-ctx]')) cfgAi().ctxOpen = e.target.open; }, true);
/* Предустановки для снимков и ревью: ?cfgai=done | fail | asking | applied открывает «Параметры» в нужном состоянии. */
(() => {
  const q = new URLSearchParams(location.search), p = q.get('cfgai'); if (!p) return;
  if (q.get('theme') === 'light') try { localStorage.setItem('theme', 'light'); } catch { /* без хранилища остаётся тёмная */ }
  const ai = cfgAi(), f = CFG_FIELDS.find((x) => x.id === (p === 'fail' ? 'parallel' : 'stale'));
  Object.assign(S.cfg, { tab: 'wizard', group: f.group, param: f.id });
  Object.assign(ai, { param: f.id, prov: 'codex', status: { codex: { ...AI_ENV.codex }, claude: { ...AI_ENV.claude } }, phase: p === 'asking' ? 'asking' : p === 'fail' ? 'fail' : p === 'applied' ? 'applied' : 'done' });
  const a = CFG_ADVICE[f.id].ai;
  if (p === 'done') ai.adv = { fieldId: f.id, prov: 'codex', ...a };
  if (p === 'fail') Object.assign(ai, { msg: 'Рекомендация несовместима со связанными параметрами.' + AI_FALLBACK, detail: 'Предложено ' + a.value + '. ' + a.incompatible });
  if (p === 'applied') { cfgSetField(f, a.value); ai.msg = 'Совет ИИ применён к черновику. Файл проекта не изменён: проверьте значение во вкладке «Изменения».'; }
  location.hash = '#/configuration';
})();
