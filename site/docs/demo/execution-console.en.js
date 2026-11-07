// Throwaway, in-memory UI prototype. No filesystem, process or ledger mutations.
const $=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=(name,cls='')=>window.HarnessIcons?window.HarnessIcons.get(name,cls):'';
const navGroups=[
  {label:'Overview',items:[
    {id:'home',label:'Home',icon:'home'},
    {id:'diagnostics',label:'Diagnostics',icon:'pulse',count:'2',countClass:'err'},
    {id:'update-harness',label:'Update',icon:'refresh',count:'1',countClass:'warn'},
    {id:'open-project',label:'Project',icon:'folder'},
  ]},
  {label:'Work',items:[
    {id:'board',label:'Task board',icon:'board'},
    {id:'agent-activity',label:'Activity',icon:'activity'},
    {id:'orchestration',label:'Orchestration',icon:'orchestration'},
    {id:'reports',label:'Reports',icon:'reports'},
    {id:'publish',label:'Publish',icon:'github'},
  ]},
  {label:'Context',items:[
    {id:'harness',label:'Harness',icon:'harness',count:'1',countClass:'warn'},
    {id:'repo-map',label:'Repo Map',icon:'map',count:'full',countClass:'full'},
    {id:'configuration',label:'Settings',icon:'settings'},
    {id:'help',label:'Help',icon:'help'},
  ]},
];
const hiddenRoutes=['recovery','container-route','navigation'];
const routes=new Set([...navGroups.flatMap(g=>g.items.map(i=>i.id)),...hiddenRoutes]);
let route='home',project='claude-agent-harness',branch='integration/harness-runtime-reliability',configText='{\n  "name": "claude-agent-harness",\n  "runtime": "native",\n  "stale_seconds": 120\n}',versions=[],readerText='',actor='all',file='project.json',homeFilter='all',healthMode='offline',diagFilter='all',diagQuery='',diagSelected='skills.drift',updateMode='normal',updateSelected='implement/SKILL.md',seedSelected={},projectSelectedId='harness',projectPath='',projectPathStatus='',projectManual=null,projectCapability='workflow',workFilter='all',workRole='all',workSelected='#716',workTab='overview',workUpdatedAt=new Date(),reportFilter='all',reportStatus='all',reportQuery='',reportSelected='r-716-qa',reportTab='list',reportUpdatedAt=new Date(),orchRole='all',orchStatus='all',orchUpdatedAt=new Date(),orchTab='map',harnessTab='overview',harnessUpdatedAt=new Date(),repoTab='overview',repoModule='all',repoKind='all',repoQuery='',repoSelected='runtime::serve',repoExpanded={'tests':false},repoFile='utils',repoUpdatedAt=new Date(),settingsTab='overview',settingsParamIndex=5,settingsAiAdvice='',settingsCheckedAt=new Date(),helpTab='start',publishTab='overview',connectionState='connected',boardSpecId=862,boardQuery='',boardPriorityFilter='all',boardOnlyFree=false,boardDemo='ok',boardSelected=912,boardTab='context',boardSnapshotAt=new Date(),publishCheckedAt=new Date(),updateCheckedAt=new Date(),checkedAt=new Date();
const panel=(title,body,extra='')=>`<section class="panel"><div class="panel-head"><h2>${title}</h2>${extra}</div>${body}</section>`;
const body=s=>`<div class="body">${s}</div>`;
const btn=(name,action,cls='')=>`<button class="${cls}" data-action="${action}">${name}</button>`;
const row=(name,description,status='',cls='')=>`<div class="row"><div><b>${name}</b><small>${description}</small></div><span class="status ${cls}">${status}</span></div>`;
const note=s=>`<div class="note">${s}</div>`;
function title(name,sub){return `<div class="page-title"><div><h1>${name}</h1><p>${sub}</p></div><a href="#home">← Home</a></div>`}
function toast(text){const node=$('#toast');node.textContent=text;node.classList.add('on');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('on'),4200)}
function reader(title,text){readerText=text;$('#reader-title').textContent=title;$('#reader-search').value='';$('#reader-output').textContent=text;$('#reader-status').textContent='Demo data';$('#reader').showModal()}
const sources={diff:'--- project/implement/SKILL.md\n+++ package/implement/SKILL.md\n@@ language contract @@\n- Record workflow output\n+ Record executable evidence\n\nCONFLICT: local changes require review.\nNo files were modified.',health:'DEMO · harness health --offline\n[ok] Git repository\n[ok] harness.lock\n[warn] Skill drift\n[error] Integration configuration\n[skipped] Online permissions\nSkipped checks do not count as passed.',report:'DEMO · QA report\nCandidate: demo-candidate (not a real commit SHA)\nResult: requires attention\nEvidence: policy boundary check failed\nDecision: human review required\nNo publication performed.',log:'DEMO · worker log\nDispatch accepted\nEnvironment checked\nSandbox policy evaluated\nResult recorded\nProcess was not actually launched.'};
function graph(){return `<svg class="diagram" viewBox="0 0 600 180" role="group" aria-label="Demo links for coordinator, developer, code-review, and QA"><path class="edge" d="M130 85H190M310 85H370M490 85H540M430 105V150H250V105"/><a href="#agent-activity"><rect class="node" x="10" y="65" width="120" height="40"/><text class="node-label" x="22" y="89">coordinator</text></a><a href="#agent-activity"><rect class="node" x="190" y="65" width="120" height="40"/><text class="node-label" x="210" y="89">developer</text></a><a href="#reports"><rect class="node" x="370" y="65" width="120" height="40"/><text class="node-label" x="380" y="89">code-review</text></a><text class="node-label" x="539" y="90">QA</text><text class="node-label" x="260" y="167">↶ rework</text></svg>`}
function parseRoute(){
  const raw=decodeURIComponent(location.hash.slice(1)||'home');
  const [path,qs]=raw.split('?');
  const params=new URLSearchParams(qs||'');
  return {route:routes.has(path)?path:'home',role:params.get('role'),state:params.get('state')};
}
function navHref(item){
  return `#${item.id}${item.query?'?'+new URLSearchParams(item.query).toString():''}`;
}
function navActive(item,filter){
  if(item.id!==route)return false;
  if(!item.query)return !filter.role&&!filter.state;
  return Object.entries(item.query).every(([key,value])=>filter[key]===value);
}
function renderNav(filter){
  return navGroups.map(group=>`<div class="nav-group"><div class="nav-group-label">${esc(group.label)}</div>${group.items.map(item=>{
    const active=navActive(item,filter);
    const count=item.count?`<span class="badge-count ${item.countClass||''}">${esc(item.count)}</span>`:'';
    return `<a href="${navHref(item)}" title="${esc(item.label)}" ${active?'aria-current="page"':''}><span class="nav-icon ${item.status?`nav-${item.status}`:''}">${icon(item.icon)}</span><span class="nav-label">${esc(item.label)}</span>${count}</a>`;
  }).join('')}</div>`).join('');
}
function setNavCollapsed(collapsed){
  document.body.classList.toggle('nav-collapsed',collapsed);
  const button=$('#nav-collapse');
  if(button){
    button.setAttribute('aria-expanded',String(!collapsed));
    button.setAttribute('aria-label',collapsed?'Expand menu':'Collapse menu');
    button.title=collapsed?'Expand menu':'Collapse menu';
  }
  try{localStorage.setItem('harness-nav-collapsed',collapsed?'1':'0')}catch{}
}
function closeNav(){
  document.body.classList.remove('nav-open');
  const toggle=$('#menu-toggle');if(toggle)toggle.setAttribute('aria-expanded','false');
  const scrim=$('#nav-scrim');if(scrim)scrim.hidden=true;
}
function openNav(){
  document.body.classList.add('nav-open');
  const toggle=$('#menu-toggle');if(toggle)toggle.setAttribute('aria-expanded','true');
  const scrim=$('#nav-scrim');if(scrim)scrim.hidden=false;
}
function updateFoot(parsed){
  const found=navGroups.flatMap(g=>g.items).find(i=>i.id===parsed.route);
  const hiddenLabels={recovery:'Recovery', 'container-route':'Containers', publish:'Publish', navigation:'Navigation map'};
  const label=found?found.label:(hiddenLabels[parsed.route]||parsed.route);
  const extra=parsed.role?` · role ${parsed.role}`:parsed.state?` · ${parsed.state}`:'';
  const foot=$('#foot-status');if(foot)foot.textContent=`2.0.0 · runtime-store · ${label}${extra}`;
  document.title=`Harness Console · ${label}`;
}

const CONNECTION_LABELS={connected:'online',reconnecting:'reconnect',offline:'no server',error:'error',empty:'empty'};
const CONNECTION_ORDER=['connected','reconnecting','offline','error','empty'];
function updateConnectionUI(){
  const chip=$('#connection-state');const banner=$('#connection-banner');
  const label=CONNECTION_LABELS[connectionState]||connectionState;
  if(chip){chip.className=`conn-chip ${connectionState}`;const span=chip.querySelector('span');if(span)span.textContent=label;chip.setAttribute('aria-label',`Connection state: ${label}. Toggle demo state`)}
  document.body.dataset.connection=connectionState;
  if(banner){
    if(connectionState==='reconnecting'){
      banner.hidden=false;
      banner.innerHTML=`<span class="conn-spinner"></span><div><b>Reconnecting to Harness Runtime</b><small>attempt 2 · next in 3 s · data may be stale</small></div><button class="btn" type="button" data-connection-retry>Retry now</button>`;
    }else banner.hidden=true;
  }
}
function connectionPage(kind){
  const pages={
    offline:{icon:'pulse',eyebrow:'CONNECTION · NO SERVER',title:'No connection to Harness Runtime',text:'The server is not responding. The last snapshot may be stale; actions and approvals are unavailable until the connection is restored.',facts:[['endpoint','ipc://harness-runtime'],['last snapshot','10:41'],['attempt','2']],action:'Retry connection'},
    error:{icon:'warning',eyebrow:'LOADING · ERROR',title:'Failed to load data',text:'A response arrived, but the snapshot failed the integrity check. Old data must not be shown as current.',facts:[['read','error'],['reason','integrity check'],['last snapshot','10:41']],action:'Reload'},
    empty:{icon:'reports',eyebrow:'DATA · EMPTY',title:'No data yet',text:'The connection is established, but the server returned no sessions or reports. This is not a load error.',facts:[['connection','online'],['sessions','0'],['reports','0']],action:'Refresh'}
  };
  const x=pages[kind]||pages.offline;
  return `<section class="panel connection-page ${kind}"><div class="connection-page-icon">${icon(x.icon)}</div><span class="eyebrow">${esc(x.eyebrow)}</span><h1>${esc(x.title)}</h1><p>${esc(x.text)}</p><div class="connection-facts">${x.facts.map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div><div class="connection-page-actions"><button class="btn primary" type="button" data-connection-retry>${esc(x.action)}</button><button class="btn" type="button" data-connection-cycle>Next state</button><a class="btn" href="#help">${icon('help')} Help</a></div><small class="connection-demo-note">Demo state; the network is not used.</small></section>`;
}

function render(){
  const parsed=parseRoute();route=parsed.route;
  const filter={role:parsed.role,state:parsed.state};
  $('#navigation').innerHTML=renderNav(filter);
  $('#project').textContent=project;
  const branchNode=$('#branch');if(branchNode)branchNode.textContent='⑂ '+branch;
  const main=$('#content');
  main.className='';
  updateConnectionUI();
  if(connectionState==='offline'||connectionState==='error'||connectionState==='empty'){
    main.innerHTML=connectionPage(connectionState);closeNav();updateFoot(parsed);return;
  }
  if(route==='home'){main.innerHTML=homePage();bindHome();closeNav();updateFoot(parsed);return}
  if(route==='board'){main.className='board-main';main.innerHTML=boardPage();bindBoard();closeNav();updateFoot(parsed);return}
  if(route==='navigation'){main.innerHTML=navMapPage();closeNav();updateFoot(parsed);return}
  if(route==='diagnostics'){
    main.innerHTML=diagPage();bindDiag();closeNav();updateFoot(parsed);return;
  }
  if(route==='update-harness'){
    main.innerHTML=updatePage();closeNav();updateFoot(parsed);return;
  }
  if(route==='open-project'){
    main.innerHTML=projectHubPage();closeNav();updateFoot(parsed);return;
  }
  if(route==='agent-activity'){
    main.innerHTML=workPage();bindWork();closeNav();updateFoot(parsed);return;
  }
  if(route==='reports'){
    main.innerHTML=reportsPage();bindReports();closeNav();updateFoot(parsed);return;
  }
  if(route==='harness'){
    main.innerHTML=harnessPage();bindHarness();closeNav();updateFoot(parsed);return;
  }
  if(route==='repo-map'){
    main.innerHTML=repoPage();bindRepo();closeNav();updateFoot(parsed);return;
  }
  if(route==='configuration'){
    main.innerHTML=settingsPage();bindSettings();closeNav();updateFoot(parsed);return;
  }
  if(route==='help'){
    main.innerHTML=helpPage();bindHelp();closeNav();updateFoot(parsed);return;
  }
  if(route==='publish'){
    main.innerHTML=publishPage();bindPublish();closeNav();updateFoot(parsed);return;
  }
  if(route==='orchestration'){
    main.innerHTML=orchPage();bindOrch();closeNav();updateFoot(parsed);return;
  }
  let html='';


if(route==='recovery')html=title('Recovery','The run outcome is unknown: examine the available facts first.')+note('An unknown outcome does not count as success. The prototype provides only demo evidence.')+'<div class="grid">'+panel('State',row('d-dev','Latest ledger entry','working','active')+row('Process','No real check was performed','unknown','warn')+row('Result','No confirmed completion','unknown','warn'))+panel('Safe review',body('<div class="actions">'+btn('View log','log')+btn('Show evidence','report')+'</div><p class="muted">The decision to re-run is made after checking the facts.</p><a href="#home">Back to the snapshot →</a>'))+'</div>';
if(route==='container-route')html=title('Container run','Rootless Podman · environment, stages, and evidence.')+'<div class="grid">'+panel('Route',`<ol class="timeline"><li><b>1 · Environment check</b><small>Podman · SELinux · cgroups v2</small></li><li><b>2 · Sandbox setup</b><small>Mount and policy check</small></li><li><b>3 · Dispatch worker</b><small>Runs only after confirmation</small></li><li><b>4 · Verification</b><small>Saving the result and evidence</small></li></ol>`)+panel('Environment facts',body('<dl class="fields"><dt>Podman</dt><dd>Not checked</dd><dt>SELinux</dt><dd>Not checked</dd><dt>Cgroups</dt><dd>Not checked</dd></dl><div class="actions">'+btn('Host facts example','host-facts')+btn('Log example','log')+'</div><p class="muted">This mockup does not query the user\'s host.</p>'))+'</div>';
main.innerHTML=html;if(route==='agent-activity'){actor='all';renderEvents()}if(route==='reports')renderReports('');closeNav();updateFoot(parsed)}
function checks(errors){return [['Git repository','Repository available','ok'],['Harness files','Drift found','warn'],['Integrations','Setup required','err'],['Online permissions','Not checked','warn']].filter((r,i)=>!errors||i===1||i===2).map(r=>row(r[0],r[1],r[2]==='ok'?'passed':r[2]==='err'?'error':'attention',r[2])).join('')}
const events=[['main','Dispatch accepted','Orchestration started observing'],['main','Reading files','Web console mockups and contract'],['standards','Checks standards','Project rules'],['spec','Result received','Demo note']];let added=0;
function renderEvents(){$('#events').innerHTML=events.filter(e=>actor==='all'||actor===e[0]).map((e,i)=>`<li><span class="event-time">demo #${i+1}</span><b>${e[1]}</b><small>${e[0]} · ${e[2]}</small></li>`).join('')||'<li>No events for the executor</li>'}
function renderReports(q){const reports=[['QA · b-closed','Needs attention','report'],['Code-review · d-review','Result received','report'],['Health · demo','2 problems','health']];$('#report-list').innerHTML=reports.filter(r=>(r[0]+' '+r[1]).toLowerCase().includes(q.toLowerCase())).map(r=>`<div class="row"><div><b>${r[0]}</b><small>${r[1]}</small></div>${btn('Open',r[2])}</div>`).join('')||body('<span class="muted">No matches</span>')}
function renderSymbols(q){$('#symbols').innerHTML=['runtime::serve','policy::evaluate','ledger::snapshot'].filter(s=>s.includes(q.toLowerCase())).map(s=>row(s,'Demo symbol','Rust','active')).join('')||'<p class="muted">No matches</p>'}
const configs={
  'project.json': JSON.stringify({name:'claude-agent-harness',runtime:'native',stale_seconds:120,approval:'manual',capability:'backend-orchestration'},null,2),
  'orchestration.json': JSON.stringify({roles:['architect','developer','review','qa'],retry_policy:{max_developer_retries:2,max_infrastructure_retries:1},attention_policy:{retry_queue_seconds:900},qa_lane:{stale_seconds:7200},dispatch:{wait_timeout_seconds:60,poll_interval_seconds:5}},null,2)
};function renderVersions(){const node=$('#versions');if(!node)return;node.innerHTML=versions.length?versions.map((v,i)=>`<div class="row"><div><b>${esc(v.file)}</b><small>Demo version ${i+1}</small></div><button data-restore="${i}">Restore</button></div>`).join(''):body('<span class="muted">No versions yet</span>')}
/* Draft data for the next step (Home). The navigation map is rendered while the menu is approved. */
const HOME={
  health:{ok:42,warn:1,fail:2,skipped:11},
  areas:[
    ['Runtime','runtime',5,0,0,1],['Store','store',4,0,0,0],['Skills','skills',6,0,1,0],
    ['Hooks','shield',2,0,1,0],['Environment','terminal',20,0,0,3],['Repo Map','map',2,0,0,0],
    ['Memory','memory',1,1,0,0],['Tracker','github',2,0,0,7]
  ],
  store:{authority:'runtime-store',schema:6,generation:36,audit:306,operations:170,artifacts:222,cutover:'27.10.2026',features:7},
  skills:{installed:32,managed:259,capability:1,drift:1,vendor:18,firstParty:12,project:2},
  repoMap:{tier:'full',files:1284,edges:3912,tokens:184000},
  memory:{documents:0,sources:['adr','glossary'],topK:5,maxTokens:1000},
  checks:[
    {id:'skills.drift',area:'Skills',status:'fail',title:'The skills snapshot has discrepancies',detail:'The managed snapshot differs from the installed package. harness diff will show the files; update will restore the snapshot.',href:'#diagnostics',checked:'32 skills · 259 managed files · 1 drift',why:'Managed snapshot drift breaks reproducibility between machines and makes skill verification ambiguous.',fix:'Review the diff and apply the snapshot. Do not overwrite local edits before a decision.',action:'link',actionLabel:'Open update',actionHref:'#update-harness',command:'harness update',source:'harness diff + harness update'},
    {id:'hooks.policy',area:'Hooks',status:'fail',title:'Standard profile: effective policy is not written',detail:'No .harness/hook-policy.json; codex 6/8 critical hooks, Claude 9/9. An update is needed after review.',href:'#diagnostics',checked:'No .harness/hook-policy.json · codex 6/8 · Claude 9/9',why:'Without an effective policy, hooks may differ between Codex and Claude; critical checks are not guaranteed.',fix:'Review first, then update. The policy must be written to the project.',action:'link',actionLabel:'Open update',actionHref:'#update-harness',command:'harness update',source:'harness health .'},
    {id:'memory.index',area:'Memory',status:'warn',title:'Memory index is missing',detail:'FTS5 works without a model; the vector slice is not connected. Rebuild the index from the main checkout.',href:'#repo-map',checked:'FTS5 · 0 documents · sources adr, glossary',why:'Without an index, memory search is not reproducible; answers rely on random files.',fix:'Rebuild the index in the main checkout; do not include working copies.',action:'toast',actionLabel:'Rebuild the index',command:'harness memory index',source:'harness memory status'},
    {id:'runtime.store',area:'Runtime',status:'ok',title:'Runtime store authority=runtime-store',detail:'schema 6 · generation 36 · audit 306 · cutover 27.10.2026. Python-writer removed.',href:'#harness',checked:'authority runtime-store · schema 6 · generation 36 · audit 306',why:'A single writer and the audit chain are the basis of deterministic 2.0.0 state.',fix:'Do nothing; the Python writer is removed, Rust remains the only writer.',action:'link',actionLabel:'Open Harness',actionHref:'#harness',command:'harness health .',source:'harness health .'},
    {id:'repo.map',area:'Repo Map',status:'ok',title:'Repo Map tier=full',detail:'Offline parser bundle: Python 3.14, Linux x86_64. Dispatch can use the full map.',href:'#repo-map',checked:'tier full · 1 284 files · 3 912 edges · 184k tokens',why:'Dispatch needs the full map for context; an incomplete map gives wrong routes.',fix:'Do nothing; the offline parser bundle is available.',action:'link',actionLabel:'Open Repo Map',actionHref:'#repo-map',command:'harness repo-map',source:'harness repo-map'},
    {id:'environment',area:'Environment',status:'ok',title:'Environment is consistent',detail:'Python 3.14.8 · Git 2.56.0 · uv 0.12.21 · .harness/.venv is in sync with uv.lock.',href:'#diagnostics',checked:'Python 3.14.8 · Git 2.56.0 · uv 0.12.21 · .venv sync',why:'Different environments break the reproducibility of checks and QA.',fix:'Re-run the check after changes; do not edit the lock by hand.',action:'refresh',actionLabel:'Re-run the check',command:'harness health .',source:'harness health .'},
    {id:'tracker.online',area:'Tracker',status:'skipped',title:'Tracker online checks skipped',detail:'gh auth, permissions, reachability, and labels were not checked. Skipped does not count as success.',href:'#diagnostics',checked:'gh auth · permissions · reachability · labels',why:'Without online checks you cannot claim the tracker is reachable; a skip is not a success.',fix:'Run online checks when network and permissions are available; the mockup uses no network.',action:'online',actionLabel:'Run online',command:'harness health . --online',source:'harness health . --online'}
  ],
  provider:{type:'github',host:'github.com',repo:'PVMalove/agent-harness-next'},
  tasks:[
    {id:'#716',role:'architect',title:'Early worker failure and run observation',status:'Running',tone:'ok',time:'2 min',active:true},
    {id:'#704',role:'developer',title:'Offline worker in rootful Docker',status:'Blocked',tone:'err',time:'14 min'},
    {id:'#555',role:'architect',title:'Full red → green → refactor cycle',status:'Awaiting decision',tone:'warn',time:'31 min'}
  ],
  route:{id:'#716',steps:[
    {name:'Architect',state:'current',label:'Running'},
    {name:'Developer',state:'pending',label:'Not started'},
    {name:'Review',state:'pending',label:'Not started'},
    {name:'QA',state:'pending',label:'Not started'},
    {name:'PR',state:'pending',label:'Not started',icon:'pr'}
  ]}
};
const UPDATE={
  current:'1.5.1',target:'2.0.0',channel:'pre-release',published:'04.11.2026',package:'pvmalove-suite',
  managed:259,skills:32,updateCount:12,createCount:1,conflictCount:1,keepCount:2,
  migration:{from:3,to:6,authority:'runtime-store',generation:36,audit:306,cutover:'27.10.2026'},
  changes:[
    {path:'implement/SKILL.md',kind:'conflict',title:'Changed locally and in the package',explain:'A normal update will stop: overwriting replaces the file with the package version.',diff:`--- project/implement/SKILL.md
+++ after-update/implement/SKILL.md
@@ -41,7 +41,9 @@
 Language contract: agents communicate with each other
-and write free-text protocol evidence in Russian.
+and write free-text protocol/state evidence in English.
+Every completion report addressed to this coordinator is in Russian.
 ## Route
 This is the opt-in backend-orchestration route.`},
    {path:'.harness/hook-policy.json',kind:'create',title:'Effective policy will be created',explain:'Standard profile: codex 6/8, Claude 9/9. The write appears after review.',diff:`--- /dev/null
+++ .harness/hook-policy.json
@@ -0,0 +1,8 @@
+{
+  "profile": "standard",
+  "codex": { "critical": "6/8" },
+  "claude": { "critical": "9/9" }
+}`},
    {path:'skills/first-party/engineering/playbook.md',kind:'update',title:'Managed file will update',explain:'There are no local edits; version 2.0.0 will be applied.',diff:`--- project/skills/first-party/engineering/playbook.md
+++ after update/skills/first-party/engineering/playbook.md
@@ -12,5 +12,6 @@
 ## Update
--Run update from the project root.
+-Run update from the project root after reviewing the diff.
+-Keep uncommitted local edits until the conflict is resolved.`},
    {path:'AGENTS.md',kind:'keep',seed:true,title:'Local changes are preserved',explain:'Seed file. In normal mode it stays yours; in seed mode you can mark it for overwrite.',diff:`--- project/AGENTS.md
+++ after update/AGENTS.md
@@ -3,4 +3,5 @@
 ## Language
--Write final reports in Russian.
+-Write final reports in Russian.
+-Keep protocol evidence in English.`},
    {path:'runtime.db',kind:'migration',title:'Schema 3 → 6',explain:'SQLite WAL, backup before migration; Rust remains the only writer.',diff:`--- runtime.db (schema 3)
+++ runtime.db (schema 6)
@@ runtime-store @@
-user_version = 3
+user_version = 6
+authority = runtime-store
+generation = 36
+audit = 306`},
    {path:'harness/CAPABILITIES.json',kind:'update',title:'The capability catalog will update',explain:'1 capability · backend-orchestration; the contract is verified after the write.',diff:`--- project/harness/CAPABILITIES.json
+++ after update/harness/CAPABILITIES.json
@@ -1,3 +1,4 @@
-{ "version": "1.5.1" }
+{ "version": "2.0.0", "orchestration": "runtime-store" }`},
    {path:'harness/VERSION',kind:'update',title:'Package version: 1.5.1 → 2.0.0',explain:'pre-release; cutover and audit chain are part of the update.',diff:`--- project/harness/VERSION
+++ after update/harness/VERSION
@@ -1 +1 @@
-1.5.1
+2.0.0`},
    {path:'docs/agents/git-workflow.md',kind:'keep',seed:true,title:'Local changes are preserved',explain:'Seed file. In normal mode it stays yours; in seed mode you can mark it for overwrite.',diff:`--- project/docs/agents/git-workflow.md
+++ updated/docs/agents/git-workflow.md
@@ -18,3 +18,4 @@
 ## PR
--Use Related to for integration PRs.
+-Use Related to for integration PRs.
+-Close the issue only after developer confirmation.`}
  ]
};
const SEED_FILES=[
  '.claude/agents/code-review-spec.md',
  '.claude/agents/code-review-standards.md',
  '.claude/agents/pr-composer.md',
  '.claude/agents/test-author.md',
  '.claude/hooks/block-pr-merge.sh',
  '.claude/hooks/block-scratch-outside-docs-tasks.sh',
  '.claude/hooks/hook_response.py',
  '.claude/hooks/pr_commands.py',
  '.claude/hooks/protect_hook_policy.py',
  '.claude/hooks/require-bounded-check.sh',
  '.claude/hooks/test-author-guard.py',
  '.claude/settings.local.json',
  'AGENTS.md',
  'docs/agents/git-workflow.md',
  'README.md'
];
const PROJECTS=[
  {id:'harness',name:'claude-agent-harness',path:'/home/malove/Projects/Code/claude-agent-harness',branch:'integration/harness-runtime-reliability',provider:'github',repo:'PVMalove/agent-harness-next',version:'2.0.0 pre-release',installed:'1.5.1',skills:32,managed:259,drift:1,capability:'backend-orchestration',dirty:2,git:true,config:true,health:{ok:42,warn:1,fail:2,skipped:11}},
  {id:'backend-api',name:'backend-api',path:'/home/malove/Projects/Code/backend-api',branch:'feature/auth',provider:'github',repo:'PVMalove/backend-api',version:'1.5.1',installed:'1.5.1',skills:28,managed:210,drift:0,capability:'backend-orchestration',dirty:4,git:true,config:true,health:{ok:38,warn:0,fail:1,skipped:9}},
  {id:'ops-console',name:'ops-console',path:'/home/malove/Projects/Code/ops-console',branch:'main',provider:'gitlab',repo:'PVMalove/ops-console',version:'1.4.6',installed:'1.4.6',skills:24,managed:188,drift:2,capability:'workflow',dirty:0,git:true,config:false,health:{ok:30,warn:2,fail:0,skipped:12}},
  {id:'docs-site',name:'docs-site',path:'/home/malove/Projects/Code/docs-site',branch:'main',provider:'github',repo:'PVMalove/docs-site',version:'1.5.1',installed:'1.5.1',skills:20,managed:140,drift:0,capability:'docs',dirty:0,git:true,config:true,health:{ok:24,warn:0,fail:0,skipped:6}},
  {id:'payments-api',name:'payments-api',path:'/home/malove/Projects/Code/payments-api',branch:'release/2.1',provider:'github',repo:'PVMalove/payments-api',version:'1.4.6',installed:'1.4.6',skills:26,managed:195,drift:1,capability:'backend-orchestration',dirty:7,git:true,config:true,health:{ok:33,warn:1,fail:0,skipped:6}}
];
const CAPABILITIES=[
  {id:'workflow',label:'Workflow',status:'installed',desc:'Tasks, QA, and manual project.json setup',footer:'Task, QA, and code-review workflow; creates project.json. Needed for the project.json wizard; without orchestration roles.'},
  {id:'base',label:'Base',status:'',desc:'A small set of instructions and skills',footer:'A minimal set of rules and skills without workflow tasks.'},
  {id:'upstream',label:'Upstream',status:'',desc:'Full pinned skill set',footer:'A complete upstream snapshot of skills; suitable for manual selection.'},
  {id:'backend',label:'Backend',status:'',desc:'Workflow and roles; adds orchestration.json',footer:'Workflow and roles; adds orchestration.json. Required for the roles wizard and orchestration.'}
];
const WORK_SESSIONS=[
  {id:'#716',role:'architect',title:'Early worker failure and run observation',status:'running',statusLabel:'Running',tone:'ok',elapsed:'2 min',started:'21:58',branch:'integration/harness-runtime-reliability',current:0,
    steps:[{name:'Architect',state:'current',label:'Running'},{name:'Developer',state:'pending',label:'Not started'},{name:'Review',state:'pending',label:'Not started'},{name:'QA',state:'pending',label:'Not started'},{name:'PR',state:'pending',label:'Not started',icon:'pr'}],
    events:[{time:'21:58:05',role:'architect',text:'Task accepted',detail:'Dispatch passed the context and branch'},{time:'21:58:24',role:'architect',text:'Reading worker logs',detail:'The last 200 lines, without internal reasoning'},{time:'21:59:02',role:'architect',text:'Checks for early failure',detail:'worker exited before readiness'},{time:'22:00:01',role:'architect',text:'Watching continues',detail:'Next step expected'} ]},
  {id:'#704',role:'developer',title:'Offline worker in rootful Docker',status:'blocked',statusLabel:'Blocked',tone:'err',elapsed:'14 min',started:'21:44',branch:'feature/offline-worker',current:1,
    steps:[{name:'Architect',state:'done',label:'Done'},{name:'Developer',state:'current',label:'Blocked'},{name:'Review',state:'pending',label:'Not started'},{name:'QA',state:'pending',label:'Not started'},{name:'PR',state:'pending',label:'Not started',icon:'pr'}],
    events:[{time:'21:44:10',role:'developer',text:'Starting rootful Docker',detail:'Environment check'},{time:'21:45:02',role:'developer',text:'Daemon error',detail:'The container did not start; a mode choice is required'},{time:'21:46:30',role:'architect',text:'Awaiting a decision',detail:'Continuing is impossible without changing the environment'} ]},
  {id:'#555',role:'architect',title:'Full red → green → refactor cycle',status:'awaiting',statusLabel:'Awaiting decision',tone:'warn',elapsed:'31 min',started:'21:28',branch:'feature/refactor-cycle',current:2,
    steps:[{name:'Architect',state:'done',label:'Done'},{name:'Developer',state:'done',label:'Done'},{name:'Review',state:'current',label:'Awaiting decision'},{name:'QA',state:'pending',label:'Not started'},{name:'PR',state:'pending',label:'Not started',icon:'pr'}],
    events:[{time:'21:28:12',role:'architect',text:'Task analysis complete',detail:'Plan and criteria handed to Developer'},{time:'21:32:44',role:'developer',text:'red → green',detail:'Tests pass; refactoring is complete'},{time:'21:36:09',role:'review',text:'Review awaits a decision',detail:'Reviewer selection required'} ]}
];

const WORK_METRICS={
  kpi:{lastEvent:'12 s',silence:1,currentAge:'31 min',retry:1,rate:'3.2 / min'},
  timeline:[
    {id:'#716',total:'2 min',last:'12 s',silent:false,segments:[{label:'Plan',from:0,to:1,tone:'mint'},{label:'Architect',from:1,to:2,tone:'cyan'}]},
    {id:'#704',total:'14 min',last:'4 min',silent:true,segments:[{label:'Plan',from:0,to:2,tone:'mint'},{label:'Architect',from:2,to:7,tone:'cyan'},{label:'Developer',from:7,to:14,tone:'violet'}]},
    {id:'#555',total:'31 min',last:'31 min',silent:true,segments:[{label:'Plan',from:0,to:3,tone:'mint'},{label:'Architect',from:3,to:9,tone:'cyan'},{label:'Developer',from:9,to:17,tone:'cyan'},{label:'Review',from:17,to:31,tone:'blue'}]}
  ],
  rate:[2,2,3,2,4,3,2,5,4,3,2,3,4,5,3,2,3,4,3,2,3,2,4,3],
  eventTypes:[{label:'tool',count:18,tone:'cyan'},{label:'lifecycle',count:12,tone:'mint'},{label:'approval',count:4,tone:'blue'},{label:'retry',count:3,tone:'violet'},{label:'report',count:2,tone:'lavender'},{label:'error',count:1,tone:'muted'}],
  roles:[{label:'Architect',count:1,tone:'cyan'},{label:'Developer',count:1,tone:'violet'},{label:'Review',count:1,tone:'blue'},{label:'QA',count:0,tone:'muted'}],
  stageAge:[{stage:'Architect',current:2,p50:4,p95:9},{stage:'Developer',current:14,p50:12,p95:26},{stage:'Review',current:31,p50:18,p95:41}],
  retries:[{label:'code',count:1,tone:'violet'},{label:'infrastructure',count:1,tone:'blue'},{label:'unknown',count:1,tone:'lavender'}]
};

