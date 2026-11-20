(function () {
  var serial = 0;
  var dispose = null;
  var en = document.documentElement.lang.indexOf('en') === 0;
  function words(ru, english) { return en ? english : ru; }
  var caps = ['project-foundation', 'mattpocock-suite', 'engineering-suite', 'backend-orchestration'];
  var descriptions = [
    words('База по умолчанию: дизайн, research, handoff и язык проекта.', 'Default foundation: design, research, handoff and project language.'),
    words('Закреплённый upstream-набор скиллов.', 'Pinned upstream skill collection.'),
    words('Инженерный workflow поверх mattpocock-suite.', 'Engineering workflow extending mattpocock-suite.'),
    words('Роли и backend-оркестрация поверх engineering-suite.', 'Roles and backend orchestration extending engineering-suite.')
  ];
  function mount(host, note) {
    var selected = 'engineering-suite';
    var mode = 'init';
    var NS = 'http://www.w3.org/2000/svg';
    var uid = 'ah-install-' + (++serial);
    var motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    var svg = null;
    var controls = document.createElement('div');
    controls.className = 'ah-install-controls';
    host.replaceChildren(controls);
    function element(name, attrs, parent) {
      var e = document.createElementNS(NS, name);
      Object.keys(attrs || {}).forEach(function (key) { e.setAttribute(key, attrs[key]); });
      if (parent) parent.appendChild(e);
      return e;
    }
    function label(parent, x, y, text, cls) {
      var e = element('text', {x:x,y:y,'text-anchor':'middle',class:cls}, parent);
      e.textContent = text;
    }
    function setNote(title, body) {
      var heading = document.createElement('b'); heading.textContent = title;
      var text = document.createElement('span'); text.textContent = body;
      note.replaceChildren(heading, text);
    }
    function choices(title, values, onChange) {
      var group = document.createElement('fieldset');
      var legend = document.createElement('legend'); legend.textContent = title;
      group.appendChild(legend);
      values.forEach(function (value) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'ah-install-option'; b.textContent = value;
        b.dataset.choice = value;
        b.addEventListener('click', function () { onChange(value); draw(); announce(); });
        group.appendChild(b);
      });
      controls.appendChild(group);
    }
    choices(words('Сборка', 'Capability'), caps, function (value) { selected = value; });
    choices(words('Команда', 'Command'), ['init', 'adopt'], function (value) { mode = value; });
    function announce() {
      setNote(selected + ' · ' + mode, descriptions[caps.indexOf(selected)] + ' ' +
        (mode === 'init' ? words('init устанавливает snapshot в Git-репозиторий.', 'init installs the snapshot into a Git repository.') :
          words('adopt сохраняет сторонние скиллы; конфликты требуют отдельного решения.', 'adopt preserves unrelated skills; conflicts need a separate decision.')) + ' ' +
        words('Затем проверьте health. Выбор в схеме не запускает установку.', 'Check health afterwards. Choosing here does not run an installation.'));
    }
    function draw() {
      if (!host.isConnected) return;
      var active = document.activeElement && document.activeElement.getAttribute('data-install-node');
      var narrow = host.clientWidth < 560;
      var medium = host.clientWidth < 900;
      var positions = narrow ? [[100,130],[300,230],[100,330],[300,430],[100,530],[300,630]] :
        medium ? [[100,140],[300,240],[500,140],[700,240],[500,440],[700,540]] :
          [[150,150],[390,270],[630,150],[870,270],[630,470],[870,590]];
      var size = narrow ? [400,725] : medium ? [800,635] : [1040,685];
      var top = narrow ? 32 : medium ? 42 : 52;
      var next = element('svg', {viewBox:'0 '+top+' '+size[0]+' '+(size[1]-top),role:'group',class:'ah-iso-svg ah-install-iso',
        'aria-label':words('Установка: глобальный слой, capability, init или adopt, snapshot, health, первые команды',
          'Installation: global layer, capability, init or adopt, snapshot, health, first commands')});
      var defs = element('defs', {}, next);
      var marker = element('marker', {id:uid+'-arrow',viewBox:'0 0 8 8',refX:7,refY:4,markerWidth:5,markerHeight:5,orient:'auto'}, defs);
      element('path', {d:'M0 0L8 4L0 8Z',class:'ah-core-arrowhead'}, marker);
      var floor = element('g', {class:'ah-iso-floor','aria-hidden':'true'}, next);
      for (var x=-size[1]*2; x<size[0]+size[1]*2; x+=40) {
        element('path',{d:'M'+x+',0l'+size[1]*2+','+size[1]},floor);
        element('path',{d:'M'+x+',0l'+(-size[1]*2)+','+size[1]},floor);
      }
      function point(a,x,y,z) { return [a[0]+(x-y)*8,a[1]+(x+y)*4-z*9]; }
      function cube(parent,a,x,y,z,w,d,h,cls) {
        var g=element('g',{class:'ah-voxel '+(cls||'')},parent);
        function p(x,y,z) {return point(a,x,y,z).join(',');}
        function face(points,cls) {element('polygon',{points:points.join(' '),class:cls},g);}
        face([p(x,y,z+h),p(x+w,y,z+h),p(x+w,y+d,z+h),p(x,y+d,z+h)],'ah-voxel-top');
        face([p(x,y+d,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x,y+d,z+h)],'ah-voxel-front');
        face([p(x+w,y,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x+w,y,z+h)],'ah-voxel-side');
        for(var k=1;k<w;k++) element('path',{d:'M'+p(x+k,y+d,z)+'L'+p(x+k,y+d,z+h),class:'ah-voxel-seam'},g);
      }
      function path(points) {return 'M'+points.map(function(p){return p.join(',');}).join('L');}
      function route(a,b) {
        if (Math.abs(Math.abs(b[1]-a[1])-Math.abs(b[0]-a[0])/2)<1) return [a,b];
        var u=a[1]+a[0]/2, v=b[1]-b[0]/2;
        return [a,[u-v,(u+v)/2],b];
      }
      var links=element('g',{'aria-hidden':'true'},next);
      for(var i=0;i<positions.length-1;i++) {
        var points=route(positions[i],positions[i+1]);
        // Keep the line on the grid; expose its arrow before the destination platform.
        var end=points[points.length-1], previous=points[points.length-2];
        var dx=end[0]-previous[0], dy=end[1]-previous[1];
        var inset=Math.min(60,Math.hypot(dx,dy)/3)/Math.hypot(dx,dy);
        points[points.length-1]=[end[0]-dx*inset,end[1]-dy*inset];
        element('path',{d:path(points),class:'ah-iso-edge is-on','marker-end':'url(#'+uid+'-arrow)'},links);
        if(!motion.matches) {
          var packet=element('circle',{r:3.5,class:'ah-core-packet is-request'},links);
          element('animateMotion',{dur:'5s',begin:(-i)+'s',repeatCount:'indefinite',path:path(points)},packet);
        }
      }
      var data=[
        ['global',words('Глобальный слой','Global layer'),'install-global.py',words('Профиль и скиллы входа start-project / integrate-project. Ставится один раз на машину; --check показывает статус.', 'Profile and entry skills start-project / integrate-project. Install once per machine; --check reports status.')],
        ['cap',words('Выбранная сборка','Selected capability'),selected,descriptions[caps.indexOf(selected)]],
        ['install',mode,words('в Git-репозиторий','into a Git repository'),words('Параметры проекта и capability задаются явно. Установка, конфликты и перезапись требуют просмотра команды.', 'Project settings and capability are explicit. Review the command, conflicts and replacement effects before installation.')],
        ['snapshot',words('Snapshot проекта','Project snapshot'),'.harness/',words('skills/, harness.lock, REGISTRY.md, project.json и hook-policy.json. Native roots: .claude/skills и .agents/skills. backend-orchestration добавляет coordinator и роли.', 'skills/, harness.lock, REGISTRY.md, project.json and hook-policy.json. Native roots: .claude/skills and .agents/skills. backend-orchestration adds the coordinator and roles.')],
        ['health','health',words('проверка без записи','check without writes'),words('Проверьте файлы, зависимости и обнаружение. --fix и --online — отдельные действия; skipped не означает pass.', 'Check files, dependencies and discovery. --fix and --online are separate actions; skipped does not mean pass.')],
        ['tools',words('Первые команды','First commands'),'list · diff · update',words('list и diff показывают состояние. update и cleanup --apply меняют файлы; console требует uv и может скачать зависимости.', 'list and diff inspect state. update and cleanup --apply change files; console needs uv and may download dependencies.')]
      ];
      data.forEach(function(item,index) {
        var a=positions[index];
        var g=element('g',{class:'ah-iso-node is-on',role:'button',tabindex:0,'data-install-node':item[0],'aria-label':item[1]+': '+item[2]},next);
        element('rect',{x:a[0]-90,y:a[1]-88,width:180,height:163,rx:4,class:'ah-iso-focus'},g);
        cube(g,a,-5,-4,-1,10,8,1,'ah-voxel-platform');
        if(index===0 || index===5) {
          cube(g,a,-3,-2,0,6,1,5,'');cube(g,a,-2,-0.9,1,4,0.1,3,'ah-voxel-screen');cube(g,a,-3,-1,0,6,4,0.7,'ah-voxel-neutral');
        } else if(index===1 || index===3) {
          for(var level=0;level<(index===1?3:2);level++) cube(g,a,-3,-2,level*1.5,6,4,1.2,level===1?'ah-voxel-neutral':'');
          if(index===3) cube(g,a,-3,-2,3,2,1,1,'');
        } else if(index===2) {
          cube(g,a,-3,-2,0,6,4,2,'');cube(g,a,-2,-1,2,4,2,1,'ah-voxel-neutral');
        } else {
          cube(g,a,-2,-1,0,4,2,5,'ah-voxel-neutral');
          [[-1,0,2],[0,0,1],[1,0,2],[2,0,3]].forEach(function(q){cube(g,a,q[0],q[1],q[2],1,1,1,'ah-voxel-light');});
        }
        label(g,a[0],a[1]+44,item[1],'ah-core-label');
        label(g,a[0],a[1]+64,item[2],'ah-core-sub');
        g.addEventListener('click',function(){setNote(item[1],item[3]);});
        g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();setNote(item[1],item[3]);}});
      });
      controls.querySelectorAll('button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.choice===selected||b.dataset.choice===mode));});
      if(svg) svg.replaceWith(next); else host.appendChild(next);
      svg=next;
      if(active) {var focus=svg.querySelector('[data-install-node="'+active+'"]');if(focus)focus.focus();}
    }
    var observer=new ResizeObserver(draw);observer.observe(host);
    motion.addEventListener('change',draw);
    draw();announce();
    return {destroy:function(){observer.disconnect();motion.removeEventListener('change',draw);}};
  }
  function init() {
    en=document.documentElement.lang.indexOf('en')===0;
    if(dispose){dispose();dispose=null;}
    var host=document.getElementById('ah-install-map');if(!host)return;
    dispose=mount(host,document.getElementById('ah-install-note')).destroy;

  }
  if(window.document$)window.document$.subscribe(init);else init();
})();
