"""示例驱动的确定性 mock 输出。

当用户输入与前端示例文本（SUGGESTIONS）相同或命中关键词时，返回对应的完整
单文件示范网页。这些网页同时作为 MockOutputProvider 的输出，以及未来真实 AI
Provider 在示例输入下的短路返回值，保证首体验稳定、不依赖外部模型调用。

所有网页遵循真实 Provider 的同一条产物规约：单文件、无外部资源、内联
SVG/CSS/JS、核心交互真实可用、语义化 + 响应式 + 可访问性。
"""

HYDRATION_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日饮水追踪器</title>
<style>
:root{--brand:#0ea5e9;--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);padding:24px;line-height:1.6}
.wrap{max-width:720px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);margin:0 0 20px;font-size:14px}
.panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:24px;margin-bottom:16px}
.row{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.ring{flex:0 0 auto;width:180px;height:180px}
.ring text{font-weight:600}
.stats{flex:1;min-width:200px}.stats .num{font-size:30px;font-weight:700}.stats .goal{color:var(--muted);font-size:13px}
.bar{height:8px;background:#e2e8f0;border-radius:99px;margin:12px 0;overflow:hidden}.bar>div{height:100%;background:var(--brand);border-radius:99px;transition:width .3s}
.cups{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.cups button{padding:12px 8px;border:1px solid var(--line);background:#fff;border-radius:12px;font-size:14px;cursor:pointer;transition:.15s}
.cups button:hover{border-color:var(--brand);color:var(--brand)}
.cups button:focus-visible{outline:3px solid #bae6fd}
.badge{display:inline-block;background:#e0f2fe;color:#0369a1;border-radius:99px;padding:2px 10px;font-size:12px;font-weight:600}
ul.records{list-style:none;margin:0;padding:0}ul.records li{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
ul.records li:last-child{border-bottom:0}.time{color:var(--muted);font-size:12px}
button.undo{margin-top:12px;padding:8px 14px;border:1px solid var(--line);background:#fff;border-radius:10px;font-size:13px;cursor:pointer}
button.undo:disabled{opacity:.4;cursor:not-allowed}
.done{background:#f0fdf4;border-color:#86efac;color:#166534}
@media(max-width:560px){.ring{width:140px;height:140px}.cups{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="wrap">
  <h1>每日饮水追踪器</h1>
  <p class="sub">按杯记录今天的饮水量，进度环随目标实时更新。</p>

  <div class="panel">
    <div class="row">
      <svg class="ring" viewBox="0 0 120 120" role="img" aria-label="饮水进度环">
        <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="12"/>
        <circle id="ring" cx="60" cy="60" r="50" fill="none" stroke="#0ea5e9" stroke-width="12"
          stroke-linecap="round" stroke-dasharray="314.16" stroke-dashoffset="314.16"
          transform="rotate(-90 60 60)"/>
        <text id="pct" x="60" y="58" text-anchor="middle" font-size="20">0%</text>
        <text x="60" y="78" text-anchor="middle" font-size="11" fill="#64748b">达成</text>
      </svg>
      <div class="stats">
        <div class="num"><span id="now">0</span> <span style="font-size:14px;color:var(--muted)">/ 2000 ml</span></div>
        <div class="goal">今日目标 2000 ml</div>
        <div class="bar"><div id="fill" style="width:0%"></div></div>
        <div id="status"; class="badge">继续加油</div>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2 style="font-size:15px;margin:0 0 12px">喝一杯</h2>
    <div class="cups">
      <button data-ml="150">150 ml</button>
      <button data-ml="250">250 ml</button>
      <button data-ml="330">330 ml</button>
      <button data-ml="500">500 ml</button>
    </div>
  </div>

  <div class="panel">
    <h2 style="font-size:15px;margin:0 0 4px">今日记录</h2>
    <ul class="records" id="records"></ul>
    <button class="undo" id="undo" disabled>撤销最后一杯</button>
  </div>
</div>
<script>
const GOAL = 2000;
let total = 0;
const records = [];
function time(){const d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}
function render(){
  document.getElementById('now').textContent = total;
  const pct = Math.min(100, Math.round(total/GOAL*100));
  document.getElementById('fill').style.width = pct+'%';
  document.getElementById('pct').textContent = pct+'%';
  document.getElementById('ring').setAttribute('stroke-dashoffset', (314.16*(1-Math.min(1,total/GOAL))).toFixed(2));
  const st = document.getElementById('status');
  if(total>=GOAL){st.textContent='今日目标已达成';st.className='badge done';}
  else{st.textContent='继续加油';st.className='badge';}
  const ul = document.getElementById('records');
  ul.innerHTML = records.map(r=>'<li><span>'+r.ml+' ml</span><span class="time">'+r.at+'</span></li>').join('');
  document.getElementById('undo').disabled = records.length===0;
}
document.querySelectorAll('.cups button').forEach(b=>b.addEventListener('click',()=>{
  total += Number(b.dataset.ml); records.push({ml:Number(b.dataset.ml),at:time()}); render();
}));
document.getElementById('undo').addEventListener('click',()=>{
  if(!records.length)return; const last=records.pop(); total=Math.max(0,total-last.ml); render();
});
render();
</script>
</body>
</html>"""

KANBAN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>团队任务看板</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);padding:24px;line-height:1.5}
.wrap{max-width:960px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);font-size:14px;margin:0 0 16px}
.toolbar{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.toolbar input{flex:1;min-width:180px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:14px}
.toolbar input:focus-visible{outline:3px solid #bae6fd}
.toolbar button{padding:10px 14px;border:0;border-radius:10px;background:#0ea5e9;color:#fff;font-size:14px;cursor:pointer}
.columns{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.col{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;min-height:200px}
.col h2{font-size:14px;margin:0 0 10px;padding-bottom:8px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.col h2 .cnt{background:#e2e8f0;border-radius:99px;padding:1px 8px;font-size:12px}
.card{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px;font-size:14px;cursor:grab}
.card.dragging{opacity:.4}
.card .tag{display:inline-block;background:#e0f2fe;color:#0369a1;border-radius:6px;padding:1px 6px;font-size:11px;margin-top:6px}
.col.drag-over{outline:2px dashed #0ea5e9;outline-offset:-4px}
.empty{color:#cbd5e1;font-size:12px;text-align:center;padding:18px 0}
@media(max-width:720px){.columns{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <h1>团队任务看板</h1>
  <p class="sub">新增任务、拖拽卡片切换状态、输入关键词即时筛选。</p>
  <div class="toolbar">
    <input id="newTask" placeholder="新增任务，例如：撰写发布文案" aria-label="新增任务">
    <button id="add">新增</button>
    <input id="filter" placeholder="筛选任务关键词…" aria-label="筛选任务">
  </div>
  <div class="columns" id="columns"></div>
</div>
<script>
const COLS = [
  {key:'todo',name:'待办'},
  {key:'doing',name:'进行中'},
  {key:'done',name:'已完成'},
];
const tags = ['前端','后端','设计','运营'];
let tasks = [
  {id:1,title:'敲定首页视觉稿',col:'todo',tag:'设计'},
  {id:2,title:'实现沙箱预览服务',col:'doing',tag:'后端'},
  {id:3,title:'补齐导航集成用例',col:'done',tag:'前端'},
];
let nextId = 10;
let filter = '';
let dragId = null;
function render(){
  const root = document.getElementById('columns');
  root.innerHTML = COLS.map(c=>{
    const items = tasks.filter(t=>t.col===c.key && (!filter || t.title.includes(filter)));
    const cards = items.length
      ? items.map(t=>'<div class="card" draggable="true" data-id="'+t.id+'">'+esc(t.title)+'<br><span class="tag">'+esc(t.tag)+'</span></div>').join('')
      : '<div class="empty">暂无任务</div>';
    return '<div class="col" data-col="'+c.key+'"><h2>'+c.name+' <span class="cnt">'+items.length+'</span></h2>'+cards+'</div>';
  }).join('');

  document.querySelectorAll('.card').forEach(card=>{
    card.addEventListener('dragstart',e=>{dragId=Number(card.dataset.id);card.classList.add('dragging');});
    card.addEventListener('dragend',()=>{card.classList.remove('dragging');dragId=null;});
  });
  document.querySelectorAll('.col').forEach(col=>{
    col.addEventListener('dragover',e=>{e.preventDefault();col.classList.add('drag-over');});
    col.addEventListener('dragleave',()=>col.classList.remove('drag-over'));
    col.addEventListener('drop',e=>{
      e.preventDefault();col.classList.remove('drag-over');
      if(dragId==null)return;
      const t = tasks.find(x=>x.id===dragId); if(t){t.col=col.dataset.col;render();}
    });
  });
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
document.getElementById('add').addEventListener('click',()=>{
  const v = document.getElementById('newTask').value.trim(); if(!v)return;
  tasks.push({id:nextId++,title:v,col:'todo',tag:tags[Math.floor(Math.random()*tags.length)]});
  document.getElementById('newTask').value=''; render();
});
document.getElementById('newTask').addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('add').click();});
document.getElementById('filter').addEventListener('input',e=>{filter=e.target.value.trim();render();});
render();
</script>
</body>
</html>"""

LEDGER_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>个人记账本</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);padding:24px;line-height:1.5}
.wrap{max-width:820px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);font-size:14px;margin:0 0 16px}
.panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:16px}
.sum{font-size:30px;font-weight:700}.sum small{font-size:13px;color:var(--muted);font-weight:400;margin-left:6px}
.form{display:flex;gap:10px;flex-wrap:wrap}
.form input,.form select{padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:14px}
.form input[type=number]{width:130px}.form input:focus-visible,.form select:focus-visible{outline:3px solid #fecdd3}
.form button{padding:10px 16px;border:0;border-radius:10px;background:#f43f5e;color:#fff;font-size:14px;cursor:pointer}
.chart{margin:16px 0}
.chart .bar-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px}
.chart .bar-row .label{width:60px;text-align:right;color:var(--muted)}
.chart .bar-row .track{flex:1;height:18px;background:#f1f5f9;border-radius:99px;overflow:hidden}
.chart .bar-row .fill{height:100%;border-radius:99px;transition:width .3s}
.chart .bar-row .amt{width:80px;color:var(--muted)}
ul.items{list-style:none;margin:0;padding:0}
ul.items li{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
ul.items li:last-child{border-bottom:0}
ul.items .del{background:#fff;border:1px solid var(--line);border-radius:8px;padding:4px 10px;font-size:12px;cursor:pointer;color:var(--muted)}
.cat{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
</style>
</head>
<body>
<div class="wrap">
  <h1>个人记账本</h1>
  <p class="sub">记录每一笔支出，按分类统计本月开销。</p>

  <div class="panel">
    <div class="sum">¥<span id="total">0</span><small>本月支出</small></div>
    <div class="chart" id="chart"></div>
  </div>

  <div class="panel">
    <div class="form">
      <input type="number" id="amount" placeholder="金额" min="0" aria-label="金额">
      <select id="category" aria-label="分类">
        <option>餐饮</option><option>交通</option><option>购物</option><option>居住</option><option>娱乐</option><option>其他</option>
      </select>
      <button id="add">记一笔</button>
    </div>
  </div>

  <div class="panel">
    <ul class="items" id="items"></ul>
  </div>
</div>
<script>
const COLORS = {餐饮:'#f43f5e',交通:'#0ea5e9',购物:'#8b5cf6',居住:'#f59e0b',娱乐:'#10b981',其他:'#94a3b8'};
let entries = [
  {id:1,amount:28.5,cat:'餐饮'},
  {id:2,amount:120,cat:'交通'},
  {id:3,amount:499,cat:'购物'},
];
let nextId = 10;
function render(){
  const total = entries.reduce((s,e)=>s+e.amount,0);
  document.getElementById('total').textContent = total.toFixed(2);
  const byCat = {};
  entries.forEach(e=>byCat[e.cat]=(byCat[e.cat]||0)+e.amount);
  const max = Math.max(1,...Object.values(byCat));
  document.getElementById('chart').innerHTML = Object.keys(COLORS).map(c=>{
    const v = byCat[c]||0;
    const pct = Math.round(v/max*100);
    return '<div class="bar-row"><span class="label">'+c+'</span><span class="track"><span class="fill" style="width:'+pct+'%;background:'+COLORS[c]+'"></span></span><span class="amt">¥'+(v? v.toFixed(0):'0')+'</span></div>';
  }).join('');
  document.getElementById('items').innerHTML = entries.slice().reverse().map(e=>
    '<li><span><span class="cat" style="background:'+COLORS[e.cat]+'"></span>'+e.cat+'</span><span>¥'+e.amount.toFixed(2)+' <button class="del" data-id="'+e.id+'">删除</button></span></li>'
  ).join('');
  document.querySelectorAll('.del').forEach(b=>b.addEventListener('click',()=>{
    entries = entries.filter(e=>e.id!==Number(b.dataset.id)); render();
  }));
}
document.getElementById('add').addEventListener('click',()=>{
  const amt = parseFloat(document.getElementById('amount').value);
  if(!amt || amt<=0)return;
  entries.push({id:nextId++,amount:amt,cat:document.getElementById('category').value});
  document.getElementById('amount').value=''; render();
});
render();
</script>
</body>
</html>"""

NOTES_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>读书笔记库</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);padding:24px;line-height:1.55}
.wrap{max-width:900px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);font-size:14px;margin:0 0 16px}
.toolbar{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.toolbar input{flex:1;min-width:160px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:14px}
.toolbar input:focus-visible{outline:3px solid #ddd6fe}
.tags{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.tags .tag{padding:6px 12px;border:1px solid var(--line);border-radius:99px;font-size:13px;cursor:pointer;background:#fff}
.tags .tag.on{background:#8b5cf6;color:#fff;border-color:#8b5cf6}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.note{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:10px}
.note h3{margin:0;font-size:15px}
.note .body{color:#475569;font-size:13px;flex:1}
.note .meta{display:flex;gap:6px;flex-wrap:wrap}
.note .meta span{background:#ede9fe;color:#6d28d9;border-radius:6px;padding:2px 7px;font-size:11px}
.form{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.form input,.form textarea{padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:14px;font-family:inherit}
.form textarea{flex:1;min-width:200px;resize:vertical}
.form button{padding:10px 16px;border:0;border-radius:10px;background:#8b5cf6;color:#fff;font-size:14px;cursor:pointer}
</style>
</head>
<body>
<div class="wrap">
  <h1>读书笔记库</h1>
  <p class="sub">记录阅读心得，用标签归类，随时搜索回顾。</p>

  <div class="form">
    <input id="title" placeholder="书名" aria-label="书名">
    <input id="tags" placeholder="标签，逗号分隔" aria-label="标签">
    <textarea id="body" rows="2" placeholder="一句话笔记…" aria-label="笔记内容"></textarea>
    <button id="add">保存</button>
  </div>

  <div class="tags" id="tagFilter"></div>
  <div class="grid" id="grid"></div>
</div>
<script>
let notes = [
  {id:1,title:'《人类简史》',tags:['历史','通识'],body:'认知革命让人类学会虚构故事，从而组织起大规模协作。'},
  {id:2,title:'《代码整洁之道》',tags:['工程','编程'],body:'命名与分层是让代码可维护的起点，注释要解释「为什么」。'},
  {id:3,title:'《设计中的设计》',tags:['设计'],body:'留白不是空白，而是信息呼吸的空间。'},
];
let nextId = 10;
let activeTag = null;
let search = '';
function allTags(){const s=new Set();notes.forEach(n=>n.tags.forEach(t=>s.add(t)));return [...s];}
function render(){
  document.getElementById('tagFilter').innerHTML =
    '<span class="tag'+(activeTag===null?' on':'')+'" data-tag="">全部</span>' +
    allTags().map(t=>'<span class="tag'+(activeTag===t?' on':'')+'" data-tag="'+esc(t)+'">'+esc(t)+'</span>').join('');
  document.querySelectorAll('#tagFilter .tag').forEach(el=>el.addEventListener('click',()=>{
    activeTag = el.dataset.tag || null; render();
  }));

  const list = notes.filter(n=>
    (activeTag===null || n.tags.includes(activeTag)) &&
    (!search || (n.title+n.body).includes(search))
  );
  document.getElementById('grid').innerHTML = list.map(n=>
    '<div class="note"><h3>'+esc(n.title)+'</h3><div class="body">'+esc(n.body)+'</div><div class="meta">'+n.tags.map(t=>'<span>'+esc(t)+'</span>').join('')+'</div></div>'
  ).join('') || '<p class="sub">没有匹配的笔记。</p>';
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
document.getElementById('add').addEventListener('click',()=>{
  const title = document.getElementById('title').value.trim();
  const tags = document.getElementById('tags').value.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
  const body = document.getElementById('body').value.trim();
  if(!title && !body)return;
  notes.push({id:nextId++,title:title||'未命名',tags:tags.length?tags:['未分类'],body:body||'…'});
  document.getElementById('title').value='';document.getElementById('tags').value='';document.getElementById('body').value='';
  render();
});
render();
</script>
</body>
</html>"""

GENERIC_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>原型预览</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f8fafc;color:#0f172a;padding:40px 24px;line-height:1.6}
.wrap{max-width:520px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;text-align:center}
h1{font-size:22px;margin:0 0 12px}
p{color:#64748b;font-size:14px;margin:0 0 20px}
.actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
button{padding:10px 16px;border:0;border-radius:10px;background:#0ea5e9;color:#fff;font-size:14px;cursor:pointer}
button.alt{background:#fff;color:#0f172a;border:1px solid #e2e8f0}
button:focus-visible{outline:3px solid #bae6fd}
#msg{margin-top:16px;font-size:13px;color:#16a34a;min-height:20px}
</style>
</head>
<body>
<div class="wrap">
  <h1>原型预览已就绪</h1>
  <p>这是一个通用演示页面。输入更具体的需求（例如饮水追踪器、任务看板、记账本或读书笔记库），即可生成对应的可交互成品。</p>
  <div class="actions">
    <button id="demo">点我试试</button>
    <button id="reset" class="alt">重置</button>
  </div>
  <div id="msg"></div>
</div>
<script>
let n=0;
document.getElementById('demo').addEventListener('click',()=>{
  n++;document.getElementById('msg').textContent='你点击了 '+n+' 次，交互正常。';
});
document.getElementById('reset').addEventListener('click',()=>{
  n=0;document.getElementById('msg').textContent='已重置。';
});
</script>
</body>
</html>"""


def _plan(summary, stack, steps, files):
    return {"summary": summary, "stack": stack, "steps": steps, "files": files}


def _outline(title, sections, interactions, seed_data):
    return {"title": title, "sections": sections, "interactions": interactions, "seed_data": seed_data}


EXAMPLES = [
    {
        "id": "hydration",
        "exact": "一个记录每日饮水量的追踪器，带进度环",
        "keywords": ["饮水", "喝水", "补水", "水分", "水量"],
        "plan": _plan(
            "做一个带进度环的每日饮水追踪器",
            ["HTML", "内联SVG"],
            [
                {"title": "搭建进度环", "detail": "内联 SVG 圆环随饮水量实时更新"},
                {"title": "杯量快捷记录", "detail": "四档杯量按钮一键累加"},
                {"title": "今日记录", "detail": "列表展示每次饮水并支持撤销"},
            ],
            [{"path": "index.html", "purpose": "饮水追踪单文件应用"}],
        ),
        "outline": _outline(
            "每日饮水追踪器",
            [
                {"name": "进度概览", "blocks": ["SVG 进度环", "当前/目标饮水", "达成状态"]},
                {"name": "快捷记录", "blocks": ["150/250/330/500ml 按钮"]},
                {"name": "今日记录", "blocks": ["饮水列表", "撤销操作"]},
            ],
            ["点击杯量按钮累加饮水并刷新进度环", "撤销最后一杯"],
            ["2000 目标", "150", "250", "330", "500"],
        ),
        "html": HYDRATION_HTML,
    },
    {
        "id": "kanban",
        "exact": "团队任务看板，支持新增、拖动状态、筛选",
        "keywords": ["看板", "任务", "拖拽", "拖动", "kanban"],
        "plan": _plan(
            "做一个支持拖拽与筛选的团队任务看板",
            ["HTML", "内联脚本"],
            [
                {"title": "三列布局", "detail": "待办/进行中/已完成三列"},
                {"title": "拖拽换列", "detail": "原生拖拽事件切换任务状态"},
                {"title": "新增与筛选", "detail": "输入新增、关键词即时筛选"},
            ],
            [{"path": "index.html", "purpose": "任务看板单文件应用"}],
        ),
        "outline": _outline(
            "团队任务看板",
            [
                {"name": "看板列", "blocks": ["待办", "进行中", "已完成"]},
                {"name": "任务卡片", "blocks": ["标题", "分类标签"]},
                {"name": "工具栏", "blocks": ["新增输入", "筛选输入"]},
            ],
            ["新增任务进入待办列", "拖拽卡片切换状态", "关键词筛选"],
            ["敲定首页视觉稿", "实现沙箱预览服务", "补齐导航集成用例"],
        ),
        "html": KANBAN_HTML,
    },
    {
        "id": "ledger",
        "exact": "个人记账本，按分类统计月度支出",
        "keywords": ["记账", "账单", "支出", "开销", "记一笔"],
        "plan": _plan(
            "做一个按分类统计月度支出的个人记账本",
            ["HTML", "内联脚本"],
            [
                {"title": "记账表单", "detail": "金额 + 分类新增支出"},
                {"title": "分类统计", "detail": "按分类柱状图汇总本月开销"},
                {"title": "明细列表", "detail": "倒序展示并可删除"},
            ],
            [{"path": "index.html", "purpose": "记事本单文件应用"}],
        ),
        "outline": _outline(
            "个人记账本",
            [
                {"name": "月度总览", "blocks": ["本月支出总额", "分类柱状图"]},
                {"name": "记账表单", "blocks": ["金额输入", "分类选择", "记一笔"]},
                {"name": "支出明细", "blocks": ["列表", "删除"]},
            ],
            ["新增支出并刷新总额与图表", "删除某笔支出"],
            ["餐饮 28.5", "交通 120", "购物 499"],
        ),
        "html": LEDGER_HTML,
    },
    {
        "id": "notes",
        "exact": "读书笔记库，支持标签和搜索",
        "keywords": ["读书", "笔记", "书单", "阅读", "标签", "搜索"],
        "plan": _plan(
            "做一个支持标签与搜索的读书笔记库",
            ["HTML", "内联脚本"],
            [
                {"title": "笔记卡片", "detail": "卡片网格展示标题/标签/内容"},
                {"title": "标签筛选", "detail": "按标签过滤笔记"},
                {"title": "搜索与新增", "detail": "关键词搜索、表单新增"},
            ],
            [{"path": "index.html", "purpose": "读书笔记库单文件应用"}],
        ),
        "outline": _outline(
            "读书笔记库",
            [
                {"name": "新增表单", "blocks": ["书名", "标签", "笔记内容"]},
                {"name": "标签栏", "blocks": ["全部", "按标签筛选"]},
                {"name": "笔记网格", "blocks": ["标题", "正文", "标签"]},
            ],
            ["保存新笔记", "点击标签筛选", "关键词搜索"],
            ["人类简史 (历史/通识)", "代码整洁之道 (工程/编程)", "设计中的设计 (设计)"],
        ),
        "html": NOTES_HTML,
    },
]


def _normalize(text: str) -> str:
    return " ".join((text or "").split())


def match_example(requirement: str):
    """返回命中的示例 dict；无命中返回 None。

    优先精确匹配前端示例文本，其次按关键词命中，保证示例输入稳定复用示范网页。
    """
    norm = _normalize(requirement).lower()
    if not norm:
        return None
    for example in EXAMPLES:
        if norm == _normalize(example["exact"]).lower():
            return example
    for example in EXAMPLES:
        if any(kw in norm for kw in example["keywords"]):
            return example
    return None


def generic_fixture():
    return {
        "plan": _plan(
            "演示通用可交互原型",
            ["HTML"],
            [{"title": "生成演示页", "detail": "输出通用可交互的单文件页面"}],
            [{"path": "index.html", "purpose": "通用演示"}],
        ),
        "outline": _outline(
            "原型预览",
            [{"name": "演示区", "blocks": ["交互按钮", "状态反馈"]}],
            ["点击反馈", "重置"],
            ["示例交互"],
        ),
        "html": GENERIC_HTML,
    }


def fixture(requirement: str):
    """按需求返回确定性的 plan/outline/html 三件套。"""
    example = match_example(requirement)
    if example:
        return {
            "plan": example["plan"],
            "outline": example["outline"],
            "html": example["html"],
        }
    return generic_fixture()