const WORK_SOURCES=[
  {name:'Claude Code',kind:'structured',label:'structure available',tone:'mint',detail:'Steps, roles, and tools arrive structured.'},
  {name:'Codex',kind:'plain',label:'structure unavailable',tone:'violet',detail:'Only the plain tail of the log. We do not present it as steps and do not show thinking.'}
];
const WORK_ROLES={architect:'Architect',developer:'Developer',review:'Review',qa:'QA'};
const REPORTS=[
  {id:'r-716-qa',type:'qa',typeLabel:'QA',title:'QA · worker readiness',session:'#716',role:'qa',status:'attention',statusLabel:'Needs attention',created:'22:00',summary:'The worker\'s second run reached readiness, but the evidence is incomplete: no exit code for the bounded restart.',conclusion:'A rerun with recorded exit evidence is required; publish is blocked.',evidence:[{name:'qa-report.json',status:'attention',detail:'readiness ok · exit evidence missing'},{name:'worker.log',status:'attention',detail:'restart bounded · last exit unknown'},{name:'receipt.json',status:'passed',detail:'attempt 2 accepted'}]},
  {id:'r-716-review',type:'review',typeLabel:'Review',title:'Code review · #716',session:'#716',role:'review',status:'passed',statusLabel:'Passed',created:'21:59',summary:'The changes match standards and spec; there are no critical findings.',conclusion:'Ready to hand off to QA; review evidence is saved.',evidence:[{name:'review.md',status:'passed',detail:'standards + spec'},{name:'diff.patch',status:'passed',detail:'only managed files'}]},
  {id:'r-704-dev',type:'developer',typeLabel:'Developer',title:'Developer · #704 · offline Docker',session:'#704',role:'developer',status:'blocked',statusLabel:'Blocked',created:'21:46',summary:'The rootful Docker daemon did not start; no container was created.',conclusion:'An environment decision is needed: rootful or offline worker.',evidence:[{name:'daemon.log',status:'blocked',detail:'permission denied'},{name:'env.json',status:'attention',detail:'rootful=true'}]},
  {id:'r-555-review',type:'review',typeLabel:'Review',title:'Review · #555 · refactor cycle',session:'#555',role:'review',status:'attention',statusLabel:'Awaiting decision',created:'21:36',summary:'The changes are ready, but a second reviewer is needed for independent confirmation.',conclusion:'Assign a reviewer; do not start QA yet.',evidence:[{name:'review.md',status:'attention',detail:'needs second reviewer'},{name:'tests.log',status:'passed',detail:'red → green'}]},
  {id:'r-health',type:'health',typeLabel:'Health',title:'Health · project snapshot',session:'—',role:'system',status:'passed',statusLabel:'Passed',created:'21:30',summary:'42 ok · 1 warn · 2 fail · 11 skipped; the data does not replace online checks.',conclusion:'Checks are local; online access was not checked.',evidence:[{name:'health.json',status:'passed',detail:'56 checks'}]},
  {id:'r-publish',type:'publish',typeLabel:'Publish',title:'Publish evidence · #716',session:'#716',role:'system',status:'blocked',statusLabel:'Blocked',created:'22:01',summary:'PR not created: the QA report needs attention, the candidate SHA is not pinned.',conclusion:'Close the QA evidence first, then prepare the PR/MR.',evidence:[{name:'publish.json',status:'blocked',detail:'qa evidence missing'}]}
];

const REPORT_METRICS={
  kpi:{completeness:58,stale:2,latency:'14 min',firstPass:'2 / 6'},
  evidence:[
    {id:'r-716-qa',label:'QA #716',type:'QA',items:[{name:'report',state:'present'},{name:'worker log',state:'present'},{name:'receipt',state:'present'},{name:'checks',state:'stale'},{name:'publish',state:'missing'}]},
    {id:'r-716-review',label:'Review #716',type:'Review',items:[{name:'report',state:'present'},{name:'diff',state:'present'},{name:'receipt',state:'present'},{name:'checks',state:'stale'},{name:'publish',state:'missing'}]},
    {id:'r-704-dev',label:'Developer #704',type:'Developer',items:[{name:'report',state:'present'},{name:'log',state:'present'},{name:'receipt',state:'missing'},{name:'checks',state:'missing'},{name:'publish',state:'missing'}]},
    {id:'r-555-review',label:'Review #555',type:'Review',items:[{name:'report',state:'present'},{name:'diff',state:'present'},{name:'receipt',state:'present'},{name:'checks',state:'stale'},{name:'publish',state:'missing'}]},
    {id:'r-health',label:'Health',type:'Health',items:[{name:'report',state:'present'},{name:'log',state:'missing'},{name:'receipt',state:'missing'},{name:'checks',state:'present'},{name:'publish',state:'missing'}]},
    {id:'r-publish',label:'Publish #716',type:'Publish',items:[{name:'report',state:'present'},{name:'log',state:'missing'},{name:'receipt',state:'missing'},{name:'checks',state:'stale'},{name:'publish',state:'missing'}]}
  ],
  columns:['report file','worker log','receipt','checks','publish'],
  quality:{
    findings:[{label:'blocker',count:1,tone:'violet'},{label:'warning',count:4,tone:'lavender'},{label:'info',count:7,tone:'blue'}],
    versions:[
      {report:'QA #716',steps:[{label:'attempt 1',state:'fail'},{label:'attempt 2',state:'pass'},{label:'current',state:'current'}]},
      {report:'Review #555',steps:[{label:'review 1',state:'pass'},{label:'second reviewer',state:'wait'}]},
      {report:'Publish #716',steps:[{label:'blocked',state:'blocked'},{label:'current',state:'current'}]}
    ],
    latency:[{type:'QA',p50:14,p95:31},{type:'Review',p50:9,p95:24},{type:'Developer',p50:6,p95:18},{type:'Publish',p50:3,p95:8}],
    firstPass:{passed:2,total:6}
  },
  readiness:[
    {candidate:'#716',target:'master',tree:'match',qa:'full',verdict:'pending',blocker:'missing checks evidence'},
    {candidate:'#555',target:'master',tree:'pending',qa:'focused',verdict:'blocked',blocker:'focused QA is not evidence'},
    {candidate:'#704',target:'master',tree:'mismatch',qa:'not_run',verdict:'refused',blocker:'branch head mismatch'}
  ],
  blockers:[
    {label:'#716 · checks evidence',why:'stale',tone:'lavender'},
    {label:'#555 · independent review',why:'missing',tone:'blue'},
    {label:'#704 · candidate / target',why:'tree mismatch',tone:'violet'}
  ]
};
const REPORT_TYPES={qa:{icon:'qa',label:'QA'},review:{icon:'review',label:'Review'},developer:{icon:'developer',label:'Developer'},health:{icon:'pulse',label:'Health'},publish:{icon:'pr',label:'Publish'}};
const ORCH_BATCHES=[
  {id:'b-work',session:'#716',title:'Early worker failure and run observation',status:'working',statusLabel:'In progress',role:'architect',dispatch:'d-arch',heartbeat:'2 s',steps:['current','pending','pending','pending','pending']},
  {id:'b-approval',session:'#555',title:'Full red → green → refactor cycle',status:'awaiting',statusLabel:'Awaiting decision',role:'review',dispatch:'d-review',heartbeat:'31 s',steps:['done','done','current','pending','pending']},
  {id:'b-closed',session:'#704',title:'Offline worker in rootful Docker',status:'attention',statusLabel:'Needs attention',role:'developer',dispatch:'d-dev',heartbeat:'—',steps:['done','current','pending','pending','pending']}
];
const ORCH_DISPATCHES=[
  {id:'d-arch',batch:'b-work',session:'#716',role:'architect',status:'working',statusLabel:'Running',heartbeat:'2 s',task:'Watching the worker launch'},
  {id:'d-review',batch:'b-approval',session:'#555',role:'review',status:'awaiting',statusLabel:'Awaiting decision',heartbeat:'31 s',task:'Independent review of the change'},
  {id:'d-dev',batch:'b-closed',session:'#704',role:'developer',status:'attention',statusLabel:'Needs attention',heartbeat:'—',task:'Rootful Docker did not start'}
];

const ORCH_GATES_TREND={
  avg:[8,7,9,8,9,10,9,8,9,10,11,10,12,11,14,11,10,9,9,8,9,10,9,10],
  p95:[18,17,20,19,21,24,22,20,21,23,25,24,26,22,31,26,22,21,20,19,20,22,21,23],
  peak:{i:14,label:'Peak 31 min · 14:00'}
};
const ORCH_TICKETS=[
  {id:'#716',title:'Early worker failure and run observation',batch:'b-work',stage:'Architect',role:'architect',status:'active',label:'In progress',tone:'cyan',age:'2 min',updated:'10:24'},
  {id:'#704',title:'Offline worker in rootful Docker',batch:'b-closed',stage:'Developer',role:'developer',status:'attention',label:'Needs attention',tone:'violet',age:'14 min',updated:'10:12'},
  {id:'#555',title:'Full red → green → refactor cycle',batch:'b-approval',stage:'Code review',role:'review',status:'awaiting',label:'Awaiting decision',tone:'blue',age:'31 min',updated:'09:55'},
  {id:'#787',title:'Harness Next — Rust runtime, recovery, QA',batch:'b-work',stage:'PR / evidence',role:'system',status:'blocked',label:'Evidence incomplete',tone:'lavender',age:'—',updated:'09:57'},
  {id:'#784',title:'Harness Next epic',batch:'—',stage:'Plan',role:'architect',status:'planned',label:'Planned',tone:'muted',age:'—',updated:'—'},
  {id:'#810',title:'Container executor: Podman network cleanup',batch:'b-closed',stage:'Completed',role:'developer',status:'done',label:'Done',tone:'mint',age:'—',updated:'09:20'}
];

const HARNESS={
  version:{installed:'1.5.1',available:'2.0.0',channel:'pre-release',capability:'backend-orchestration'},
  store:{authority:'runtime-store',schema:6,generation:36,audit:306,cutover:'27.10.2026',protocol:'ipc-v1',binary:'harness-runtime',uptime:'4 h 12 min'},
  components:[
    {name:'Harness package',value:'1.5.1',detail:'2.0.0 available',tone:'violet',state:'outdated'},
    {name:'Skills snapshot',value:'32',detail:'drift 1 · 259 managed',tone:'lavender',state:'drift'},
    {name:'Managed files',value:'259',detail:'managed by harness',tone:'mint',state:'ok'},
    {name:'Hook policy',value:'standard',detail:'Claude 9/9 · Codex 6/8',tone:'blue',state:'attention'},
    {name:'Runtime store',value:'schema 6',detail:'generation 36 · audit 306',tone:'mint',state:'ok'},
    {name:'harness.lock',value:'present',detail:'read-only in mockup',tone:'cyan',state:'ok'}
  ],
  adapters:[
    {name:'Claude Code',kind:'terminal',version:'2.0.14',hooks:'9 / 9',status:'ready',tone:'mint',detail:'standard profile · hooks verified'},
    {name:'Codex',kind:'harness',version:'0.9.3',hooks:'6 / 8',status:'needs update',tone:'violet',detail:'two critical hooks are missing'},
    {name:'GitHub',kind:'github',version:'gh 2.76',hooks:'—',status:'online unchecked',tone:'blue',detail:'network and permissions not checked'}
  ],
  commands:[
    {cmd:'harness health .',purpose:'run 56 checks',mode:'read-only',last:'42 ok · 1 warn · 2 fail',tone:'mint'},
    {cmd:'harness diff',purpose:'show changes in managed files',mode:'read-only',last:'8 files',tone:'blue'},
    {cmd:'harness update .',purpose:'update plan 1.5.1 → 2.0.0',mode:'plan',last:'plan only',tone:'violet'},
    {cmd:'harness cleanup',purpose:'check orphan worktrees',mode:'plan',last:'0 orphan',tone:'lavender'},
    {cmd:'harness repo-map',purpose:'build the repository map',mode:'read-only',last:'tier full',tone:'cyan'},
    {cmd:'harness runtime status',purpose:'read the runtime store',mode:'read-only',last:'schema 6 · generation 36',tone:'mint'}
  ],
  audit:[
    {time:'04.11 21:00',event:'harness update plan',detail:'1.5.1 → 2.0.0 · pre-release',tone:'violet'},
    {time:'27.10 18:40',event:'runtime-store cutover',detail:'authority=runtime-store',tone:'mint'},
    {time:'27.10 18:38',event:'schema migration',detail:'5 → 6 · backup created',tone:'blue'},
    {time:'27.10 18:36',event:'audit chain initialized',detail:'306 records',tone:'cyan'}
  ]
};


const REPO_MAP={
  tier:'full',files:1284,symbolCount:7842,edges:3912,tokens:184000,built:'10:41',generation:'map-36',parser:'Python 3.14 · Linux x86_64',
  coverage:{included:1284,excluded:336,percent:79,groups:[{label:'source',value:1040,tone:'cyan'},{label:'docs',value:164,tone:'blue'},{label:'tests',value:80,tone:'mint'},{label:'excluded',value:336,tone:'muted'}]},
  modules:[
    {id:'runtime',label:'runtime',icon:'harness',files:342,symbols:2104,x:40,y:70,w:150,h:56},
    {id:'policy',label:'policy',icon:'shield',files:96,symbols:618,x:260,y:40,w:150,h:56},
    {id:'ledger',label:'ledger',icon:'reports',files:128,symbols:744,x:260,y:160,w:150,h:56},
    {id:'orchestration',label:'orchestration',icon:'orchestration',files:214,symbols:1460,x:500,y:90,w:160,h:56},
    {id:'console',label:'console',icon:'terminal',files:188,symbols:1288,x:740,y:40,w:150,h:56},
    {id:'diagnostics',label:'diagnostics',icon:'pulse',files:116,symbols:890,x:740,y:170,w:150,h:56},
    {id:'skills',label:'skills',icon:'settings',files:200,symbols:738,x:500,y:220,w:160,h:56}
  ],
  links:[
    {from:'runtime',to:'policy',label:'calls',count:14},
    {from:'runtime',to:'ledger',label:'writes',count:9},
    {from:'policy',to:'orchestration',label:'allows',count:11},
    {from:'ledger',to:'orchestration',label:'state',count:7},
    {from:'orchestration',to:'console',label:'events',count:18},
    {from:'orchestration',to:'diagnostics',label:'health',count:6},
    {from:'console',to:'diagnostics',label:'reads',count:5},
    {from:'skills',to:'orchestration',label:'routes',count:8}
  ],
  symbols:[
    {id:'runtime::serve',name:'runtime::serve',kind:'function',path:'native/harness-runtime/src/main.rs',line:42,module:'runtime',used:12,summary:'Starts the Rust runtime and accepts IPC requests.',imports:['policy::evaluate','ledger::append'],usedBy:['console::renderModule','orchestration::dispatch']},
    {id:'policy::evaluate',name:'policy::evaluate',kind:'function',path:'harness/orchestration/policy.py',line:87,module:'policy',used:9,summary:'Checks an operation against project policy and configuration.',imports:['config::read'],usedBy:['runtime::serve']},
    {id:'ledger::append',name:'ledger::append',kind:'function',path:'harness/orchestration/ledger/lifecycle.py',line:154,module:'ledger',used:7,summary:'Writes a record to the runtime store with generation and audit hash.',imports:['store::write'],usedBy:['runtime::serve','orchestration::dispatch']},
    {id:'orchestration::dispatch',name:'orchestration::dispatch',kind:'function',path:'harness/orchestration/workflow/dispatch.py',line:211,module:'orchestration',used:15,summary:'Creates a dispatch, checks approval, and issues the brief.',imports:['policy::evaluate','ledger::append'],usedBy:['console::renderModule']},
    {id:'console::renderModule',name:'console::renderModule',kind:'module',path:'harness/console/render.py',line:18,module:'console',used:4,summary:'Renders orchestration state to the console.',imports:['orchestration::dispatch'],usedBy:['diagnostics::health']},
    {id:'diagnostics::health',name:'diagnostics::health',kind:'function',path:'harness/health/checks.py',line:63,module:'diagnostics',used:6,summary:'Collects Harness and runtime checks.',imports:['runtime::serve','console::renderModule'],usedBy:[]},
    {id:'skills::resolve',name:'skills::resolve',kind:'function',path:'harness/skills/registry.py',line:49,module:'skills',used:5,summary:'Resolves a skill via the runtime route.',imports:['config::read'],usedBy:['orchestration::dispatch']}
  ]
};

const REPO_FILE_DATA={
  utils:{name:'utils.py',path:'harness/orchestration/core/utils.py',status:'ok',symbols:['class CoordinatorError','def _now()','def _non_empty()','def _read_object()','def _strings()','def _canonical()','def sealed()','def _safe_id()','def _repo()','def _moment()','def _lease_expired()','def _silent_seconds()','def _sanitise()','def _concise_evidence()','def _short()'],code:`class CoordinatorError(HarnessError):
    """An error the coordinator explains to a human."""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _non_empty(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())

def _read_object(path: Path, label: str) -> JsonObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CoordinatorError(f"{label}: expected object")
    return data

def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

def _safe_id(value: object, label: str) -> str:
    text = _non_empty(value) if isinstance(value, str) else ""
    if not text:
        raise CoordinatorError(f"{label}: expected id")
    return text

def _moment(value: object, label: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise CoordinatorError(f"{label}: invalid timestamp") from exc` ,relations:{out:[{path:'harness/errors.py',type:'import',weight:'high',count:1},{path:'harness/console/tui/configuration_steps.py',type:'unique-name-ref',weight:'medium',count:3},{path:'harness/orchestration/ledger/lifecycle.py',type:'ambiguous-name-ref',weight:'low',count:1}],in:[{path:'harness/orchestration/ledger/lifecycle.py',type:'unique-name-ref',weight:'medium',count:3},{path:'harness/orchestration/recovery_api.py',type:'ambiguous-name-ref',weight:'low',count:3},{path:'tests/orchestration/runtime_store_support.py',type:'import',weight:'high',count:3}]}},
  recovery:{name:'recovery_api.py',path:'harness/orchestration/recovery_api.py',status:'ok',symbols:['def recovery_status()','def resume()','def abort()'],code:`def recovery_status(batch: Batch) -> JsonObject:
    checks = [config_check(), store_check(), ledger_check()]
    return {"batch": batch.id, "checks": checks}

def resume(batch: Batch) -> RecoveryOutcome:
    if not batch.can_resume():
        return RecoveryOutcome.refused("attention-open")
    return reconcile(batch)` ,relations:{out:[{path:'harness/orchestration/core/utils.py',type:'import',weight:'medium',count:2},{path:'harness/orchestration/ledger/lifecycle.py',type:'unique-name-ref',weight:'medium',count:4}],in:[{path:'harness/console/render.py',type:'unique-name-ref',weight:'low',count:2}]}},
  lifecycle:{name:'lifecycle.py',path:'harness/orchestration/ledger/lifecycle.py',status:'ok',symbols:['def append()','def read()','def store_is_authority()'],code:`def append(store: Store, record: JsonObject) -> str:
    generation = store.generation
    digest = audit_hash(record, generation)
    store.write(record, generation=generation, audit=digest)
    return digest

def store_is_authority(repo: Path) -> bool:
    return read_pointer(repo).get("authority") == "runtime-store"` ,relations:{out:[{path:'harness/orchestration/core/utils.py',type:'ambiguous-name-ref',weight:'low',count:1},{path:'harness/orchestration/recovery_api.py',type:'unique-name-ref',weight:'medium',count:3}],in:[{path:'harness/orchestration/workflow/dispatch.py',type:'import',weight:'high',count:2}]}},
  dispatch:{name:'dispatch.py',path:'harness/orchestration/workflow/dispatch.py',status:'ok',symbols:['def dispatch()','def propose()','def heartbeat()'],code:`def dispatch(batch: Batch, role: str) -> Dispatch:
    policy = evaluate(batch, role)
    if not policy.allowed:
        raise DispatchRefused(policy.reason)
    brief = build_brief(batch, role)
    append(store, {"kind": "dispatch", "brief": brief})
    return Dispatch(brief)` ,relations:{out:[{path:'harness/orchestration/ledger/lifecycle.py',type:'import',weight:'high',count:2},{path:'harness/orchestration/policy.py',type:'calls',weight:'high',count:5}],in:[{path:'harness/console/render.py',type:'events',weight:'medium',count:4}]}},
  render:{name:'render.py',path:'harness/console/render.py',status:'ok',symbols:['def renderModule()'],code:`def renderModule(state: JsonObject) -> str:
    batch = state.get("batch", {})
    return template("orchestration.html", batch=batch)` ,relations:{out:[{path:'harness/orchestration/workflow/dispatch.py',type:'import',weight:'medium',count:2}],in:[{path:'harness/health/checks.py',type:'reads',weight:'low',count:1}]}},
  errors:{name:'errors.py',path:'harness/errors.py',status:'ok',symbols:['class HarnessError'],code:`class HarnessError(Exception):
    """Base error for Harness operations."""` ,relations:{out:[],in:[{path:'harness/orchestration/core/utils.py',type:'import',weight:'high',count:1}]}},
  health:{name:'checks.py',path:'harness/health/checks.py',status:'ok',symbols:['def health()'],code:`def health(repo: Path) -> JsonObject:
    return {"checks": run_checks(repo), "ok": True}` ,relations:{out:[{path:'harness/console/render.py',type:'reads',weight:'low',count:1}],in:[]}},
  release_test:{name:'test_release_gate.py',path:'tests/orchestration/test_release_gate.py',status:'ok',symbols:['def test_release_gate()'],code:`def test_release_gate() -> None:
    pair = make_pair()
    assert release_gate(pair).verdict == "allowed"` ,relations:{out:[{path:'harness/orchestration/release_gate.py',type:'import',weight:'high',count:2}],in:[]}}
};
const REPO_TREE=[
  {id:'harness',name:'harness',type:'dir',children:[
    {id:'orchestration',name:'orchestration',type:'dir',children:[
      {id:'core',name:'core',type:'dir',children:[{id:'utils',name:'utils.py',type:'file'},{id:'recovery',name:'recovery_api.py',type:'file'}]},
      {id:'ledger',name:'ledger',type:'dir',children:[{id:'lifecycle',name:'lifecycle.py',type:'file'}]},
      {id:'dispatch',name:'dispatch.py',type:'file'}
    ]},
    {id:'console',name:'console',type:'dir',children:[{id:'render',name:'render.py',type:'file'}]},
    {id:'errors',name:'errors.py',type:'file'},
    {id:'health_dir',name:'health',type:'dir',children:[{id:'health',name:'checks.py',type:'file'}]}
  ]},
  {id:'tests',name:'tests',type:'dir',children:[{id:'release_test',name:'test_release_gate.py',type:'file'}]}
];

const SETTINGS={
  project:{name:'claude-agent-harness',branch:'integration/harness-runtime-reliability',path:'.harness/project.json',schema:'project.schema.json',status:'valid',tone:'mint'},
  orchestration:{path:'.harness/orchestration.json',schema:'orchestration.schema.json',status:'valid',tone:'mint'},
  hooks:{path:'.harness/hook-policy.json',profile:'standard',digest:'sha256:7f3a…c21e',status:'standard',tone:'blue'},
  runtime:{authority:'runtime-store',schema:6,stale:120,protocol:'ipc-v1',tone:'mint'},
  resolved:[
    {label:'project',value:'claude-agent-harness'},
    {label:'runtime',value:'native'},
    {label:'stale_seconds',value:'120'},
    {label:'approval',value:'manual'},
    {label:'capability',value:'backend-orchestration'},
    {label:'roles',value:'architect · developer · review · qa'}
  ],
  policies:[
    {label:'Developer retries',value:'2',tone:'violet'},
    {label:'Infrastructure retries',value:'1',tone:'blue'},
    {label:'Retry queue',value:'900 s',tone:'lavender'},
    {label:'QA lane stale',value:'7200 s',tone:'lavender'},
    {label:'Dispatch timeout',value:'60 s',tone:'cyan'}
  ],
  history:[
    {file:'project.json',at:'04.11 21:00',summary:'stale_seconds 120 · approval manual',tone:'mint'},
    {file:'orchestration.json',at:'27.10 18:40',summary:'roles · retry budgets · qa lane',tone:'blue'},
    {file:'hook-policy.json',at:'27.10 18:36',summary:'standard profile · digest recorded',tone:'violet'}
  ]
};

const SETTINGS_WIZARD={
  groups:[
    {id:'project',label:'Project',params:['project.name','runtime','stale_seconds','approval','capability']},
    {id:'orchestration',label:'Orchestration',params:['infrastructure_retry_policy.enabled','attention_policy.max_infrastructure_retries','retry_policy.max_developer_retries']},
    {id:'qa',label:'QA',params:['qa_lane.stale_seconds']},
    {id:'dispatch',label:'Dispatch',params:['dispatch.wait_timeout_seconds','dispatch.poll_interval_seconds']},
    {id:'hooks',label:'Hooks',params:['hook_policy.profile']}
  ],
  params:[
    {key:'project.name',group:'project',label:'Project name',type:'text',value:'claude-agent-harness',recommend:'claude-agent-harness',desc:'Project name in project.json; used in context and reports.',why:'The current name matches the Git repository; no reason to change it.',use:true},
    {key:'runtime',group:'project',label:'Runtime',type:'select',value:'native',recommend:'native',options:['native','container'],desc:'How to run dispatched workers: directly or in a container.',why:'Native is selected for the current project; the container runtime needs Docker/Podman.',use:true},
    {key:'stale_seconds',group:'project',label:'Stale threshold',type:'number',value:120,recommend:120,desc:'How many seconds without an event make a state stale.',why:'120 seconds match the project heartbeat interval.',use:true},
    {key:'approval',group:'project',label:'Approval mode',type:'select',value:'manual',recommend:'manual',options:['manual','policy'],desc:'Who approves dispatch: a human or a policy.',why:'For the current workflow, approvals stay manual.',use:true},
    {key:'capability',group:'project',label:'Capability',type:'select',value:'backend-orchestration',recommend:'backend-orchestration',options:['workflow','backend-orchestration'],desc:'The role set and Harness configuration.',why:'Backend orchestration is already installed; a change will affect roles and the QA lane.',use:true},
    {key:'infrastructure_retry_policy.enabled',group:'orchestration',label:'Infrastructure retry policy',type:'boolean',value:true,recommend:true,desc:'Explicit permission for limited infrastructure retries within approved bounds; grants no native rights. Budget: attention_policy.max_infrastructure_retries.',why:'Keep the current project setting; without additional data there is no reason to change it automatically.',use:true},
    {key:'attention_policy.max_infrastructure_retries',group:'orchestration',label:'Max infrastructure retries',type:'number',value:1,recommend:1,desc:'How many times an infrastructure failure can be retried before attention.',why:'One retry bounds the loop and leaves the decision to a human.',use:true},
    {key:'retry_policy.max_developer_retries',group:'orchestration',label:'Max developer retries',type:'number',value:2,recommend:2,desc:'Developer-retry budget per batch.',why:'Two retries are enough for the current task size.',use:true},
    {key:'qa_lane.stale_seconds',group:'qa',label:'QA lane stale',type:'number',value:7200,recommend:7200,desc:'After how many seconds a QA lane lease is considered stale.',why:'Two hours match long clean-room checks.',use:true},
    {key:'dispatch.wait_timeout_seconds',group:'dispatch',label:'Dispatch wait timeout',type:'number',value:60,recommend:60,desc:'How long to wait for dispatch readiness before attention.',why:'The current timeout matches the poll interval.',use:true},
    {key:'dispatch.poll_interval_seconds',group:'dispatch',label:'Dispatch poll interval',type:'number',value:5,recommend:5,desc:'Dispatch state check interval.',why:'Five seconds give a fast enough response without extra requests.',use:true},
    {key:'hook_policy.profile',group:'hooks',label:'Hook profile',type:'select',value:'standard',recommend:'standard',options:['standard','strict'],desc:'Hooks profile for Claude Code and Codex.',why:'Standard is already checked; strict needs a separate check of critical hooks.',use:true}
  ]
};

const HELP={
  screens:[
    {id:'home',label:'Home',icon:'home',desc:'Harness health, runtime-store, skills, and recent tasks.'},
    {id:'diagnostics',label:'Diagnostics',icon:'pulse',desc:'56 checks, causes, skips, and a fix plan.'},
    {id:'update-harness',label:'Update',icon:'refresh',desc:'1.5.1 → 2.0.0, diff, seed files, and runtime-store migration.'},
    {id:'open-project',label:'Project',icon:'folder',desc:'Current project, installation, capability, and checks.'},
    {id:'board',label:'Task board',icon:'board',desc:'Specs, five columns, filters, cards, and moves.'},
    {id:'agent-activity',label:'Activity',icon:'activity',desc:'Sessions, timeline, events, and per-role statistics.'},
    {id:'orchestration',label:'Orchestration',icon:'orchestration',desc:'Pipeline, batches, dispatch, QA lane, and analytics.'},
    {id:'reports',label:'Reports',icon:'reports',desc:'Evidence, report versions, findings, and Release Gate.'},
    {id:'publish',label:'Publish',icon:'github',desc:'Candidate, gate, preflight, PR/MR, and evidence.'},
    {id:'harness',label:'Harness',icon:'harness',desc:'Runtime, adapters, Docker containers, and commands.'},
    {id:'repo-map',label:'Repo Map',icon:'map',desc:'File hierarchy and contents, symbols, and links.'},
    {id:'configuration',label:'Settings',icon:'settings',desc:'Configuration overview, parameter wizard, and history.'},
    {id:'help',label:'Help',icon:'help',desc:'Screens, commands, hotkeys, and limits.'}
  ],
  faqs:[
    {q:'Why does «skipped» not count as success?',a:'Skipped means the check did not run. It proves neither success nor failure, so it is shown separately.'},
    {q:'What is stale?',a:'Stale is the computed age of data or a heartbeat. It is not necessarily a stopped process: a missing event does not prove that work has stalled.'},
    {q:'Why are offline and online different?',a:'Offline checks read local settings. Online checks also verify the network, access, and GitHub/GitLab permissions; the mockup does not run online checks.'},
    {q:'What counts as evidence?',a:'The full check suite on a specific candidate SHA: results, exit code, artifacts, plan digest, and environment fingerprint. Focused and not_run do not replace full QA.'}
  ],
  keys:[
    {key:'?',label:'Open help'},
    {key:'g',label:'Go to Home'},
    {key:'d',label:'Go to Diagnostics'},
    {key:'o',label:'Go to Orchestration'},
    {key:'Esc',label:'Close the menu or dialog'}
  ],
  limits:[
    {title:'No changes',text:'The mockup does not write files, start processes, or change Git. Commands show a plan or demo output.'},
    {title:'Observed facts only',text:'Internal agent reasoning is not shown. Events, statuses, roles, evidence, and human decisions are visible.'},
    {title:'Stale ≠ stopped',text:'A missing event lowers confidence but does not prove a stop. A conclusion needs a heartbeat, execution state, or another fact.'},
    {title:'Evidence is not opinion',text:'A role report is not proof. Publish is allowed only by full QA evidence on the final SHA and the Release Gate.'}
  ]
};


