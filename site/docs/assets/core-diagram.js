/* Isometric view of the checked Archify model; no operational requests are sent. */
(function () {
  var source = document.currentScript.src;
  var dispose = null;
  function init() {
  if (dispose) { dispose(); dispose = null; }
  var host = document.getElementById("ah-core");
  if (!host) return;
  var english = document.documentElement.lang === "en";
  var script = source;
  var NS = "http://www.w3.org/2000/svg";
  var note = document.getElementById("ah-flow-note");
  var controls = document.getElementById("ah-core-controls");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var narrow = window.matchMedia("(max-width: 600px)");
  var medium = window.matchMedia("(max-width: 980px)");
  var playing = !reduced.matches;
  var mode = "launch";
  var selection = null;
  var model;
  var svg;
  var edges;
  var nodes;
  var packets;
  var moving = [];
  var animationFrame = null;
  var animationTime = 0;
  var lastFrame = null;
  var dimensions;
  var text = english ? {
    diagram: "Task execution: Repo Map, opt-in RAG memory, clients, human or auto approval, Python, IPC, Rust, workers and SQLite WAL",
    loading: "Loading diagram…",
    error: "The diagram could not load. Open the architecture documentation below.",
    launch: ["Task execution", "Python prepares a plan and collects approval. The approved brief crosses IPC. Rust records intent, starts the worker, and returns an observation to Python."],
    state: ["Read state", "Python requests a runtime observation over IPC. Rust reads the runtime store and returns a response. Python uses that observation to choose the dispatch state; it never writes directly to SQLite."],
    recovery: ["Recover execution", "Python asks Rust to reconcile. Rust checks the actual process or container against saved intent, records the observation, and returns it to Python. An existing execution is not launched again."],
    clients: "The CLI and console are entry points. A client sends an action to Python. The Python console server returns snapshots and results to the TUI or Web client; runtime operations go through IPC to Rust and back.",
    approval: "A human or the configured auto policy approves the handoff. Auto approval requires both project configuration and the batch plan to choose auto; auto_stop or manual recovery returns control to a human. The mascot marks this decision point.",
    repomap: "Repo Map builds a deterministic map of tracked files, symbols and imports at a pinned Git commit. Python uses that slice to assemble the Context Package; the map cache is derived, not authoritative.",
    memory: "Opt-in project memory retrieves pointers to allowed sources, such as ADRs and CONTEXT.md. Python includes selected evidence in the Context Package. Local SQLite FTS5 retrieval needs no embedding model or network; disabled memory does not block the workflow.",
    context: ["Build context", "Python combines the pinned code map with relevant project-memory pointers in a Context Package. Repo Map supplies files and relationships; opt-in RAG supplies allowed prior decisions. Dispatched workers use the supplied package rather than searching memory themselves."],
    python: "The coordinator plans work, collects approvals and accepts reports. runtime_client sends requests with operation_id and request_deadline. If Rust is unavailable, Python reports an error instead of writing state itself.",
    rust: "Rust receives typed IPC requests, checks the approved brief and executes the pinned plan. Supervisor starts workers; reconcile observes what is actually running. Rust returns observations, while Python chooses dispatch transitions.",
    store: "Rust owns writes to operational state in SQLite WAL: intent, execution observations, audit, leases and idempotent operation results. Python has no direct write path.",
    worker: "Worker and QA run as a process or container under the Rust supervisor. They receive an approved brief and cannot access the engine or runtime sockets.",
    request: "IPC", command: "action / result", approved: "brief / approval", map: "code context", memoryEdge: "retrieval", write: "intent / state", launchEdge: "launch / status"
  } : {
    diagram: "Выполнение задачи: Repo Map, опциональная память RAG, клиенты, человек или автополитика, Python, IPC, Rust, исполнители и SQLite WAL",
    loading: "Загрузка схемы…",
    error: "Не удалось загрузить схему. Откройте документацию по архитектуре ниже.",
    launch: ["Выполнение задачи", "Python готовит план и собирает подтверждение. Одобренный brief передаётся через IPC. Rust записывает intent, запускает исполнителя и возвращает наблюдение в Python."],
    state: ["Чтение состояния", "Python запрашивает наблюдение runtime через IPC. Rust читает runtime-store и возвращает ответ. По этому наблюдению Python выбирает состояние dispatch; напрямую в SQLite он не пишет."],
    recovery: ["Восстановление исполнения", "Python запрашивает reconcile. Rust сверяет процесс или контейнер с сохранённым intent, записывает наблюдение и возвращает его в Python. Уже существующее исполнение повторно не запускается."],
    clients: "CLI и консоль — точки входа. Клиент отправляет действие в Python. Python-сервер консоли возвращает снимки и результаты клиенту TUI или Web; операции runtime проходят через IPC в Rust и обратно.",
    approval: "Handoff подтверждает человек или настроенная политика auto. Для auto конфигурация проекта и план batch должны выбрать auto; auto_stop и ручное восстановление возвращают решение человеку. Маскот обозначает эту точку решения.",
    repomap: "Repo Map строит детерминированную карту tracked-файлов, символов и импортов на закреплённом Git-коммите. Python использует этот срез для Context Package; кэш карты — производный, а не авторитетный источник.",
    memory: "Опциональная память проекта находит ссылки на разрешённые источники: например, ADR и CONTEXT.md. Python включает выбранные свидетельства в Context Package. Локальному поиску SQLite FTS5 не нужны embedding-модель и сеть; выключенная память не блокирует работу.",
    context: ["Подготовка контекста", "Python собирает Context Package из карты кода и найденных ссылок на память проекта. Repo Map даёт файлы и связи; опциональный RAG — разрешённые прошлые решения. Запущенные роли используют готовый пакет, а не ищут в памяти самостоятельно."],
    python: "Coordinator планирует работу, собирает approvals и принимает отчёты. runtime_client отправляет запросы с operation_id и request_deadline. При недоступном Rust Python возвращает ошибку, а не пишет состояние самостоятельно.",
    rust: "Rust принимает типизированные IPC-запросы, проверяет approved brief и исполняет закреплённый план. Supervisor запускает исполнителей, reconcile наблюдает фактическое исполнение. Rust возвращает наблюдения; переходы dispatch выбирает Python.",
    store: "Rust владеет записью operational state в SQLite WAL: intent, наблюдения исполнения, audit, leases и результаты идемпотентных операций. У Python нет прямого пути записи.",
    worker: "Worker и QA работают как процесс или контейнер под Rust supervisor. Они получают approved brief; сокеты engine и runtime им недоступны.",
    request: "IPC", command: "действие / ответ", approved: "brief / approval", map: "контекст кода", memoryEdge: "retrieval", write: "intent / state", launchEdge: "запуск / статус"
  };
  var routes = {
    launch: ["command", "map", "memory", "approved", "request", "write", "launch"],
    context: ["command", "map", "memory"],
    state: ["command", "request", "write"],
    recovery: ["command", "request", "launch", "write"]
  };

  function element(tag, attrs, parent) {
    var result = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) { result.setAttribute(key, attrs[key]); });
    if (parent) parent.appendChild(result);
    return result;
  }
  function label(parent, x, y, value, cls) {
    var result = element("text", { x: x, y: y, class: cls, "text-anchor": "middle" }, parent);
    result.textContent = value;
    return result;
  }
  function point(anchor, x, y, z) {
    return [anchor[0] + (x - y) * 8, anchor[1] + (x + y) * 4 - z * 9];
  }
  function face(parent, points, cls) {
    element("polygon", { points: points.map(function (p) { return p.join(","); }).join(" "), class: cls }, parent);
  }
  function box(parent, anchor, x, y, z, w, d, h, cls) {
    var g = element("g", { class: "ah-voxel " + (cls || "") }, parent);
    var p = function (a, b, c) { return point(anchor, a, b, c); };
    face(g, [p(x,y,z+h),p(x+w,y,z+h),p(x+w,y+d,z+h),p(x,y+d,z+h)], "ah-voxel-top");
    face(g, [p(x,y+d,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x,y+d,z+h)], "ah-voxel-front");
    face(g, [p(x+w,y,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x+w,y,z+h)], "ah-voxel-side");
  }
  function block(parent, anchor, x, y, z, w, d, h, cls) {
    box(parent, anchor, x,y,z,w,d,h,cls);
    // Discrete seams on visible faces retain the mascot's cube scale.
    for (var i = 1; i < w; i++) {
      var a = point(anchor,x+i,y+d,z), b = point(anchor,x+i,y+d,z+h);
      element("path",{d:"M"+a.join(",")+"L"+b.join(","),class:"ah-voxel-seam"},parent);
    }
    for (var j = 1; j < d; j++) {
      var c = point(anchor,x+w,y+j,z), e = point(anchor,x+w,y+j,z+h);
      element("path",{d:"M"+c.join(",")+"L"+e.join(","),class:"ah-voxel-seam"},parent);
    }
  }
  function object(parent, id, anchor) {
    block(parent,anchor,-5,-4,-1,10,8,1,"ah-voxel-platform");
    if (id === "clients") {
      block(parent,anchor,-3,-1,0,6,3,1,"ah-voxel-neutral");
      block(parent,anchor,-3,-3,1,6,1,5,"");
      box(parent,anchor,-2,-1.9,2,4,0.08,3,"ah-voxel-screen");
      box(parent,anchor,-2,-1.8,3,1,0.1,1,"ah-voxel-light");
    } else if (id === "approval") {
      element("image",{href:new URL("mascot.svg",script).href,x:anchor[0]-27,y:anchor[1]-71,width:54,height:71,"aria-hidden":"true"},parent);
    } else if (id === "repomap") {
      block(parent,anchor,-3,-2,0,2,2,2,"");
      block(parent,anchor,1,-2,0,2,2,4,"");
      block(parent,anchor,-1,1,0,2,2,3,"ah-voxel-neutral");
    } else if (id === "memory") {
      for (var book=0;book<3;book++) block(parent,anchor,-3+book*2,-2,0,1.5,4,3+book,"ah-voxel-neutral");
    } else if (id === "python" || id === "rust") {
      var levels = id === "rust" ? 3 : 2;
      for (var k=0;k<levels;k++) {
        block(parent,anchor,-3,-3,k*3,6,6,2.5,"");
        box(parent,anchor,-2,3.06,k*3+1,1,0.1,0.7,"ah-voxel-light");
        box(parent,anchor,0,3.06,k*3+1,2,0.1,0.7,"ah-voxel-screen");
      }
      block(parent,anchor,-1,-1,levels*3,2,2,1,"ah-voxel-neutral");
    } else if (id === "store") {
      for (var n=0;n<3;n++) block(parent,anchor,-3,-2,n*1.8,6,4,1.4, n===1 ? "ah-voxel-neutral" : "");
    } else {
      block(parent,anchor,-4,-2,0,8,4,4,"");
      block(parent,anchor,-3,-1,4,6,2,1,"ah-voxel-neutral");
    }
  }
  function geometry() {
    if (narrow.matches) return {
      size:[420,850], repomap:[108,100],approval:[312,100],clients:[108,300],python:[312,300],memory:[108,520],rust:[312,520],worker:[108,740],store:[312,740]
    };
    if (medium.matches) return {
      size:[800,590],repomap:[96,120],approval:[480,120],clients:[96,312],python:[288,216],memory:[288,504],rust:[480,312],worker:[672,216],store:[672,408]
    };
    return {
      size:[1024,640],repomap:[128,160],approval:[640,160],clients:[128,416],python:[384,288],memory:[384,544],rust:[640,416],worker:[896,288],store:[896,544]
    };
  }
  function path(points) { return "M" + points.map(function (p) {return p.join(",");}).join("L"); }
  function distance(a,b) { return Math.hypot(b[0]-a[0],b[1]-a[1]); }
  function segmentDistance(p,a,b) {
    var dx=b[0]-a[0],dy=b[1]-a[1],square=dx*dx+dy*dy;
    var t=square ? Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/square)) : 0;
    return distance(p,[a[0]+t*dx,a[1]+t*dy]);
  }
  function plane(p) { return [p[1]+p[0]/2,p[1]-p[0]/2]; }
  function screen(p) { return [p[0]-p[1],(p[0]+p[1])/2]; }
  function inside(p,r) {return p[0]>r[0] && p[0]<r[2] && p[1]>r[1] && p[1]<r[3];}
  function obstacles() {
    return model.components.flatMap(function(c){var p=dimensions[c.id];
      var main=c.label.length*(narrow.matches?10:9)/2+4, sub=c.sublabel.length*(narrow.matches?9.7:7.3)/2+4;
      var titleY=c.id==="python"?-98:52,subY=c.id==="python"?-78:73;
      return [
      {id:c.id,box:[p[0]-76,p[1]-96,p[0]+76,p[1]+48],art:true},
      {id:c.id,box:[p[0]-main,p[1]+titleY-15,p[0]+main,p[1]+titleY+4],art:false},
      {id:c.id,box:[p[0]-sub,p[1]+subY-13,p[0]+sub,p[1]+subY+4],art:false}
    ];});
  }
  function route(c,used) {
    var start=dimensions[c.from], end=dimensions[c.to];
    if(!narrow.matches && c.id==="memory") {
      var drop=end[1]-start[1];
      return [start,[start[0]-32,start[1]+16],[start[0]+96,start[1]+80],[start[0]+128-drop,start[1]+drop/2+64],end];
    }
    if(Math.abs(Math.abs(end[1]-start[1])-Math.abs(end[0]-start[0])/2)<0.01)return [start,end];
    var ports=[[0,0]];
    var blocks=obstacles(),best=null,bestScore=Infinity;
    ports.forEach(function(a){ports.forEach(function(b){
      var p=[start[0]+a[0],start[1]+a[1]],q=[end[0]+b[0],end[1]+b[1]],s=plane(p),t=plane(q);
      var candidates=[[p,screen([s[0],t[1]]),q],[p,screen([t[0],s[1]]),q]];
      [-160,-80,0,80,160].forEach(function(offset){
        var u=(s[0]+t[0])/2+offset,v=(s[1]+t[1])/2+offset;
        candidates.push([p,screen([u,s[1]]),screen([u,t[1]]),q]);
        candidates.push([p,screen([s[0],v]),screen([t[0],v]),q]);
      });
      candidates.forEach(function(points){
        points=points.filter(function(x,i){return !i || distance(x,points[i-1])>0.1;});
        if(points.length<2)return;
        var score=(points.length-2)*36;
        points.forEach(function(x){if(x[0]<8 || x[0]>dimensions.size[0]-8 || x[1]<8 || x[1]>dimensions.size[1]-8)score+=5000;});
        for(var i=1;i<points.length;i++){
          var x=points[i-1],y=points[i],length=distance(x,y);score+=length;
          if(length<28)score+=250;
          for(var k=1;k<length/10;k++){
            var sample=[x[0]+(y[0]-x[0])*k*10/length,x[1]+(y[1]-x[1])*k*10/length];
            blocks.forEach(function(o){if(o.art && (o.id===c.from || o.id===c.to))return;if(inside(sample,o.box))score+=350;});
            if(!blocks.some(function(o){return o.art && inside(sample,o.box);})) {
              used.forEach(function(prior){for(var segment=1;segment<prior.length;segment++){if(segmentDistance(sample,prior[segment-1],prior[segment])<10)score+=90;}});
            }
          }
        }
        if(score<bestScore){best=points;bestScore=score;}
      });
    });});
    return best;
  }
  function captionPosition(points,placed,actual,measurement) {
    var best,bestScore=Infinity,width=measurement.width+16;
    var blocks=actual.map(function(b){return [b.x-8,b.y-5,b.x+b.width+8,b.y+b.height+5];}).concat(placed);
    for(var i=1;i<points.length;i++){
      [0.25,0.5,0.75].forEach(function(t){[-12,22,-30,40,-54,62,-78,86,-102,110].forEach(function(offset){[0,-36,36].forEach(function(dx){
        var x=points[i-1][0]+(points[i][0]-points[i-1][0])*t+dx,y=points[i-1][1]+(points[i][1]-points[i-1][1])*t+offset;
        var r=[x-width/2,y+measurement.y-5,x+width/2,y+measurement.y+measurement.height+5],score=Math.abs(offset)+Math.abs(dx)+Math.abs(t-.5)*20;
        if(r[0]<5 || r[2]>dimensions.size[0]-5 || r[1]<5 || r[3]>dimensions.size[1]-5)score+=10000;
        blocks.forEach(function(b){if(r[0]<b[2] && r[2]>b[0] && r[1]<b[3] && r[3]>b[1])score+=2000;});
        if(score<bestScore){bestScore=score;best=[x,y];}
      });});});
    }
    if(bestScore>=1000) {
      for(var gx=width/2+8;gx<dimensions.size[0]-width/2-8;gx+=12) {
        for(var gy=26;gy<dimensions.size[1]-12;gy+=12) {
          var candidate=[gx-width/2,gy+measurement.y-5,gx+width/2,gy+measurement.y+measurement.height+5];
          if(blocks.some(function(b){return candidate[0]<b[2]&&candidate[2]>b[0]&&candidate[1]<b[3]&&candidate[3]>b[1];}))continue;
          var proximity=Infinity;
          for(var segment=1;segment<points.length;segment++)proximity=Math.min(proximity,segmentDistance([gx,gy],points[segment-1],points[segment]));
          if(proximity+20<bestScore){bestScore=proximity+20;best=[gx,gy];}
        }
      }
    }
    placed.push([best[0]-width/2,best[1]+measurement.y-5,best[0]+width/2,best[1]+measurement.y+measurement.height+5]);
    return best;
  }
  function showNote(title, body) {
    note.replaceChildren();
    var strong = document.createElement("b"), span = document.createElement("span");
    strong.textContent=title; span.textContent=body;
    note.append(strong,span);
  }
  function syncMotion() {
    if (!svg) return;
    host.classList.toggle("is-playing",playing && !document.hidden);
    if(animationFrame!==null){cancelAnimationFrame(animationFrame);animationFrame=null;}
    lastFrame=null;
    if(playing && !document.hidden) animationFrame=requestAnimationFrame(tick);
  }
  function tick(now) {
    animationFrame=null;
    if(!playing || document.hidden)return;
    if(lastFrame!==null)animationTime+=Math.min(now-lastFrame,100);
    lastFrame=now;
    paintPackets();
    animationFrame=requestAnimationFrame(tick);
  }
  function paintPackets() {
    moving.forEach(function(item,index){
      var phase=((animationTime/1000+index*.7)%7)/7,forward=phase<.5;
      var remaining=(forward ? phase*2 : (1-phase)*2)*item.length;
      var points=item.points,segment=1;
      while(segment<points.length-1 && remaining>distance(points[segment-1],points[segment])){remaining-=distance(points[segment-1],points[segment]);segment++;}
      var a=points[segment-1],b=points[segment],length=distance(a,b),ratio=length?remaining/length:0;
      var angle=Math.atan2(b[1]-a[1],b[0]-a[0])*180/Math.PI+(forward?0:180);
      item.el.setAttribute("transform","translate("+(a[0]+(b[0]-a[0])*ratio)+","+(a[1]+(b[1]-a[1])*ratio)+") rotate("+angle+")");
      item.el.classList.toggle("is-answer",!forward);
      item.el.setAttribute("data-direction",forward?"request":"response");
    });
  }
  function applySelection() {
    if (!svg) return;
    var active = selection ? model.connections.filter(function (c) {return c.from===selection || c.to===selection;}).map(function (c) {return c.id;}) : routes[mode];
    var activeNodes = new Set(selection ? [selection] : []);
    packets.replaceChildren();
    moving=[];
    model.connections.forEach(function (c,index) {
      var on=active.indexOf(c.id)!==-1;
      edges[c.id].classList.toggle("is-on",on);
      if (!on) return;
      activeNodes.add(c.from); activeNodes.add(c.to);
      var points=dimensions.links[c.id];
      var packet=element("path",{d:"M-6,-4L5,0L-6,4L-3,0Z",class:"ah-iso-packet","aria-hidden":"true","data-connection":c.id},packets);
      var length=points.slice(1).reduce(function(total,p,i){return total+distance(points[i],p);},0);
      moving.push({el:packet,points:points,length:length});
    });
    Object.keys(nodes).forEach(function(id){
      nodes[id].classList.toggle("is-on",activeNodes.has(id));
      nodes[id].setAttribute("aria-pressed",String(id===selection));
    });
    var selected=model.components.find(function(c){return c.id===selection;});
    showNote(selected ? selected.label : text[mode][0], selected ? text[selection] : text[mode][1]);
    controls.querySelectorAll("[data-core-route]").forEach(function(button){button.setAttribute("aria-pressed",String(!selection && button.dataset.coreRoute===mode));});
    // The same store link represents a write on launch and a read on observation.
    var storeLabel=svg.querySelector('[data-edge-label="write"]');
    storeLabel.textContent=mode==="state" ? (english ? "read state" : "чтение state") : text.write;
    var workerLabel=svg.querySelector('[data-edge-label="launch"]');
    workerLabel.textContent=mode==="recovery" ? (english ? "reconcile" : "reconcile") : text.launchEdge;
    paintPackets();
    syncMotion();
  }
  function render() {
    dimensions=geometry();
    dimensions.links={};
    var used=[];
    model.connections.slice().sort(function(a,b){return (a.id==="request"?-1:0)-(b.id==="request"?-1:0);}).forEach(function(c){
      dimensions.links[c.id]=route(c,used);
      used.push(dimensions.links[c.id]);
    });
    svg=element("svg",{viewBox:"0 0 "+dimensions.size.join(" "),class:"ah-iso-svg",role:"group","aria-label":text.diagram});
    var floor=element("g",{"aria-hidden":"true",class:"ah-iso-floor"},svg);
    for(var gy=-dimensions.size[0]/2;gy<dimensions.size[1];gy+=32){
      element("path",{d:"M0,"+gy+"l"+dimensions.size[0]+","+(dimensions.size[0]/2)},floor);
      element("path",{d:"M"+dimensions.size[0]+","+gy+"l-"+dimensions.size[0]+","+(dimensions.size[0]/2)},floor);
    }
    var connections=element("g",{"aria-hidden":"true"},svg);
    edges={}; nodes={};
    model.connections.forEach(function(c){
      edges[c.id]=element("path",{d:path(dimensions.links[c.id]),class:"ah-iso-edge","data-connection":c.id,"data-from":c.from,"data-to":c.to},connections);
    });
    packets=element("g",{"aria-hidden":"true",class:"ah-iso-packets"},svg);
    model.components.slice().sort(function(a,b){return dimensions[a.id][1]-dimensions[b.id][1];}).forEach(function(c){
      var anchor=dimensions[c.id];
      var g=element("g",{class:"ah-iso-node ah-iso-node--"+c.id,role:"button",tabindex:0,"aria-label":c.label+": "+c.sublabel,"aria-describedby":"ah-flow-note","data-node":c.id},svg);
      element("rect",{x:anchor[0]-90,y:anchor[1]-(c.id==="python"?116:100),width:180,height:c.id==="python"?192:176,rx:4,class:"ah-iso-focus"},g);
      var art=element("g",{"aria-hidden":"true"},g);
      object(art,c.id,anchor);
      label(g,anchor[0],anchor[1]+(c.id==="python"?-98:52),c.label,"ah-iso-label");
      label(g,anchor[0],anchor[1]+(c.id==="python"?-78:73),c.sublabel,"ah-iso-sub");
      g.addEventListener("click",function(){selection=selection===c.id ? null : c.id; applySelection();});
      g.addEventListener("keydown",function(event){
        if(event.key==="Enter" || event.key===" "){event.preventDefault();g.dispatchEvent(new MouseEvent("click"));}
        if(event.key==="Escape"){selection=null;applySelection();}
      });
      nodes[c.id]=g;
    });
    var captions=element("g",{"aria-hidden":"true"},svg);
    host.replaceChildren(svg);
    host.style.aspectRatio=dimensions.size.join(" / ");
    // Measure the actual font and voxel silhouettes after CSS applies.
    var actual=model.components.flatMap(function(c){return [
      nodes[c.id].querySelector('g[aria-hidden]').getBBox(),
      nodes[c.id].querySelector('.ah-iso-label').getBBox(),
      nodes[c.id].querySelector('.ah-iso-sub').getBBox()
    ];});
    var placed=[];
    model.connections.forEach(function(c){
      var value=text[c.id==="launch" ? "launchEdge" : c.id==="memory" ? "memoryEdge" : c.id];
      var caption=label(captions,0,0,value,"ah-iso-edge-label");
      var p=captionPosition(dimensions.links[c.id],placed,actual,caption.getBBox());
      caption.setAttribute("x",p[0]);caption.setAttribute("y",p[1]);
      caption.setAttribute("data-edge-label",c.id);
    });
    applySelection();
  }
  fetch(new URL((english ? "../en/" : "../")+"diagrams/harness-core.architecture.json",script)).then(function(response){
    if(!response.ok) throw new Error("diagram");
    return response.json();
  }).then(function(data){
    if (!host.isConnected) return;
    model=data;
    render();
    controls.querySelectorAll("button").forEach(function(button){button.disabled=false;});
    controls.addEventListener("click",function(event){
      var button=event.target.closest("[data-core-route]");
      if(!button) return;
      mode=button.dataset.coreRoute; selection=null; applySelection();
    });
    narrow.addEventListener("change",render); medium.addEventListener("change",render);
    function onReduced() { playing=!reduced.matches; syncMotion(); }
    reduced.addEventListener("change",onReduced);
    dispose = function () {
      playing=false;
      if(animationFrame!==null) cancelAnimationFrame(animationFrame);
      narrow.removeEventListener("change",render);
      medium.removeEventListener("change",render);
      reduced.removeEventListener("change",onReduced);
      document.removeEventListener("visibilitychange",syncMotion);
    };
    document.addEventListener("visibilitychange",syncMotion);
  }).catch(function(){showNote(english ? "Architecture" : "Архитектура",text.error);});
  }
  if (window.document$) window.document$.subscribe(init);
  else init();
})();
