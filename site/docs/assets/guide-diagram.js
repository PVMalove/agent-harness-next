(function () {
  var source = document.currentScript.src;
  var serial = 0;
  var dispose;
  var NS = "http://www.w3.org/2000/svg";
  function mount(host, note) {
    var en = document.documentElement.lang === "en";
    function words(ru, english) { return en ? english : ru; }
    var steps = [
      [words("Идея", "Idea"), "/grilling", "../skills/grilling/", words("Согласуй цель и границы. Для существующего проекта grill-with-docs также записывает договорённости.", "Agree on the goal and scope. In an existing project, grill-with-docs also records decisions.")],
      [words("Спецификация", "Specification"), "/to-spec", "../skills/to-spec/", words("Проверь описание проблемы, решения, проверок и исключённого объёма до публикации.", "Review the problem, solution, testing decisions and excluded scope before publication.")],
      [words("Тикеты", "Tickets"), "/to-tickets", "../skills/to-tickets/", words("Согласуй проверяемые задачи и зависимости. Для готового тикета эти подготовительные этапы не повторяются.", "Agree on verifiable tasks and dependencies. A ready ticket does not repeat these preparation stages.")],
      [words("Реализация", "Implementation"), "/implement", "workflow/#steps", words("Выбери implement, fast-implement или to-guide по режиму задачи. Независимые роли требуют backend-orchestration.", "Choose implement, fast-implement or to-guide for the task's execution mode. Independent roles require backend-orchestration.")],
      ["PR", "/to-pull-requests", "../skills/to-pull-requests/", words("Открытие PR требует отдельного подтверждения. Merge выполняет человек.", "Opening a PR requires separate confirmation. A person performs the merge.")]
    ];
    var uid = "ah-guide-" + (++serial);
    var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var selected = 0;
    function element(tag, attrs, parent) {
      var e = document.createElementNS(NS, tag);
      Object.keys(attrs).forEach(function (key) { e.setAttribute(key, attrs[key]); });
      if (parent) parent.appendChild(e);
      return e;
    }
    function text(parent, x, y, value, cls) {
      var e = element("text", {x:x, y:y, "text-anchor":"middle", class:cls}, parent);
      e.textContent = value;
    }
    function describe() {
      var heading = document.createElement("b"); heading.textContent = steps[selected][0];
      var description = document.createElement("span"); description.textContent = steps[selected][3];
      var link = document.createElement("a"); link.textContent = steps[selected][1]; link.href = steps[selected][2];
      note.replaceChildren(heading, description, link);
    }
    function draw() {
      if (!host.isConnected) return;
      var focused = document.activeElement && document.activeElement.getAttribute("data-guide-step");
      var narrow = host.clientWidth < 580;
      var positions = narrow ? [[100,110],[290,205],[100,300],[290,395],[100,490]] : [[120,120],[340,230],[560,120],[780,230],[560,340]];
      var width = narrow ? 400 : 900;
      var height = narrow ? 575 : 425;
      var svg = element("svg", {viewBox:"0 20 "+width+" "+(height-20), role:"group", class:"ah-iso-svg", "aria-label":words("Полный маршрут от идеи к PR. Выбери этап для пояснения.", "Full route from idea to PR. Choose a stage for details.")});
      var defs = element("defs", {}, svg);
      var marker = element("marker", {id:uid+"-arrow", viewBox:"0 0 8 8", refX:7, refY:4, markerWidth:5, markerHeight:5, orient:"auto"}, defs);
      element("path", {d:"M0 0L8 4L0 8Z", class:"ah-core-arrowhead"}, marker);
      var floor = element("g", {class:"ah-iso-floor", "aria-hidden":"true"}, svg);
      for (var x=-height*2; x<width+height*2; x+=40) {
        element("path", {d:"M"+x+",0l"+height*2+","+height}, floor);
        element("path", {d:"M"+x+",0l"+(-height*2)+","+height}, floor);
      }
      var links = element("g", {"aria-hidden":"true"}, svg);
      positions.slice(0,-1).forEach(function (start, i) {
        var end = positions[i+1];
        var length = Math.hypot(end[0]-start[0], end[1]-start[1]);
        var inset = 55/length;
        var path = "M"+start.join(",")+"L"+[end[0]-(end[0]-start[0])*inset,end[1]-(end[1]-start[1])*inset].join(",");
        element("path", {d:path, class:"ah-iso-edge is-on", "marker-end":"url(#"+uid+"-arrow)"}, links);
        if (!motion.matches) {
          var packet = element("circle", {r:3.5, class:"ah-core-packet is-request"}, links);
          element("animateMotion", {dur:"5s", begin:(-i)+"s", repeatCount:"indefinite", path:path}, packet);
        }
      });
      function cube(parent, a, x, y, z, w, d, h, cls) {
        function p(x,y,z) {return [a[0]+(x-y)*8,a[1]+(x+y)*4-z*9].join(",");}
        var g = element("g", {class:"ah-voxel "+(cls||"")}, parent);
        function face(points, cls) {element("polygon", {points:points.join(" "), class:cls}, g);}
        face([p(x,y,z+h),p(x+w,y,z+h),p(x+w,y+d,z+h),p(x,y+d,z+h)],"ah-voxel-top");
        face([p(x,y+d,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x,y+d,z+h)],"ah-voxel-front");
        face([p(x+w,y,z),p(x+w,y+d,z),p(x+w,y+d,z+h),p(x+w,y,z+h)],"ah-voxel-side");
      }
      steps.forEach(function (step, i) {
        var a=positions[i];
        var node=element("g", {class:"ah-iso-node is-on", role:"button", tabindex:0, "aria-label":step[0]+": "+step[1], "aria-pressed":String(selected===i), "data-guide-step":i}, svg);
        element("rect", {x:a[0]-85,y:a[1]-65,width:170,height:138,rx:8,class:"ah-iso-focus"}, node);
        var shapes=element("g", {"aria-hidden":"true"}, node);
        cube(shapes,a,-3,-3,-1,6,6,1,"ah-voxel-platform");
        if (i===0) {
          [[0,0,0],[0,0,2],[0,0,3],[1,0,3],[1,0,4],[-1,0,5],[0,0,5],[1,0,5]].forEach(function(p){cube(shapes,a,p[0],p[1],p[2],1,1,1);});
        } else if (i===1) {
          cube(shapes,a,-2,-1,0,4,2,4);
          for(var line=0;line<3;line++) cube(shapes,a,-1,1,line+.5,2,.3,.3,"ah-voxel-screen");
        } else if (i===2) {
          cube(shapes,a,-2,-2,0,2,2,.8);cube(shapes,a,1,-2,0,2,2,.8);cube(shapes,a,-.5,1,0,2,2,.8);
        } else if (i===3) {
          cube(shapes,a,-2,-1,0,4,2,.5,"ah-voxel-neutral");
          cube(shapes,a,-2,-2,.5,4,1,3);
          cube(shapes,a,-1.5,-.9,1,3,.08,2,"ah-voxel-screen");
          cube(shapes,a,-1,-.8,1.8,.6,.1,.6,"ah-voxel-light");
        } else {
          element("image", {href:new URL("mascot.svg",source).href,x:a[0]-21,y:a[1]-56,width:42,height:56,"aria-hidden":"true"}, shapes);
        }
        text(node,a[0],a[1]+44,step[0],"ah-iso-label");
        text(node,a[0],a[1]+63,step[1],"ah-iso-sub");
        function activate() {selected=i;describe();svg.querySelectorAll("[data-guide-step]").forEach(function(g,j){g.setAttribute("aria-pressed",String(j===i));});}
        node.addEventListener("click",activate);
        node.addEventListener("keydown",function(event){if(event.key==="Enter"||event.key===" "){event.preventDefault();activate();}});
      });
      host.replaceChildren(svg);
      if (focused!==null && focused!==undefined) {
        var target=svg.querySelector('[data-guide-step="'+focused+'"]');if(target)target.focus();
      }
    }
    var observer = new ResizeObserver(draw);
    observer.observe(host);
    motion.addEventListener("change",draw);
    draw();describe();
    return function(){observer.disconnect();motion.removeEventListener("change",draw);};
  }
  function init(){if(dispose)dispose();var host=document.getElementById("ah-guide-flow"),note=document.getElementById("ah-guide-note");dispose=host&&note?mount(host,note):null;}
  if(window.document$)window.document$.subscribe(init);
  else if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);
  else init();
})();