const BOARD_SPECS=[
  {n:862,title:'Harness web console: mockups and shell',branch:'integration/web-console',tickets:[
    {n:912,title:'Web console task board mockup',what:'HTML task board mockup in the web console shell: five columns, filters, cards, a modal, and card moves.',criteria:['The mockup opens locally without external resources','Wide and narrow widths, the modal, and wrap states are covered','Status selection in the modal is keyboard accessible','A human approved the mockup'],labels:['hitl','type::chore','status::in-progress','priority::p0'],sp:5,batch:'b-912',dispatch:'architect',files:[{path:'docs/rfc/web-console-task-board.html',why:'reference for the board and rules'},{path:'docs/design/web-console-mockups/',why:'embedding scaffold'}]},
    {n:882,title:'Web — shell and Home',what:'Jinja2 pages based on the approved mockups: shell, navigation, Home, and connection state.',criteria:['Home opens by URL with a token','WebSocket refreshes the snapshot','Reconnection is supported','The CSS copy matches the mockup'],labels:['afk','status::ready','priority::p0'],sp:8,files:[{path:'harness/console/',why:'web client scaffold'}]},
    {n:885,title:'Web — live list of agent steps',what:'Live step list for Claude and Codex with filters by dispatch and role.',criteria:['Steps appear without a reload','Codex shows «structure unavailable»','No thinking or raw JSON'],labels:['afk','status::blocked','priority::p1'],sp:8,blockers:[{n:882,why:'needs the shell and Home'}],files:[{path:'harness/console/tui/screens/worker_observation.py',why:'step observation'}]},
    {n:886,title:'Web — Diagnostics and Harness',what:'Diagnostics and Harness pages per the approved mockups.',criteria:['Facts match the TUI','Commands require confirmation'],labels:['afk','status::in-progress','priority::p1'],sp:5,dispatch:'code-review',pr:'#958',files:[{path:'harness/console/tui/screens/diagnostics.py',why:'checks'}]},
    {n:880,title:'Web console mockups: shell and Home',what:'The shell and basic screens of the web console.',criteria:['Wide and narrow widths','Empty and error states','Human acceptance'],labels:['hitl','type::chore','priority::p0'],sp:8,closed:true,files:[{path:'docs/design/web-console-mockups/',why:'approved mockup'}]},
    {n:881,title:'Mockups for the remaining screens and the live list',what:'All screens and the live list of agent steps.',criteria:['All screens next to the core','Codex unavailable','Human acceptance'],labels:['hitl','type::chore','priority::p1'],sp:8,closed:true,files:[{path:'docs/design/web-console-mockups/',why:'approved mockup'}]}
  ]},
  {n:784,title:'Harness Next: Rust runtime and ledger',branch:'integration/harness-runtime-reliability',tickets:[
    {n:790,title:'systemFields.v1 without runtime dictionaries',what:'Import of the systemFields.v1 registry and normalizer without the Python store.',criteria:['Registry matches Rust','No runtime.*','Full verify is green'],labels:['afk','status::ready','priority::p0'],sp:8,files:[{path:'harness/orchestration/contract.py',why:'contract'}]},
    {n:792,title:'Rust workspace and runtime_client',what:'UDS IPC and a typed client for the coordinator.',criteria:['Unix socket and peer check','Error codes','Seam 1 tests'],labels:['afk','status::blocked','priority::p0'],sp:8,blockers:[{n:790,why:'systemFields registry needed'}],files:[{path:'native/harness-runtime/',why:'Rust runtime'}]},
    {n:801,title:'Lifecycle write through the store',what:'CAS, idempotency, and the audit chain for batch and dispatch.',criteria:['BEGIN IMMEDIATE','operations state','audit checkpoint'],labels:['afk','status::in-progress','priority::p0'],sp:8,batch:'b-801',dispatch:'developer',files:[{path:'harness/orchestration/ledger/lifecycle.py',why:'store write'}]},
    {n:814,title:'Cutover and the 2.0.0 release',what:'Release from the integration branch to master after full QA.',criteria:['Rehearsal migrate','Release Gate','Full QA'],labels:['hitl','status::blocked','priority::p0'],sp:3,blockers:[{n:801,why:'needs a store'},{n:812,why:'Release Gate required'}],files:[{path:'docs/adr/0020-runtime-store-cutover.md',why:'cutover'}]},
    {n:803,title:'Rollback to legacy and CLI parity',what:'Export the store to generation v3 and golden parity.',criteria:['human approval','v3 readable by 1.x','Direct migrations only'],labels:['afk','priority::p1'],sp:8,files:[{path:'harness/orchestration/ledger/lifecycle.py',why:'format v3'}]}
  ]}
];
const PUBLISH={
  candidate:{sha:'6a7f74807b10',short:'6a7f748',session:'#716',branch:'integration/harness-runtime-reliability',target:'master',title:'Harness Next — Rust runtime, transactional recovery, hardened QA'},
  gate:{verdict:'blocked',tree:'match',qa:'full',reason:'checks evidence incomplete',detail:'candidate/target pair not ready for merge'},
  preflight:[
    {label:'QA evidence',status:'attention',tone:'lavender',detail:'checks evidence stale · no full pair'},
    {label:'Review',status:'passed',tone:'mint',detail:'2 eyes · no blockers'},
    {label:'Release Gate',status:'blocked',tone:'violet',detail:'candidate / target pair not ready'},
    {label:'Branch head',status:'passed',tone:'mint',detail:'head == candidate SHA'},
    {label:'Target freshness',status:'pending',tone:'blue',detail:'master must be rechecked before merge'}
  ],
  pr:{title:'Harness Next — Rust runtime, transactional recovery, hardened QA',body:'Rust runtime, durable recovery, incremental verification and hardened QA.\n\nIncludes runtime-store, Release Gate and QA evidence contracts.\n\nHuman merge only.',labels:['status::specs','risk:medium'],base:'master',draft:true},
  evidence:[
    {name:'qa-report.json',status:'attention',tone:'lavender',detail:'checks stale · exit evidence incomplete'},
    {name:'review.md',status:'passed',tone:'mint',detail:'standards + spec · 2 eyes'},
    {name:'release-gate.json',status:'blocked',tone:'violet',detail:'verdict blocked · pair not ready'},
    {name:'pr-receipt.json',status:'missing',tone:'muted',detail:'not created'}
  ],
  audit:[
    {time:'11:02',event:'preflight read',detail:'candidate 6a7f748 · target master',tone:'cyan'},
    {time:'10:41',event:'QA evidence checked',detail:'checks stale',tone:'lavender'},
    {time:'09:57',event:'Release Gate',detail:'blocked · evidence_refused',tone:'violet'}
  ],
  reasons:[
    'QA evidence incomplete: checks stage stale.',
    'Release Gate refuses the candidate/target pair.',
    'PR receipt does not exist yet.'
  ]
};
const HARNESS_CONTAINERS={
  engine:{name:'Docker',version:'27.4.1',rootless:true,cgroup:'v2',selinux:'enforcing',dns:'127.0.0.1:53',daemon:'reachable',socket:'unix:///run/user/1000/docker.sock'},
  summary:{running:1,stopped:1,failed:1,images:3,volumes:2,networks:2,disk:'1.8 GB'},
  containers:[
    {id:'qa-716',name:'harness-qa-716',role:'qa',state:'running',label:'running',tone:'mint',image:'harness-sandbox:2.0.0',uptime:'2 min',cpu:'0.4',mem:'312 MB',network:'harness-sandboxes',exit:'—'},
    {id:'review-555',name:'harness-review-555',role:'review',state:'exited',label:'exited 0',tone:'blue',image:'harness-sandbox:2.0.0',uptime:'31 min',cpu:'—',mem:'—',network:'harness-sandboxes',exit:'0'},
    {id:'dev-704',name:'harness-dev-704',role:'developer',state:'failed',label:'failed',tone:'violet',image:'harness-sandbox:2.0.0',uptime:'14 min',cpu:'—',mem:'—',network:'—',exit:'permission denied'}
  ],
  images:[
    {name:'harness-sandbox',tag:'2.0.0',size:'780 MB',used:'10 min'},
    {name:'python',tag:'3.14-slim',size:'120 MB',used:'1 h'},
    {name:'node',tag:'22-alpine',size:'180 MB',used:'2 d'}
  ],
  networks:[
    {name:'harness-sandboxes',driver:'bridge',scope:'local',state:'active'},
    {name:'harness-dns',driver:'bridge',scope:'local',state:'active'}
  ],
  volumes:[
    {name:'harness-cache',size:'640 MB',state:'in use'},
    {name:'harness-logs',size:'120 MB',state:'in use'}
  ],
  cleanup:[
    {label:'stopped containers',count:1,tone:'blue'},
    {label:'dangling images',count:0,tone:'muted'},
    {label:'unused volumes',count:0,tone:'muted'}
  ]
};
const ORCH_ROLES={architect:'Architect',developer:'Developer',review:'Review',qa:'QA'};
const ORCH_METRICS={
  kpi:{wip:3,oldest:'31 min',rework:'1 of 3',qaFirst:'0 of 1',stale:1,unknown:0,flowEfficiency:46},
  flow:{
    states:[
      {label:'planned',value:0,tone:'muted'},
      {label:'awaiting approval',value:1,tone:'violet'},
      {label:'active',value:1,tone:'cyan'},
      {label:'blocked',value:1,tone:'lavender'},
      {label:'paused',value:0,tone:'blue'},
      {label:'completed',value:0,tone:'mint'}
    ],
    aging:[
      {stage:'Architect',buckets:[1,0,0,0],oldest:'2 min'},
      {stage:'Developer',buckets:[0,1,0,0],oldest:'14 min'},
      {stage:'Code review',buckets:[0,0,1,0],oldest:'31 min'},
      {stage:'QA',buckets:[0,0,0,0],oldest:'—'},
      {stage:'Approve QA',buckets:[0,0,0,0],oldest:'—'}
    ],
    stageTimes:[
      {stage:'Architect',p50:4,p95:9},
      {stage:'Developer',p50:12,p95:26},
      {stage:'Code review',p50:18,p95:41},
      {stage:'QA',p50:22,p95:48},
      {stage:'Approve QA',p50:9,p95:25},
      {stage:'Publish',p50:3,p95:8}
    ],
    queue:[
      {label:'Waiting for review',value:8},
      {label:'Waiting for QA lane',value:0},
      {label:'Awaiting approve',value:31},
      {label:'Waiting for PR handoff',value:0}
    ],
    throughput:{completed:1,window:'7 days',demo:true}
  },
  quality:{
    retries:[
      {reason:'code',label:'code',count:1,route:'developer-retry',tone:'violet'},
      {reason:'verification-infrastructure',label:'infrastructure',count:1,route:'verification',tone:'blue'},
      {reason:'unknown',label:'unknown',count:1,route:'human decision',tone:'lavender'}
    ],
    review:{returned:1,total:2},
    qa:{returned:0,total:1,firstPass:0,defectEscape:0},
    findings:[{label:'blocker',count:1,tone:'violet'},{label:'warning',count:2,tone:'lavender'},{label:'info',count:3,tone:'blue'}],
    verification:[
      {label:'full',value:2,tone:'cyan'},
      {label:'focused',value:3,tone:'blue'},
      {label:'failed-only',value:1,tone:'lavender'},
      {label:'not_run',value:1,tone:'muted'}
    ],
    evidence:[
      {batch:'#716',checks:[{name:'lint',state:'pass'},{name:'typecheck',state:'pass'},{name:'pytest',state:'fail'},{name:'clean-room',state:'not_run'}]},
      {batch:'#555',checks:[{name:'lint',state:'pass'},{name:'typecheck',state:'pass'},{name:'pytest',state:'pass'},{name:'clean-room',state:'not_run'}]},
      {batch:'#704',checks:[{name:'lint',state:'pass'},{name:'typecheck',state:'not_run'},{name:'pytest',state:'not_run'},{name:'clean-room',state:'not_run'}]}
    ],
    releaseGate:[
      {candidate:'#716',target:'master',tree:'match',qa:'full',verdict:'pending',reason:'QA evidence incomplete'},
      {candidate:'#555',target:'master',tree:'pending',qa:'focused',verdict:'blocked',reason:'focused QA is not evidence'},
      {candidate:'#704',target:'master',tree:'mismatch',qa:'not_run',verdict:'refused',reason:'branch head mismatch'}
    ],
    localQA:[
      {state:'completed',count:2,tone:'mint'},
      {state:'failed',count:0,tone:'violet'},
      {state:'unavailable',count:1,tone:'blue'},
      {state:'exhausted',count:0,tone:'lavender'}
    ]
  },
  runtime:{
    health:[
      {label:'heartbeat p95',value:'31 s',tone:'cyan'},
      {label:'stale dispatch',value:'1',tone:'violet'},
      {label:'unknown execution',value:'0',tone:'muted'},
      {label:'lost execution',value:'0',tone:'muted'},
      {label:'QA lease',value:'free',tone:'mint'},
      {label:'fencing errors',value:'0',tone:'muted'},
      {label:'recovery holds',value:'0',tone:'mint'},
      {label:'recovery MTTR',value:'12 min',tone:'blue'}
    ],
    execution:[
      {label:'launching',value:0,tone:'blue'},
      {label:'running',value:1,tone:'cyan'},
      {label:'stopping',value:0,tone:'lavender'},
      {label:'exited',value:2,tone:'mint'},
      {label:'lost',value:0,tone:'violet'},
      {label:'unknown',value:0,tone:'muted'}
    ],
    checks:[
      {name:'config',status:'passed'},{name:'store',status:'passed'},{name:'ledger',status:'passed'},
      {name:'batch',status:'passed'},{name:'lifecycle',status:'passed'},{name:'runtime',status:'passed'},
      {name:'snapshot',status:'pending'},{name:'context',status:'pending'},{name:'compatibility',status:'passed'},
      {name:'operation',status:'passed'},{name:'liveness',status:'passed'},{name:'attention',status:'passed'},
      {name:'approval',status:'passed'}
    ],
    operations:{intent:142,committed:140,failed:2},
    holds:[
      {reason:'operational-hold',count:0},{reason:'unknown-reason',count:0},
      {reason:'stale-dispatch',count:0},{reason:'stale-evidence',count:0}
    ]
  },
  gates:[
    {name:'Approve plan',p50:'4 min',p95:'9 min',p50v:4,p95v:9,oldest:'—',rejected:0,conditional:0,stale:0,handoff:'—'},
    {name:'Approve QA',p50:'9 min',p95:'25 min',p50v:9,p95v:25,oldest:'—',rejected:0,conditional:0,stale:0,handoff:'—'},
    {name:'PR handoff',p50:'3 min',p95:'8 min',p50v:3,p95v:8,oldest:'—',rejected:0,conditional:0,stale:0,handoff:'—'}
  ]
};

