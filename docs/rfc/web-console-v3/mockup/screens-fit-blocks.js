/* Дополнительные блоки, которые занимают свободную высоту на страницах, вписанных в окно, вместо растянутых строк.
   Плитки не выдумывают данных: названия, описания и счётчики берутся из меню (badges), справки (HELP_SECTION_TEXT) и констант справки. */
function fitTile(href, icon, title, meta, text, act) {
  const attrs = act ? `data-act="${act}"` : `href="${href}"`, tag = act ? 'button type="button"' : 'a';
  return `<${tag} class="fit-tile" ${attrs}><span class="fit-tile-i">${ic(icon, 'sm')}</span><span class="fit-tile-t"><b>${title}</b>${meta ? `<em>${meta}</em>` : ''}<small>${text}</small></span>${ic('chev', 'sm')}</${act ? 'button' : 'a'}>`;
}
const fitCols = (n) => (n <= 4 ? n : n % 3 === 0 ? 3 : n % 2 === 0 ? 3 : 4);
const fitBlock = (title, tiles, count) => `<section class="panel fit-fill"><div class="ph"><h2>${title}</h2>${count != null ? `<span class="tag">${count}</span>` : ''}</div><div class="fit-tiles" style="--cols:${fitCols(count || 3)}">${tiles}</div></section>`;
function fitRelated(title, ids) {
  const b = badges(), icons = Object.fromEntries(NAV.flatMap(([, items]) => items.map(([id, , icon]) => [id, icon])));
  return fitBlock(title, ids.map((id) => fitTile('#/' + id, icons[id], TITLES[id], b[id] ? `${b[id][0]}` : '', HELP_SECTION_TEXT[id])).join(''), ids.length);
}
const FIT_HELP_NEXT = {
  start: ['Начало', 'help', 'Схема окна и порядок чтения'],
  sections: ['Разделы', 'flow', 'Что внутри каждого из 13 разделов'],
  keys: ['Клавиши', 'terminal', 'Переходы между разделами и общие сочетания'],
  status: ['Статусы', 'check', 'Значки сессий и проверок'],
  safety: ['Безопасность', 'shield', 'Что консоль не делает без подтверждения'],
  faq: ['Вопросы', 'msg', 'Почему «пропущено» не успех и что такое stale'],
  docs: ['Документация', 'file', 'Команды CLI и файлы с подробностями'],
};
function helpNext(current) {
  const count = { sections: 13, keys: 10, status: HELP_STATUS.length + HELP_CHECKS.length, safety: HELP_SAFETY.reduce((n, [, , r]) => n + r.length, 0), faq: HELP_FAQ.length, docs: HELP_DOCS.length + HARNESS_CMDS.length };
  const ids = Object.keys(FIT_HELP_NEXT).filter((k) => k !== current);
  return fitBlock('Читать дальше', ids.map((k) => fitTile('', FIT_HELP_NEXT[k][1], FIT_HELP_NEXT[k][0], count[k] ?? '', FIT_HELP_NEXT[k][2], 'help-open:' + k)).join(''), ids.length);
}
/* Вставка блока в конец страницы нужной вкладки. */
function fitAppend(screen, pick) {
  const orig = screens[screen];
  screens[screen] = () => { const html = orig(), extra = S.empty ? '' : pick(); return extra ? html.replace(/<\/div>\s*$/, extra + '</div>') : html; };
}
fitAppend('reports', () => ['quality', 'ready', 'evid'].includes(S.rep.tab) ? fitRelated('Связанные разделы', ['publish', 'board', 'agent-activity', 'orchestration']) : '');
fitAppend('harness', () => ['overview', 'runtime', 'adapters', 'cmds'].includes(S.har.tab) ? fitRelated('Связанные разделы', ['diagnostics', 'update-harness', 'open-project', 'orchestration', 'repo-map', 'configuration']) : '');
fitAppend('configuration', () => ['overview', 'changes'].includes(S.cfg.tab) ? fitRelated('Связанные разделы', ['harness', 'diagnostics', 'update-harness', 'open-project', 'orchestration', 'help']) : '');
fitAppend('repo-map', () => ['symbols', 'links'].includes(S.repo.tab) ? fitRelated('Связанные разделы', ['harness', 'configuration', 'diagnostics', 'orchestration']) : '');