const healthTotals=()=>{const h=HOME.health;return {...h,total:h.ok+h.warn+h.fail+h.skipped,run:h.ok+h.warn+h.fail}};
const fmtNum=n=>new Intl.NumberFormat('ru-RU').format(n);
const fmtClock=date=>new Intl.DateTimeFormat('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(date);
function homeAttention(){
  const issues=HOME.checks.filter(c=>c.status==='fail'||c.status==='warn');
  return issues.map(c=>`<div class="it"><span class="home-alert-icon ${c.status==='fail'?'err':'warn'}">${icon(c.status==='fail'?'x':'warning')}</span><div class="t"><b>${esc(c.title)}</b><small>${esc(c.detail)}</small></div><a href="${esc(c.href)}">Open →</a></div>`).join('');
}
function healthSummary(){
  const h=healthTotals();
  const part=(value)=>`${(value/h.total)*100}%`;
  return `<div class="health-summary">
    <div class="hs-item"><span class="ok">${h.ok}</span><small>passed</small></div>
    <div class="hs-item"><span class="warn">${h.warn}</span><small>attention</small></div>
    <div class="hs-item"><span class="err">${h.fail}</span><small>errors</small></div>
    <div class="hs-item"><span class="muted">${h.skipped}</span><small>skipped</small></div>
  </div>
  <div class="health-strip" role="img" aria-label="Health: ${h.run} of ${h.total} done; errors ${h.fail}; skipped ${h.skipped}">
    <span class="ok" style="width:${part(h.ok)}"></span><span class="warn" style="width:${part(h.warn)}"></span><span class="fail" style="width:${part(h.fail)}"></span><span class="skip" style="width:${part(h.skipped)}"></span>
  </div>`;
}
function homeAreas(){
  return HOME.areas.map(([name,ic,ok,warn,fail,skip])=>{
    const total=ok+warn+fail+skip||1;
    const seg=(value,cls)=>value?`<i class="${cls}" style="width:${value/total*100}%"></i>`:'';
    return `<div class="health-row"><span class="health-name">${icon(ic)}<span>${esc(name)}</span></span><span class="health-bar" role="img" aria-label="${esc(name)}: ok ${ok}, warn ${warn}, fail ${fail}, skip ${skip}">${seg(ok,'ok')}${seg(warn,'warn')}${seg(fail,'fail')}${seg(skip,'skip')}</span><span class="health-count">${ok}✓ ${warn}⚠ ${fail}✖ ${skip}–</span></div>`;
  }).join('');
}
function homeChecks(filter=homeFilter){
  const rows=filter==='problem'?HOME.checks.filter(c=>c.status==='fail'||c.status==='warn'):filter==='skipped'?HOME.checks.filter(c=>c.status==='skipped'):HOME.checks;
  return rows.map(c=>`<a class="check-row" href="${esc(c.href)}"><span class="check-icon ${c.status}">${icon(c.status==='skipped'?'clock':c.status==='fail'?'x':c.status==='warn'?'warning':'check')}</span><span class="check-main"><b>${esc(c.title)}</b><small>${esc(c.detail)}</small></span><span class="check-area">${esc(c.area)}</span></a>`).join('')||`<div class="empty">No checks in this filter. This does not prove there are no problems outside the list.</div>`;
}
const DIAG_STATUS={
  fail:{short:'FAIL',word:'error',icon:'x',cls:'err'},
  warn:{short:'WARN',word:'attention',icon:'warning',cls:'warn'},
  skipped:{short:'SKIP',word:'skipped',icon:'clock',cls:'skip'},
  ok:{short:'OK',word:'passed',icon:'check',cls:'ok'}
};
function diagVisible(){
  const q=diagQuery.trim().toLowerCase();
  const order={fail:0,warn:1,skipped:2,ok:3};
  return HOME.checks.filter(c=>{
    const byFilter=diagFilter==='all'||(diagFilter==='problem'&&(c.status==='fail'||c.status==='warn'))||(diagFilter==='skipped'&&c.status==='skipped')||(diagFilter==='ok'&&c.status==='ok');
    const byQuery=!q||[c.title,c.area,c.detail,c.id,c.checked].join(' ').toLowerCase().includes(q);
    return byFilter&&byQuery;
  }).sort((a,b)=>order[a.status]-order[b.status]||a.title.localeCompare(b.title,'ru'));
}
function ensureDiagSelection(){
  const rows=diagVisible();
  if(!rows.some(c=>c.id===diagSelected)) diagSelected=rows[0]?.id||null;
}
function diagCountText(){
  const visible=diagVisible().length;
  return `${visible} of ${HOME.checks.length} key · ${healthTotals().total} total`;
}
function diagList(){
  const rows=diagVisible();
  if(!rows.length) return `<div class="diag-empty"><b>Nothing found</b><span>Change the filter or the search query.</span><button class="btn" data-diag-reset>Reset</button></div>`;
  return rows.map(c=>{
    const meta=DIAG_STATUS[c.status];
    return `<button type="button" class="diag-row ${meta.cls}" data-diag-select="${c.id}" aria-pressed="${c.id===diagSelected}">
      <span class="diag-status-icon ${meta.cls}">${icon(meta.icon)}</span>
      <span class="diag-row-main"><b>${esc(c.title)}</b><small>${esc(c.area)} · ${esc(c.detail)}</small></span>
      <span class="diag-pill ${meta.cls}">${meta.short}</span>
      <span class="diag-chevron">${icon('chevron')}</span>
    </button>`;
  }).join('');
}
function diagAction(c){
  if(c.action==='link') return `<div class="diag-action"><a class="btn" href="${esc(c.actionHref)}">${icon('chevron')} ${esc(c.actionLabel)}</a></div>`;
  if(c.action==='refresh') return `<div class="diag-action"><button class="btn" type="button" data-diag-refresh>${icon('refresh')} ${esc(c.actionLabel)}</button></div>`;
  if(c.action==='online') return `<div class="diag-action"><button class="btn" type="button" data-health-mode="online">${icon('pulse')} ${esc(c.actionLabel)}</button></div>`;
  if(c.action==='toast') return `<div class="diag-action"><button class="btn" type="button" data-diag-memory>${icon('memory')} ${esc(c.actionLabel)}</button></div>`;
  return '';
}
function diagDetail(){
  const c=HOME.checks.find(x=>x.id===diagSelected);
  if(!c) return `<section class="panel diag-detail-panel"><div class="diag-empty"><b>No check selected</b><span>Select a row on the left.</span></div></section>`;
  const meta=DIAG_STATUS[c.status];
  return `<section class="panel diag-detail-panel">
    <div class="panel-head"><h2>Check details</h2><div class="diag-detail-head-actions"><button class="btn primary diag-fix-btn" type="button" data-diag-fix ${c.status==='ok'?'disabled aria-disabled="true" title="Check passed — nothing to fix"':'title="Open the fix plan"'}>${icon('settings')} Fix</button><span class="diag-pill ${meta.cls}">${meta.short}</span></div></div>
    <div class="diag-detail-body">
      <div class="diag-detail-top"><span class="diag-area">${esc(c.area)}</span><code>${esc(c.id)}</code></div>
      <h3>${esc(c.title)}</h3>
      <p class="diag-detail-lead">${esc(c.detail)}</p>
      <dl class="diag-facts">
        <div><dt>What was checked</dt><dd>${esc(c.checked)}</dd></div>
        <div><dt>Why it matters</dt><dd>${esc(c.why)}</dd></div>
        <div><dt>What to do</dt><dd>${esc(c.fix)}</dd></div>
      </dl>
      ${diagAction(c)}
      <div class="diag-source"><span>Source</span><code>${esc(c.command)}</code><span>${healthMode==='online'?'online':'offline'} · ${fmtClock(checkedAt)}</span></div>
      ${c.status==='skipped'?`<p class="diag-callout">A skip does not count as success. Online checks require network and permissions.</p>`:''}
    </div>
  </section>`;
}
function diagPage(){
  const counts={all:HOME.checks.length,problem:HOME.checks.filter(c=>c.status==='fail'||c.status==='warn').length,skipped:HOME.checks.filter(c=>c.status==='skipped').length,ok:HOME.checks.filter(c=>c.status==='ok').length};
  const chip=(key,label)=>`<button class="chip ${diagFilter===key?'on':''}" type="button" data-diag-filter="${key}" aria-pressed="${diagFilter===key}">${label} ${counts[key]}</button>`;
  return `<div class="page-title diag-title"><div><h1>Diagnostics</h1><p>Harness 2.0.0 health checks: result, reason, skips, and next step. Online — only with network and permissions.</p><div class="home-facts"><span>7 key checks</span><span>56 total</span><span>${healthMode==='online'?'online not run':'offline'}</span></div></div><div class="actions"><button class="btn" type="button" data-diag-refresh>${icon('refresh')} Check</button><button class="btn" type="button" data-diag-export>${icon('download')} Export</button><a class="btn primary" href="#update-harness">Update</a></div></div>
  <section class="panel diag-summary"><div class="panel-head"><h2>Health summary</h2><div class="health-mode"><span id="diag-mode-note" class="small muted">${healthMode==='online'?'online not run · 11 skipped':'offline · 56 checks'}</span><div class="seg"><button class="${healthMode==='offline'?'on':''}" type="button" data-health-mode="offline" aria-pressed="${healthMode==='offline'}">Offline</button><button class="${healthMode==='online'?'on':''}" type="button" data-health-mode="online" aria-pressed="${healthMode==='online'}">Online</button></div></div></div><div class="body">${healthSummary()}<div class="diag-summary-note"><span id="diag-checked">${fmtClock(checkedAt)} · ${healthTotals().total} checks</span><span>Showing 7 key checks · full report: <code>harness health .</code></span></div></div></section>
  <div class="diag-grid">
    <section class="panel diag-list-panel"><div class="panel-head"><h2>Checks</h2><span class="small muted" id="diag-count">${diagCountText()}</span></div><div class="diag-tools"><div class="chips">${chip('all','All')}${chip('problem','Problems')}${chip('skipped','Skipped')}${chip('ok','Passed')}</div><label class="diag-search">${icon('search')}<input id="diag-search" type="search" placeholder="Find a check" value="${esc(diagQuery)}" aria-label="Search checks"></label></div><div id="diag-list">${diagList()}</div><div class="diag-list-foot">Key checks · full report: <code>harness health .</code></div></section>
    <div id="diag-detail">${diagDetail()}</div>
  </div>`;
}
function diagFix(){
  const c=HOME.checks.find(x=>x.id===diagSelected);
  if(!c||c.status==='ok') return;
  reader(`Fix plan · ${c.area}`, `DEMO · FIX PLAN

Check: ${c.title}
ID: ${c.id}

What to do:
${c.fix}

Command:
${c.command}

Mode: ${healthMode}

The command does not run in the mockup. For a real fix, open the relevant screen or run the command in the terminal.`);
  toast('Fix plan opened; the command does not run');
}
function exportDiag(){
  const rows=diagVisible();
  const payload={generatedAt:new Date().toISOString(),snapshotAt:checkedAt.toISOString(),demo:true,mode:healthMode,summary:healthTotals(),filter:diagFilter,query:diagQuery,scope:'key-checks',checks:rows.map(c=>({id:c.id,area:c.area,status:c.status,title:c.title,detail:c.detail,checked:c.checked,why:c.why,fix:c.fix,command:c.command}))};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download=`harness-diagnostics-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`;
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast(`Checks exported: ${rows.length}`);
}
const UPDATE_KIND={
  conflict:{label:'conflict',icon:'x',cls:'err'},
  create:{label:'will be added',icon:'download',cls:'ok'},
  update:{label:'will be updated',icon:'check',cls:'active'},
  keep:{label:'your edits',icon:'warning',cls:'warn'},
  migration:{label:'migration',icon:'store',cls:'warn'}
};
function seedFiles(){return SEED_FILES}
function selectedSeedPaths(){return seedFiles().filter(path=>seedSelected[path])}
function updateCommand(){
  if(updateMode==='replace')return `harness update . --to ${UPDATE.target} --replace-managed`;
  if(updateMode==='seed'){const seeds=selectedSeedPaths();return `harness update . --to ${UPDATE.target} --seed ${seeds.length?seeds.join(','):'none'}`}
  return `harness update .`;
}
function updateWarning(){
  if(updateMode==='replace')return {tone:'err',title:'Overwriting managed files',text:'Will replace 3 files with local edits. Uncommitted edits in them will be lost; backup is required.'};
  if(updateMode==='seed'){
    const selected=selectedSeedPaths().length;
    return selected?{tone:'warn',title:`Seed files to be overwritten: ${selected}`,text:'Other managed files do not change. Mark the seed files you need in the panel above.'}:{tone:'err',title:'No seed files selected',text:'Select at least one seed file in the panel above; otherwise the update has nothing to apply.'};
  }
  return {tone:'warn',title:'A normal update will stop: 1 conflict',text:'Choose an overwrite mode or resolve the file by hand (see the diff below).'};
}
function updateCounts(){
  if(updateMode==='seed'){
    const selected=selectedSeedPaths().length;
    return [
      {value:selected,label:'seed selected',icon:'check',cls:'ok'},
      {value:seedFiles().length,label:'seed total',icon:'warning',cls:'warn'},
      {value:UPDATE.updateCount+UPDATE.createCount,label:'managed unchanged',icon:'refresh',cls:'muted'}
    ];
  }
  return [
    {value:UPDATE.updateCount,label:'will be updated',icon:'check',cls:'ok'},
    {value:UPDATE.createCount,label:'will be added',icon:'download',cls:'ok'},
    {value:UPDATE.keepCount,label:'with local edits (preserved)',icon:'warning',cls:'warn'},
    {value:UPDATE.conflictCount,label:'in conflict (overwrite needed)',icon:'x',cls:'err'}
  ];
}
function updateModes(){
  const mode=(key,label,desc,tag,tone)=>`<label class="update-mode-card ${updateMode===key?'on':''}"><input type="radio" name="update-mode" data-update-mode="${key}" ${updateMode===key?'checked':''}><span class="mode-copy"><b>${label}</b><small>${desc}</small></span><span class="mode-tag ${tone}">${tag}</span></label>`;
  return `${mode('normal','Normal','Local edits are kept; stop on conflicts.','recommended','ok')}${mode('replace','With overwrite of managed files','Will replace managed and conflicting files; edits will be lost.','dangerous','err')}${mode('seed','With overwrite of selected seed files','Only marked seed files.','selectively','active')}`;
}
function updateCountsBody(){
  return updateCounts().map(r=>`<div class="update-count-row ${r.cls}"><span class="count-value">${r.value}</span><span class="count-icon ${r.cls}">${icon(r.icon)}</span><span class="count-label">${r.label}</span></div>`).join('');
}
function updateChangesCard(){
  return `<section class="panel changes-card"><div class="panel-head"><h2>What changes in managed files</h2><span class="small muted">harness diff</span></div><div id="update-counts-body" class="update-counts">${updateCountsBody()}</div><div class="changes-foot"><span id="update-mode-note">${updateMode==='seed'?'Seed mode: select files in the Seed files panel.':'Normal mode will keep local edits.'}</span><button class="btn" type="button" data-update-refresh>${icon('refresh')} Check again</button></div></section>`;
}
function updatePlanCard(){
  const w=updateWarning();
  const disabled=updateMode==='seed'&&selectedSeedPaths().length===0;
  return `<div id="update-plan-body" class="update-plan-body"><div class="plan-command"><span>$</span><code>${updateCommand()}</code></div><div class="plan-warning ${w.tone}">${icon(w.tone==='err'?'x':'warning')}<div><b>${w.title}</b><p>${w.text}</p></div></div><p class="plan-explain">The command overwrites managed/seed files; uncommitted edits will be lost. Confirmation before launch.</p><button class="btn primary update-apply" type="button" data-update-apply ${disabled?'disabled':''}>${icon('download')} Update</button><p class="plan-note">Nothing runs in the mockup.</p></div>`;
}
function updatePlanCardWrap(){
  return `<section class="panel plan-card"><div class="panel-head"><h2>Plan</h2><span class="update-pill muted">demo</span></div>${updatePlanCard()}</section>`;
}
function updateDiffLines(diff){
  return diff.split('\n').map(line=>{
    const cls=line.startsWith('+++')||line.startsWith('---')?'file':line.startsWith('+')?'add':line.startsWith('-')?'del':line.startsWith('@@')?'hunk':'ctx';
    return `<span class="diff-line ${cls}">${esc(line)||' '}</span>`;
  }).join('\n');
}
function updateDiffList(){
  return UPDATE.changes.map(c=>{
    const k=UPDATE_KIND[c.kind];
    const seed=Boolean(c.seed);
    return `<div class="diff-file ${c.path===updateSelected?'on':''} ${c.kind}" data-update-file="${esc(c.path)}" role="button" tabindex="0"><span class="diff-status ${k.cls}">${icon(k.icon)}</span><span class="diff-path">${esc(c.path)}</span><span class="diff-kind ${k.cls}">${k.label}</span></div>`;
  }).join('');
}
function updateDiffDetail(){
  const c=UPDATE.changes.find(x=>x.path===updateSelected)||UPDATE.changes[0];
  if(!c) return '';
  const k=UPDATE_KIND[c.kind];
  return `<div class="diff-detail-head"><span class="diff-status ${k.cls}">${icon(k.icon)}</span><code>${esc(c.path)}</code><span class="update-pill ${k.cls}">${k.label}</span></div><p class="diff-explain">${esc(c.explain)}</p>${c.kind==='conflict'?`<div class="diff-warning">${icon('warning')} Conflict: a normal update stops; overwrite replaces the file with the package version.</div>`:''}${c.seed?`<div class="diff-warning seed">${icon('warning')} Seed file: in seed mode, select it on the left to overwrite.</div>`:''}<pre class="diff-code">${updateDiffLines(c.diff)}</pre>`;
}
function updateDiffCard(){
  return `<section class="panel diff-panel"><div class="panel-head"><h2>Diff — what will change in files</h2><span class="small muted">file selection · ${UPDATE.changes.length} files · <span id="update-checked">${fmtClock(updateCheckedAt)}</span></span></div><div class="diff-layout"><div id="update-diff-list" class="diff-list">${updateDiffList()}</div><div id="update-diff-detail" class="diff-detail">${updateDiffDetail()}</div></div></section>`;
}
function updateMigration(){
  return `<section class="panel migration-panel"><div class="panel-head"><h2>Runtime-store migration</h2><span class="small muted">schema ${UPDATE.migration.from} → ${UPDATE.migration.to}</span></div><div class="body"><div class="migration-track"><div class="migration-step pending"><span class="migration-num">01</span><b>Backup</b><small>copy of runtime.db before write</small><span class="migration-state">required</span></div><span class="migration-arrow">→</span><div class="migration-step pending"><span class="migration-num">02</span><b>Schema ${UPDATE.migration.from} → ${UPDATE.migration.to}</b><small>SQLite WAL · reversible</small><span class="migration-state">waiting</span></div><span class="migration-arrow">→</span><div class="migration-step pending"><span class="migration-num">03</span><b>Cutover</b><small>${UPDATE.migration.cutover} · authority ${UPDATE.migration.authority}</small><span class="migration-state">waiting</span></div><span class="migration-arrow">→</span><div class="migration-step after"><span class="migration-num">04</span><b>Health</b><small>harness health . after migration</small><span class="migration-state">after</span></div></div><div class="migration-facts"><div><span>authority</span><b>${UPDATE.migration.authority}</b></div><div><span>generation</span><b>${UPDATE.migration.generation}</b></div><div><span>audit</span><b>${UPDATE.migration.audit}</b></div><div><span>cutover</span><b>${UPDATE.migration.cutover}</b></div></div><p class="migration-note">The Python-writer is removed; the Rust runtime is the only writer. Rollback is allowed only from the backup taken before cutover.</p></div></section>`;
}
function updateResult(){
  return `<section class="panel result-panel"><div class="panel-head"><h2>Last run result</h2><span class="small muted">not run yet</span></div><div class="result-empty">${icon('terminal')} The update result appears here.</div></section>`;
}
function updateSeedPanel(){
  if(updateMode!=='seed') return '';
  const selected=selectedSeedPaths().length;
  const rows=SEED_FILES.map(path=>`<label class="seed-file" title="${esc(path)}"><input type="checkbox" data-seed-file="${esc(path)}" ${seedSelected[path]?'checked':''}><code>${esc(path)}</code></label>`).join('');
  return `<section class="panel seed-panel"><div class="panel-head"><h2>Seed files <span class="small muted">marked ${selected} of ${SEED_FILES.length}</span></h2><div class="seed-actions"><button class="btn" type="button" data-seed-all>Select all</button><button class="btn" type="button" data-seed-none>Clear selection</button></div></div><div class="seed-body"><p class="seed-warning">${icon('warning')} The selected files will be overwritten with the reference version; their edits will be lost.</p><div class="seed-grid">${rows}</div></div></section>`;
}
function updatePage(){
  const status=UPDATE.current===UPDATE.target?'Version is current':'Update 2.0.0 available';
  return `<div class="page-title update-title"><div><h1>Update Harness</h1><p>We first show what will change in managed files. Execution starts only after your confirmation.</p><div class="home-facts"><span>${UPDATE.current} → ${UPDATE.target}</span><span>${UPDATE.managed} managed files</span><span>${UPDATE.skills} skills</span><span>schema ${UPDATE.migration.from} → ${UPDATE.migration.to}</span></div></div><div class="actions"><button class="btn" type="button" data-update-refresh>${icon('refresh')} Check again</button><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div>
  <div class="update-top-grid">
    <section class="panel versions-card"><div class="panel-head"><h2>Versions</h2><span class="update-pill warn">available</span></div><div class="versions-body"><div class="version-pair"><div><span>Installed</span><b>${UPDATE.current}</b></div><div><span>Available</span><b>${UPDATE.target}</b></div></div><div class="version-status">${icon('warning')} ${status}</div><dl class="kv version-facts"><div><dt>Contents</dt><dd>${UPDATE.package}</dd></div><div><dt>Skills</dt><dd>${UPDATE.skills}</dd></div><div><dt>Managed files</dt><dd>${UPDATE.managed}</dd></div><div><dt>Lock updated</dt><dd>04.11.2026 · 21:00 UTC</dd></div><div><dt>Schema</dt><dd>${UPDATE.migration.from} → ${UPDATE.migration.to}</dd></div></dl></div><div class="versions-changes"><div class="integrated-head"><h3>What changes in managed files</h3><span>harness diff</span></div><div id="update-counts-body" class="update-counts">${updateCountsBody()}</div></div><div class="changes-foot"><span id="update-mode-note">${updateMode==='seed'?'Seed mode: select files in the Seed files panel.':'Normal mode will keep local edits.'}</span><button class="btn" type="button" data-update-refresh>${icon('refresh')} Check again</button></div></section>
    <section class="panel modes-card"><div class="panel-head"><h2>Update mode</h2></div><div id="update-modes" class="update-modes">${updateModes()}</div><div class="modes-plan"><div class="integrated-head"><h3>Plan</h3><span>demo</span></div>${updatePlanCard()}</div></section>
  </div>
  <div id="update-seed-wrap">${updateSeedPanel()}</div>
  ${updateDiffCard()}
  ${updateMigration()}
  ${updateResult()}`;
}
function refreshUpdate(){
  const modes=$('#update-modes');if(modes)modes.innerHTML=updateModes();
  const seedWrap=$('#update-seed-wrap');if(seedWrap)seedWrap.innerHTML=updateSeedPanel();
  const plan=$('#update-plan-body');if(plan)plan.innerHTML=updatePlanCard();
  const counts=$('#update-counts-body');if(counts)counts.innerHTML=updateCountsBody();
  const modeNote=$('#update-mode-note');if(modeNote)modeNote.textContent=updateMode==='seed'?'Seed mode: select files in the Seed files panel.':'Normal mode will keep local edits.';
  const list=$('#update-diff-list');if(list)list.innerHTML=updateDiffList();
  const detail=$('#update-diff-detail');if(detail)detail.innerHTML=updateDiffDetail();
}
function updateConfirm(){
  if(updateMode==='seed'&&selectedSeedPaths().length===0){toast('Select at least one seed file');return}
  const w=updateWarning();
  reader('Update confirmation',`DEMO · UPDATE CONFIRM\n\n${UPDATE.current} → ${UPDATE.target} ${UPDATE.channel}\nMode: ${updateMode==='normal'?'normal':updateMode==='replace'?'overwrite managed files':'selected seed files'}\n\n${w.title}\n${w.text}\n\nCommand:\n${updateCommand()}\n\nNothing runs in the mockup. A real update requires a backup and confirmation.`);
  toast('Confirmation opened; the update does not run');
}

function bindDiag(){
  document.querySelectorAll('[data-diag-filter]').forEach(btn=>{
    const on=btn.dataset.diagFilter===diagFilter;
    btn.classList.toggle('on',on);
    btn.setAttribute('aria-pressed',String(on));
  });
  document.querySelectorAll('[data-health-mode]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.healthMode===healthMode)));
}
function updateDiag(){
  ensureDiagSelection();
  const list=$('#diag-list');if(list)list.innerHTML=diagList();
  const detail=$('#diag-detail');if(detail)detail.innerHTML=diagDetail();
  const count=$('#diag-count');if(count)count.textContent=diagCountText();
  bindDiag();
}
function installPath(){return projectPath||projectCurrent().path}
function installProjectName(){const p=installPath();const cur=projectCurrent();return p===cur.path?cur.name:(p.split('/').filter(Boolean).at(-1)||cur.name)}
function installCapability(){return CAPABILITIES.find(c=>c.id===projectCapability)||CAPABILITIES[0]}
function installCommand(){return `harness update ${installPath()} --capability pvmalove-suite`}
function installSteps(){
  const steps=[
    ['Project selection','done'],['Pre-checks','active'],['Install / integrate','pending'],['Setup','pending'],['Final diagnostics','pending']
  ];
  return `<div class="install-steps"><div class="install-steps-track">${steps.map(([label,state],i)=>`<span class="install-step ${state}">${state==='done'?icon('check'):state==='active'?icon('play'):icon('clock')}${label}</span>${i<steps.length-1?'<i class="install-sep">—</i>':''}`).join('')}</div><span class="install-step-count">Step 2 of 5</span></div>`;
}
function installFlow(){
  const h=healthTotals();
  const nodes=[
    ['folder','Project','Git project found',installProjectName(),'ok'],
    ['harness','Harness','1.5.1 → 2.0.0',`update · ${UPDATE.channel}`,'warn'],
    ['settings','Capability',installCapability().label,installCapability().desc,'active'],
    ['store','Runtime','schema 3 → 6',`generation ${UPDATE.migration.generation} · audit ${UPDATE.migration.audit}`,'pending'],
    ['pulse','Health','after install',`${h.ok}/${h.total} passed`,'after']
  ];
  return `<section class="panel install-flow-panel"><div class="panel-head"><h2>Rollout map</h2><span class="small muted">project path → harness → capability → runtime → health</span></div><div class="install-flow">${nodes.map(([ic,label,value,sub,state],i)=>`<div class="install-flow-node ${state}"><span class="install-flow-num">${String(i+1).padStart(2,'0')}</span><span class="install-flow-icon">${icon(ic)}</span><b>${label}</b><span class="install-flow-value" ${label==='Capability'?'data-flow-cap':''}>${value}</span><small ${label==='Capability'?'data-flow-cap-desc':''}>${sub}</small></div>${i<nodes.length-1?'<span class="install-flow-arrow">→</span>':''}`).join('')}</div></section>`;
}
function installProjectPage(){
  const path=installPath();
  const cap=installCapability();
  const status=projectPathStatus||'Git project found · action: update';
  const h=healthTotals();
  return `<div class="install-wrap"><h1 class="sr-only">Project</h1>${installSteps()}
  <div class="install-top-grid">
    <section class="panel install-project"><div class="panel-head"><h2>Project</h2><span class="small muted">Local Git</span></div><div class="install-project-body"><label class="field">Path to the local Git project<input id="install-path" value="${esc(path)}"></label><div class="install-actions"><button class="btn" type="button" data-install-browse>${icon('folder')} Browse folders</button><button class="btn" type="button" data-install-check>${icon('check')} Check path</button><button class="btn primary" type="button" data-install-open>Open project ${icon('chevron')}</button></div><div id="install-path-status" class="install-path-status ok">${icon('check')} ${esc(status)}</div><small>harness.lock exists · installed: pvmalove-suite</small></div></section>
    <section class="panel install-plan"><div class="panel-head"><h2>Install plan</h2><span class="update-pill warn">update</span></div><div class="install-plan-body"><dl class="install-plan-facts"><div><dt>Project</dt><dd id="install-project-name">${esc(installProjectName())}</dd></div><div><dt>Contents</dt><dd id="install-composition">${esc(cap.label)} (pvmalove-suite)</dd></div><div><dt>Conflicts</dt><dd><span class="install-ok">${icon('check')} None</span></dd></div></dl><div class="install-command-label">Command</div><pre id="install-command" class="install-command">${esc(installCommand())}</pre><div class="install-plan-actions"><button class="btn primary" type="button" data-install-apply>${icon('download')} Install</button><span>Confirmation required</span></div></div></section>
  </div>
  ${installFlow()}
  <div class="install-lower-grid">
    <section class="panel install-capabilities"><div class="panel-head"><h2>Harness contents</h2><span class="small muted">what will be installed</span></div><div class="cap-list">${CAPABILITIES.map(c=>`<label class="cap-row ${c.id===projectCapability?'on':''}"><input type="radio" name="install-capability" data-capability="${c.id}" ${c.id===projectCapability?'checked':''}><span class="cap-copy"><b>${c.label}</b>${c.status?`<span class="cap-status">${c.status}</span>`:''}<small>${c.desc}</small></span></label>`).join('')}</div><p id="install-cap-footer" class="cap-footer">${esc(cap.footer)}</p></section>
    <section class="panel install-checks"><div class="panel-head"><h2>Checks</h2><span class="small muted">${h.run} of ${h.total} checked</span></div><div class="install-checks-body"><div class="install-check-actions"><button class="chip ${healthMode==='offline'?'on':''}" type="button" data-health-mode="offline">Offline</button><button class="chip ${healthMode==='online'?'on':''}" type="button" data-health-mode="online">Online</button><a class="btn" href="#diagnostics">${icon('pulse')} Fix</a><a class="btn" href="#configuration">${icon('settings')} Settings</a></div><div class="install-health"><span class="ok">${icon('check')} ${h.ok} passed</span><span class="warn">${icon('warning')} ${h.warn} attention</span><span class="err">${icon('x')} ${h.fail} errors</span><span class="skip">${icon('clock')} ${h.skipped} not checked</span></div><div class="install-health-bar" role="img" aria-label="Checked ${h.run} of ${h.total}"><span class="ok" style="width:${h.ok/h.total*100}%"></span><span class="warn" style="width:${h.warn/h.total*100}%"></span><span class="fail" style="width:${h.fail/h.total*100}%"></span><span class="skip" style="width:${h.skipped/h.total*100}%"></span></div><p id="install-mode-note" class="install-checks-note">Online — a separate check of GitHub/GitLab and access rights. Sandbox checks analyze settings; actual access may stay unverified.</p></div></section>
  </div>
  </div>`;
}
function checkInstallPath(){
  const input=$('#install-path');
  const path=(input?.value||'').trim();
  const node=$('#install-path-status');
  const apply=$('[data-install-apply]');
  if(!path.startsWith('/')||path.length<2){
    projectPathStatus='Enter an absolute path';
    if(node){node.className='install-path-status err';node.innerHTML=`${icon('x')} Enter an absolute path`}
    if(apply)apply.disabled=true;
    return;
  }
  projectPath=path;
  projectPathStatus='Git project found · action: update';
  if(node){node.className='install-path-status ok';node.innerHTML=`${icon('check')} ${projectPathStatus}`}
  if(apply)apply.disabled=false;
  const command=$('#install-command');if(command)command.textContent=installCommand();
  const name=$('#install-project-name');if(name)name.textContent=installProjectName();
}
function refreshInstallCapability(){
  const cap=installCapability();
  document.querySelectorAll('.cap-row').forEach(row=>{
    const input=row.querySelector('[data-capability]');
    row.classList.toggle('on',input?.dataset.capability===projectCapability);
  });
  const comp=$('#install-composition');if(comp)comp.textContent=`${cap.label} (pvmalove-suite)`;
  const foot=$('#install-cap-footer');if(foot)foot.textContent=cap.footer;
  const flowCap=document.querySelector('[data-flow-cap]');if(flowCap)flowCap.textContent=cap.label;
  const flowDesc=document.querySelector('[data-flow-cap-desc]');if(flowDesc)flowDesc.textContent=cap.desc;
}

function installConfirm(){
  if(!installPath().startsWith('/')){toast('Enter a valid project path');return}
  reader('Install confirmation',`DEMO · INSTALL CONFIRM\n\nProject: ${installProjectName()}\nPath: ${installPath()}\nContents: ${installCapability().label} (pvmalove-suite)\n\nCommand:\n${installCommand()}\n\nOnly managed Harness files will change. Confirmation is required. The mockup does not run the install.`);
  toast('Confirmation opened; installation does not run');
}
function projectHubPage(){
  const cur=projectCurrent();
  const selected=projectSelected();
  const {h,total}=projectHealth(cur);
  const hh=healthTotals();
  return `<div class="page-title project-title"><div><h1>Project</h1><p>Current project, Harness 2.0.0 installation, and checks. Git and files do not change.</p><div class="home-facts"><span>${esc(cur.name)}</span><span>${esc(cur.branch)}</span><span>${esc(cur.version)}</span></div></div><div class="actions"><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div>
  ${installSteps()}
  <section class="panel current-project"><div class="current-project-icon">${icon('folder')}</div><div class="current-project-main"><span class="eyebrow">Current project</span><h2>${esc(cur.name)}</h2><code>${esc(cur.path)}</code><div class="current-project-meta">${icon('branch')} ${esc(cur.branch)} · ${icon(cur.provider==='gitlab'?'gitlab-mark':cur.provider==='local'?'folder':'github-mark')} ${esc(cur.repo)}</div></div><div class="current-project-stats"><div><span>Harness</span><b>${esc(cur.version)}</b></div><div><span>Skills</span><b>${cur.skills||'—'}</b></div><div><span>Managed</span><b>${cur.managed||'—'}</b></div><div><span>Health</span><b>${total?`${h.ok}/${total}`:'—'}</b></div></div></section>
  <div class="project-grid"><div class="project-left"><section class="panel projects-panel"><div class="panel-head"><h2>Projects</h2><span class="small muted">${projectListAll().length} found</span></div><div class="project-list">${projectList()}</div><div class="project-list-foot">Select a project to see the checks on the right.</div></section><section class="panel project-path-panel"><div class="panel-head"><h2>Path to another project</h2><span class="small muted">demo check</span></div><div class="project-path-body"><label class="field">Path to the local Git project<input id="project-path" value="${esc(projectPath)}" placeholder="/home/…/project"></label><button class="btn" type="button" data-project-check>${icon('check')} Check path</button></div><div class="project-path-info"><span id="project-path-status">${esc(projectPathStatus)}</span><span class="project-hint">In the mockup, the path is checked without reading Git, branch, or .harness.</span></div></section></div><div id="project-detail">${projectDetail()}</div></div>
  ${installFlow()}
  <div class="install-bottom-grid">
    <section class="panel install-plan"><div class="panel-head"><h2>Install plan</h2><span class="update-pill warn">update</span></div><div class="install-plan-body"><dl class="install-plan-facts"><div><dt>Project</dt><dd>${esc(installProjectName())}</dd></div><div><dt>Contents</dt><dd id="install-composition">${esc(installCapability().label)} (pvmalove-suite)</dd></div><div><dt>Conflicts</dt><dd><span class="install-ok">${icon('check')} None</span></dd></div></dl><div class="install-command-label">Command</div><pre id="install-command" class="install-command">${esc(installCommand())}</pre><div class="install-plan-actions"><button class="btn primary" type="button" data-install-apply>${icon('download')} Install</button><span>Confirmation required</span></div></div></section>
    <section class="panel install-capabilities"><div class="panel-head"><h2>Harness contents</h2><span class="small muted">what will be installed</span></div><div class="cap-list">${CAPABILITIES.map(c=>`<label class="cap-row ${c.id===projectCapability?'on':''}"><input type="radio" name="install-capability" data-capability="${c.id}" ${c.id===projectCapability?'checked':''}><span class="cap-copy"><b>${c.label}</b>${c.status?`<span class="cap-status">${c.status}</span>`:''}<small>${c.desc}</small></span></label>`).join('')}</div><p id="install-cap-footer" class="cap-footer">${esc(installCapability().footer)}</p></section>
    <section class="panel install-checks"><div class="panel-head"><h2>Checks</h2><span class="small muted">${hh.run} of ${hh.total} checked</span></div><div class="install-checks-body"><div class="install-check-actions"><button class="chip ${healthMode==='offline'?'on':''}" type="button" data-health-mode="offline">Offline</button><button class="chip ${healthMode==='online'?'on':''}" type="button" data-health-mode="online">Online</button><a class="btn" href="#diagnostics">${icon('pulse')} Fix</a><a class="btn" href="#configuration">${icon('settings')} Settings</a></div><div class="install-health"><span class="ok">${icon('check')} ${hh.ok} passed</span><span class="warn">${icon('warning')} ${hh.warn} warnings</span><span class="err">${icon('x')} ${hh.fail} errors</span><span class="skip">${icon('clock')} ${hh.skipped} not checked</span></div><div class="install-health-bar" role="img" aria-label="Checked ${hh.run} of ${hh.total}"><span class="ok" style="width:${hh.ok/hh.total*100}%"></span><span class="warn" style="width:${hh.warn/hh.total*100}%"></span><span class="fail" style="width:${hh.fail/hh.total*100}%"></span><span class="skip" style="width:${hh.skipped/hh.total*100}%"></span></div><p id="install-mode-note" class="install-checks-note">Online — a separate check of GitHub/GitLab and access rights. Sandbox checks analyze settings; actual access may stay unverified.</p></div></section>
  </div>`;
}

function projectCurrent(){
  if(projectManual&&projectManual.name===project)return projectManual;
  return PROJECTS.find(p=>p.name===project)||PROJECTS[0];
}
function projectSelected(){
  if(projectSelectedId==='manual'&&projectManual)return projectManual;
  return PROJECTS.find(p=>p.id===projectSelectedId)||projectCurrent();
}
function projectListAll(){
  if(projectManual&&!PROJECTS.some(p=>p.name===projectManual.name))return [projectManual,...PROJECTS];
  return PROJECTS;
}
function projectHealth(p){
  const h=p.health||{ok:0,warn:0,fail:0,skipped:0};
  const total=h.ok+h.warn+h.fail+h.skipped;
  return {h,total,text:total?`${h.ok}/${total}`:'—'};
}
function projectCheck(label,status,text){
  const iconName=status==='ok'?'check':status==='warn'?'warning':status==='fail'?'x':'clock';
  return `<div class="project-check"><span class="project-check-icon ${status}">${icon(iconName)}</span><span class="project-check-main"><b>${label}</b><small>${text}</small></span><span class="project-check-state ${status}">${status==='ok'?'passed':status==='warn'?'attention':status==='fail'?'error':'not checked'}</span></div>`;
}
function projectDetail(){
  const p=projectSelected();
  const current=p.name===project;
  const total=projectHealth(p).total;
  const checks=[
    projectCheck('Git repository',p.git===null?'skip':p.git?'ok':'fail',p.git===null?'not checked in the mockup':p.git?p.path:'path is not a Git repository'),
    projectCheck('Harness config',p.config===null?'skip':p.config?'ok':'warn',p.config===null?'not checked in the mockup':p.config?'.harness/project.json found':'.harness/project.json is missing'),
    projectCheck('Capability',p.capability==='—'?'skip':'ok',p.capability==='—'?'not checked':p.capability),
    projectCheck('Skills snapshot',p.drift?'warn':'ok',`${p.skills||'—'} skills · drift ${p.drift}`),
    projectCheck('Uncommitted files',p.dirty?'warn':'ok',p.dirty?`${p.dirty} files with local edits`:'no local edits')
  ].join('');
  const command=`cd ${p.path} && harness`;
  return `<section class="panel project-detail-panel"><div class="panel-head"><h2>Project details</h2><span class="project-pill ${current?'ok':'muted'}">${current?'Open':'Not opened'}</span></div><div class="project-detail-body"><div class="project-detail-top"><span class="project-provider">${icon(p.provider==='gitlab'?'gitlab-mark':p.provider==='local'?'folder':'github-mark')} ${p.provider==='gitlab'?'GitLab':'GitHub'}</span><code>${esc(p.id==='manual'?'manual':p.id)}</code></div><h3>${esc(p.name)}</h3><code class="project-path">${esc(p.path)}</code><div class="project-meta"><span>${icon('branch')} ${esc(p.branch)}</span><span>${icon('harness')} ${esc(p.version)}</span><span>${total?`${projectHealth(p).h.fail} errors · ${projectHealth(p).h.warn} attention`:'health not checked'}</span></div><div class="project-checks">${checks}</div><div class="project-command"><div class="project-command-head"><span>Command for another console</span><button class="btn" type="button" data-project-copy="${p.id}">${icon('download')} Copy</button></div><code>${esc(command)}</code></div><div class="project-actions">${current?`<button class="btn" type="button" disabled>Already open</button>`:`<button class="btn primary" type="button" data-project-open="${p.id}">Open project</button>`}<span class="project-note">Only the mockup context changes; Git and files do not change.</span></div></div></section>`;
}
function projectList(){
  const cur=projectCurrent();
  return projectListAll().map(p=>{
    const current=p.name===project;
    return `<button type="button" class="project-row ${p.id===projectSelectedId?'on':''}" data-project-select="${p.id}"><span class="project-row-icon">${icon('folder')}</span><span class="project-row-main"><b>${esc(p.name)}</b><small>${esc(p.path)}</small><small>${esc(p.branch)} · ${esc(p.version)}</small></span><span class="project-pill ${current?'ok':'muted'}">${current?'Open':'Not opened'}</span></button>`;
  }).join('');
}
function projectPage(){
  const cur=projectCurrent();
  const {h,total}=projectHealth(cur);
  return `<div class="page-title project-title"><div><h1>Project</h1><p>Current project and safe context switching. Git and files do not change.</p><div class="home-facts"><span>${esc(cur.name)}</span><span>${esc(cur.branch)}</span><span>${esc(cur.version)}</span></div></div><div class="actions"><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div>
  <section class="panel current-project"><div class="current-project-icon">${icon('folder')}</div><div class="current-project-main"><span class="eyebrow">Current project</span><h2>${esc(cur.name)}</h2><code>${esc(cur.path)}</code><div class="current-project-meta">${icon('branch')} ${esc(cur.branch)} · ${icon(cur.provider==='gitlab'?'gitlab-mark':cur.provider==='local'?'folder':'github-mark')} ${esc(cur.repo)}</div></div><div class="current-project-stats"><div><span>Harness</span><b>${esc(cur.version)}</b></div><div><span>Skills</span><b>${cur.skills||'—'}</b></div><div><span>Managed</span><b>${cur.managed||'—'}</b></div><div><span>Health</span><b>${total?`${h.ok}/${total}`:'—'}</b></div></div></section>
  <div class="project-grid"><section class="panel projects-panel"><div class="panel-head"><h2>Projects</h2><span class="small muted">${projectListAll().length} found</span></div><div class="project-list">${projectList()}</div><div class="project-path-box"><label class="field">Path to another project<input id="project-path" value="${esc(projectPath)}" placeholder="/home/…/project"></label><div class="project-path-actions"><button class="btn" type="button" data-project-check>${icon('check')} Check path</button><span id="project-path-status">${esc(projectPathStatus)}</span></div><p class="project-hint">In the mockup, the path is checked without reading Git, branch, or .harness.</p></div></section><div id="project-detail">${projectDetail()}</div></div>`;
}
function checkProjectPath(){
  const input=$('#project-path');
  const path=(input?.value||projectPath).trim();
  projectPath=path;
  if(!path.startsWith('/')||path.length<2){
    projectManual=null;
    projectPathStatus='Enter an absolute path';
    projectSelectedId=projectCurrent().id;
    render();return;
  }
  const name=path.split('/').filter(Boolean).at(-1)||'project';
  projectManual={id:'manual',name,path,branch:'—',provider:'local',repo:'—',version:'—',installed:'—',skills:0,managed:0,drift:0,capability:'—',dirty:0,git:null,config:null,health:{ok:0,warn:0,fail:0,skipped:0}};
  projectSelectedId='manual';
  projectPathStatus='Path accepted (demo). Git, branch, and .harness were not checked.';
  render();
}
function openProject(id){
  const p=id==='manual'?projectManual:PROJECTS.find(x=>x.id===id);
  if(!p)return;
  project=p.name;
  branch=p.branch||'—';
  projectSelectedId=p.id;
  projectPath=p.path;
  projectPathStatus='';
  if(p.id!=='manual')projectManual=null;
  render();
  toast(`Context switched to ${p.name}; files did not change`);
}
function copyProjectCommand(p){
  const command=`cd ${p.path} && harness`;
  if(navigator.clipboard?.writeText){
    navigator.clipboard.writeText(command).then(()=>toast('Command copied')).catch(()=>{reader('Command for another console',command);toast('Copy the command manually')});
  }else{
    reader('Command for another console',command);
    toast('Copy the command manually');
  }
}

function workCounts(){return {all:WORK_SESSIONS.length,running:WORK_SESSIONS.filter(s=>s.status==='running').length,blocked:WORK_SESSIONS.filter(s=>s.status==='blocked').length,awaiting:WORK_SESSIONS.filter(s=>s.status==='awaiting').length}}
function workVisible(){
  return WORK_SESSIONS.filter(s=>(workFilter==='all'||s.status===workFilter)&&(workRole==='all'||s.role===workRole));
}
function ensureWorkSelection(){
  const rows=workVisible();
  if(!rows.some(s=>s.id===workSelected))workSelected=rows[0]?.id||null;
}
function workSession(){return WORK_SESSIONS.find(s=>s.id===workSelected)||null}
function workList(){
  const rows=workVisible();
  if(!rows.length)return '<div class="work-empty">No sessions with these filters.</div>';
  return rows.map(s=>`<button type="button" class="work-row ${s.id===workSelected?'on':''}" data-work-session="${s.id}"><span class="work-role">${icon(s.role)}</span><span class="work-row-main"><b>${s.id} · ${esc(s.title)}</b><small>${WORK_ROLES[s.role]} · ${esc(s.branch)}</small></span><span class="work-status ${s.tone}">${esc(s.statusLabel)}</span><span class="work-time">${esc(s.elapsed)}</span></button>`).join('');
}
function workRoute(){
  const s=workSession();
  if(!s)return '<section class="panel work-route-panel"><div class="work-empty">Select a session on the left.</div></section>';
  const current=s.steps.find(x=>x.state==='current')||s.steps[0];
  const flow=s.steps.map((step,i)=>{
    const edge=s.steps[i+1]?.state==='current'?'active':(step.state==='done'&&s.steps[i+1]?.state==='done'?'done':'');
    return `<div class="work-flow-node ${step.state} ${step.state==='current'?s.tone:''}"><span class="work-flow-icon">${icon(step.icon||step.name.toLowerCase())}</span><b>${step.name}</b><small>${step.label}</small></div>${i<s.steps.length-1?`<div class="work-flow-edge ${edge} ${edge==='active'?s.tone:''}"></div>`:''}`;
  }).join('');
  return `<section class="panel work-route-panel"><div class="panel-head"><h2>Session route ${s.id}</h2><span class="work-status ${s.tone}">${esc(s.statusLabel)}</span></div><div class="work-route-body"><div class="work-task-meta"><span>${icon(s.role)} ${WORK_ROLES[s.role]}</span><span class="branch-inline">${icon('branch')}<b>${esc(s.branch)}</b></span><span>${icon('clock')} ${esc(s.elapsed)} · start ${esc(s.started)}</span></div><div class="work-flow-scroll"><div class="work-flow">${flow}</div></div><div class="work-current ${s.tone}"><span>Current step</span><b>${current.name}</b><small>${current.label}</small></div><div class="work-route-actions"><button class="btn" type="button" data-work-open>Open the task</button><a class="btn" href="#orchestration">Orchestration ${icon('chevron')}</a></div></div></section>`;
}
function workEvents(){
  const s=workSession();
  if(!s)return '<div class="work-empty">No events.</div>';
  return s.events.map(e=>`<div class="work-event"><span class="work-event-time">${esc(e.time)}</span><span class="work-event-role">${icon(e.role)} ${WORK_ROLES[e.role]||e.role}</span><span class="work-event-main"><b>${esc(e.text)}</b><small>${esc(e.detail)}</small></span></div>`).join('');
}
function workKpis(){
  const k=WORK_METRICS.kpi;
  return `<div class="work-kpis"><div><span>Last event</span><b class="cyan">${esc(k.lastEvent)}</b><small>observable fact</small></div><div><span>Silence</span><b class="violet">${k.silence}</b><small>session silent</small></div><div><span>Step age</span><b class="blue">${esc(k.currentAge)}</b><small>Review · #555</small></div><div><span>Retries</span><b class="lavender">${k.retry}</b><small>for the current slice</small></div></div>`;
}
function workTabs(){
  const tabs=[['overview','Overview'],['timeline','Timeline'],['stats','Statistics']];
  return `<div class="orch-tabbar work-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${workTab===id?'on':''}" data-work-tab="${id}" role="tab" aria-selected="${workTab===id}">${label}</button>`).join('')}</div>`;
}
function workGantt(){
  const max=35;
  const ticks=[0,5,10,15,20,25,30];
  return `<section class="panel work-analytics"><div class="panel-head"><h2>Timeline</h2><span class="small muted">past and current step · no internal reasoning</span></div><div class="work-gantt"><div class="work-gantt-axis"><span></span><div class="work-gantt-ticks">${ticks.map(t=>`<span style="left:${t/max*100}%">${t}m</span>`).join('')}</div><span>last</span></div>${WORK_METRICS.timeline.map(row=>`<div class="work-gantt-row"><div class="work-gantt-name"><b>${row.id}</b><small>${row.total}</small></div><div class="work-gantt-track">${row.segments.map(s=>`<div class="work-gantt-seg ${s.tone}" style="left:${s.from/max*100}%;width:${(s.to-s.from)/max*100}%" title="${esc(s.label)} · ${s.from}–${s.to} min"><span>${s.label}</span></div>`).join('')}</div><div class="work-gantt-last ${row.silent?'silent':''}">${row.silent?'silence':''} ${esc(row.last)}</div></div>`).join('')}</div><div class="orch-legend"><span><i class="mint"></i>done</span><span><i class="cyan"></i>active</span><span><i class="blue"></i>waiting</span><span><i class="violet"></i>blocked</span></div></section>`;
}
function workRateChart(){
  const d=WORK_METRICS.rate,max=6,W=760,H=170,L=28,R=10,T=12,B=24;
  const x=i=>L+i*(W-L-R)/23,y=v=>T+(max-v)/max*(H-T-B);
  const pts=d.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const base=y(0);
  const area=`M ${x(0).toFixed(1)} ${base} L ${pts.split(' ').join(' L ')} L ${x(23).toFixed(1)} ${base} Z`;
  return `<div class="work-rate-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Events per minute over the last hour"><defs><linearGradient id="work-rate-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#70c2d8" stop-opacity=".25"/><stop offset="1" stop-color="#70c2d8" stop-opacity="0"/></linearGradient></defs>${[0,2,4,6].map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" class="work-rate-grid"/><text x="${L-5}" y="${y(v)+3}" text-anchor="end" class="work-rate-axis">${v}</text>`).join('')}${[0,15,30,45,60].map(m=>`<text x="${L+(m/60)*(W-L-R)}" y="${H-7}" text-anchor="middle" class="work-rate-axis">${m}m</text>`).join('')}<path d="${area}" fill="url(#work-rate-fill)"/><polyline points="${pts}" class="work-rate-line"/><circle cx="${x(23)}" cy="${y(d[23])}" r="3" class="work-rate-dot"/></svg></div>`;
}
function workStats(){
  const m=WORK_METRICS;
  const maxType=Math.max(...m.eventTypes.map(x=>x.count));
  const maxRole=Math.max(...m.roles.map(x=>x.count));
  const maxAge=Math.max(...m.stageAge.map(x=>x.p95));
  const maxRetry=Math.max(...m.retries.map(x=>x.count));
  return `<section class="panel work-analytics"><div class="panel-head"><h2>Statistics</h2><span class="small muted">last-hour snapshot · events only</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Events per minute</h3><span>${m.kpi.rate}</span></div>${workRateChart()}</article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Event types</h3><span>per hour</span></div>${m.eventTypes.map(x=>`<div class="work-stat-row"><span>${esc(x.label)}</span>${orchBar(x.count,maxType,x.tone)}<b>${x.count}</b></div>`).join('')}</article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Role load</h3><span>active sessions</span></div>${m.roles.map(x=>`<div class="work-stat-row"><span>${esc(x.label)}</span>${orchBar(x.count,maxRole,x.tone)}<b>${x.count}</b></div>`).join('')}</article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Step age vs p50/p95</h3><span>minutes</span></div>${m.stageAge.map(x=>`<div class="work-stage-age"><span>${esc(x.stage)}</span><div class="work-age-bars"><div>${orchBar(x.current,maxAge,'blue')}<small>${x.current}</small></div><div>${orchBar(x.p50,maxAge,'cyan')}<small>${x.p50}</small></div><div>${orchBar(x.p95,maxAge,'violet')}<small>${x.p95}</small></div></div></div>`).join('')}<div class="orch-legend"><span><i class="blue"></i>current</span><span><i class="cyan"></i>p50</span><span><i class="violet"></i>p95</span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Retry</h3><span>${m.retries.reduce((n,x)=>n+x.count,0)} returns</span></div>${m.retries.map(x=>`<div class="work-stat-row"><span>${esc(x.label)}</span>${orchBar(x.count,maxRetry,x.tone)}<b>${x.count}</b></div>`).join('')}<p class="orch-note">Return reasons are recorded from observed data only.</p></article>
  </div></section>`;
}

function workSources(){
  return `<section class="panel work-sources"><div class="panel-head"><h2>Step sources</h2><span class="small muted">observable data</span></div><div class="work-source-grid">${WORK_SOURCES.map(x=>`<div class="work-source ${x.kind}"><span>${icon(x.kind==='plain'?'terminal':'activity')}</span><div><b>${esc(x.name)}</b><small>${esc(x.detail)}</small></div><em class="orch-pill ${x.tone}">${esc(x.label)}</em>${x.kind==='plain'?`<button class="btn" type="button" data-work-codex>${icon('terminal')} Log tail</button>`:''}</div>`).join('')}</div></section>`;
}

function workOverview(){
  const c=workCounts();
  return `${workSources()}<div class="work-grid"><section class="panel work-sessions"><div class="panel-head"><h2>Sessions</h2><span class="small muted" id="work-count">${workVisible().length} of ${c.all}</span></div><div class="work-filters"><div class="chips">${workChips()}</div><select id="work-role" aria-label="Filter by role"><option value="all">All roles</option><option value="architect">Architect</option><option value="developer">Developer</option><option value="review">Review</option><option value="qa">QA</option></select></div><div id="work-list">${workList()}</div><div class="work-note">Observed events only; a missing event does not prove a stop.</div></section><div id="work-route">${workRoute()}</div></div><section class="panel work-events-panel"><div class="panel-head"><h2>Session events <span id="work-events-id">${workSelected||'—'}</span></h2><span class="small muted">observable facts</span></div><div id="work-events">${workEvents()}</div></section>`;
}
function workTabContent(){
  if(workTab==='timeline')return workGantt();
  if(workTab==='stats')return workStats();
  return workOverview();
}
function workChips(){
  const c=workCounts();
  return ['all','running','blocked','awaiting'].map(key=>{const label=key==='all'?'All':key==='running'?'Running':key==='blocked'?'Blocked':'Waiting';return `<button class="chip ${workFilter===key?'on':''}" type="button" data-work-status="${key}" aria-pressed="${workFilter===key}">${label} ${c[key]}</button>`}).join('');
}
function refreshWorkView(){
  const view=$('#work-view');if(!view)return;
  view.innerHTML=workTabContent();
  bindWork();
}

function workPage(){
  const c=workCounts();
  return `<div class="page-title work-title"><div><h1>Activity</h1><p>Observed steps, roles, and events. Internal reasoning is not shown.</p><div class="home-facts"><span>${c.all} sessions</span><span>${c.running} running</span><span>${c.blocked} blocked</span><span>${c.awaiting} awaiting a decision</span><span id="work-updated">${fmtClock(workUpdatedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-work-refresh>${icon('refresh')} Update</button><a class="btn" href="#orchestration">${icon('orchestration')} Orchestration</a></div></div>
  <div class="work-summary"><div><span>Sessions</span><b>${c.all}</b><small>under observation</small></div><div><span>Running</span><b class="ok">${c.running}</b><small>live step</small></div><div><span>Blocked</span><b class="err">${c.blocked}</b><small>decision needed</small></div><div><span>Awaiting decision</span><b class="warn">${c.awaiting}</b><small>next step not started</small></div></div>
  ${workKpis()}
  ${workTabs()}
  <div id="work-view">${workTab==='overview'?workOverview():workTabContent()}</div>`;
}
function bindWork(){
  document.querySelectorAll('[data-work-status]').forEach(btn=>{const on=btn.dataset.workStatus===workFilter;btn.classList.toggle('on',on);btn.setAttribute('aria-pressed',String(on))});
  const sel=$('#work-role');if(sel)sel.value=workRole;
  document.querySelectorAll('[data-work-tab]').forEach(btn=>{const on=btn.dataset.workTab===workTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshWork(){
  ensureWorkSelection();
  const list=$('#work-list');if(list)list.innerHTML=workList();
  const route=$('#work-route');if(route)route.innerHTML=workRoute();
  const events=$('#work-events');if(events)events.innerHTML=workEvents();
  const count=$('#work-count');if(count)count.textContent=`${workVisible().length} of ${workCounts().all}`;
  const eid=$('#work-events-id');if(eid)eid.textContent=workSelected||'—';
  bindWork();
}

function reportsCounts(){
  return {all:REPORTS.length,passed:REPORTS.filter(r=>r.status==='passed').length,attention:REPORTS.filter(r=>r.status==='attention').length,blocked:REPORTS.filter(r=>r.status==='blocked').length};
}
function reportsVisible(){
  const q=reportQuery.trim().toLowerCase();
  return REPORTS.filter(r=>(reportFilter==='all'||r.type===reportFilter)&&(reportStatus==='all'||r.status===reportStatus)&&(!q||[r.title,r.session,r.role,r.summary,r.conclusion].join(' ').toLowerCase().includes(q)));
}
function ensureReportSelection(){
  const rows=reportsVisible();
  if(!rows.some(r=>r.id===reportSelected))reportSelected=rows[0]?.id||null;
}
function reportSelectedItem(){return REPORTS.find(r=>r.id===reportSelected)||null}
function reportTypeIcon(type){return REPORT_TYPES[type]?.icon||'reports'}
function reportTypeLabel(type){return REPORT_TYPES[type]?.label||type}
function reportList(){
  const rows=reportsVisible();
  if(!rows.length)return '<div class="report-empty">No reports with these filters.</div>';
  return rows.map(r=>`<button type="button" class="report-row ${r.id===reportSelected?'on':''}" data-report-select="${r.id}"><span class="report-type-icon">${icon(reportTypeIcon(r.type))}</span><span class="report-row-main"><b>${esc(r.title)}</b><small>${esc(r.session)} · ${esc(r.role)} · ${esc(r.typeLabel)}</small></span><span class="report-status ${r.status}">${esc(r.statusLabel)}</span><span class="report-time">${esc(r.created)}</span></button>`).join('');
}
function reportDetail(){
  const r=reportSelectedItem();
  if(!r)return '<section class="panel report-detail-panel"><div class="report-empty">Select a report on the left.</div></section>';
  const evidence=(r.evidence||[]).map(e=>`<button class="report-evidence" type="button" data-report-evidence="${esc(e.name)}"><span class="report-evidence-icon ${e.status}">${icon(e.status==='passed'?'check':e.status==='blocked'?'x':'warning')}</span><span><b>${esc(e.name)}</b><small>${esc(e.detail)}</small></span><span class="report-evidence-state ${e.status}">${e.status==='passed'?'ok':e.status==='blocked'?'blocked':'attention'}</span></button>`).join('');
  return `<section class="panel report-detail-panel"><div class="panel-head"><h2>Report details</h2><span class="report-status ${r.status}">${esc(r.statusLabel)}</span></div><div class="report-detail-body"><div class="report-detail-top"><span class="report-type-label">${icon(reportTypeIcon(r.type))} ${esc(r.typeLabel)}</span><code>${esc(r.id)}</code></div><h3>${esc(r.title)}</h3><div class="report-meta"><span>${esc(r.session)}</span><span>${esc(r.role)}</span><span>${esc(r.created)}</span></div><p class="report-summary">${esc(r.summary)}</p><div class="report-evidence-head">Evidence</div><div class="report-evidences">${evidence}</div><div class="report-conclusion ${r.status}">${icon(r.status==='passed'?'check':r.status==='blocked'?'x':'warning')}<p>${esc(r.conclusion)}</p></div><div class="report-actions"><button class="btn primary" type="button" data-report-open>${icon('reports')} Open report</button><a class="btn" href="#orchestration">Orchestration ${icon('chevron')}</a></div></div></section>`;
}
function qaLane(variant=''){
  return `<section class="panel qa-lane-panel ${variant}"><div class="panel-head"><h2>QA lane · #716</h2><span class="small muted">2 attempts · 1 defect</span></div><div class="qa-lane"><div class="qa-attempt fail"><span class="qa-attempt-num">01</span><b>Worker exit</b><small>readiness timeout · evidence missing</small><span class="qa-attempt-state">fail</span></div><span class="qa-arrow">→</span><div class="qa-attempt pass"><span class="qa-attempt-num">02</span><b>Bounded restart</b><small>receipt accepted · ready for review</small><span class="qa-attempt-state">pass</span></div><span class="qa-arrow">→</span><div class="qa-attempt wait"><span class="qa-attempt-num">03</span><b>Publish</b><small>blocked by QA evidence</small><span class="qa-attempt-state">wait</span></div></div></section>`;
}
function reportKpis(){
  const k=REPORT_METRICS.kpi;
  return `<div class="report-kpis"><div><span>Evidence completeness</span><b class="cyan">${k.completeness}%</b><small>required vs present</small></div><div><span>Stale evidence</span><b class="violet">${k.stale}</b><small>cannot be considered current</small></div><div><span>Report latency p50</span><b class="blue">${esc(k.latency)}</b><small>dispatch → report</small></div><div><span>First-pass</span><b class="mint">${esc(k.firstPass)}</b><small>without a re-run</small></div></div>`;
}
function reportTabs(){
  const tabs=[['list','Reports'],['evidence','Evidence'],['quality','Quality'],['readiness','Readiness']];
  return `<div class="orch-tabbar report-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${reportTab===id?'on':''}" data-report-tab="${id}" role="tab" aria-selected="${reportTab===id}">${label}</button>`).join('')}</div>`;
}
function reportOverview(){
  const c=reportsCounts();
  const typeChip=(key,label)=>`<button class="chip ${reportFilter===key?'on':''}" type="button" data-report-type="${key}" aria-pressed="${reportFilter===key}">${label}</button>`;
  return `<div class="reports-grid"><section class="panel reports-panel"><div class="panel-head"><h2>Reports</h2><span class="small muted" id="reports-count">${reportsVisible().length} of ${c.all}</span></div><div class="report-filters"><div class="chips">${typeChip('all','All')}${typeChip('qa','QA')}${typeChip('review','Review')}${typeChip('developer','Developer')}${typeChip('health','Health')}${typeChip('publish','Publish')}</div><div class="report-filter-row"><select id="report-status" aria-label="Report status"><option value="all">All statuses</option><option value="passed">Passed</option><option value="attention">Attention</option><option value="blocked">Blocked</option></select><label class="report-search">${icon('search')}<input id="reports-search" type="search" placeholder="Find report" value="${esc(reportQuery)}" aria-label="Report search"></label></div></div><div id="report-list">${reportList()}</div><div class="report-list-foot">Reports do not replace the decision; evidence is available in the details.</div></section><div id="report-detail">${reportDetail()}</div></div>${qaLane()}`;
}
function reportEvidence(){
  const m=REPORT_METRICS;
  const stateMark=s=>s==='present'?'✓':s==='stale'?'!':s==='missing'?'—':'·';
  const complete=row=>row.items.filter(x=>x.state==='present').length;
  return `<section class="panel report-analytics"><div class="orch-analytics-head"><h2>Evidence</h2><span>present / stale / missing</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Coverage by report</h3><span>required artifacts</span></div><div class="report-evidence-matrix"><div class="report-evidence-head"><span>report</span>${m.columns.map(c=>`<span>${esc(c)}</span>`).join('')}</div>${m.evidence.map(row=>`<div class="report-evidence-row"><b>${esc(row.label)}</b>${row.items.map(item=>`<span class="report-evidence-cell ${item.state}" title="${esc(item.name)}: ${item.state}">${stateMark(item.state)}</span>`).join('')}</div>`).join('')}</div><div class="orch-legend"><span><i class="mint"></i>present</span><span><i class="lavender"></i>stale</span><span><i class="muted"></i>missing</span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Completeness</h3><span>present / 5</span></div>${m.evidence.map(row=>{const n=complete(row);return `<div class="report-complete-row"><span>${esc(row.label)}</span>${orchBar(n,5,n===5?'mint':'lavender')}<b>${n} / 5</b></div>`}).join('')}<p class="orch-note">Stale evidence stays visible but does not count as current proof.</p></article>
  </div></section>`;
}
function reportQuality(){
  const q=REPORT_METRICS.quality;
  const maxF=Math.max(...q.findings.map(x=>x.count));
  const maxL=Math.max(...q.latency.map(x=>x.p95));
  const stateLabel=s=>s==='pass'?'pass':s==='fail'?'fail':s==='wait'?'wait':s==='blocked'?'blocked':'current';
  return `<section class="panel report-analytics"><div class="orch-analytics-head"><h2>Quality</h2><span>findings · versions · latency</span></div><div class="orch-analytics-grid">
    <article class="orch-chart"><div class="orch-chart-head"><h3>Findings by severity</h3><span>${q.findings.reduce((n,x)=>n+x.count,0)} findings</span></div>${q.findings.map(x=>`<div class="work-stat-row"><span>${esc(x.label)}</span>${orchBar(x.count,maxF,x.tone)}<b>${x.count}</b></div>`).join('')}</article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>First-pass acceptance</h3><span>reports</span></div><div class="report-firstpass"><b>${q.firstPass.passed} / ${q.firstPass.total}</b>${orchBar(q.firstPass.passed,q.firstPass.total,'mint')}<small>accepted without a re-run</small></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Report versions</h3><span>attempts / revisions</span></div>${q.versions.map(v=>`<div class="report-version-row"><b>${esc(v.report)}</b><div class="report-version-steps">${v.steps.map((s,i)=>`<span class="report-version-step ${s.state}"><i></i>${esc(s.label)}</span>${i<v.steps.length-1?'<em>→</em>':''}`).join('')}</div></div>`).join('')}</article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Report latency p50 / p95</h3><span>minutes</span></div>${q.latency.map(x=>`<div class="report-latency-row"><span>${esc(x.type)}</span><div class="work-age-bars"><div>${orchBar(x.p50,maxL,'cyan')}<small>${x.p50}</small></div><div>${orchBar(x.p95,maxL,'violet')}<small>${x.p95}</small></div></div></div>`).join('')}<div class="orch-legend"><span><i class="cyan"></i>p50</span><span><i class="violet"></i>p95</span></div></article>
  </div></section>`;
}
function reportReadiness(){
  const r=REPORT_METRICS;
  return `<section class="panel report-analytics"><div class="orch-analytics-head"><h2>Readiness</h2><span>Release Gate · publish blockers</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Release Gate</h3><span>candidate / target / tree</span></div><div class="report-ready-table"><div class="report-ready-head"><span>candidate</span><span>target</span><span>tree</span><span>QA</span><span>verdict</span><span>blocker</span></div>${r.readiness.map(x=>`<div class="report-ready-row"><b>${esc(x.candidate)}</b><span>${esc(x.target)}</span><span class="orch-pill ${x.tree==='match'?'mint':x.tree==='mismatch'?'violet':'blue'}">${esc(x.tree)}</span><span>${esc(x.qa)}</span><span class="orch-pill ${x.verdict==='pending'?'blue':x.verdict==='blocked'?'lavender':'violet'}">${esc(x.verdict)}</span><small>${esc(x.blocker)}</small></div>`).join('')}</div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Publish blockers</h3><span>${r.blockers.length} in queue</span></div><div class="report-blockers">${r.blockers.map(x=>`<div><span>${esc(x.label)}</span><b class="orch-pill ${x.tone}">${esc(x.why)}</b></div>`).join('')}</div></article>
  </div></section>`;
}
function reportTabContent(){
  if(reportTab==='evidence')return reportEvidence();
  if(reportTab==='quality')return reportQuality();
  if(reportTab==='readiness')return reportReadiness();
  return reportOverview();
}
function refreshReportView(){
  const view=$('#reports-view');if(!view)return;
  view.innerHTML=reportTabContent();
  bindReports();
}

function reportsPage(){
  const c=reportsCounts();
  return `<div class="page-title reports-title"><div><h1>Reports</h1><p>Role results, QA evidence, and events. Reports are kept separate from human decisions.</p><div class="home-facts"><span>${c.all} reports</span><span>${c.passed} passed</span><span>${c.attention} attention</span><span>${c.blocked} blocked</span><span id="reports-updated">${fmtClock(reportUpdatedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-report-refresh>${icon('refresh')} Update</button><button class="btn" type="button" data-report-export>${icon('download')} Export</button></div></div>
  <div class="reports-summary"><div><span>Reports</span><b>${c.all}</b><small>in selection</small></div><div><span>Passed</span><b class="ok">${c.passed}</b><small>evidence present</small></div><div><span>Attention</span><b class="warn">${c.attention}</b><small>review needed</small></div><div><span>Blocked</span><b class="err">${c.blocked}</b><small>human decision</small></div></div>
  ${reportKpis()}
  ${reportTabs()}
  <div id="reports-view">${reportTab==='list'?reportOverview():reportTabContent()}</div>`;
}
function bindReports(){
  document.querySelectorAll('[data-report-type]').forEach(btn=>{const on=btn.dataset.reportType===reportFilter;btn.classList.toggle('on',on);btn.setAttribute('aria-pressed',String(on))});
  const sel=$('#report-status');if(sel)sel.value=reportStatus;
  document.querySelectorAll('[data-report-tab]').forEach(btn=>{const on=btn.dataset.reportTab===reportTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshReports(){
  ensureReportSelection();
  const list=$('#report-list');if(list)list.innerHTML=reportList();
  const detail=$('#report-detail');if(detail)detail.innerHTML=reportDetail();
  const count=$('#reports-count');if(count)count.textContent=`${reportsVisible().length} of ${reportsCounts().all}`;
  bindReports();
}
function openReport(){
  const r=reportSelectedItem();if(!r)return;
  reader(r.title,`DEMO · REPORT\n\n${r.title}\n${r.session} · ${r.role} · ${r.created}\n\n${r.summary}\n\n${r.conclusion}\n\nEvidence:\n${r.evidence.map(e=>`- ${e.name}: ${e.detail} (${e.status})`).join('\n')}`);
  toast('Report opened; the data is demo data');
}
function exportReports(){
  const rows=reportsVisible();
  const payload={generatedAt:new Date().toISOString(),snapshotAt:reportUpdatedAt.toISOString(),demo:true,filter:reportFilter,status:reportStatus,query:reportQuery,reports:rows.map(r=>({id:r.id,type:r.type,title:r.title,session:r.session,role:r.role,status:r.status,created:r.created,summary:r.summary,conclusion:r.conclusion,evidence:r.evidence}))};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`harness-reports-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast(`Reports exported: ${rows.length}`);
}

function orchCounts(){
  return {batches:ORCH_BATCHES.length,dispatches:ORCH_DISPATCHES.length,active:ORCH_DISPATCHES.filter(d=>d.status==='working'||d.status==='awaiting').length,attention:ORCH_DISPATCHES.filter(d=>d.status==='attention').length};
}
function orchVisibleDispatches(){
  return ORCH_DISPATCHES.filter(d=>(orchRole==='all'||d.role===orchRole)&&(orchStatus==='all'||d.status===orchStatus));
}
function orchFlow(){
  const c=orchCounts();
  const nodes=[
    ['orchestration','Batch',String(c.batches),'1 in progress','active'],
    ['branch','Dispatch',String(c.dispatches),'2 active','active'],
    ['developer','Roles','4','architect · developer · review · qa','pending'],
    ['qa','QA',String(c.attention),'needs attention','warn'],
    ['pr','PR','blocked','candidate SHA needed','blocked']
  ];
  return `<section class="panel orch-flow-panel"><div class="panel-head"><h2>Pipeline</h2><span class="small muted">batch → dispatch → roles → QA → PR</span></div><div class="orch-flow">${nodes.map(([ic,label,value,sub,state],i)=>`<div class="orch-node ${state}"><span class="orch-node-icon">${icon(ic)}</span><b>${label}</b><strong>${value}</strong><small>${sub}</small></div>${i<nodes.length-1?`<div class="orch-edge ${i<2?'active':''}"></div>`:''}`).join('')}</div></section>`;
}
function orchBatchCards(){
  return `<div class="orch-batches">${ORCH_BATCHES.map(b=>`<article class="panel orch-batch ${b.status}"><div class="orch-batch-head"><span class="orch-batch-id">${b.id}</span><span class="orch-status ${b.status==='attention'?'err':b.status==='awaiting'?'warn':'ok'}">${b.statusLabel}</span></div><h3>${b.session} · ${esc(b.title)}</h3><div class="orch-batch-meta">${icon(b.role)} ${ORCH_ROLES[b.role]} · heartbeat ${b.heartbeat}</div><div class="orch-mini">${b.steps.map((s,i)=>`<span class="orch-mini-step ${s}" title="${['Architect','Developer','Review','QA','PR'][i]}"></span>`).join('')}</div><div class="orch-batch-foot"><span>${b.dispatch} · ${esc(b.heartbeat)}</span><a href="#agent-activity">Progress ${icon('chevron')}</a></div></article>`).join('')}</div>`;
}
function orchDispatchList(){
  const rows=orchVisibleDispatches();
  if(!rows.length)return '<div class="orch-empty">No dispatches with these filters.</div>';
  return rows.map(d=>`<div class="orch-dispatch-row"><span class="orch-role">${icon(d.role)}</span><span class="orch-dispatch-main"><b>${d.id} · ${d.session}</b><small>${d.batch} · ${esc(d.task)}</small></span><span class="orch-status ${d.status==='attention'?'err':d.status==='awaiting'?'warn':'ok'}">${d.statusLabel}</span><span class="orch-heartbeat">${d.heartbeat}</span><a class="orch-link" href="#agent-activity">Progress ${icon('chevron')}</a></div>`).join('');
}
function orchMap(){
  const at=i=>ORCH_BATCHES.find(b=>b.steps[i]==='current');
  const roleStatus=s=>{
    if(!s)return {cls:'idle',chip:'—',count:0};
    const cls=s.status==='attention'?'err':s.status==='awaiting'?'warn':'active';
    return {cls,chip:s.session,count:1};
  };
  const arch=roleStatus(at(0)),dev=roleStatus(at(1)),rev=roleStatus(at(2)),qa=roleStatus(at(3));
  const statusCounts={working:ORCH_BATCHES.filter(b=>b.status==='working').length,attention:ORCH_BATCHES.filter(b=>b.status==='attention').length,awaiting:ORCH_BATCHES.filter(b=>b.status==='awaiting').length};
  const node=(x,y,w,h,type,cls,title,sub1,sub2,chip,count)=>{
    const prefix=chip?`${esc(chip)} · `:'';
    const sub2Text=sub2?`<tspan x="${x+14}" dy="11">${esc(sub2)}</tspan>`:'';
    return `<g class="orch-map-node ${type} ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7" class="orch-map-bg"></rect><rect x="${x}" y="${y+9}" width="3" height="${h-18}" rx="1.5" class="orch-map-accent"></rect><text class="orch-map-title" x="${x+14}" y="${y+21}">${esc(title)}</text><text class="orch-map-sub" x="${x+14}" y="${y+36}">${prefix}${esc(sub1)}${sub2Text}</text><g class="orch-map-count ${count?'on':''}"><circle cx="${x+w-12}" cy="${y+11}" r="8"></circle><text x="${x+w-12}" y="${y+14}" text-anchor="middle">${count}</text></g></g>`;
  };
  return `<section class="panel orch-map-panel"><div class="panel-head"><h2>Pipeline</h2><span class="small muted">grouped flow · current tasks in nodes</span></div><div class="orch-map-statusbar"><span class="ok"><b>${statusCounts.working}</b> in progress</span><span class="err"><b>${statusCounts.attention}</b> blocked</span><span class="warn"><b>${statusCounts.awaiting}</b> waiting</span><span class="muted"><b>0</b> QA</span><span class="muted">${statusCounts.working+statusCounts.attention+statusCounts.awaiting} tasks in the pipeline</span></div><div class="orch-map-scroll"><svg class="orch-map" viewBox="0 0 1200 416" role="img" aria-label="Grouped pipeline: plan and approve, build and review with findings, evidence and publish">
    <title>Orchestration pipeline</title>
    <defs>
      <marker id="om-aqua" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#7fc9bb"/></marker>
      <marker id="om-sky" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#70c2d8"/></marker>
      <marker id="om-rose" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#b79ae8"/></marker>
      <marker id="om-orange" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#6f9fe0"/></marker>
      <marker id="om-gray" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#8793a3"/></marker>
    </defs>

    <g class="orch-group violet"><rect x="20" y="24" width="220" height="372" rx="8" class="orch-group-bg"></rect><text class="orch-group-label" x="36" y="44">01 · PLAN &amp; APPROVE</text><line x1="20" y1="56" x2="240" y2="56" class="orch-group-line"/></g>
    <g class="orch-group sky"><rect x="260" y="24" width="560" height="372" rx="8" class="orch-group-bg"></rect><text class="orch-group-label" x="276" y="44">02 · BUILD / REVIEW + FINDINGS</text><line x1="260" y1="56" x2="820" y2="56" class="orch-group-line"/></g>
    <g class="orch-group peach"><rect x="840" y="24" width="340" height="372" rx="8" class="orch-group-bg"></rect><text class="orch-group-label" x="856" y="44">03 · EVIDENCE &amp; PUBLISH</text><line x1="840" y1="56" x2="1180" y2="56" class="orch-group-line"/></g>

    ${node(40,80,180,58,'human','done','Approve plan','human gate · approved','before implementation','',0)}
    ${node(280,80,220,52,'role',arch.cls,'Architect','task analysis','',arch.chip,arch.count)}
    ${node(280,145,220,52,'role',dev.cls,'Developer','context + TDD','',dev.chip,dev.count)}
    ${node(280,210,220,52,'role',rev.cls,'Code review','base freshness · 2 eyes','',rev.chip,rev.count)}
    ${node(280,275,220,52,'role',qa.cls,'QA · clean-room','pinned SHA','',qa.chip,qa.count)}
    ${node(540,210,240,52,'exception','review','Review findings','back to Developer','', '',0)}
    ${node(540,275,240,52,'exception','qa','QA findings','retry / defect','', '',0)}
    ${node(860,80,280,52,'human','wait','Approve QA','human gate','final diff','',0)}
    ${node(860,145,280,52,'coord','wait','Final report','evidence + decision','','',0)}
    ${node(860,210,280,52,'coord','blocked','Publish','accepted SHA','','',0)}
    ${node(860,275,280,52,'human','blocked','/to-pull-requests','human handoff','triggered by a human','',0)}

    <path class="orch-map-edge aqua active" d="M220 109H280" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge aqua" d="M390 132V145" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge sky" d="M390 197V210" marker-end="url(#om-sky)"/>
    <path class="orch-map-edge aqua" d="M390 262V275" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge rose" d="M500 236H540" marker-end="url(#om-rose)"/>
    <path class="orch-map-edge rose" d="M500 301H540" marker-end="url(#om-rose)"/>
    <path class="orch-map-edge rose dashed" d="M540 236H520V160H500" marker-end="url(#om-rose)"/>
    <path class="orch-map-edge rose dashed" d="M540 301H510V205H440V197" marker-end="url(#om-rose)"/>
    <path class="orch-map-edge aqua" d="M390 327V350H800V106H860" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge orange dashed" d="M780 301H810V171H860" marker-end="url(#om-orange)"/>
    <path class="orch-map-edge aqua" d="M1000 132V145" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge aqua" d="M1000 197V210" marker-end="url(#om-aqua)"/>
    <path class="orch-map-edge aqua" d="M1000 262V275" marker-end="url(#om-aqua)"/>









  </svg></div></section>`;
}
function orchBar(value,max,tone='cyan'){
  const pct=max>0?Math.round((value/max)*100):0;
  return `<span class="orch-bar"><i class="${tone}" style="width:${value?Math.max(3,pct):0}%"></i></span>`;
}
function orchStack(items,total,toneFallback='muted'){
  const sum=total||items.reduce((n,x)=>n+x.value,0)||1;
  return `<div class="orch-stack">${items.filter(x=>x.value>0).map(x=>`<i class="${x.tone||toneFallback}" style="width:${Math.round(x.value/sum*100)}%" title="${esc(x.label)}: ${x.value}"></i>`).join('')}</div>`;
}
function orchLegend(items){
  return `<div class="orch-legend">${items.map(x=>`<span><i class="${x.tone||'muted'}"></i>${esc(x.label)}<b>${x.value}</b></span>`).join('')}</div>`;
}
function orchTabs(){
  const tabs=[['map','Schema'],['flow','Flow'],['quality','Quality'],['runtime','Runtime'],['gates','Gates']];
  return `<div class="orch-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${orchTab===id?'on':''}" data-orch-tab="${id}" role="tab" aria-selected="${orchTab===id}">${label}</button>`).join('')}</div>`;
}
function orchKpis(){
  const k=ORCH_METRICS.kpi;
  return `<div class="orch-kpis"><div><span>In progress / oldest</span><b>${k.wip} / ${esc(k.oldest)}</b><small>2 active + 1 blocked</small></div><div><span>Rework</span><b class="violet">${esc(k.rework)}</b><small>at least one retry</small></div><div><span>QA on first pass</span><b class="lavender">${esc(k.qaFirst)}</b><small>first QA run</small></div><div><span>Stale + unknown</span><b class="blue">${k.stale} + ${k.unknown}</b><small>dispatch / execution</small></div><div><span>Flow efficiency</span><b class="mint">${k.flowEfficiency}%</b><small>active / lead time</small></div></div>`;
}
function orchFlowTab(){
  const f=ORCH_METRICS.flow;
  const maxP95=Math.max(...f.stageTimes.map(x=>x.p95));
  const maxQueue=Math.max(...f.queue.map(x=>x.value));
  return `<section class="panel orch-analytics"><div class="orch-analytics-head"><h2>Flow</h2><span>snapshot, not a trend</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>In progress by state</h3><span>${f.states.reduce((n,x)=>n+x.value,0)} batches</span></div>${orchStack(f.states)}${orchLegend(f.states)}<p class="orch-note">A snapshot of current WIP; history appears once the runtime store accumulates.</p></article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Work aging</h3><span> oldest ${esc(f.aging.reduce((a,b)=>a.oldest.localeCompare(b.oldest)>0?a:b).oldest)}</span></div><div class="orch-aging-head"><span></span><span>&lt;15m</span><span>15–60m</span><span>1–4h</span><span>&gt;4h</span></div>${f.aging.map(x=>`<div class="orch-aging-row"><span>${esc(x.stage)}</span>${x.buckets.map((v,i)=>`<span class="orch-aging-cell ${v?'on':''} t${i}">${v||''}</span>`).join('')}<small>${esc(x.oldest)}</small></div>`).join('')}</article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Cycle time p50 / p95</h3><span>minutes</span></div>${f.stageTimes.map(x=>`<div class="orch-stage-row"><span>${esc(x.stage)}</span><div class="orch-stage-bars"><div>${orchBar(x.p50,maxP95,'cyan')}<small>${x.p50}</small></div><div>${orchBar(x.p95,maxP95,'violet')}<small>${x.p95}</small></div></div></div>`).join('')}<div class="orch-legend"><span><i class="cyan"></i>p50</span><span><i class="violet"></i>p95</span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Waiting</h3><span>p50, minutes</span></div>${f.queue.map(x=>`<div class="orch-queue-row"><span>${esc(x.label)}</span>${orchBar(x.value,maxQueue,'blue')}<b>${x.value}</b></div>`).join('')}</article>
    <article class="orch-chart wide orch-mini-flow"><div><span>Completed</span><b>${f.throughput.completed}</b><small>${esc(f.throughput.window)} · demo</small></div><div><span>Flow efficiency</span><b>${ORCH_METRICS.kpi.flowEfficiency}%</b>${orchBar(ORCH_METRICS.kpi.flowEfficiency,100,'mint')}<small>active / lead time</small></div><div><span>Oldest</span><b>${esc(ORCH_METRICS.kpi.oldest)}</b><small>Code review · #555</small></div></article>
  </div></section>`;
}
function orchQualityTab(){
  const q=ORCH_METRICS.quality;
  const maxRetry=Math.max(...q.retries.map(x=>x.count));
  const verifyTotal=q.verification.reduce((n,x)=>n+x.value,0);
  return `<section class="panel orch-analytics"><div class="orch-analytics-head"><h2>Quality</h2><span>rework and evidence</span></div><div class="orch-analytics-grid">
    <article class="orch-chart"><div class="orch-chart-head"><h3>Retries by reason</h3><span>${q.retries.reduce((n,x)=>n+x.count,0)} returns</span></div>${q.retries.map(x=>`<div class="orch-retry-row"><span>${esc(x.label)}</span>${orchBar(x.count,maxRetry,x.tone)}<b>${x.count}</b><small>${esc(x.route)}</small></div>`).join('')}<div class="orch-findings"><span>review findings</span>${q.findings.map(x=>`<b class="${x.tone}">${esc(x.label)} ${x.count}</b>`).join('')}</div><p class="orch-note">Review and QA rework is counted separately; unknown requires a human.</p></article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Returns and first-pass</h3><span>share</span></div><div class="orch-return-grid"><div><span>Review → Developer</span><b>${q.review.returned} / ${q.review.total}</b>${orchBar(q.review.returned,q.review.total,'violet')}</div><div><span>QA → Developer</span><b>${q.qa.returned} / ${q.qa.total}</b>${orchBar(q.qa.returned,q.qa.total,'lavender')}</div><div><span>QA on first pass</span><b>${q.qa.firstPass}%</b>${orchBar(q.qa.firstPass,100,'cyan')}</div><div><span>Defect escape</span><b>${q.qa.defectEscape}%</b>${orchBar(q.qa.defectEscape,100,'lavender')}</div></div></article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Check types</h3><span>${verifyTotal} runs</span></div>${orchStack(q.verification,verifyTotal)}${orchLegend(q.verification)}<p class="orch-note">focused / failed-only are not evidence for publish; not_run does not count as pass.</p></article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Evidence by stage</h3><span>pass / fail / not_run</span></div><div class="orch-heatmap"><div class="orch-heat-head"><span></span><span>lint</span><span>types</span><span>pytest</span><span>clean</span></div>${q.evidence.map(row=>`<div class="orch-heat-row"><b>${row.batch}</b>${row.checks.map(c=>`<span class="orch-heat-cell ${c.state}">${c.state==='pass'?'✓':c.state==='fail'?'×':'—'}</span>`).join('')}</div>`).join('')}</div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Release Gate</h3><span>candidate / target pair</span></div><div class="orch-gate-table"><div class="orch-gate-head"><span>candidate</span><span>target</span><span>tree</span><span>QA</span><span>verdict</span><span>reason</span></div>${q.releaseGate.map(g=>`<div class="orch-gate-row"><b>${esc(g.candidate)}</b><span>${esc(g.target)}</span><span class="orch-pill ${g.tree==='match'?'mint':g.tree==='mismatch'?'violet':'blue'}">${esc(g.tree)}</span><span>${esc(g.qa)}</span><span class="orch-pill ${g.verdict==='pending'?'blue':g.verdict==='blocked'?'lavender':'violet'}">${esc(g.verdict)}</span><small>${esc(g.reason)}</small></div>`).join('')}</div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Local QA attempts</h3><span>pair evidence</span></div><div class="orch-localqa">${q.localQA.map(x=>`<div><span>${esc(x.state)}</span><b class="${x.tone}">${x.count}</b></div>`).join('')}</div></article>
  </div></section>`;
}
function orchRuntimeTab(){
  const r=ORCH_METRICS.runtime;
  const execTotal=r.execution.reduce((n,x)=>n+x.value,0);
  const opTotal=r.operations.intent;
  return `<section class="panel orch-analytics"><div class="orch-analytics-head"><h2>Runtime</h2><span>heartbeat · lease · recovery</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Health strip</h3><span>observable facts</span></div><div class="orch-health">${r.health.map(x=>`<div><span>${esc(x.label)}</span><b class="${x.tone}">${esc(x.value)}</b></div>`).join('')}</div></article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Execution states</h3><span>${execTotal} dispatch</span></div>${orchStack(r.execution,execTotal)}${orchLegend(r.execution)}</article>
    <article class="orch-chart"><div class="orch-chart-head"><h3>Operations</h3><span>intent / committed / failed</span></div>${orchStack([{label:'committed',value:r.operations.committed,tone:'mint'},{label:'intent',value:r.operations.intent-r.operations.committed-r.operations.failed,tone:'blue'},{label:'failed',value:r.operations.failed,tone:'violet'}],opTotal)}<div class="orch-legend"><span><i class="mint"></i>committed<b>${r.operations.committed}</b></span><span><i class="blue"></i>intent<b>${r.operations.intent-r.operations.committed-r.operations.failed}</b></span><span><i class="violet"></i>failed<b>${r.operations.failed}</b></span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Recovery checks</h3><span>${r.checks.filter(c=>c.status==='passed').length} passed · ${r.checks.filter(c=>c.status==='pending').length} pending</span></div><div class="orch-checks">${r.checks.map(c=>`<div class="orch-check ${c.status}"><span>${esc(c.name)}</span><b>${esc(c.status)}</b></div>`).join('')}</div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Recovery holds</h3><span>0 active holds</span></div><div class="orch-holds">${r.holds.map(x=>`<div><span>${esc(x.reason)}</span><b>${x.count}</b></div>`).join('')}</div></article>
  </div></section>`;
}
function orchLatencyChart(){
  const t=ORCH_GATES_TREND, W=1000,H=250,L=54,R=18,T=16,B=34,max=40;
  const x=i=>L+(i*(W-L-R)/23);
  const y=v=>T+(max-v)/max*(H-T-B);
  const pts=a=>a.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const base=y(0);
  const area=`M ${x(0).toFixed(1)} ${base.toFixed(1)} L ${pts(t.p95).split(' ').join(' L ')} L ${x(23).toFixed(1)} ${base.toFixed(1)} Z`;
  const ticks=[0,10,20,30,40];
  const hours=[0,3,6,9,12,15,18,21,23];
  const peakX=x(t.peak.i),peakY=y(t.p95[t.peak.i]);
  return `<div class="orch-line-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Approval latency over a day: p95 and average"><defs><linearGradient id="orch-lat-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b79ae8" stop-opacity=".28"/><stop offset="1" stop-color="#b79ae8" stop-opacity="0"/></linearGradient></defs>${ticks.map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" class="orch-line-grid"/><text x="${L-8}" y="${y(v)+3}" text-anchor="end" class="orch-line-axis">${v}</text>`).join('')}${hours.map(i=>`<text x="${x(i)}" y="${H-12}" text-anchor="middle" class="orch-line-axis">${String(i).padStart(2,'0')}:00</text>`).join('')}<path d="${area}" fill="url(#orch-lat-fill)"/><polyline points="${pts(t.p95)}" class="orch-line-p95"/><polyline points="${pts(t.avg)}" class="orch-line-avg"/><circle cx="${peakX}" cy="${peakY}" r="3.5" class="orch-line-peak-dot"/><text x="${peakX}" y="${peakY-10}" text-anchor="middle" class="orch-line-peak">${esc(t.peak.label)}</text><text x="${L-8}" y="${T+4}" text-anchor="end" class="orch-line-axis">min</text></svg></div>`;
}
function orchTickets(){
  const rows=ORCH_TICKETS;
  return `<section class="panel orch-tickets"><div class="panel-head"><h2>All tickets</h2><span class="small muted">${rows.length} in the sample</span></div><div class="orch-ticket-table"><div class="orch-ticket-head"><span>ticket</span><span>title</span><span>stage / role</span><span>status</span><span>age</span><span>updated</span></div>${rows.map(t=>`<div class="orch-ticket-row"><b>${esc(t.id)}</b><div class="orch-ticket-title"><span>${esc(t.title)}</span><small>${esc(t.batch)}</small></div><span>${esc(t.stage)} · ${esc(t.role)}</span><span class="orch-pill ${t.tone}">${esc(t.label)}</span><span>${esc(t.age)}</span><span>${esc(t.updated)}</span></div>`).join('')}</div></section>`;
}

function orchGatesTab(){
  const g=ORCH_METRICS.gates;
  const maxP95=Math.max(...g.map(x=>x.p95v));
  return `<section class="panel orch-analytics"><div class="orch-analytics-head"><h2>Gates</h2><span>human approval latency</span></div><div class="orch-analytics-grid">
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Approval latency over 24 hours</h3><span>p95 vs average · demo</span></div>${orchLatencyChart()}<div class="orch-legend"><span><i class="cyan"></i>Average</span><span><i class="lavender"></i>p95</span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Approval latency</h3><span>p50 / p95, minutes</span></div><div class="orch-gate-chart">${g.map(x=>`<div class="orch-gate-chart-row"><span>${esc(x.name)}</span><div class="orch-gate-bars"><div>${orchBar(x.p50v,maxP95,'cyan')}<small>${x.p50v}</small></div><div>${orchBar(x.p95v,maxP95,'violet')}<small>${x.p95v}</small></div></div></div>`).join('')}</div><div class="orch-legend"><span><i class="cyan"></i>p50</span><span><i class="violet"></i>p95</span></div></article>
    <article class="orch-chart wide"><div class="orch-chart-head"><h3>Gate queue</h3><span>p50 / p95 · oldest</span></div><div class="orch-gates-table compact"><div class="orch-gates-head"><span>gate</span><span>p50 / p95</span><span>oldest</span><span>rej / cond / stale</span><span>handoff</span></div>${g.map(x=>`<div class="orch-gates-row"><b>${esc(x.name)}</b><span data-label="p50 / p95">${esc(x.p50)} / ${esc(x.p95)}</span><span data-label="oldest">${esc(x.oldest)}</span><span data-label="rejected / conditional / stale">${x.rejected} / ${x.conditional} / ${x.stale}</span><span data-label="handoff">${esc(x.handoff)}</span></div>`).join('')}</div></article>
  </div><p class="orch-note">Gates do not count as role work: waiting for a human is shown separately. All values are a demo slice.</p></section>`;
}
function orchTabContent(){
  if(orchTab==='flow')return orchFlowTab();
  if(orchTab==='quality')return orchQualityTab();
  if(orchTab==='runtime')return orchRuntimeTab();
  if(orchTab==='gates')return orchGatesTab();
  return orchMap();
}
function refreshOrchView(){
  const view=$('#orch-view');if(!view)return;
  view.innerHTML=orchTabContent();
  bindOrch();
}

function orchPage(){
  const c=orchCounts();
  return `<div class="page-title orch-title"><div><h1>Orchestration</h1><p>Batch → Dispatch → roles → QA → PR. Observable statuses and transitions only.</p><div class="home-facts"><span>${c.batches} batches</span><span>${c.dispatches} dispatch</span><span>${c.active} active</span><span id="orch-updated">${fmtClock(orchUpdatedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-orch-refresh>${icon('refresh')} Update</button><a class="btn" href="#reports">${icon('reports')} Reports</a></div></div>
  <div class="orch-summary"><div><span>Batches</span><b>${c.batches}</b><small>in the pipeline</small></div><div><span>Dispatch</span><b>${c.dispatches}</b><small>assigned</small></div><div><span>Active</span><b class="ok">${c.active}</b><small>working or waiting</small></div><div><span>Needs attention</span><b class="warn">${c.attention}</b><small>dispatch needs a decision</small></div></div>
  ${orchKpis()}
  ${orchTabs()}
  <div id="orch-view">${orchTab==='map'?orchMap():orchTabContent()}</div>
  ${orchBatchCards()}
  <section class="panel orch-dispatch-panel"><div class="panel-head"><h2>Dispatch</h2><span class="small muted" id="orch-dispatch-count">${orchVisibleDispatches().length} of ${c.dispatches}</span></div><div class="orch-dispatch-filters"><select id="orch-role" aria-label="Dispatch role"><option value="all">All roles</option><option value="architect">Architect</option><option value="developer">Developer</option><option value="review">Review</option><option value="qa">QA</option></select><select id="orch-status" aria-label="Dispatch status"><option value="all">All statuses</option><option value="working">Running</option><option value="awaiting">Awaiting decision</option><option value="attention">Needs attention</option></select></div><div id="orch-dispatch-list">${orchDispatchList()}</div></section>
  ${qaLane('orch')}
  ${orchTickets()}`;
}
function bindOrch(){
  const r=$('#orch-role');if(r)r.value=orchRole;
  const s=$('#orch-status');if(s)s.value=orchStatus;
  document.querySelectorAll('[data-orch-tab]').forEach(btn=>{const on=btn.dataset.orchTab===orchTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshOrch(){
  const list=$('#orch-dispatch-list');if(list)list.innerHTML=orchDispatchList();
  const count=$('#orch-dispatch-count');if(count)count.textContent=`${orchVisibleDispatches().length} of ${orchCounts().dispatches}`;
  bindOrch();
}

function harnessKpis(){
  const v=HARNESS.version,s=HARNESS.store;
  return `<div class="harness-kpis"><div><span>Installed</span><b class="violet">${v.installed}</b><small>available ${v.available} · ${v.channel}</small></div><div><span>Runtime store</span><b class="mint">schema ${s.schema}</b><small>generation ${s.generation} · audit ${s.audit}</small></div><div><span>Audit chain</span><b class="cyan">${s.audit}</b><small>cutover ${s.cutover}</small></div><div><span>Skills</span><b class="lavender">32</b><small>drift 1 · 259 managed</small></div></div>`;
}
function harnessTabs(){
  const tabs=[['overview','Overview'],['runtime','Runtime'],['adapters','Adapters'],['containers','Containers'],['commands','Commands']];
  return `<div class="orch-tabbar harness-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${harnessTab===id?'on':''}" data-harness-tab="${id}" role="tab" aria-selected="${harnessTab===id}">${label}</button>`).join('')}</div>`;
}
function harnessFlow(compact=false){
  const nodes=[
    ['harness','Python policy','project + roles','violet'],
    ['branch','IPC','protocol v1','cyan'],
    ['harness','Rust runtime','authority','mint'],
    ['settings','SQLite WAL','schema 6','blue'],
    ['orchestration','Supervisor','workers','lavender'],
    ['shield','Audit chain','306 records','cyan']
  ];
  return `<div class="harness-flow ${compact?'compact':''}">${nodes.map(([ic,label,sub,tone],i)=>`<div class="harness-flow-node ${tone}"><span>${icon(ic)}</span><b>${label}</b><small>${sub}</small></div>${i<nodes.length-1?'<i class="harness-flow-arrow">→</i>':''}`).join('')}</div>`;
}
function harnessStoreFacts(){
  const s=HARNESS.store;
  return `<div class="harness-store-facts">${[['authority',s.authority],['schema',s.schema],['generation',s.generation],['audit',s.audit],['cutover',s.cutover],['protocol',s.protocol]].map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(String(v))}</b></div>`).join('')}</div>`;
}
function harnessInstall(){
  const v=HARNESS.version;
  return `<section class="panel harness-install"><div class="panel-head"><h2>Installation</h2><span class="orch-pill violet">pre-release</span></div><div class="harness-install-body"><div class="harness-version-pair"><div><span>Installed</span><b>${v.installed}</b></div><span>→</span><div><span>Available</span><b>${v.available}</b></div></div><p class="harness-install-note">Capability: <code>${v.capability}</code>. Update runs by plan only; files do not change.</p><div class="harness-components">${HARNESS.components.map(c=>`<div class="harness-component"><span>${esc(c.name)}</span><b>${esc(c.value)}</b><small>${esc(c.detail)}</small><em class="orch-pill ${c.tone}">${esc(c.state)}</em></div>`).join('')}</div><div class="harness-install-actions"><a class="btn primary" href="#update-harness">${icon('download')} Open update</a><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div></section>`;
}
function harnessRuntimePanel(compact=false){
  return `<section class="panel harness-runtime"><div class="panel-head"><h2>Runtime</h2><span class="orch-pill mint">healthy</span></div><div class="harness-runtime-body"><div class="harness-runtime-line"><span>${icon('harness')} ${HARNESS.store.binary}</span><span>${HARNESS.store.authority}</span><span>uptime ${HARNESS.store.uptime}</span></div>${harnessStoreFacts()}${harnessFlow(compact)}<div class="harness-runtime-actions"><a class="btn" href="#orchestration">${icon('orchestration')} Orchestration</a><button class="btn" type="button" data-harness-cmd="harness runtime status">${icon('terminal')} runtime status</button></div></div></section>`;
}
function harnessAdapters(compact=false){
  return `<section class="panel harness-adapters"><div class="panel-head"><h2>Adapters</h2><span class="small muted">Claude Code · Codex · GitHub</span></div><div class="harness-adapter-grid">${HARNESS.adapters.map(a=>`<article class="harness-adapter"><div class="harness-adapter-head"><span>${icon(a.kind)}</span><em class="orch-pill ${a.tone}">${esc(a.status)}</em></div><h3>${esc(a.name)}</h3><div class="harness-adapter-meta"><span>${esc(a.version)}</span><span>hooks ${esc(a.hooks)}</span></div><p>${esc(a.detail)}</p>${compact?'':`<div class="harness-adapter-foot"><span>standard profile</span><button class="btn" type="button" data-harness-cmd="harness health .">${icon('pulse')} Check</button></div>`}</article>`).join('')}</div></section>`;
}
function harnessCommands(compact=false){
  const rows=compact?HARNESS.commands.slice(0,3):HARNESS.commands;
  return `<section class="panel harness-commands"><div class="panel-head"><h2>Commands</h2><span class="small muted">${compact?'quick access':'plan and read only'}</span></div><div class="harness-command-table"><div class="harness-command-head"><span>command</span><span>purpose</span><span>mode</span><span>last result</span><span></span></div>${rows.map(c=>`<div class="harness-command-row"><code>${esc(c.cmd)}</code><span>${esc(c.purpose)}</span><em class="orch-pill ${c.mode==='plan'?'violet':'mint'}">${esc(c.mode)}</em><span>${esc(c.last)}</span><button class="btn" type="button" data-harness-cmd="${esc(c.cmd)}">${icon('terminal')} Show</button></div>`).join('')}</div><p class="harness-note">Commands in the mockup are not executed; only the plan or demo output is shown.</p></section>`;
}
function harnessAudit(){
  return `<section class="panel harness-audit"><div class="panel-head"><h2>Audit chain</h2><span class="small muted">${HARNESS.store.audit} records</span></div><div class="harness-audit-list">${HARNESS.audit.map(a=>`<div><i class="${a.tone}"></i><span>${esc(a.time)}</span><b>${esc(a.event)}</b><small>${esc(a.detail)}</small></div>`).join('')}</div></section>`;
}
function harnessOverview(){
  return `<div class="harness-grid">${harnessInstall()}${harnessRuntimePanel(true)}</div>${harnessAdapters(true)}${harnessCommands(true)}`;
}
function harnessRuntimeTab(){
  return `<div class="harness-runtime-tab">${harnessRuntimePanel()}${harnessAudit()}</div>`;
}
function harnessContainersTab(){
  const c=HARNESS_CONTAINERS,e=c.engine;
  return `<section class="panel harness-containers"><div class="panel-head"><h2>Containers</h2><span class="small muted">${e.name} ${e.version} · rootless · cgroup ${e.cgroup}</span></div>
    <div class="harness-container-summary"><div><span>Engine</span><b class="mint">${e.name}</b><small>${e.version} · ${e.rootless?'rootless':'rootful'}</small></div><div><span>Running</span><b class="mint">${c.summary.running}</b><small>+ ${c.summary.stopped} stopped · ${c.summary.failed} failed</small></div><div><span>Images / volumes</span><b class="cyan">${c.summary.images} / ${c.summary.volumes}</b><small>${c.summary.networks} networks</small></div><div><span>Disk</span><b class="violet">${c.summary.disk}</b><small>sandbox cache + logs</small></div></div>
    <div class="harness-engine"><span class="ok">${icon('check')} daemon ${e.daemon}</span><span class="ok">${icon('check')} rootless</span><span class="ok">${icon('check')} cgroup ${e.cgroup}</span><span class="ok">${icon('check')} SELinux ${e.selinux}</span><span class="ok">${icon('check')} DNS ${e.dns}</span><span class="muted">${e.socket}</span></div>
    <div class="harness-container-table"><div class="harness-container-head"><span>container</span><span>role</span><span>state</span><span>image</span><span>uptime</span><span>CPU / RAM</span><span>network</span><span></span></div>${c.containers.map(x=>`<div class="harness-container-row"><b>${esc(x.name)}</b><span>${icon(x.role)} ${esc(x.role)}</span><em class="orch-pill ${x.tone}">${esc(x.label)}</em><span>${esc(x.image)}</span><span>${esc(x.uptime)}</span><span>${esc(x.cpu)} / ${esc(x.mem)}</span><span>${esc(x.network)}</span><button class="btn" type="button" data-harness-container="${esc(x.id)}">${icon('terminal')} Logs</button></div>`).join('')}</div>
    <div class="harness-container-grid"><section class="harness-container-block"><div class="harness-block-head"><h3>Images</h3><span>${c.images.length}</span></div><div class="harness-image-table"><div class="harness-image-head"><span>image</span><span>tag</span><span>size</span><span>used</span></div>${c.images.map(x=>`<div class="harness-image-row"><b>${esc(x.name)}</b><span>${esc(x.tag)}</span><span>${esc(x.size)}</span><span>${esc(x.used)}</span></div>`).join('')}</div></section><section class="harness-container-block"><div class="harness-block-head"><h3>Networks / volumes</h3><span>${c.networks.length} / ${c.volumes.length}</span></div><div class="harness-net-list">${c.networks.map(x=>`<div><span>${icon('branch')} ${esc(x.name)}</span><small>${esc(x.driver)} · ${esc(x.state)}</small></div>`).join('')}${c.volumes.map(x=>`<div><span>${icon('folder')} ${esc(x.name)}</span><small>${esc(x.size)} · ${esc(x.state)}</small></div>`).join('')}</div><div class="harness-cleanup"><span>Cleanup</span>${c.cleanup.map(x=>`<b class="${x.tone}">${esc(x.label)} ${x.count}</b>`).join('')}<button class="btn" type="button" data-harness-cleanup>${icon('terminal')} Cleanup plan</button></div></section></div>
    <p class="harness-note">Docker/Podman do not start from the mockup. Logs and the cleanup plan are demo data; nothing is deleted.</p>
  </section>`;
}
function harnessContainerLogs(id){
  const x=HARNESS_CONTAINERS.containers.find(c=>c.id===id);if(!x)return;
  reader(`Container · ${x.name}`,`DEMO · CONTAINER\n\nstate: ${x.label}\nrole: ${x.role}\nimage: ${x.image}\nuptime: ${x.uptime}\ncpu / ram: ${x.cpu} / ${x.mem}\nnetwork: ${x.network}\nexit: ${x.exit}\n\nLast log lines:\n[harness] sandbox ready\n[harness] role ${x.role} attached\n[harness] ${x.state==='failed'?'daemon permission denied':'heartbeat recorded'}\n\nDemo output; Docker was not called.`);
}

function harnessAdaptersTab(){return harnessAdapters(false)}
function harnessCommandsTab(){return harnessCommands(false)}
function harnessTabContent(){
  if(harnessTab==='runtime')return harnessRuntimeTab();
  if(harnessTab==='adapters')return harnessAdaptersTab();
  if(harnessTab==='containers')return harnessContainersTab();
  if(harnessTab==='commands')return harnessCommandsTab();
  return harnessOverview();
}
function harnessPage(){
  return `<div class="page-title harness-title"><div><h1>Harness</h1><p>Installation, runtime, adapters, and maintenance. Commands are shown as a plan; files do not change.</p><div class="home-facts"><span>${HARNESS.version.installed} → ${HARNESS.version.available}</span><span>${HARNESS.store.authority}</span><span>schema ${HARNESS.store.schema}</span><span>32 skills</span><span id="harness-updated">${fmtClock(harnessUpdatedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-harness-refresh>${icon('refresh')} Check</button><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a><a class="btn primary" href="#update-harness">${icon('download')} Update</a></div></div>
  ${harnessKpis()}
  ${harnessTabs()}
  <div id="harness-view">${harnessTab==='overview'?harnessOverview():harnessTabContent()}</div>`;
}
function bindHarness(){
  document.querySelectorAll('[data-harness-tab]').forEach(btn=>{const on=btn.dataset.harnessTab===harnessTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshHarnessView(){
  const view=$('#harness-view');if(!view)return;
  view.innerHTML=harnessTabContent();
  bindHarness();
}
function harnessCommand(cmd){
  if(cmd==='harness health .')return reader(cmd,sources.health);
  if(cmd==='harness diff')return reader(cmd,sources.diff);
  if(cmd==='harness cleanup')return reader(cmd,'DEMO · CLEANUP PLAN\n\nOrphan worktrees: 0\nActive batches: 3\nNo files or worktrees were removed.');
  if(cmd==='harness runtime status')return reader(cmd,`DEMO · RUNTIME STATUS\n\nauthority: ${HARNESS.store.authority}\nschema: ${HARNESS.store.schema}\ngeneration: ${HARNESS.store.generation}\naudit: ${HARNESS.store.audit}\ncutover: ${HARNESS.store.cutover}\nprotocol: ${HARNESS.store.protocol}\n\nThe mock does not contact a runtime.`);
  if(cmd==='harness repo-map')return reader(cmd,'DEMO · REPO MAP\n\ntier: full\nfiles: 1 284\nedges: 3 912\ntokens: 184k\n\nNo parser was started.');
  return reader(cmd,`DEMO · COMMAND PREVIEW\n\n${cmd}\n\nThis is a plan, not an execution. Project files are not modified.`);
}

function repoKpis(){
  return `<div class="repo-kpis"><div><span>Tier</span><b class="cyan">${REPO_MAP.tier}</b><small>${esc(REPO_MAP.parser)}</small></div><div><span>Files</span><b class="mint">${fmtNum(REPO_MAP.files)}</b><small>${fmtNum(REPO_MAP.symbolCount)} symbols</small></div><div><span>Links</span><b class="blue">${fmtNum(REPO_MAP.edges)}</b><small>import / call / writes</small></div><div><span>Tokens</span><b class="violet">≈${fmtNum(REPO_MAP.tokens)}</b><small>full map budget</small></div></div>`;
}
function repoTabs(){
  const tabs=[['overview','Overview'],['symbols','Symbols'],['links','Links']];
  return `<div class="orch-tabbar repo-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${repoTab===id?'on':''}" data-repo-tab="${id}" role="tab" aria-selected="${repoTab===id}">${label}</button>`).join('')}</div>`;
}
function repoGraph(){
  const mods=Object.fromEntries(REPO_MAP.modules.map(m=>[m.id,m]));
  const center=id=>{const m=mods[id];return {x:m.x+m.w/2,y:m.y+m.h/2}};
  return `<div class="repo-graph-scroll"><svg class="repo-graph" viewBox="0 0 960 330" role="img" aria-label="Map of modules and links"><defs><marker id="repo-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#6f9fe0"/></marker></defs>${REPO_MAP.links.map(l=>{const a=center(l.from),b=center(l.to);return `<path class="repo-edge" d="M${a.x} ${a.y}L${b.x} ${b.y}" marker-end="url(#repo-arrow)"/>`}).join('')}${REPO_MAP.modules.map(m=>`<g class="repo-node ${repoModule===m.id?'on':''}" data-repo-module="${m.id}"><rect x="${m.x}" y="${m.y}" width="${m.w}" height="${m.h}" rx="7"></rect><text x="${m.x+12}" y="${m.y+21}" class="repo-node-title">${esc(m.label)}</text><text x="${m.x+12}" y="${m.y+36}" class="repo-node-sub">${m.files} files · ${m.symbols} symbols</text><text x="${m.x+m.w-10}" y="${m.y+18}" text-anchor="end" class="repo-node-mark">${repoModule===m.id?'●':''}</text></g>`).join('')}</svg></div>`;
}
function repoIndex(){
  const r=REPO_MAP;
  return `<section class="panel repo-index"><div class="panel-head"><h2>Index</h2><span class="orch-pill mint">fresh</span></div><div class="repo-index-body"><div class="repo-index-row"><span>Tier</span><b>${r.tier} · ${esc(r.parser)}</b></div><div class="repo-index-row"><span>Generation</span><b>${esc(r.generation)}</b></div><div class="repo-index-row"><span>Built</span><b>${esc(r.built)} · ${fmtClock(repoUpdatedAt)}</b></div><div class="repo-index-row"><span>Volume</span><b>${fmtNum(r.files)} files · ${fmtNum(r.edges)} edges · ≈${fmtNum(r.tokens)} tokens</b></div><div class="repo-index-actions"><button class="btn" type="button" data-repo-rebuild>${icon('refresh')} Rebuild</button><button class="btn" type="button" data-repo-export>${icon('download')} Export</button></div></div></section>`;
}
function repoCoverage(){
  const c=REPO_MAP.coverage;
  return `<section class="panel repo-coverage"><div class="panel-head"><h2>Coverage</h2><span class="small muted">${c.percent}% enabled</span></div><div class="repo-coverage-body"><div class="orch-stack">${c.groups.map(g=>`<i class="${g.tone}" style="width:${Math.round(g.value/(c.included+c.excluded)*100)}%" title="${g.label}: ${g.value}"></i>`).join('')}</div><div class="orch-legend">${c.groups.map(g=>`<span><i class="${g.tone}"></i>${g.label}<b>${fmtNum(g.value)}</b></span>`).join('')}</div><p class="orch-note">Vendor, generated, and assets are excluded from the index. The full map is available for dispatch.</p></div></section>`;
}
function repoHighlight(line){
  let x=esc(line);
  x=x.replace(/\b(class|def|return|import|from|if|not|raise|as|with|for|in)\b/g,'<span class="repo-syn-key">$1</span>');
  x=x.replace(/(&quot;[^&]*?&quot;)/g,'<span class="repo-syn-str">$1</span>');
  return x;
}
function repoTreeNodes(nodes,depth=0){
  return nodes.map(n=>{
    if(n.type==='dir'){
      const open=repoExpanded[n.id]!==false;
      return `<button type="button" class="repo-dir" data-repo-dir="${n.id}"><span class="repo-tree-indent" style="width:${depth*14}px"></span><span class="repo-caret ${open?'open':''}">${icon('chevron')}</span>${icon('folder')}<b>${esc(n.name)}/</b></button>${open?repoTreeNodes(n.children,depth+1):''}`;
    }
    const f=REPO_FILE_DATA[n.id];
    return `<button type="button" class="repo-file ${repoFile===n.id?'on':''}" data-repo-file="${n.id}"><span class="repo-tree-indent" style="width:${depth*14}px"></span><span class="repo-caret dot">·</span>${icon('terminal')}<b>${esc(n.name)}</b><em>[${esc(f?.status||'ok')}]</em></button>`;
  }).join('');
}
function repoFileViewer(){
  const f=REPO_FILE_DATA[repoFile];
  if(!f)return '<div class="repo-empty">Select a file.</div>';
  const relGroup=(items,label)=>`<div class="repo-rel-group"><h4>${label}</h4>${items.length?items.map(r=>`<div class="repo-rel-item"><span class="repo-rel-weight ${r.weight}">${esc(r.weight)}</span><code>${esc(r.path)}</code><small>${esc(r.type)} · ${r.count}</small></div>`).join(''):'<div class="repo-rel-empty">no</div>'}</div>`;
  return `<div class="repo-file-head"><div><span>FILE</span><b>${esc(f.path)}</b></div><span class="orch-pill mint">${esc(f.status)}</span></div><div class="repo-file-layout"><div class="repo-code"><div class="repo-code-head"><span>Contents</span><span>${f.code.split('\n').length} lines</span></div><pre>${f.code.split('\n').map((line,i)=>`<span class="repo-line"><i>${i+1}</i><code>${repoHighlight(line)}</code></span>`).join('')}</pre></div><aside class="repo-rel-panel"><div class="repo-rel-head"><h3>Links</h3><span>${f.relations.out.length+f.relations.in.length}</span></div>${relGroup(f.relations.out,'Outgoing')}${relGroup(f.relations.in,'Incoming')}</aside></div>`;
}
function repoFilesPanel(){
  return `<section class="panel repo-files-panel"><div class="panel-head"><h2>Files</h2><span class="small muted">hierarchy + content view</span></div><div class="repo-files-layout"><div class="repo-tree"><div class="repo-tree-root">${icon('branch')} 6a7f74807b10 · full</div>${repoTreeNodes(REPO_TREE)}</div><div id="repo-file-viewer">${repoFileViewer()}</div></div></section>`;
}
function refreshRepoFileView(){
  const v=$('#repo-file-viewer');if(v)v.innerHTML=repoFileViewer();
  document.querySelectorAll('[data-repo-file]').forEach(btn=>btn.classList.toggle('on',btn.dataset.repoFile===repoFile));
}

function repoOverview(){
  return `<div class="repo-grid">${repoIndex()}${repoCoverage()}</div>${repoFilesPanel()}`;
}
function repoVisibleSymbols(){
  const q=repoQuery.trim().toLowerCase();
  return REPO_MAP.symbols.filter(s=>(repoModule==='all'||s.module===repoModule)&&(repoKind==='all'||s.kind===repoKind)&&(!q||[s.name,s.path,s.summary].join(' ').toLowerCase().includes(q)));
}
function ensureRepoSelection(){
  const rows=repoVisibleSymbols();
  if(!rows.some(s=>s.id===repoSelected))repoSelected=rows[0]?.id||null;
}
function repoSelectedItem(){return REPO_MAP.symbols.find(s=>s.id===repoSelected)||null}
function repoSymbolList(){
  const rows=repoVisibleSymbols();
  if(!rows.length)return '<div class="repo-empty">No symbols match these filters.</div>';
  return rows.map(s=>`<button type="button" class="repo-symbol-row ${s.id===repoSelected?'on':''}" data-repo-symbol="${s.id}"><span class="repo-kind ${s.kind}">${esc(s.kind)}</span><span class="repo-symbol-main"><b>${esc(s.name)}</b><small>${esc(s.path)}:${s.line}</small></span><span class="repo-symbol-module">${esc(s.module)}</span></button>`).join('');
}
function repoDetail(){
  const s=repoSelectedItem();
  if(!s)return '<section class="panel repo-detail"><div class="repo-empty">Select a symbol.</div></section>';
  const list=(arr,label)=>arr.length?`<div class="repo-rel"><span>${label}</span>${arr.map(x=>`<code>${esc(x)}</code>`).join('')}</div>`:'';
  return `<section class="panel repo-detail"><div class="panel-head"><h2>Symbol</h2><span class="orch-pill ${s.kind==='function'?'mint':'blue'}">${esc(s.kind)}</span></div><div class="repo-detail-body"><code class="repo-symbol-name">${esc(s.name)}</code><div class="repo-meta"><span>${esc(s.path)}:${s.line}</span><span>module ${esc(s.module)}</span><span>used ${s.used}</span></div><p>${esc(s.summary)}</p>${list(s.imports,'imports')}${list(s.usedBy,'used by')}<div class="repo-detail-actions"><button class="btn primary" type="button" data-repo-open>${icon('terminal')} Open file</button><a class="btn" href="#reports">${icon('reports')} Reports</a></div></div></section>`;
}
function repoSymbols(){
  const c={all:REPO_MAP.symbols.length,function:REPO_MAP.symbols.filter(s=>s.kind==='function').length,module:REPO_MAP.symbols.filter(s=>s.kind==='module').length};
  const chip=(key,label)=>`<button class="chip ${repoKind===key?'on':''}" type="button" data-repo-kind="${key}" aria-pressed="${repoKind===key}">${label} ${c[key]}</button>`;
  return `<div class="repo-symbol-grid"><section class="panel repo-symbols"><div class="panel-head"><h2>Symbols</h2><span class="small muted">${repoVisibleSymbols().length} of ${REPO_MAP.symbols.length}</span></div><div class="repo-filters"><div class="chips">${chip('all','All')}${chip('function','Functions')}${chip('module','Modules')}</div><label class="diag-search repo-search">${icon('search')}<input id="repo-symbol-search" type="search" placeholder="Find a symbol" value="${esc(repoQuery)}" aria-label="Symbol search"></label></div><div id="repo-symbol-list">${repoSymbolList()}</div><div class="repo-note">${repoModule==='all'?'All modules':'Module: '+esc(repoModule)}</div></section><div id="repo-detail">${repoDetail()}</div></div>`;
}
function repoLinks(){
  const mods=Object.fromEntries(REPO_MAP.modules.map(m=>[m.id,m.label]));
  return `<section class="panel repo-links"><div class="panel-head"><h2>Links</h2><span class="small muted">${REPO_MAP.links.length} types</span></div>${repoGraph()}<div class="repo-link-table"><div class="repo-link-head"><span>from</span><span>to</span><span>type</span><span>count</span></div>${REPO_MAP.links.map(l=>`<div class="repo-link-row"><b>${esc(mods[l.from])}</b><span>${esc(mods[l.to])}</span><span>${esc(l.label)}</span><span>${l.count}</span></div>`).join('')}</div></section>`;
}
function repoPage(){
  return `<div class="page-title repo-title"><div><h1>Repo Map</h1><p>Index of symbols, modules, and imports. Full map for dispatch; read-only.</p><div class="home-facts"><span>tier ${REPO_MAP.tier}</span><span>${fmtNum(REPO_MAP.files)} files</span><span>${fmtNum(REPO_MAP.symbolCount)} symbols</span><span>${fmtNum(REPO_MAP.edges)} edges</span><span id="repo-updated">${fmtClock(repoUpdatedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-repo-rebuild>${icon('refresh')} Rebuild</button><button class="btn" type="button" data-repo-export>${icon('download')} Export</button></div></div>
  ${repoKpis()}
  ${repoTabs()}
  <div id="repo-view">${repoTab==='overview'?repoOverview():repoTab==='symbols'?repoSymbols():repoLinks()}</div>`;
}
function bindRepo(){
  document.querySelectorAll('[data-repo-tab]').forEach(btn=>{const on=btn.dataset.repoTab===repoTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
  document.querySelectorAll('[data-repo-kind]').forEach(btn=>{const on=btn.dataset.repoKind===repoKind;btn.classList.toggle('on',on);btn.setAttribute('aria-pressed',String(on))});
}
function refreshRepoView(){
  const view=$('#repo-view');if(!view)return;
  ensureRepoSelection();
  view.innerHTML=repoTab==='overview'?repoOverview():repoTab==='symbols'?repoSymbols():repoLinks();
  bindRepo();
}
function updateRepoSymbols(){
  ensureRepoSelection();
  const list=$('#repo-symbol-list');if(list)list.innerHTML=repoSymbolList();
  const detail=$('#repo-detail');if(detail)detail.innerHTML=repoDetail();
  const count=document.querySelector('.repo-symbols .panel-head span');if(count)count.textContent=`${repoVisibleSymbols().length} of ${REPO_MAP.symbols.length}`;
  bindRepo();
}
function repoExport(){
  const payload={generatedAt:new Date().toISOString(),demo:true,tier:REPO_MAP.tier,files:REPO_MAP.files,symbols:REPO_MAP.symbols.length,edges:REPO_MAP.edges,modules:REPO_MAP.modules,symbolData:REPO_MAP.symbols};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`repo-map-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Repo Map exported (demo)');
}
function repoOpenFile(){
  const s=repoSelectedItem();if(!s)return;
  reader(`File · ${s.path}`, `DEMO · ${s.path}\n\n${s.line}: ${s.name}\n${s.summary}\n\nShowing a demo index fragment; the file was not read.`);
}

function settingsParam(){return SETTINGS_WIZARD.params[settingsParamIndex]||SETTINGS_WIZARD.params[0]}
function settingsGroupOf(p){return SETTINGS_WIZARD.groups.find(g=>g.id===p.group)||SETTINGS_WIZARD.groups[0]}
function settingsValueField(p){
  if(p.type==='boolean')return `<label class="settings-toggle"><input type="checkbox" data-settings-bool ${p.value?'checked':''}> <span>${p.value?'On':'Off'}</span><small>On — yes; off — no</small></label>`;
  if(p.type==='select')return `<select class="settings-input" data-settings-value>${p.options.map(o=>`<option value="${esc(o)}" ${o===p.value?'selected':''}>${esc(o)}</option>`).join('')}</select>`;
  return `<input class="settings-input" data-settings-value type="${p.type==='number'?'number':'text'}" value="${esc(String(p.value))}">`;
}
function settingsWizard(){
  const p=settingsParam(),g=settingsGroupOf(p),total=SETTINGS_WIZARD.params.length;
  const groups=SETTINGS_WIZARD.groups.map(gr=>`<button type="button" class="wizard-group ${gr.id===g.id?'on':''}" data-settings-group="${gr.id}"><span>${esc(gr.label)}</span><b>${gr.params.length}</b></button>`).join('');
  const options=SETTINGS_WIZARD.params.map((x,i)=>`<option value="${i}" ${i===settingsParamIndex?'selected':''}>${esc(x.group)} → ${esc(x.key)}</option>`).join('');
  const rec=p.type==='boolean'?(p.recommend?'yes':'no'):String(p.recommend);
  const aiDisabled=settingsAiAdvice?'':' disabled aria-disabled="true"';
  return `<div class="settings-wizard"><aside class="wizard-side"><div class="wizard-side-head"><span>Groups</span><b>${SETTINGS_WIZARD.groups.length}</b></div><div class="wizard-groups">${groups}</div><div class="wizard-progress"><span>Progress</span><div class="orch-bar"><i class="cyan" style="width:${Math.round((settingsParamIndex+1)/total*100)}%"></i></div><small>${settingsParamIndex+1} of ${total} parameters</small></div></aside><section class="wizard-main"><div class="wizard-step"><span>STEP</span><b>Group ${SETTINGS_WIZARD.groups.indexOf(g)+1} / ${SETTINGS_WIZARD.groups.length}</b><b>Parameter ${settingsParamIndex+1} / ${total}</b><select class="wizard-param-select" data-settings-param-select aria-label="Choose a parameter">${options}</select></div><article class="wizard-param"><div class="wizard-param-head"><span>PARAMETER</span><code>${esc(p.group)} → ${esc(p.key)}</code></div><p class="wizard-desc">${esc(p.desc)}</p><div class="wizard-rec"><b>Recommendation (*):</b> <code>${esc(rec)}</code></div><div class="wizard-why"><b>Why:</b> ${esc(p.why)}</div><label class="wizard-use"><input type="checkbox" data-settings-use ${p.use?'checked':''}> <span>Use this parameter</span><small>Uncheck — leave it absent</small></label>${settingsValueField(p)}<div class="wizard-accept-row"><button class="btn" type="button" data-settings-accept>Accept recommendation</button></div></article><article class="wizard-ai"><div class="wizard-ai-head"><span>AI suggestions</span><small>request only on button click</small></div><p class="wizard-ai-note">AI suggestions use the existing CLI authorization; the request runs only on button click, and the CLI check does not call the model.</p><div class="wizard-ai-status"><span class="ok">●</span> No AI — plain hints</div><div class="wizard-ai-status"><span class="ok">●</span> Codex CLI — ready for a request; network and limits are checked on request</div><div class="wizard-ai-status muted"><span>●</span> Claude Code CLI — unavailable; check network, rate limit, and authorization</div><div class="wizard-ai-actions"><button class="btn" type="button" data-settings-ai-check>Check CLI</button><button class="btn" type="button" data-settings-ai-ask>Ask AI</button><button class="btn" type="button" data-settings-ai-accept ${aiDisabled}>Accept AI advice</button></div>${settingsAiAdvice?`<div class="wizard-ai-advice">${esc(settingsAiAdvice)}</div>`:'<p class="wizard-ai-hint">«Accept AI advice» is available after «Ask AI».</p>'}</article><div class="wizard-actions"><button class="btn" type="button" data-settings-prev ${settingsParamIndex===0?'disabled':''}>${icon('chevron')} Previous step</button><button class="btn primary" type="button" data-settings-next ${settingsParamIndex===SETTINGS_WIZARD.params.length-1?'disabled':''}>Next ${icon('chevron')}</button><button class="btn" type="button" data-settings-preview>Preview</button><button class="btn" type="button" data-settings-draft>Save draft</button></div></section></div>`;
}
function refreshSettingsWizard(){
  const view=$('#settings-view');if(!view)return;
  view.innerHTML=settingsWizard();
  bindSettings();
}

function settingsKpis(){
  return `<div class="settings-kpis"><div><span>project.json</span><b class="mint">valid</b><small>${SETTINGS.project.schema}</small></div><div><span>orchestration.json</span><b class="mint">valid</b><small>${SETTINGS.orchestration.schema}</small></div><div><span>Hook policy</span><b class="blue">standard</b><small>${SETTINGS.hooks.digest}</small></div><div><span>Runtime store</span><b class="cyan">schema ${SETTINGS.runtime.schema}</b><small>${SETTINGS.runtime.authority}</small></div></div>`;
}
function settingsTabs(){
  const tabs=[['overview','Overview'],['wizard','Settings'],['project','project.json'],['orchestration','orchestration.json'],['history','History']];
  return `<div class="orch-tabbar settings-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${settingsTab===id?'on':''}" data-settings-tab="${id}" role="tab" aria-selected="${settingsTab===id}">${label}</button>`).join('')}</div>`;
}
function settingsOverview(){
  return `<div class="settings-grid"><section class="panel settings-configs"><div class="panel-head"><h2>Configuration</h2><span class="orch-pill mint">2 files</span></div><div class="settings-config-list">${[
    ['project.json',SETTINGS.project.path,SETTINGS.project.status,SETTINGS.project.schema],
    ['orchestration.json',SETTINGS.orchestration.path,SETTINGS.orchestration.status,SETTINGS.orchestration.schema],
    ['hook-policy.json',SETTINGS.hooks.path,SETTINGS.hooks.status,SETTINGS.hooks.digest],
    ['runtime-store',SETTINGS.runtime.authority,`schema ${SETTINGS.runtime.schema}`,SETTINGS.runtime.protocol]
  ].map(([name,path,status,meta])=>`<div class="settings-config-row"><span>${icon(name.endsWith('.json')?'settings':'harness')}</span><div><b>${esc(name)}</b><small>${esc(path)} · ${esc(meta)}</small></div><em class="orch-pill ${name==='hook-policy.json'?'blue':name==='runtime-store'?'cyan':'mint'}">${esc(status)}</em></div>`).join('')}</div><div class="settings-config-foot"><span>Changes in the mockup are not written to disk.</span><a class="btn" href="#harness">${icon('harness')} Harness</a></div></section>
  <section class="panel settings-policy"><div class="panel-head"><h2>Policies</h2><span class="small muted">resolved values</span></div><div class="settings-resolved">${SETTINGS.resolved.map(x=>`<div><span>${esc(x.label)}</span><b>${esc(x.value)}</b></div>`).join('')}</div><div class="settings-policy-chips">${SETTINGS.policies.map(x=>`<span class="orch-pill ${x.tone}">${esc(x.label)} ${esc(x.value)}</span>`).join('')}</div></section></div><section class="panel settings-note"><div class="settings-note-body">${icon('shield')}<div><b>Read-only in the mockup</b><p>The editor keeps changes in page memory. Schema is checked separately; file saves, Git, and runtime are not performed.</p></div><a class="btn" href="#diagnostics">${icon('pulse')} Check in Diagnostics</a></div></section>`;
}
function settingsEditor(){
  file=settingsTab==='orchestration'?'orchestration.json':'project.json';
  const f=file, cfg=SETTINGS[f==='orchestration.json'?'orchestration':'project'];
  return `<div class="settings-editor-grid"><section class="panel settings-editor"><div class="panel-head"><h2>Editor · ${esc(f)}</h2><span class="orch-pill ${cfg.tone}">${esc(cfg.status)}</span></div><div class="settings-editor-body"><div class="settings-file-line"><code>${esc(cfg.path)}</code><span>${esc(cfg.schema)}</span></div><label class="field">JSON<textarea id="config" class="settings-textarea" spellcheck="false">${esc(configs[f]??configText)}</textarea></label><div class="settings-editor-actions"><button class="btn" data-action="validate">${icon('check')} Validate JSON</button><button class="btn" data-action="save-version">${icon('download')} Save demo version</button><span id="validation" role="status" class="muted"></span></div></div></section><aside class="panel settings-editor-side"><div class="panel-head"><h2>Schema</h2><span class="small muted">syntax check only</span></div><div class="settings-side-body"><div class="settings-side-row"><span>File</span><b>${esc(f)}</b></div><div class="settings-side-row"><span>Schema</span><b>${esc(cfg.schema)}</b></div><div class="settings-side-row"><span>Mode</span><b>in-memory</b></div><div class="settings-side-row"><span>Files</span><b>do not change</b></div><p class="orch-note">JSON.parse checks syntax only. Conformance to the schema and the runtime contract needs a separate check.</p><button class="btn" type="button" data-settings-export>${icon('download')} Export configurations</button></div></aside></div>`;
}
function settingsHistory(){
  const saved=versions.map((v,i)=>`<div class="settings-history-row"><span>${icon('clock')}</span><div><b>${esc(v.file)}</b><small>demo version ${i+1} · in-memory</small></div><button class="btn" type="button" data-restore="${i}">${icon('refresh')} Restore</button></div>`).join('');
  return `<section class="panel settings-history"><div class="panel-head"><h2>History</h2><span class="small muted">demo records</span></div><div class="settings-history-list"><div class="settings-history-head"><span></span><span>file</span><span>change</span><span>when</span></div>${SETTINGS.history.map(x=>`<div class="settings-history-row"><span><i class="${x.tone}"></i></span><div><b>${esc(x.file)}</b><small>${esc(x.summary)}</small></div><span>${esc(x.summary)}</span><span>${esc(x.at)}</span></div>`).join('')}${saved}</div><div class="settings-history-foot">Restore changes only the text in memory; files and Git are not touched.</div></section>`;
}
function settingsPage(){
  if(settingsTab==='project')file='project.json';
  if(settingsTab==='orchestration')file='orchestration.json';
  return `<div class="page-title settings-title"><div><h1>Settings</h1><p>project.json, orchestration.json, hook policy, and runtime. Changes are kept only in mockup memory.</p><div class="home-facts"><span>${esc(SETTINGS.project.name)}</span><span>${esc(SETTINGS.project.branch)}</span><span>2 config</span><span>schema ${SETTINGS.runtime.schema}</span><span id="settings-updated">${fmtClock(settingsCheckedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-settings-refresh>${icon('refresh')} Check</button><button class="btn" type="button" data-settings-export>${icon('download')} Export</button><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div>
  ${settingsKpis()}
  ${settingsTabs()}
  <div id="settings-view">${settingsTab==='wizard'?settingsWizard():settingsTab==='overview'?settingsOverview():settingsTab==='history'?settingsHistory():settingsEditor()}</div>`;
}
function bindSettings(){
  document.querySelectorAll('[data-settings-tab]').forEach(btn=>{const on=btn.dataset.settingsTab===settingsTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshSettingsView(){
  const view=$('#settings-view');if(!view)return;
  view.innerHTML=settingsTab==='wizard'?settingsWizard():settingsTab==='overview'?settingsOverview():settingsTab==='history'?settingsHistory():settingsEditor();
  bindSettings();
}
function exportSettings(){
  const payload={generatedAt:new Date().toISOString(),demo:true,project:configs['project.json'],orchestration:configs['orchestration.json'],hookPolicy:SETTINGS.hooks,runtime:SETTINGS.runtime};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`harness-settings-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Configurations exported (demo)');
}

function helpKpis(){
  return `<div class="help-kpis"><div><span>Screens</span><b class="cyan">${HELP.screens.length}</b><small>in console 2.0.0</small></div><div><span>Commands</span><b class="blue">${HARNESS.commands.length}</b><small>read / plan</small></div><div><span>Hotkeys</span><b class="violet">${HELP.keys.length}</b><small>without field input</small></div><div><span>Limits</span><b class="lavender">${HELP.limits.length}</b><small>observation and evidence</small></div></div>`;
}
function helpTabs(){
  const tabs=[['start','Start'],['screens','Screens'],['commands','Commands'],['keys','Keyboard shortcuts'],['limits','Bounds']];
  return `<div class="orch-tabbar help-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${helpTab===id?'on':''}" data-help-tab="${id}" role="tab" aria-selected="${helpTab===id}">${label}</button>`).join('')}</div>`;
}
function helpStart(){
  return `<section class="panel help-hero"><div class="help-hero-head"><span>HELP · 2.0.0</span><h2>How to read the console</h2><p>Observe facts, check evidence, and make decisions. The console does not replace a human.</p></div><div class="help-pillars"><div><b>01 · Observe</b><span>Sessions, dispatch, heartbeat, and events.</span></div><div><b>02 · Verify</b><span>Health, QA evidence, Release Gate.</span></div><div><b>03 · Decide</b><span>Approvals, retry, public handoff.</span></div></div></section><div class="help-quick">${[['pulse','Check health','#diagnostics','56 checks'],['refresh','Open update','#update-harness','1.5.1 → 2.0.0'],['map','Explore Repo Map','#repo-map','1 284 files'],['settings','Configure Harness','#configuration','project.json']].map(([ic,label,href,sub])=>`<a class="help-quick-card" href="${href}"><span>${icon(ic)}</span><b>${label}</b><small>${sub}</small></a>`).join('')}</div><section class="panel help-faq"><div class="panel-head"><h2>FAQ</h2><span class="small muted">the essentials</span></div><div class="help-faq-list">${HELP.faqs.map(f=>`<details><summary>${esc(f.q)}</summary><p>${esc(f.a)}</p></details>`).join('')}</div></section>`;
}
function helpScreens(){
  return `<section class="panel help-screens"><div class="panel-head"><h2>Screens</h2><span class="small muted">${HELP.screens.length} sections</span></div><div class="help-screen-grid">${HELP.screens.map(s=>`<a class="help-screen" href="#${s.id}"><span>${icon(s.icon)}</span><div><b>${esc(s.label)}</b><small>${esc(s.desc)}</small></div>${icon('chevron')}</a>`).join('')}</div></section>`;
}
function helpCommands(){
  return `<section class="panel help-commands"><div class="panel-head"><h2>Commands</h2><span class="small muted">read-only or plan only</span></div><div class="help-command-table"><div class="help-command-head"><span>command</span><span>purpose</span><span>mode</span><span></span></div>${HARNESS.commands.map(c=>`<div class="help-command-row"><code>${esc(c.cmd)}</code><span>${esc(c.purpose)}</span><em class="orch-pill ${c.mode==='plan'?'violet':'mint'}">${esc(c.mode)}</em><button class="btn" type="button" data-help-command="${esc(c.cmd)}">${icon('terminal')} Show</button></div>`).join('')}</div><p class="harness-note">Commands are not executed; the plan or demo output is shown.</p></section>`;
}
function helpKeys(){
  return `<section class="panel help-keys"><div class="panel-head"><h2>Keyboard shortcuts</h2><span class="small muted">work outside input fields</span></div><div class="help-key-grid">${HELP.keys.map(k=>`<div><kbd>${esc(k.key)}</kbd><span>${esc(k.label)}</span></div>`).join('')}</div></section>`;
}
function helpLimits(){
  return `<section class="panel help-limits"><div class="panel-head"><h2>Observation limits</h2><span class="small muted">what the console does not claim</span></div><div class="help-limit-grid">${HELP.limits.map(x=>`<div><span>${icon('shield')}</span><b>${esc(x.title)}</b><p>${esc(x.text)}</p></div>`).join('')}</div></section>`;
}
function helpPage(){
  return `<div class="page-title help-title"><div><h1>Help</h1><p>Screens, commands, keyboard shortcuts, and observation limits. No internal reasoning.</p><div class="home-facts"><span>Harness 2.0.0</span><span>pre-release</span><span>interactive mockup</span><span>${HELP.screens.length} screens</span></div></div><div class="actions"><button class="btn" type="button" data-help-readme>${icon('reports')} README</button><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a></div></div>${helpKpis()}${helpTabs()}<div id="help-view">${helpStart()}</div>`;
}


function helpTabContent(){
  if(helpTab==='screens')return helpScreens();
  if(helpTab==='commands')return helpCommands();
  if(helpTab==='keys')return helpKeys();
  if(helpTab==='limits')return helpLimits();
  return helpStart();
}
function bindHelp(){
  document.querySelectorAll('[data-help-tab]').forEach(btn=>{const on=btn.dataset.helpTab===helpTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshHelpView(){
  const view=$('#help-view');if(!view)return;
  view.innerHTML=helpTabContent();
  bindHelp();
}

function publishKpis(){
  return `<div class="publish-kpis"><div><span>Candidate</span><b class="cyan">${PUBLISH.candidate.short}</b><small>${PUBLISH.candidate.session} · target ${PUBLISH.candidate.target}</small></div><div><span>Release Gate</span><b class="violet">blocked</b><small>${esc(PUBLISH.gate.reason)}</small></div><div><span>QA source</span><b class="mint">full</b><small>candidate / target pair</small></div><div><span>PR receipt</span><b class="lavender">missing</b><small>creation was not performed</small></div></div>`;
}
function publishTabs(){
  const tabs=[['overview','Overview'],['preflight','Preflight'],['pr','PR / MR'],['evidence','Evidence']];
  return `<div class="orch-tabbar publish-tabbar" role="tablist">${tabs.map(([id,label])=>`<button type="button" class="orch-tab ${publishTab===id?'on':''}" data-publish-tab="${id}" role="tab" aria-selected="${publishTab===id}">${label}</button>`).join('')}</div>`;
}
function publishPreflightRows(compact=false){
  const rows=compact?PUBLISH.preflight.slice(0,3):PUBLISH.preflight;
  return `<div class="publish-preflight">${rows.map(x=>`<div class="publish-check"><span class="orch-pill ${x.tone}">${esc(x.status)}</span><div><b>${esc(x.label)}</b><small>${esc(x.detail)}</small></div></div>`).join('')}</div>`;
}
function publishDecision(){
  return `<section class="panel publish-decision"><div class="panel-head"><h2>Human decision</h2><span class="orch-pill violet">blocked</span></div><div class="publish-decision-body"><div class="publish-decision-text"><b>PR is not ready to create</b><p>${PUBLISH.reasons.map(x=>esc(x)).join(' · ')}</p></div><div class="publish-decision-actions"><button class="btn primary" type="button" disabled aria-disabled="true" title="Preflight not passed">Prepare PR</button><button class="btn" type="button" data-publish-why>Why</button><a class="btn" href="#reports">${icon('reports')} Reports</a></div></div></section>`;
}
function publishOverview(){
  const c=PUBLISH.candidate,g=PUBLISH.gate;
  return `<div class="publish-grid"><section class="panel publish-candidate"><div class="panel-head"><h2>Release candidate</h2><span class="small muted">${c.session}</span></div><div class="publish-candidate-body"><code class="publish-sha">${c.sha}</code><h3>${esc(c.title)}</h3><div class="publish-meta"><span>${icon('branch')} ${esc(c.branch)}</span><span>target ${esc(c.target)}</span><span>QA full</span></div><div class="publish-candidate-actions"><a class="btn" href="#orchestration">${icon('orchestration')} Orchestration</a><a class="btn" href="#reports">${icon('reports')} Reports</a></div></div></section><section class="panel publish-gate"><div class="panel-head"><h2>Release Gate</h2><span class="orch-pill violet">${esc(g.verdict)}</span></div><div class="publish-gate-body"><div class="publish-gate-verdict"><b>${esc(g.verdict)}</b><span>${esc(g.detail)}</span></div><div class="publish-gate-facts"><div><span>tree</span><b>${esc(g.tree)}</b></div><div><span>QA</span><b>${esc(g.qa)}</b></div><div><span>reason</span><b>${esc(g.reason)}</b></div><div><span>merge</span><b>human only</b></div></div></div></section></div><section class="panel publish-preflight-panel"><div class="panel-head"><h2>Preflight</h2><span class="small muted">${PUBLISH.preflight.filter(x=>x.status==='passed').length} / ${PUBLISH.preflight.length} passed</span></div>${publishPreflightRows()}</section>${publishDecision()}`;
}
function publishPreflight(){return `<section class="panel publish-preflight-panel"><div class="panel-head"><h2>Preflight</h2><span class="orch-pill violet">blocked</span></div>${publishPreflightRows(false)}<div class="publish-preflight-foot">Publish evidence must be tied to the candidate SHA and the target SHA. Merge remains a human decision.</div></section>`;}
function publishPR(){
  const p=PUBLISH.pr;
  return `<div class="publish-pr-grid"><section class="panel publish-pr"><div class="panel-head"><h2>PR / MR</h2><span class="orch-pill blue">draft</span></div><div class="publish-pr-body"><div class="publish-pr-field"><span>base</span><b>${esc(p.base)}</b></div><div class="publish-pr-field"><span>title</span><b>${esc(p.title)}</b></div><div class="publish-pr-field"><span>labels</span><div class="publish-labels">${p.labels.map(x=>`<em class="orch-pill blue">${esc(x)}</em>`).join('')}</div></div><div class="publish-pr-field"><span>body</span><pre>${esc(p.body)}</pre></div><div class="publish-pr-actions"><button class="btn" type="button" data-publish-copy>${icon('download')} Copy body</button><button class="btn primary" type="button" disabled>Prepare PR</button></div></div></section><aside class="panel publish-pr-side"><div class="panel-head"><h2>Publication</h2><span class="small muted">human handoff</span></div><div class="publish-side-body"><div><span>Provider</span><b>GitHub</b></div><div><span>Repo</span><b>PVMalove/agent-harness-next</b></div><div><span>Mode</span><b>draft · no create</b></div><p class="orch-note">No PR/MR is created from the mockup. Merge and publication stay with the human.</p><a class="btn" href="#reports">${icon('reports')} Evidence</a></div></aside></div>`;
}
function publishEvidence(){
  return `<section class="panel publish-evidence"><div class="panel-head"><h2>Publish evidence</h2><span class="small muted">${PUBLISH.evidence.length} artifacts</span></div><div class="publish-evidence-table"><div class="publish-evidence-head"><span>artifact</span><span>status</span><span>details</span></div>${PUBLISH.evidence.map(x=>`<div class="publish-evidence-row"><b>${esc(x.name)}</b><span class="orch-pill ${x.tone}">${esc(x.status)}</span><small>${esc(x.detail)}</small></div>`).join('')}</div></section><section class="panel publish-audit"><div class="panel-head"><h2>Audit</h2><span class="small muted">publish handoff</span></div><div class="publish-audit-list">${PUBLISH.audit.map(a=>`<div><i class="${a.tone}"></i><span>${esc(a.time)}</span><b>${esc(a.event)}</b><small>${esc(a.detail)}</small></div>`).join('')}</div></section>`;
}
function publishPage(){
  return `<div class="page-title publish-title"><div><h1>Publish</h1><p>Candidate → target, PR/MR, and evidence. Merge and publication stay with the human.</p><div class="home-facts"><span>${PUBLISH.candidate.short}</span><span>target ${PUBLISH.candidate.target}</span><span>QA full</span><span>gate blocked</span><span id="publish-updated">${fmtClock(publishCheckedAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-publish-refresh>${icon('refresh')} Check</button><a class="btn" href="#reports">${icon('reports')} Reports</a><a class="btn" href="#orchestration">${icon('orchestration')} Orchestration</a></div></div>${publishKpis()}${publishTabs()}<div id="publish-view">${publishTab==='overview'?publishOverview():publishTab==='preflight'?publishPreflight():publishTab==='pr'?publishPR():publishEvidence()}</div>`;
}
function bindPublish(){
  document.querySelectorAll('[data-publish-tab]').forEach(btn=>{const on=btn.dataset.publishTab===publishTab;btn.classList.toggle('on',on);btn.setAttribute('aria-selected',String(on))});
}
function refreshPublishView(){
  const view=$('#publish-view');if(!view)return;
  view.innerHTML=publishTab==='overview'?publishOverview():publishTab==='preflight'?publishPreflight():publishTab==='pr'?publishPR():publishEvidence();
  bindPublish();
}

const BOARD_COLUMNS=[
  {id:'backlog',name:'Backlog',hint:'blocked / no status'},
  {id:'ready',name:'Ready to work',hint:'status::ready'},
  {id:'progress',name:'In progress',hint:'status::in-progress'},
  {id:'review',name:'Review / QA',hint:'dispatch or PR'},
  {id:'done',name:'Done',hint:'closed after merge'}
];
function boardSpec(){return BOARD_SPECS.find(s=>s.n===boardSpecId)||BOARD_SPECS[0]}
function boardTickets(){return boardDemo==='empty'?[]:boardSpec().tickets}
function boardFind(n){return BOARD_SPECS.flatMap(s=>s.tickets).find(t=>t.n===n)}
function boardStatus(t){return (t.labels||[]).find(l=>l.startsWith('status::'))||''}
function boardPriority(t){return (t.labels||[]).find(l=>l.startsWith('priority::'))||''}
function boardColumn(t){
  if(t.closed)return 'done';
  const s=boardStatus(t);
  if(s==='status::in-progress')return (t.dispatch==='code-review'||t.dispatch==='qa'||t.pr)?'review':'progress';
  return s==='status::ready'?'ready':'backlog';
}
function boardColumnName(id){return (BOARD_COLUMNS.find(c=>c.id===id)||{}).name||id}
function boardOpenBlockers(t){return (t.blockers||[]).filter(b=>{const x=boardFind(b.n);return x&&!x.closed})}
function boardVisible(t){
  if(boardPriorityFilter!=='all'&&boardPriority(t)!==boardPriorityFilter)return false;
  if(boardOnlyFree&&boardOpenBlockers(t).length)return false;
  const q=boardQuery.trim().toLowerCase();
  if(!q)return true;
  return (['#'+t.n,t.title,t.what,(t.labels||[]).join(' '),(t.blockers||[]).map(b=>'#'+b.n+' '+b.why).join(' '),(t.files||[]).map(f=>f.path).join(' ')].join(' ')).toLowerCase().includes(q);
}
function boardCommand(t){return (t.labels||[]).includes('hitl')?'/to-guide':(t.labels||[]).includes('pipeline::fast')?'/fast-implement':'/implement'}
function boardTransition(t,to){
  const from=boardColumn(t);
  if(from===to)return {ok:false,same:true};
  if(to==='review')return {ok:false,reason:'«Review / QA» is set by dispatch and PR; the card is not moved there'};
  if(to==='done')return {ok:false,reason:'«Done» completes ticket closure after a confirmed merge'};
  if(from==='done')return {ok:false,reason:'A closed ticket cannot be moved'};
  if(from==='review')return {ok:false,reason:'The ticket has an active batch or PR'};
  if(from==='backlog'&&to==='ready'){
    const ob=boardOpenBlockers(t);
    return ob.length?{ok:false,reason:'Open blockers: '+ob.map(b=>'#'+b.n).join(', ')}:{ok:true};
  }
  if(from==='ready'&&to==='progress')return {ok:true};
  if(from==='progress'&&to==='ready')return t.batch?{ok:false,reason:'Active batch '+t.batch}:{ok:true};
  return {ok:false,reason:'The transition goes through «Ready to work»'};
}
function boardPrompt(t){
  const s=boardSpec();
  const blockers=(t.blockers||[]).length?t.blockers.map(b=>`- #${b.n} — ${b.why}`).join('\n'):'- None';
  return [boardCommand(t)+' #'+t.n,'',`TICKET: #${t.n} — ${t.title}`,`EPIC: #${s.n} — ${s.title}`,`BRANCH: ${s.branch}`,'', 'WHAT TO BUILD:',t.what,'','ACCEPTANCE:',...(t.criteria||[]).map((c,i)=>`${i+1}. ${c}`),'','BLOCKERS:',blockers,'','DISCOVERY:',...(t.files||[]).map(f=>`- ${f.path}${f.why?' — '+f.why:''}`)].join('\n');
}
function boardKpis(){
  const ts=boardTickets(),open=ts.filter(t=>!t.closed).length,blocked=ts.filter(t=>boardOpenBlockers(t).length).length,active=ts.filter(t=>t.batch).length;
  return `<div class="board-kpis"><div><span>Open</span><b class="cyan">${open}</b><small>of ${ts.length} tickets</small></div><div><span>With blockers</span><b class="lavender">${blocked}</b><small>cannot be moved</small></div><div><span>Active batch</span><b class="violet">${active}</b><small>busy</small></div><div><span>Snapshot</span><b class="blue">2 min</b><small>${boardDemo==='down'?'tracker unavailable':'updated'}</small></div></div>`;
}
function boardState(kind){
  const map={
    nospecs:['No specs yet','The spec appears after /to-spec and /to-tickets. The board will show it after a refresh.'],
    empty:['No tasks on the board','The selected spec has no tickets yet. Split the spec with /to-tickets.'],
    loading:['Refreshing the board','Reading the tracker and statuses. The last confirmed snapshot is shown; cards are temporarily unavailable.']
  };
  const [h,p]=map[kind]||map.empty;
  return `<section class="panel board-state"><div class="board-state-icon">${icon(kind==='loading'?'refresh':'board')}</div><span class="eyebrow">BOARD · ${kind==='loading'?'LOADING':'EMPTY'}</span><h2>${h}</h2><p>${p}</p><div class="actions"><button class="btn primary" type="button" data-board-refresh>${icon('refresh')} Update</button><a class="btn" href="#help">${icon('help')} Help</a></div></section>`;
}
function boardToolbar(){
  return `<div class="board-toolbar"><label class="board-search">${icon('search')}<input id="board-search" type="search" value="${esc(boardQuery)}" placeholder="Find a task" aria-label="Task search"></label><select id="board-priority" aria-label="Priority"><option value="all">All priorities</option><option value="priority::p0" ${boardPriorityFilter==='priority::p0'?'selected':''}>P0</option><option value="priority::p1" ${boardPriorityFilter==='priority::p1'?'selected':''}>P1</option><option value="priority::p2" ${boardPriorityFilter==='priority::p2'?'selected':''}>P2</option></select><label class="board-free"><input id="board-free" type="checkbox" ${boardOnlyFree?'checked':''}> No blockers</label><button class="btn" type="button" data-board-reset>Reset</button></div>`;
}
function boardBanner(){
  if(boardDemo==='down')return `<div class="board-banner down">${icon('warning')}<span><b>Tracker is unavailable.</b> gh: authentication required. A snapshot from 2 min ago is shown; moving cards is unavailable.</span></div>`;
  if(boardDemo==='busy')return `<div class="board-banner busy">${icon('clock')}<span><b>A mutating command is running:</b> harness update (started from the TUI). Reads work; a move will be rejected as «busy».</span></div>`;
  return '';
}
function boardCard(t){
  const ob=boardOpenBlockers(t),prio=boardPriority(t).replace('priority::','').toUpperCase();
  return `<article class="board-card" tabindex="0" draggable="true" data-board-ticket="${t.n}" aria-label="#${t.n} ${esc(t.title)}"><div class="board-card-meta"><span>#${t.n}</span>${prio?`<em class="board-prio ${prio.toLowerCase()}">${prio}</em>`:''}</div><h3>${esc(t.title)}</h3><p>${esc(t.what.split('\n')[0])}</p><div class="board-card-chips"><span class="board-chip command">${esc(boardCommand(t))}</span>${t.dispatch?`<span class="board-chip role">dispatch: ${esc(t.dispatch)}</span>`:''}${t.closed?'':ob.length?`<span class="board-chip blocker">blockers: ${ob.length}</span>`:'<span class="board-chip free">no blockers</span>'}</div><div class="board-card-foot"><span>criteria: ${(t.criteria||[]).length}</span><a href="https://github.com/PVMalove/agent-harness-next/issues/${t.n}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">Open ${icon('external')}</a></div></article>`;
}
function boardColumns(){
  const shown=boardTickets().filter(boardVisible);
  return `<div class="board-columns">${BOARD_COLUMNS.map(c=>{const items=shown.filter(t=>boardColumn(t)===c.id).sort((a,b)=>(boardPriority(a)||'priority::p9').localeCompare(boardPriority(b)||'priority::p9')||a.n-b.n);return `<section class="board-col" data-board-col="${c.id}"><header><div><b>${c.name}</b><small>${c.hint}</small></div><span>${items.length}</span></header><div class="board-cards">${items.length?items.map(boardCard).join(''):'<div class="board-empty">empty</div>'}</div></section>`}).join('')}</div>`;
}
function boardPage(){
  const s=boardSpec();
  let body;
  if(boardDemo==='nospecs')body=boardState('nospecs');
  else if(boardDemo==='loading')body=boardState('loading');
  else if(boardDemo==='empty')body=boardState('empty');
  else body=`${boardKpis()}${boardBanner()}${boardToolbar()}<div class="board-count" id="board-count">${boardTickets().filter(boardVisible).length} of ${boardTickets().length}</div><div id="board-columns">${boardColumns()}</div>`;
  return `<div class="board-page"><div class="page-title board-title"><div><h1>Task board</h1><p>One board per spec. Columns, blockers, and moves match the tracker.</p><div class="home-facts"><span>${esc(s.title)}</span><span>${esc(s.branch)}</span><span>${boardTickets().length} tickets</span><span id="board-snapshot">${fmtClock(boardSnapshotAt)}</span></div></div><div class="actions"><button class="btn" type="button" data-board-refresh>${icon('refresh')} Update</button><a class="btn" href="#orchestration">${icon('orchestration')} Orchestration</a></div></div><div class="board-specbar"><label>Spec<select id="board-spec" aria-label="Select a spec">${BOARD_SPECS.map(x=>`<option value="${x.n}" ${x.n===s.n?'selected':''}>#${x.n} · ${esc(x.title)} — ${x.tickets.length} tasks</option>`).join('')}</select></label><span class="board-spec-meta">${s.tickets.length} tasks · ${s.tickets.filter(t=>!t.closed).length} open</span><select id="board-demo" class="board-demo" aria-label="Demo board state"><option value="ok" ${boardDemo==='ok'?'selected':''}>State: normal</option><option value="down" ${boardDemo==='down'?'selected':''}>tracker unavailable</option><option value="busy" ${boardDemo==='busy'?'selected':''}>busy</option><option value="error" ${boardDemo==='error'?'selected':''}>write error</option><option value="nospecs" ${boardDemo==='nospecs'?'selected':''}>no specs</option><option value="empty" ${boardDemo==='empty'?'selected':''}>empty board</option><option value="loading" ${boardDemo==='loading'?'selected':''}>update</option></select></div>${body}<dialog id="board-ticket" class="board-dialog"><div class="board-modal" id="board-modal"></div></dialog><dialog id="board-confirm" class="board-dialog board-confirm"><div id="board-confirm-body"></div></dialog>`;
}
let boardDragging=null;
function bindBoardCards(){
  document.querySelectorAll('[data-board-ticket]').forEach(card=>{
    const n=Number(card.dataset.boardTicket);
    card.addEventListener('click',e=>{if(e.target.closest('a'))return;boardOpen(n)});
    card.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();boardOpen(n)}});
    card.addEventListener('dragstart',e=>{const t=boardFind(n);if(!t)return;boardDragging=t;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(n));card.classList.add('dragging');boardMarkTargets(t)});
    card.addEventListener('dragend',()=>{card.classList.remove('dragging');boardDragging=null;document.querySelectorAll('[data-board-col]').forEach(c=>c.classList.remove('drop-ok','drop-no'))});
  });
  document.querySelectorAll('[data-board-col]').forEach(col=>{
    col.addEventListener('dragover',e=>{if(boardDragging)e.preventDefault()});
    col.addEventListener('drop',e=>{e.preventDefault();if(boardDragging)requestBoardMove(boardDragging,col.dataset.boardCol)});
  });
}
function bindBoard(){
  const spec=$('#board-spec');if(spec)spec.addEventListener('change',()=>{boardSpecId=Number(spec.value);boardSnapshotAt=new Date();refreshBoard()});
  const demo=$('#board-demo');if(demo)demo.addEventListener('change',()=>{boardDemo=demo.value;refreshBoard()});
  const search=$('#board-search');if(search)search.addEventListener('input',()=>{boardQuery=search.value;refreshBoardColumns()});
  const prio=$('#board-priority');if(prio)prio.addEventListener('change',()=>{boardPriorityFilter=prio.value;refreshBoardColumns()});
  const free=$('#board-free');if(free)free.addEventListener('change',()=>{boardOnlyFree=free.checked;refreshBoardColumns()});
  const reset=$('[data-board-reset]');if(reset)reset.addEventListener('click',()=>{boardQuery='';boardPriorityFilter='all';boardOnlyFree=false;refreshBoard()});
  const refresh=$('[data-board-refresh]');if(refresh)refresh.addEventListener('click',()=>{if(boardDemo==='down'){toast('The tracker is unavailable: showing the previous snapshot','err');return}boardSnapshotAt=new Date();refreshBoard();toast('Board updated (demo)')});
  bindBoardCards();
}
function refreshBoard(){
  const main=$('#content');if(!main)return;
  main.innerHTML=boardPage();bindBoard();
}
function refreshBoardColumns(){
  const box=$('#board-columns');if(box)box.outerHTML=boardColumns();
  const count=$('#board-count');if(count)count.textContent=`${boardTickets().filter(boardVisible).length} of ${boardTickets().length}`;
  bindBoardCards();
}

function boardModalContent(){
  const t=boardFind(boardSelected);if(!t)return '';
  const ob=boardOpenBlockers(t),s=boardSpec();
  const status=boardColumn(t);
  const tabs=[['context','Context'],['acceptance',`Acceptance (${(t.criteria||[]).length})`],['prompt','Prompt']];
  const tabBody=boardTab==='context'?`<div class="board-context"><h4>Blockers</h4>${t.blockers?.length?t.blockers.map(b=>{const x=boardFind(b.n);return `<div class="board-blocker"><b>#${b.n}</b><span>${esc(b.why)}</span><em class="orch-pill ${x?.closed?'mint':'lavender'}">${x?.closed?'closed':'open'}</em></div>`}).join(''):'<p class="muted">No blockers.</p>'}<h4>Discovery Context</h4>${(t.files||[]).length?t.files.map(f=>`<div class="board-file"><code>${esc(f.path)}</code><span>${esc(f.why)}</span></div>`).join(''):'<p class="muted">No files specified.</p>'}</div>`:boardTab==='acceptance'?`<ol class="board-acceptance">${(t.criteria||[]).map(c=>`<li>${esc(c)}</li>`).join('')}</ol>`:`<pre class="board-prompt">${esc(boardPrompt(t))}</pre>`;
  return `<div class="board-modal-head"><div><span class="eyebrow">#${t.n} · ${esc(s.title)}</span><h2>${esc(t.title)}</h2><div class="board-modal-labels">${(t.labels||[]).map(l=>`<em class="orch-pill ${l.includes('p0')?'violet':l.includes('p1')?'blue':'muted'}">${esc(l)}</em>`).join('')}<em class="orch-pill mint">${t.sp||'—'} SP</em></div></div><button class="icon-btn" type="button" data-board-close aria-label="Close">✕</button></div><div class="board-modal-links"><a href="https://github.com/PVMalove/agent-harness-next/issues/${t.n}" target="_blank" rel="noopener noreferrer">issue #${t.n} ${icon('external')}</a>${t.pr?`<a href="https://github.com/PVMalove/agent-harness-next/pull/${t.pr.replace('#','')}" target="_blank" rel="noopener noreferrer">PR ${esc(t.pr)} ${icon('external')}</a>`:''}<span class="branch-inline">${icon('branch')}<b>${esc(s.branch)}</b></span><span class="board-status-label">${boardColumnName(status)}</span><select id="board-status" aria-label="Change status">${BOARD_COLUMNS.map(c=>`<option value="${c.id}" ${c.id===status?'selected':''}>${c.name}</option>`).join('')}</select></div><div class="board-modal-tabs">${tabs.map(([id,l])=>`<button type="button" class="${boardTab===id?'on':''}" data-board-tab="${id}">${l}</button>`).join('')}<button class="btn" type="button" data-board-copy>${icon('download')} Copy</button></div><div class="board-modal-body">${tabBody}</div>`;
}
function boardOpen(n){
  boardSelected=n;boardTab='context';
  const dlg=$('#board-ticket');if(!dlg)return;
  $('#board-modal').innerHTML=boardModalContent();
  dlg.showModal();
  bindBoardModal();
}
function bindBoardModal(){
  const dlg=$('#board-ticket');if(!dlg)return;
  dlg.querySelectorAll('[data-board-tab]').forEach(btn=>btn.addEventListener('click',()=>{boardTab=btn.dataset.boardTab;dlg.querySelector('#board-modal').innerHTML=boardModalContent();bindBoardModal()}));
  const close=dlg.querySelector('[data-board-close]');if(close)close.addEventListener('click',()=>dlg.close());
  const status=dlg.querySelector('#board-status');if(status)status.addEventListener('change',()=>{const t=boardFind(boardSelected);if(t)requestBoardMove(t,status.value);});
  const copy=dlg.querySelector('[data-board-copy]');if(copy)copy.addEventListener('click',()=>{const x=boardCopyPayload();copyBoardText(x.text,x.label)});
}
function boardCopyPayload(){
  const t=boardFind(boardSelected);if(!t)return {text:'',label:'Text'};
  if(boardTab==='acceptance')return {text:(t.criteria||[]).map((c,i)=>`${i+1}. ${c}`).join('\n'),label:'Criteria'};
  return {text:boardPrompt(t),label:'Prompt'};
}
function copyBoardText(text,label){
  if(navigator.clipboard?.writeText)navigator.clipboard.writeText(text).then(()=>toast(label+' copied')).catch(()=>reader(label,text));
  else reader(label,text);
}
function boardMarkTargets(t){
  document.querySelectorAll('[data-board-col]').forEach(col=>{const r=boardTransition(t,col.dataset.boardCol);col.classList.toggle('drop-ok',!!r.ok);col.classList.toggle('drop-no',!!r.reason);col.dataset.reason=r.reason||''});
}
function requestBoardMove(t,to){
  const r=boardTransition(t,to);
  if(r.same)return;
  if(!r.ok){toast(`#${t.n} → «${BOARD_COLUMNS.find(c=>c.id===to)?.name||to}»: ${r.reason}`,'err');const s=$('#board-status');if(s)s.value=boardColumn(t);return}
  if(boardDemo==='down'){toast('Tracker unavailable: the status change was not recorded','err');return}
  if(boardDemo==='busy'){toast('Busy: harness update','err');return}
  if(boardDemo==='error'){toast('Tracker write error: the change was not saved','err');return}
  const dlg=$('#board-confirm');if(!dlg)return;
  const from=boardColumn(t),toName=BOARD_COLUMNS.find(c=>c.id===to)?.name||to;
  $('#board-confirm-body').innerHTML=`<div class="board-modal-head"><div><span class="eyebrow">STATUS CHANGE</span><h2>#${t.n} → ${esc(toName)}</h2><p>${esc(t.title)}</p></div><button class="icon-btn" type="button" data-board-confirm-close>✕</button></div><div class="board-confirm-diff"><s>${from}</s><b>→</b><ins>${to}</ins></div><p class="board-confirm-note">The server will run the label change in GitHub as a mutating job and update the board.</p><div class="actions"><button class="btn" type="button" data-board-confirm-close>Cancel</button><button class="btn primary" type="button" id="board-confirm-ok">Change status</button></div>`;
  dlg.showModal();
  let moved=false;
  dlg.addEventListener('close',()=>{if(!moved){const sel=$('#board-status');if(sel)sel.value=boardColumn(t)}},{once:true});
  dlg.querySelectorAll('[data-board-confirm-close]').forEach(b=>b.addEventListener('click',()=>dlg.close()));
  const ok=$('#board-confirm-ok');ok?.addEventListener('click',()=>{moved=true;t.labels=(t.labels||[]).filter(l=>!l.startsWith('status::'));t.labels.push(to==='progress'?'status::in-progress':'status::ready');t.closed=false;boardSnapshotAt=new Date();boardSelected=t.n;dlg.close();$('#board-ticket')?.close();refreshBoard();toast(`#${t.n}: status updated (demo)`)});
}

function contourSvg(){
  const s=HOME.store;
  return `<svg class="contour-svg" viewBox="0 0 1000 400" role="img" aria-label="Harness 2.0.0 contour readiness: Python policy, IPC, Rust runtime, SQLite WAL, supervisor, and audit chain">
    <title>Harness 2.0.0 architecture</title>
    <defs><marker id="ct-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#6b7787"/></marker><marker id="ct-arrow-blue" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8z" fill="#6fa8dc"/></marker></defs>
    <rect class="ct-lane" x="12" y="10" width="976" height="105" rx="6"/>
    <rect class="ct-lane" x="12" y="125" width="976" height="140" rx="6"/>
    <rect class="ct-lane" x="12" y="272" width="976" height="112" rx="6"/>
    <text class="ct-lane-label" x="24" y="31">01 · POLICY</text>
    <text class="ct-lane-label" x="24" y="146">02 · RUNTIME</text>
    <text class="ct-lane-label" x="24" y="292">03 · EVIDENCE</text>

    <g class="ct-node"><rect x="30" y="42" width="250" height="64" rx="7"/><text class="ct-title" x="43" y="61">Python policy</text><text class="ct-sub" x="43" y="77">coordinator · approval</text><text class="ct-sub" x="43" y="89">verification plan</text><text class="ct-status" x="43" y="101">ready</text></g>
    <g class="ct-node"><rect x="342" y="42" width="200" height="64" rx="7"/><text class="ct-title" x="355" y="61">runtime_client · IPC</text><text class="ct-sub" x="355" y="77">typed request · revision CAS</text><text class="ct-status" x="355" y="101">validated</text></g>

    <g class="ct-node primary"><rect x="342" y="145" width="250" height="70" rx="7"/><text class="ct-title" x="355" y="165">Rust runtime</text><text class="ct-sub" x="355" y="181">single writer · schema ${s.schema}</text><text class="ct-status" x="355" y="199">ready</text></g>
    <g class="ct-node"><rect x="680" y="140" width="296" height="54" rx="7"/><text class="ct-title" x="693" y="160">SQLite WAL store</text><text class="ct-sub" x="693" y="176">schema ${s.schema} · generation ${s.generation}</text></g>
    <g class="ct-node"><rect x="680" y="204" width="296" height="54" rx="7"/><text class="ct-title" x="693" y="224">Supervisor</text><text class="ct-sub" x="693" y="240">process · OCI · QA · ${s.features} feat.</text></g>

    <g class="ct-node"><rect x="342" y="292" width="250" height="54" rx="7"/><text class="ct-title" x="355" y="311">Audit chain</text><text class="ct-sub" x="355" y="327">${s.audit} records · verified</text></g>
    <g class="ct-node"><rect x="680" y="292" width="296" height="54" rx="7"/><text class="ct-title" x="693" y="311">Execution receipts</text><text class="ct-sub" x="693" y="327">exit evidence · lost evidence</text></g>

    <path class="ct-edge" d="M280 74H342" marker-end="url(#ct-arrow)"/>
    <path class="ct-edge blue" d="M542 74H600V112H465V145" marker-end="url(#ct-arrow-blue)"/>
    <path class="ct-edge" d="M592 167H680" marker-end="url(#ct-arrow)"/>
    <path class="ct-edge" d="M592 200H646V231H680" marker-end="url(#ct-arrow)"/>
    <path class="ct-edge" d="M465 215V292" marker-end="url(#ct-arrow)"/>
    <path class="ct-edge" d="M828 258V292" marker-end="url(#ct-arrow)"/>
    <text class="ct-edge-label" x="288" y="68">decision</text>
    <text class="ct-edge-label" x="552" y="68">typed</text>
    <text class="ct-edge-label" x="600" y="161">write</text>
    <text class="ct-edge-label" x="600" y="194">launch</text>
    <text class="ct-edge-label" x="472" y="284">audit</text>
  </svg>`;
}
function homeContour(){
  const s=HOME.store;
  return `<section class="panel contour-panel">
    <div class="panel-head"><h2>Harness 2.0.0 architecture</h2><span class="contour-ready">${icon('check')} runtime-store · ready</span></div>
    <div class="body">
      <div class="contour-scroll">${contourSvg()}</div>
      <div class="contour-facts">
        <div><span>authority</span><b>${s.authority}</b></div>
        <div><span>schema</span><b>${s.schema}</b></div>
        <div><span>generation</span><b>${s.generation}</b></div>
        <div><span>audit</span><b>${s.audit}</b></div>
        <div><span>cutover</span><b>${s.cutover}</b></div>
        <div><span>Repo Map</span><b>${HOME.repoMap.tier}</b></div>
      </div>
      <p class="contour-note">The diagram shows 2.0.0 contour readiness, not the flow of a specific batch. Python decides; Rust writes state and executes.</p>
    </div>
  </section>`;
}
function homeContext(){
  const kv=(label,value,cls='')=>`<div><dt>${label}</dt><dd class="${cls}">${value}</dd></div>`;
  return `<section class="panel context-panel">
    <div class="panel-head"><h2>Context</h2><span class="small muted">${dataProjectLabel()}</span></div>
    <div class="context-grid">
    <div class="context-section"><h3>${icon(HOME.provider.type==='gitlab'?'gitlab-mark':'github-mark')} Project <span class="provider">${HOME.provider.type==='gitlab'?'GitLab':'GitHub'}</span></h3><dl class="kv">${kv('Name',project)}${kv('Branch',branch)}${kv('Tracker',`${HOME.provider.host}/${HOME.provider.repo.replace('/','/<wbr>')}`)}</dl></div>
    <div class="context-section"><h3>${icon('harness')} Harness</h3><dl class="kv">${kv('Package','2.0.0 · pre-release','good')}${kv('Installed','1.5.1')}${kv('Capability','1 · backend-orchestration')}${kv('Skills',`${HOME.skills.installed} · drift ${HOME.skills.drift}`,'warning')}</dl></div>
    <div class="context-section"><h3>${icon('store')} Runtime store</h3><dl class="kv">${kv('Authority',HOME.store.authority,'good')}${kv('Schema',HOME.store.schema)}${kv('Generation',HOME.store.generation)}${kv('Audit',`${HOME.store.audit} records`)}${kv('Cutover',HOME.store.cutover)}</dl></div>
    <div class="context-section"><h3>${icon('map')} Repo Map</h3><dl class="kv">${kv('Tier',HOME.repoMap.tier,'good')}${kv('Files',fmtNum(HOME.repoMap.files))}${kv('Links',fmtNum(HOME.repoMap.edges))}${kv('Volume',`≈${fmtNum(HOME.repoMap.tokens)} tokens`)}</dl></div>
    <div class="context-section"><h3>${icon('memory')} Memory</h3><dl class="kv">${kv('State','index missing','warning')}${kv('Sources','adr · glossary')}${kv('Limit',`${HOME.memory.topK} · ${fmtNum(HOME.memory.maxTokens)} tokens`)}</dl><p class="aside-note">FTS5 without a model; the vector slice is not connected.</p></div>
    </div>
  </section>`;
}
function dataProjectLabel(){return 'claude-agent-harness'}
function homeTasks(){
  const iconFor=t=>t==='ok'?'play':t==='err'?'blocked':'awaiting';
  const rows=HOME.tasks.map(t=>`<a class="task-row" href="#orchestration">
    <span class="task-id">${esc(t.id)}</span>
    <span class="task-role">${icon(t.role)}</span>
    <span class="task-title">${esc(t.title)}</span>
    <span class="task-status ${t.tone}">${icon(iconFor(t.tone))} ${esc(t.status)}</span>
    <span class="task-time">${esc(t.time)}</span>
  </a>`).join('');
  const steps=HOME.route.steps.map(step=>`<div class="route-step ${step.state}"><span class="route-dot"></span><span class="route-copy"><b>${esc(step.name)}</b><small>${esc(step.label)}</small></span></div>`).join('');
  return `<section class="panel tasks-panel">
    <div class="panel-head"><h2>Recent tasks <span class="small muted">3</span></h2><a href="#orchestration" class="small">Orchestration →</a></div>
    <div class="task-head"><span>Session</span><span></span><span>Task</span><span>Status</span><span>Time</span></div>
    <div class="task-list">${rows}</div>
    <div class="active-route"><div class="route-head"><h3>Session route ${esc(HOME.route.id)}</h3><a href="#agent-activity" class="small">Work progress →</a></div><div class="route-scroll"><div class="route-steps">${steps}</div></div></div>
  </section>`;
}
function homePage(){
  return `<div class="page-title home-title"><div><h1>Harness state</h1><p>Health, runtime-store, skills, and 2.0.0 readiness.</p><div class="home-facts"><span>2.0.0 · pre-release</span><span>installed 1.5.1</span><span>runtime-store</span><span>42 ok · 1 warn · 2 fail · 11 skip</span><span>32 skills</span><span>Repo Map full</span></div></div><div class="actions"><button class="btn" data-home-refresh>${icon('refresh')} Check</button><a class="btn" href="#diagnostics">${icon('pulse')} Diagnostics</a><a class="btn primary" href="#update-harness">Update</a></div></div>
  <div class="home-main">
    <section class="panel home-attn"><div class="panel-head"><h2>Needs attention</h2><span class="small muted">2 errors · 1 warning</span></div>${homeAttention()}</section>
    ${homeContext()}
    ${homeTasks()}
    <section class="panel health-panel"><div class="panel-head"><div class="health-head-title"><h2>Health</h2><span class="small muted" id="home-checked">${fmtClock(checkedAt)} · ${healthTotals().total} checks</span></div><div class="health-mode"><span id="health-mode-note" class="small muted">${healthMode==='online'?'online not run · 11 skipped':'offline · 56 checks'}</span><div class="seg"><button class="${healthMode==='offline'?'on':''}" type="button" data-health-mode="offline" aria-pressed="${healthMode==='offline'}">Offline</button><button class="${healthMode==='online'?'on':''}" type="button" data-health-mode="online" aria-pressed="${healthMode==='online'}">Online</button></div></div></div><div class="body">${healthSummary()}<div class="health-cols"><section class="health-areas"><div class="subhead"><h3>By area</h3><a href="#diagnostics" class="small">All checks →</a></div><div class="health-areas-grid">${homeAreas()}</div></section><section class="health-checks"><div class="subhead"><h3>Checks</h3><div class="chips"><button class="chip ${homeFilter==='all'?'on':''}" data-home-filter="all">All</button><button class="chip ${homeFilter==='problem'?'on':''}" data-home-filter="problem">Problems</button><button class="chip ${homeFilter==='skipped'?'on':''}" data-home-filter="skipped">Skipped</button></div></div><div id="home-checks" class="checks-scroll" tabindex="0" aria-label="Checks; scroll the list to see the rest">${homeChecks()}</div></section></div></div></section>
    ${homeContour()}
  </div>`;
}
function bindHome(){
  document.querySelectorAll('[data-home-filter]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.homeFilter===homeFilter)));
  document.querySelectorAll('[data-health-mode]').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.healthMode===healthMode)));
}

document.addEventListener('input',e=>{if(e.target.id==='reports-search'){reportQuery=e.target.value;refreshReports()}if(e.target.id==='repo-symbol-search'){repoQuery=e.target.value;updateRepoSymbols()}if(e.target.matches('[data-settings-value]')){const p=settingsParam();p.value=e.target.type==='number'?Number(e.target.value):e.target.value;settingsAiAdvice=''}if(e.target.id==='diag-search'){diagQuery=e.target.value;updateDiag()}if(e.target.id==='report-search')renderReports(e.target.value);if(e.target.id==='symbol-search')renderSymbols(e.target.value);if(e.target.id==='config')configs[file]=e.target.value;if(e.target.id==='reader-search'){const q=e.target.value.toLowerCase(),lines=readerText.split('\n').filter(l=>l.toLowerCase().includes(q));$('#reader-output').textContent=lines.join('\n');$('#reader-status').textContent=q?`Matching lines: ${lines.length}`:'Demo data'}});
document.addEventListener('change',e=>{
  if(e.target.id==='actor'){actor=e.target.value;renderEvents()}
  if(e.target.matches('[data-update-mode]')){updateMode=e.target.dataset.updateMode;refreshUpdate()}
  if(e.target.matches('[data-seed-file]')){seedSelected[e.target.dataset.seedFile]=e.target.checked;refreshUpdate()}
  if(e.target.matches('[data-capability]')){projectCapability=e.target.dataset.capability;refreshInstallCapability()}
  if(e.target.matches('[data-settings-use]')){settingsParam().use=e.target.checked;return}
  if(e.target.matches('[data-settings-bool]')){const p=settingsParam();p.value=e.target.checked;settingsAiAdvice='';refreshSettingsWizard();return}
  if(e.target.matches('[data-settings-param-select]')){settingsParamIndex=Number(e.target.value)||0;settingsAiAdvice='';refreshSettingsWizard();return}
  if(e.target.id==='work-role'){workRole=e.target.value;ensureWorkSelection();refreshWork()}
  if(e.target.id==='report-status'){reportStatus=e.target.value;ensureReportSelection();refreshReports()}
  if(e.target.id==='orch-role'){orchRole=e.target.value;refreshOrch()}
  if(e.target.id==='orch-status'){orchStatus=e.target.value;refreshOrch()}
});
document.addEventListener('click',e=>{const el=e.target.closest('[data-action],[data-restore],[data-config],[data-symbol]');if(!el)return;if(el.dataset.symbol){e.preventDefault();$('#symbol-search').value=el.dataset.symbol;renderSymbols(el.dataset.symbol);return}if(el.dataset.restore!==undefined){const v=versions[Number(el.dataset.restore)];file=v.file;configs[file]=v.text;if(route==='configuration'){settingsTab=v.file==='orchestration.json'?'orchestration':'project'}render();toast('Demo version restored in the editor');return}if(el.dataset.config){file=el.dataset.config;render();return}const action=el.dataset.action;if(sources[action]){reader(el.textContent,sources[action]);return}if(action==='browse'){reader('Choose a local project','Demo candidates:\n/home/developer/projects/claude-agent-harness\n/home/developer/projects/backend-api\n\nEnter the path in the project field. The browser has no access to the entire file system.');return}if(action==='check-path'){const path=$('#project-path').value.trim();const valid=path.startsWith('/')&&path.length>1;$('#path-status').textContent=valid?'Demo check: path accepted. Git presence was not checked.':'Enter an absolute path';$('#plan-project').textContent=path||'Not specified';$('#switch-project').disabled=!valid;return}if(action==='switch-project'){project=$('#project-path').value.split('/').filter(Boolean).at(-1);location.hash='home';toast('Mockup context switched; the server was not changed');return}if(action==='filter-errors'||action==='show-checks'){$('#check-list').innerHTML=checks(action==='filter-errors');return}if(action==='online'){reader('Online checks','DEMO · Online checks\nGitHub permissions: not verified\nGitLab permissions: not verified\nNo network credentials accessed.');return}if(action==='cleanup'||action==='update-plan'){reader('Plan · no execution','DEMO · Preview only\nManaged files: review required\nLocal changes: preserve\nConflicts: resolve before execution\nNo process launched, no files modified.');return}if(action==='validate'||action==='save-version'){try{JSON.parse($('#config').value);$('#validation').textContent='The JSON is syntactically valid. The project schema was not checked.';if(action==='save-version'){versions.push({file,text:$('#config').value});renderVersions();if(route==='configuration')refreshSettingsView();toast('Demo version saved in memory')}}catch(err){$('#validation').textContent='JSON error: '+err.message}return}if(action==='next-event'){events.push([['main','standards','spec'][added++%3],'Demo step '+added,'Added manually through the simulator']);renderEvents();return}if(action==='host-facts')reader('Host facts · example','DEMO · not your host\nrootless: true\nselinux: enforcing\ncgroupVersion: v2\nActual host: not inspected.')});
$('#expand').addEventListener('click',()=>{const full=$('#reader').classList.toggle('full');$('#expand').setAttribute('aria-pressed',full);$('#expand').textContent=full?'Collapse':'Expand'});
const menuToggle=$('#menu-toggle');if(menuToggle){menuToggle.innerHTML=icon('menu');menuToggle.addEventListener('click',()=>{document.body.classList.contains('nav-open')?closeNav():openNav()})}
const collapseToggle=$('#nav-collapse');if(collapseToggle){collapseToggle.innerHTML=icon('chevron');collapseToggle.addEventListener('click',()=>setNavCollapsed(!document.body.classList.contains('nav-collapsed')))}
try{setNavCollapsed(localStorage.getItem('harness-nav-collapsed')==='1')}catch{setNavCollapsed(false)}
const navScrim=$('#nav-scrim');if(navScrim)navScrim.addEventListener('click',closeNav);
$('#navigation').addEventListener('click',e=>{if(e.target.closest('a'))closeNav()});
document.addEventListener('click',e=>{
  const df=e.target.closest('[data-diag-filter]');
  if(df){e.preventDefault();diagFilter=df.dataset.diagFilter;updateDiag();return}
  const ds=e.target.closest('[data-diag-select]');
  if(ds){e.preventDefault();diagSelected=ds.dataset.diagSelect;updateDiag();return}
  const otab=e.target.closest('[data-orch-tab]');
  if(otab){e.preventDefault();orchTab=otab.dataset.orchTab;refreshOrchView();return}
  const oref=e.target.closest('[data-orch-refresh]');
  if(oref){e.preventDefault();orchUpdatedAt=new Date();const node=$('#orch-updated');if(node)node.textContent=fmtClock(orchUpdatedAt);toast('Orchestration reloaded (demo)');return}
  const hcont=e.target.closest('[data-harness-container]');
  if(hcont){e.preventDefault();harnessContainerLogs(hcont.dataset.harnessContainer);return}
  const hclean=e.target.closest('[data-harness-cleanup]');
  if(hclean){e.preventDefault();reader('Container cleanup plan','DEMO · CLEANUP PLAN\n\nstopped containers: 1\ndangling images: 0\nunused volumes: 0\n\nNothing was deleted. Human confirmation is required.');return}
  const sgroup=e.target.closest('[data-settings-group]');
  if(sgroup){e.preventDefault();const gr=SETTINGS_WIZARD.groups.find(g=>g.id===sgroup.dataset.settingsGroup);if(gr){settingsParamIndex=SETTINGS_WIZARD.params.findIndex(p=>p.key===gr.params[0]);settingsAiAdvice='';refreshSettingsWizard()}return}
  const saccept=e.target.closest('[data-settings-accept]');
  if(saccept){e.preventDefault();const p=settingsParam();p.value=p.recommend;p.use=true;settingsAiAdvice='';refreshSettingsWizard();toast('Recommendation applied to the draft');return}
  const sprev=e.target.closest('[data-settings-prev]');
  if(sprev){e.preventDefault();settingsParamIndex=Math.max(0,settingsParamIndex-1);settingsAiAdvice='';refreshSettingsWizard();return}
  const snext=e.target.closest('[data-settings-next]');
  if(snext){e.preventDefault();settingsParamIndex=Math.min(SETTINGS_WIZARD.params.length-1,settingsParamIndex+1);settingsAiAdvice='';refreshSettingsWizard();return}
  const sclicheck=e.target.closest('[data-settings-ai-check]');
  if(sclicheck){e.preventDefault();reader('CLI check',`DEMO · CLI CHECK

Codex CLI: ready
Claude Code CLI: unavailable

The network and authorization were not used. The model was not called.`);return}
  const sask=e.target.closest('[data-settings-ai-ask]');
  if(sask){e.preventDefault();const p=settingsParam();settingsAiAdvice=`I recommend ${p.type==='boolean'?(p.recommend?'enable':'disable'):'keep'} ${p.key} = ${String(p.recommend)}. Reason: the current configuration matches the project; there is no need to change it without new data.`;refreshSettingsWizard();return}
  const sai=e.target.closest('[data-settings-ai-accept]');
  if(sai){e.preventDefault();if(!settingsAiAdvice)return;const p=settingsParam();p.value=p.recommend;p.use=true;settingsAiAdvice='';refreshSettingsWizard();toast('AI advice applied to the draft');return}
  const spreview=e.target.closest('[data-settings-preview]');
  if(spreview){e.preventDefault();reader('Configuration preview',JSON.stringify(Object.fromEntries(SETTINGS_WIZARD.params.map(x=>[x.key,x.value])),null,2));return}
  const sdraft=e.target.closest('[data-settings-draft]');
  if(sdraft){e.preventDefault();toast('Draft saved in memory (demo); files did not change');return}
  const ptab=e.target.closest('[data-publish-tab]');
  if(ptab){e.preventDefault();publishTab=ptab.dataset.publishTab;refreshPublishView();return}
  const pref=e.target.closest('[data-publish-refresh]');
  if(pref){e.preventDefault();publishCheckedAt=new Date();const node=$('#publish-updated');if(node)node.textContent=fmtClock(publishCheckedAt);toast('Preflight re-read (demo); PR was not created');return}
  const pwhy=e.target.closest('[data-publish-why]');
  if(pwhy){e.preventDefault();reader('Why the PR is blocked',`DEMO · PUBLISH BLOCKED

${PUBLISH.reasons.join('\n')}

Release Gate must confirm the candidate/target pair before preparing the PR.`);return}
  const ppcopy=e.target.closest('[data-publish-copy]');
  if(ppcopy){e.preventDefault();reader('PR body',PUBLISH.pr.body);return}
  const helptab=e.target.closest('[data-help-tab]');
  if(helptab){e.preventDefault();helpTab=helptab.dataset.helpTab;refreshHelpView();return}
  const helpcmd=e.target.closest('[data-help-command]');
  if(helpcmd){e.preventDefault();harnessCommand(helpcmd.dataset.helpCommand);return}
  const helpmd=e.target.closest('[data-help-readme]');
  if(helpmd){e.preventDefault();reader('README · Harness Console 2.0.0',`DEMO · README

Harness Console 2.0.0 — interactive mockup.

Sections: Home, Diagnostics, Update, Project, Progress,
Orchestration, Reports, Harness, Repo Map, Settings.

All data is demo data. Commands are not executed.
Files, Git, and runtime are not modified.`);return}
  const stab=e.target.closest('[data-settings-tab]');
  if(stab){e.preventDefault();settingsTab=stab.dataset.settingsTab;refreshSettingsView();return}
  const sref=e.target.closest('[data-settings-refresh]');
  if(sref){e.preventDefault();settingsCheckedAt=new Date();const node=$('#settings-updated');if(node)node.textContent=fmtClock(settingsCheckedAt);toast('Configurations reloaded (demo); files were not changed');return}
  const sexp=e.target.closest('[data-settings-export]');
  if(sexp){e.preventDefault();exportSettings();return}
  const rdir=e.target.closest('[data-repo-dir]');
  if(rdir){e.preventDefault();repoExpanded[rdir.dataset.repoDir]=repoExpanded[rdir.dataset.repoDir]===false;refreshRepoView();return}
  const rfile=e.target.closest('[data-repo-file]');
  if(rfile){e.preventDefault();repoFile=rfile.dataset.repoFile;refreshRepoFileView();return}
  const rkind=e.target.closest('[data-repo-kind]');
  if(rkind){e.preventDefault();repoKind=rkind.dataset.repoKind;ensureRepoSelection();refreshRepoView();return}
  const rmod=e.target.closest('[data-repo-module]');
  if(rmod){e.preventDefault();repoModule=rmod.dataset.repoModule;ensureRepoSelection();if(repoTab!=='symbols')repoTab='symbols';refreshRepoView();return}
  const rsym=e.target.closest('[data-repo-symbol]');
  if(rsym){e.preventDefault();repoSelected=rsym.dataset.repoSymbol;refreshRepoView();return}
  const rbuild=e.target.closest('[data-repo-rebuild]');
  if(rbuild){e.preventDefault();reader('Repo Map rebuild','DEMO · REPO MAP REBUILD PLAN\n\ncommand: harness repo-map --rebuild\ntier: full\nfiles: 1 284\nedges: 3 912\n\nPlan only: the parser did not run and the index did not change.');return}
  const rexp=e.target.closest('[data-repo-export]');
  if(rexp){e.preventDefault();repoExport();return}
  const ropen=e.target.closest('[data-repo-open]');
  if(ropen){e.preventDefault();repoOpenFile();return}
  const htab=e.target.closest('[data-harness-tab]');
  if(htab){e.preventDefault();harnessTab=htab.dataset.harnessTab;refreshHarnessView();return}
  const hcmd=e.target.closest('[data-harness-cmd]');
  if(hcmd){e.preventDefault();harnessCommand(hcmd.dataset.harnessCmd);return}
  const href=e.target.closest('[data-harness-refresh]');
  if(href){e.preventDefault();harnessUpdatedAt=new Date();const node=$('#harness-updated');if(node)node.textContent=fmtClock(harnessUpdatedAt);toast('Harness re-read (demo); commands did not run');return}
  const rtab=e.target.closest('[data-report-tab]');
  if(rtab){e.preventDefault();reportTab=rtab.dataset.reportTab;refreshReportView();return}
  const rt=e.target.closest('[data-report-type]');
  if(rt){e.preventDefault();reportFilter=rt.dataset.reportType;ensureReportSelection();refreshReports();return}
  const rr=e.target.closest('[data-report-select]');
  if(rr){e.preventDefault();reportSelected=rr.dataset.reportSelect;refreshReports();return}
  const rref=e.target.closest('[data-report-refresh]');
  if(rref){e.preventDefault();reportUpdatedAt=new Date();const node=$('#reports-updated');if(node)node.textContent=fmtClock(reportUpdatedAt);toast('Reports re-read (demo)');return}
  const ro=e.target.closest('[data-report-open]');
  if(ro){e.preventDefault();openReport();return}
  const re=e.target.closest('[data-report-evidence]');
  if(re){e.preventDefault();const r=reportSelectedItem();const ev=r?.evidence.find(x=>x.name===re.dataset.reportEvidence);if(ev)reader(`Evidence · ${ev.name}`,`DEMO · EVIDENCE

${ev.name}
Status: ${ev.status}
${ev.detail}

Report: ${r.title}`);return}
  const rx=e.target.closest('[data-report-export]');
  if(rx){e.preventDefault();exportReports();return}
  const wtab=e.target.closest('[data-work-tab]');
  if(wtab){e.preventDefault();workTab=wtab.dataset.workTab;refreshWorkView();return}
  const ws=e.target.closest('[data-work-status]');
  if(ws){e.preventDefault();workFilter=ws.dataset.workStatus;ensureWorkSelection();refreshWork();return}
  const wr=e.target.closest('[data-work-session]');
  if(wr){e.preventDefault();workSelected=wr.dataset.workSession;refreshWork();return}
  const wrefresh=e.target.closest('[data-work-refresh]');
  if(wrefresh){e.preventDefault();workUpdatedAt=new Date();const node=$('#work-updated');if(node)node.textContent=fmtClock(workUpdatedAt);toast('Events re-read (demo)');return}
  const wcodex=e.target.closest('[data-work-codex]');
  if(wcodex){e.preventDefault();reader('Codex · plain tail',`DEMO · CODEX LOG TAIL

Step structure unavailable.
Showing only the plain-log tail, without thinking and raw JSON.

[codex] worker attached
[codex] reading context
[codex] sandbox policy checked
[codex] step payload not structured`);return}
  const wopen=e.target.closest('[data-work-open]');
  if(wopen){e.preventDefault();const s=workSession();if(s)reader(`Task card ${s.id}`, `DEMO · TASK\n\n${s.title}\nRole: ${WORK_ROLES[s.role]}\nStatus: ${s.statusLabel}\nBranch: ${s.branch}\nStart: ${s.started} · ${s.elapsed}\n\nInternal reasoning is not shown.`);return}
  const ib=e.target.closest('[data-install-browse]');
  if(ib){e.preventDefault();reader('Choose a local project',`Demo candidates:\n${PROJECTS.map(p=>p.path).join('\n')}\n\nEnter the path manually; the browser has no access to the entire file system.`);return}
  const ic=e.target.closest('[data-install-check]');
  if(ic){e.preventDefault();checkInstallPath();return}
  const io=e.target.closest('[data-install-open]');
  if(io){e.preventDefault();projectPath=installPath();toast('Project selected; next step is installation');return}
  const ia=e.target.closest('[data-install-apply]');
  if(ia){e.preventDefault();installConfirm();return}
  const ps=e.target.closest('[data-project-select]');
  if(ps){e.preventDefault();projectSelectedId=ps.dataset.projectSelect;render();return}
  const pc=e.target.closest('[data-project-check]');
  if(pc){e.preventDefault();checkProjectPath();return}
  const po=e.target.closest('[data-project-open]');
  if(po){e.preventDefault();openProject(po.dataset.projectOpen);return}
  const pcopy=e.target.closest('[data-project-copy]');
  if(pcopy){e.preventDefault();const id=pcopy.dataset.projectCopy;const p=id==='manual'?projectManual:PROJECTS.find(x=>x.id===id);if(p)copyProjectCommand(p);return}
  const sa=e.target.closest('[data-seed-all]');
  if(sa){e.preventDefault();SEED_FILES.forEach(p=>seedSelected[p]=true);refreshUpdate();return}
  const sn=e.target.closest('[data-seed-none]');
  if(sn){e.preventDefault();SEED_FILES.forEach(p=>seedSelected[p]=false);refreshUpdate();return}
  const ur=e.target.closest('[data-update-refresh]');
  if(ur){e.preventDefault();updateCheckedAt=new Date();const node=$('#update-checked');if(node)node.textContent=fmtClock(updateCheckedAt);toast('Diff re-read (demo); files did not change');return}
  const uf=e.target.closest('[data-update-file]');
  if(uf&&!e.target.matches('[data-seed-toggle]')){e.preventDefault();updateSelected=uf.dataset.updateFile;refreshUpdate();return}
  const ua=e.target.closest('[data-update-apply]');
  if(ua){e.preventDefault();if(!ua.disabled)updateConfirm();return}
  const dfix=e.target.closest('[data-diag-fix]');
  if(dfix){e.preventDefault();if(!dfix.disabled)diagFix();return}
  const dex=e.target.closest('[data-diag-export]');
  if(dex){e.preventDefault();exportDiag();return}
  const dreset=e.target.closest('[data-diag-reset]');
  if(dreset){e.preventDefault();diagFilter='all';diagQuery='';const s=$('#diag-search');if(s)s.value='';updateDiag();return}
  const dm=e.target.closest('[data-diag-memory]');
  if(dm){e.preventDefault();toast('Memory index rebuild does not run in the mockup');return}
  const dr=e.target.closest('[data-diag-refresh]');
  if(dr){e.preventDefault();checkedAt=new Date();const node=$('#diag-checked');if(node)node.textContent=`${fmtClock(checkedAt)} · ${healthTotals().total} checks`;updateDiag();toast('Checks reloaded (demo)');return}
  const f=e.target.closest('[data-home-filter]');
  if(f){e.preventDefault();homeFilter=f.dataset.homeFilter;$('#home-checks').innerHTML=homeChecks();bindHome();return}
  const mode=e.target.closest('[data-health-mode]');
  if(mode){e.preventDefault();healthMode=mode.dataset.healthMode;document.querySelectorAll('[data-health-mode]').forEach(btn=>btn.classList.toggle('on',btn.dataset.healthMode===healthMode));bindHome();const note=$('#health-mode-note');if(note)note.textContent=healthMode==='online'?'online not run · 11 skipped':'offline · 56 checks';const dnote=$('#diag-mode-note');if(dnote)dnote.textContent=healthMode==='online'?'online not run · 11 skipped':'offline · 56 checks';const inote=$('#install-mode-note');if(inote)inote.textContent=healthMode==='online'?'Online checks did not run: GitHub/GitLab access and permissions are unverified. Skips are preserved.':'Online — a separate check of GitHub/GitLab and access rights. Sandbox checks analyze settings; actual access may stay unverified.';if(route==='diagnostics')updateDiag();if(healthMode==='online')toast('Online checks do not run in the mockup; skips are preserved');return}
  const r=e.target.closest('[data-home-refresh]');
  if(r){e.preventDefault();checkedAt=new Date();const node=$('#home-checked');if(node)node.textContent=`${fmtClock(checkedAt)} · ${healthTotals().total} checks`;toast('Checks reloaded (demo)')}
});
document.addEventListener('keydown',e=>{
  if(e.target.matches('input,textarea,select,[contenteditable=true]'))return;
  if(e.key==='Escape'){closeNav();return}
  if(e.key==='?'){location.hash='#help';return}
  if(e.key==='g'){location.hash='#home';return}
  if(e.key==='d'){location.hash='#diagnostics';return}
  if(e.key==='o'){location.hash='#orchestration';return}
});
window.addEventListener('hashchange',()=>{closeNav();render()});render();

document.addEventListener('click',e=>{
  const t=e.target.closest('[data-repo-tab]');
  if(!t)return;
  e.preventDefault();
  repoTab=t.dataset.repoTab;
  refreshRepoView();
});


document.addEventListener('click',e=>{
  const cycle=e.target.closest('[data-connection-cycle]');
  if(cycle){e.preventDefault();const i=CONNECTION_ORDER.indexOf(connectionState);connectionState=CONNECTION_ORDER[(i+1)%CONNECTION_ORDER.length];render();toast(`Demo state: ${CONNECTION_LABELS[connectionState]}`);return}
  const retry=e.target.closest('[data-connection-retry]');
  if(retry){e.preventDefault();connectionState='connected';render();toast('Connection restored (demo)');return}
});
