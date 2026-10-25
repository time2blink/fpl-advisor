/* ===== dashboard_core.js — общая логика для всех дизайнов (данные, ЧС, скаут-лист, настройки, клики).
   Вставляется сборщиком fpl_tool.py вместо метки __CORE__ в dashboard_template*.html. Вид — в шаблонах. ===== */
const P = {}; D.players.forEach(p=>P[p.id]=p);
/* ---- чёрный список: из config.json (Python) + добавленные здесь (localStorage) ---- */
// соперники берутся из настроек (config.json → entries/names), их 1–5
const OWN = Object.fromEntries(Object.entries(D.league_names||{}).filter(([k])=>k!=='me'));
const RIV = Object.values(OWN), RIV_AND = RIV.length>1?RIV.slice(0,-1).join(', ')+' и '+RIV[RIV.length-1]:(RIV[0]||'соперников');
const ownOpts = sel => Object.entries(OWN).map(([k,v])=>`<option value="${k}" ${sel===k?'selected':''}>${esc(v)}</option>`).join('');
const BL_CFG = new Map(); (D.bl_track||[]).forEach(e=>BL_CFG.set(e.id,e));
let BL_LOCAL = new Map();
try{ JSON.parse(localStorage.getItem('fpl_blacklist2')||'[]').forEach(e=>BL_LOCAL.set(e.id,e)); }catch(e){}
const saveBL = ()=>{ try{ localStorage.setItem('fpl_blacklist2', JSON.stringify([...BL_LOCAL.values()])); }catch(e){} };
function statusOf(id){
  if(BL_CFG.has(id)) return BL_CFG.get(id);
  const e=BL_LOCAL.get(id); if(!e) return null;
  const holder=Object.keys(D.holdings||{}).find(k=>D.holdings[k].includes(id));
  if(holder) return {id,owner:holder,status:'held',pin:!!e.pin,local:true};
  if(e.owner&&D.holdings[e.owner]) return {id,owner:e.owner,status:D.verified[e.owner]?'released':'unverified',pin:!!e.pin,local:true};
  return {id,owner:null,status:'manual',pin:!!e.pin,local:true};
}
const blEntries = () => [...new Set([...BL_CFG.keys(), ...BL_LOCAL.keys()])].map(statusOf).filter(Boolean);
const isBlocked = id => { const p=P[id]; if(p&&p.taken_by&&p.taken_by!=='чёрный список') return true; const st=statusOf(id); if(st) return st.status!=='released'||st.pin; return !!(p&&p.taken_by); };
const blockWhy = id => { const p=P[id]; if(p&&p.taken_by&&p.taken_by!=='чёрный список') return 'занят: '+p.taken_by; return isBlocked(id)?'чёрный список':''; };
const releasedList = () => blEntries().filter(e=>e.status==='released'&&!e.pin);
/* ---- скаут-лист (v1.17): config.json → watchlist (Claude + добавленные кнопкой) ----
   Через run.bat (http://127.0.0.1) кнопки пишут прямо в config.json; открыт как файл — копим в localStorage
   и показываем JSON для вставки. source:'user' — добавил пользователь, иначе Claude. */
const ME_NAME = (D.league_names||{}).me || 'я';
const WL = new Map(); (D.watch||[]).forEach(w=>WL.set(w.id,Object.assign({source:'claude'},w)));
let WL_LOCAL = new Map(), WL_RM = new Set();
try{ JSON.parse(localStorage.getItem('fpl_watch_user')||'[]').forEach(e=>{ const c=WL.get(e.id); if(!c||c.prio!==e.prio||(c.note||'')!==(e.note||'')) WL_LOCAL.set(e.id,e); }); }catch(e){}
try{ JSON.parse(localStorage.getItem('fpl_watch_rm')||'[]').forEach(id=>{ if(WL.has(id)) WL_RM.add(id); }); }catch(e){}
const saveWLlocal = ()=>{ try{ localStorage.setItem('fpl_watch_user',JSON.stringify([...WL_LOCAL.values()])); localStorage.setItem('fpl_watch_rm',JSON.stringify([...WL_RM])); }catch(e){} };
const wlGet = id => WL_RM.has(id)?null:(WL_LOCAL.get(id)||WL.get(id)||null);
const wlList = () => { const m=new Map(WL); WL_LOCAL.forEach((e,id)=>m.set(id,e)); WL_RM.forEach(id=>m.delete(id)); return [...m.values()].filter(w=>P[w.id]); };
const wlSpec = id => P[id].name+':'+P[id].tname;
const wlUnsaved = () => WL_LOCAL.size+WL_RM.size;
const fmtD = s => s?s.slice(8,10)+'.'+s.slice(5,7):'';
function wlToast(msg,bad){ let t=$('#wltoast'); if(!t){t=document.createElement('div');t.id='wltoast';t.className='wltoast';document.body.appendChild(t);} t.textContent=msg; t.className='wltoast on'+(bad?' bad':''); clearTimeout(t._h); t._h=setTimeout(()=>t.className='wltoast',3200); }
async function wlAdd(id,prio,note,trigger){
  const spec=wlSpec(id), cur=wlGet(id);
  if(SRV){
    try{
      const r=await api('/api/watch',{action:'add',id,player:spec,raw:cur&&cur.player,prio,note,trigger});
      const e=r.entry; WL.set(id,{id,player:e.player,prio:e.prio,note:e.note,trigger:e.trigger,source:e.source||'claude',added:e.added||''});
      WL_LOCAL.delete(id); WL_RM.delete(id); saveWLlocal();
      wlToast('Сохранено в config.json — Claude это увидит');
    }catch(err){ wlToast(err.message,true); return; }
  } else {
    const base=cur&&cur.source!=='user'?cur:{};
    WL_LOCAL.set(id,Object.assign({},base,{id,player:spec,prio,note:note||base.note||'',trigger:trigger||base.trigger||'',source:base.source||'user',added:base.added||new Date().toISOString().slice(0,10),local:true}));
    WL_RM.delete(id); saveWLlocal();
    wlToast('Добавлено в браузере. Чтобы сохранить в config.json — открой дашборд через run.bat');
  }
  render(); if($('#drawer').classList.contains('open')) openDrawer(id);
}
async function wlRm(id){
  const cur=wlGet(id); if(!cur) return;
  if(!confirm('Убрать '+P[id].name+' из скаут-листа?')) return;
  if(cur.local&&!WL.has(id)){ WL_LOCAL.delete(id); saveWLlocal(); }
  else if(SRV){
    try{ await api('/api/watch',{action:'remove',id,player:wlSpec(id),raw:cur.player}); WL.delete(id); WL_LOCAL.delete(id); WL_RM.delete(id); saveWLlocal(); wlToast('Убрано из config.json'); }
    catch(err){ wlToast(err.message,true); return; }
  } else { WL_LOCAL.delete(id); WL_RM.add(id); saveWLlocal(); wlToast('Убрано в браузере. В config.json — через run.bat'); }
  render(); if($('#drawer').classList.contains('open')) openDrawer(id);
}
async function wlSyncLocal(){
  for(const e of [...WL_LOCAL.values()]){ try{ await api('/api/watch',{action:'add',id:e.id,player:wlSpec(e.id),prio:e.prio,note:e.note,trigger:e.trigger}); WL.set(e.id,Object.assign({},e,{local:false,source:e.source||'user'})); WL_LOCAL.delete(e.id);}catch(err){} }
  for(const id of [...WL_RM]){ const c=WL.get(id); try{ await api('/api/watch',{action:'remove',id,player:wlSpec(id),raw:c&&c.player}); WL.delete(id); WL_RM.delete(id);}catch(err){} }
  saveWLlocal(); wlToast(wlUnsaved()?'Часть изменений не сохранилась':'Всё сохранено в config.json',!!wlUnsaved()); render();
}
function wlFormAdd(pref){
  const id=+($('#'+pref+'id')?$('#'+pref+'id').value:0)||WL_PICK[($('#'+pref+'q')||{}).value];
  if(!id||!P[id]){ wlToast('Выбери игрока из списка',true); return; }
  wlAdd(id,+$('#'+pref+'p').value,$('#'+pref+'n').value.trim(),'');
}
const WL_PICK = {};
const POSN = {GK:"Вратари",DEF:"Защитники",MID:"Полузащитники",FWD:"Нападающие"};
const money = x => x==null?'–':(x/10).toFixed(1);
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pnk = id => P[id]?`<span class="plk" data-id="${id}">${esc(pn(id))}</span>`:esc(pn(id));  // кликабельно, только если есть карточка  // имя = своя область нажатия
const pn = id => P[id] ? P[id].name : (D.all_names[id]?D.all_names[id].name:('#'+id));
const pt = id => P[id] ? P[id].tname : (D.all_names[id]?D.all_names[id].team:'');
const IMG={p:c=>`https://resources.premierleague.com/premierleague/photos/players/110x140/p${c}.png`,b:c=>`https://resources.premierleague.com/premierleague/badges/70/t${c}.png`};
function av(id,sz){
  sz=sz||44; const p=P[id];
  if(!p){const n=(D.all_names[id]||{}).name||'?'; return `<span class="av" style="--s:${sz}px;--h:220"><span class="avp">${SHIRT(220)}<b>${esc(n.slice(0,2).toUpperCase())}</b></span></span>`;}
  const ini=(p.name.match(/[A-Za-zÀ-ÿА-Яа-я]/g)||['?']).slice(0,2).join('').toUpperCase(), h=(p.team*47)%360;
  const ph=p.pcode?`<img src="${IMG.p(p.pcode)}" loading="lazy" alt="" onload="this.parentNode.classList.add('has')" onerror="this.remove()">`:'';
  const bd=p.tcode?`<img class="avb" src="${IMG.b(p.tcode)}" alt="${p.tname}" onerror="this.outerHTML='<span class=&quot;avb avd&quot; style=&quot;background:hsl(${h} 62% 62%)&quot;></span>'">`:`<span class="avb avd" style="background:hsl(${h} 62% 62%)"></span>`;
  return `<span class="av" data-id="${id}" style="--s:${sz}px;--h:${h}"><span class="avp">${SHIRT(h)}<b>${esc(ini)}</b>${ph}</span>${bd}</span>`;
}
const RING=(v,sz)=>{const r=sz/2-8,c=2*Math.PI*r,o=c*(1-Math.min(1,v));return `<svg width="${sz}" height="${sz}" viewBox="0 0 ${sz} ${sz}"><defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6f86ff"/><stop offset="1" stop-color="#9a85f5"/></linearGradient></defs><circle cx="${sz/2}" cy="${sz/2}" r="${r}" fill="none" stroke="#e6e9f3" stroke-width="9"/><circle cx="${sz/2}" cy="${sz/2}" r="${r}" fill="none" stroke="url(#rg)" stroke-width="9" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${o}" transform="rotate(-90 ${sz/2} ${sz/2})"/></svg>`};
const fxHtml = (p,n)=> '<span class="fx">'+(p.fix||[]).slice(0,n||6).map(f=>`<span class="f${f.fdr}" title="GW${f.gw}">${f.opp}${f.h?'':'·'}</span>`).join('')+((p.fix||[]).length?'':'<span class="f3">—</span>')+'</span>';
const statusDot = p => p.status==='a'&&!p.news?'':`<span class="dot" style="background:${p.status==='i'||p.status==='s'||p.status==='u'?'#ff3b30':'#ff9f0a'}" title="${esc(p.news)}"></span>`;
const trendArrow = (v,suf,inv)=> v==null||v===0?'<span class="mut">–</span>':`<span class="${(v>0)!==!!inv?'up':'dn'}">${v>0?'▲':'▼'} ${Math.abs(v)}${suf||''}</span>`;
const takenPill = p => p.mine?'<span class="pill b">мой</span>':(isBlocked(p.id)?`<span class="pill ${blockWhy(p.id)==='чёрный список'?'r':'o'}">${esc(blockWhy(p.id))}</span>`:'<span class="pill g">свободен</span>');

function countdown(){
  if(!D.meta.deadline) return;
  const ms = new Date(D.meta.deadline)-new Date();
  const d=Math.floor(ms/864e5),h=Math.floor(ms%864e5/36e5),m=Math.floor(ms%36e5/6e4);
  // дизайн 2: элементы .cdl (полный отсчёт) и .cds (короткий) — только значение
  document.querySelectorAll('.cdl').forEach(e=>e.textContent=ms<=0?'прошёл':`${d} д ${h} ч ${m} мин`);
  document.querySelectorAll('.cds').forEach(e=>e.textContent=ms<=0?'прошёл':`${d} д ${h} ч`);
  const el=$('#cd'); if(!el) return;
  if(ms<=0){el.textContent='Дедлайн прошёл'; return;}
  el.textContent=`До дедлайна: ${d} д ${h} ч ${m} мин`;
}
setInterval(countdown,30000);

const stripH1=h=>h.replace(/<h1[^>]*>.*?<\/h1>/s,'');
const sect=(title,sub,html)=>`<div class="sect"><div class="chead"><h2>${title}</h2>${sub?`<span class="sub">${sub}</span>`:''}</div>${stripH1(html)}</div>`;
const fold=(title,sub,html,open)=>`<details class="fold" ${open?'open':''}><summary><b>${title}</b><span class="sub">${sub||''}</span></summary><div class="foldb">${stripH1(html)}</div></details>`;
const diverse=(arr,k)=>{const c={};return arr.filter(m=>{c[m.out]=(c[m.out]||0)+1;return c[m.out]<=k;});};

/* ---------- подсказки (работают везде: data-tip и title) ---------- */
const TERMS={'xp1':'xP1 — ожидаемые очки (expected points) на ближайший тур.','xp5':'xP5 — сумма ожидаемых очков за ближайшие 5 туров.','xp тура':'Ожидаемые очки команды за этот тур по плану.','+xp':'Прирост ожидаемых очков за 5 туров по сравнению с текущим игроком.','ft':'Свободные трансферы (free transfers): без штрафа.','ft до':'Сколько свободных трансферов было перед этим туром.','хит':'Штраф −4 очка за каждый платный трансфер сверх свободных.','форма':'Средние очки за игру за последние недели (данные FPL).','очк/игру':'Средние очки за матч за сезон.','очки за игру':'Средние очки за матч за сезон.','рейтинг':'Сводный балл 0–100 внутри позиции: очки, форма, xGI/защитные действия, календарь, минуты, цена.','δ цена':'Разница в цене: покупка минус продажа (в млн £).','банк после':'Сколько останется в банке после хода.','банк':'Деньги вне состава (млн £).','риск':'Вероятность, что друг заберёт этого игрока раньше тебя.','срочность':'Риск × твой прирост xP. Чем выше, тем раньше нужно покупать.','кто может':'Кто из друзей может купить игрока и с какой вероятностью.','мой прирост xp':'Насколько вырастут твои ожидаемые очки, если купишь игрока.','давление':'Чистые трансферы за тур: показывает, подорожает или подешевеет игрок.','удача':'Реальные очки против ожидаемых по xGI/xGC: «не везло» — вероятен рост, «перегрет» — спад.','календарь':'Ближайшие матчи. Цвет — сложность соперника: зелёный легче, красный тяжелее; «·» — гостевой матч.','замены':'Запасные варианты на эту позицию (доступные тебе).','влад.':'Процент менеджеров FPL, у которых есть игрок.','владение':'Процент менеджеров FPL, у которых есть игрок.','цена':'Текущая цена (млн £).','продать':'Игрок из твоего состава.','купить':'Игрок, которого можно купить.','игрок':'Нажми на строку — карточка игрока.'};
function applyTerms(){
  document.querySelectorAll('th,.tile .k,.ht span,.kv span,.wc-st span,.rlh span').forEach(el=>{
    if(el.getAttribute('data-tip')||el.getAttribute('title')) return;
    const t=el.textContent.trim().toLowerCase();
    for(const k in TERMS){ if(t===k||t.startsWith(k+' ')||t.startsWith(k+'(')){ el.setAttribute('data-tip',TERMS[k]); break; } }
  });
}
(function(){
  const tt=document.createElement('div'); tt.id='tt'; document.body.appendChild(tt); let cur=null;
  const hide=()=>{tt.style.display='none';cur=null};
  function show(el){
    let t=el.getAttribute('data-tip');
    if(!t&&el.hasAttribute('title')){ t=el.getAttribute('title'); el.setAttribute('data-tip',t); el.removeAttribute('title'); }
    if(!t) return;
    tt.textContent=t; tt.style.display='block';
    // z — масштаб страницы (CSS zoom у <html>, дизайн 2 = 1.1): координаты считаем в экранных px, ставим в CSS px
    const z=parseFloat(getComputedStyle(document.documentElement).zoom)||1;
    const r=el.getBoundingClientRect(), w=tt.offsetWidth*z, h=tt.offsetHeight*z;
    let x=Math.max(8,Math.min(innerWidth-w-8,r.left+r.width/2-w/2)), y=r.top-h-10; if(y<8) y=r.bottom+10;
    tt.style.left=x/z+'px'; tt.style.top=y/z+'px'; cur=el;
  }
  document.addEventListener('mouseover',e=>{const el=e.target.closest&&e.target.closest('[data-tip],[title]'); if(el){ if(el!==cur) show(el);} else hide();});
  document.addEventListener('focusin',e=>{const el=e.target.closest&&e.target.closest('[data-tip]'); if(el) show(el);});
  document.addEventListener('focusout',hide); document.addEventListener('scroll',hide,true);
})();

/* ---------- иконки (встроенные SVG, интернет не нужен) ---------- */
const ICG={wildcard:['#a24bf3','#ec6fb7'],bboost:['#2fb67c','#4cc9d4'],freehit:['#f59a2e','#ffcf56'],'3xc':['#4c6fff','#8b6cf0'],warn:['#f2a33a','#f7c765'],danger:['#e5545a','#ef8a76'],ok:['#35b27a','#5fd0a0'],hold:['#7b86a8','#a6b0cf'],mid:['#f2a33a','#f7c765'],target:['#e5545a','#f08a8a'],up:['#35b27a','#5fd0a0'],down:['#e5545a','#ef8a76'],swap:['#4c6fff','#7e92ff'],money:['#35b27a','#7ad7b0'],tools:['#8d97b5','#b9c1d9'],star:['#f4a93b','#ffd166'],compass:['#4c6fff','#8b6cf0'],info:['#4c6fff','#7e92ff'],injury:['#e5545a','#ef8a76'],shirt:['#6f86ff','#9a85f5'],news:['#2a9fd6','#5fd3e6'],claude:['#8B7CF6','#5B4CD9']};
const ICP={
 wildcard:'<rect x="5" y="5" width="10.5" height="14" rx="2.3" transform="rotate(-12 10 12)" fill="#fff" fill-opacity=".55"/><rect x="8.5" y="4.5" width="10.5" height="14.5" rx="2.3" transform="rotate(9 13.7 11.7)" fill="#fff"/><path d="M13.8 8.2l1.1 2.4 2.6.3-1.9 1.8.5 2.6-2.3-1.3-2.3 1.3.5-2.6-1.9-1.8 2.6-.3z" fill="#b657e8"/>',
 bboost:'<path d="M12 3.5l5.2 6.3h-3.3v3.6h-3.8V9.8H6.8z" fill="#fff"/><rect x="4.5" y="15.2" width="15" height="3.2" rx="1.6" fill="#fff"/><rect x="6" y="18.4" width="2.2" height="2.6" rx="1" fill="#fff" fill-opacity=".75"/><rect x="15.8" y="18.4" width="2.2" height="2.6" rx="1" fill="#fff" fill-opacity=".75"/>',
 freehit:'<path d="M13.6 2.8L6 13.2h5l-1.1 8 8.1-11.2h-5.2z" fill="#fff"/>',
 '3xc':'<circle cx="11.2" cy="13" r="7.2" fill="none" stroke="#fff" stroke-width="2.2"/><text x="11.2" y="16.8" text-anchor="middle" font-size="10" font-weight="800" fill="#fff" font-family="Segoe UI,Arial,sans-serif">C</text><circle cx="19" cy="5.2" r="4.1" fill="#ffd166"/><text x="19" y="7.8" text-anchor="middle" font-size="6.8" font-weight="800" fill="#5a3b00" font-family="Segoe UI,Arial,sans-serif">3</text>',
 warn:'<path d="M12 4.2l8.2 14.2H3.8z" fill="#fff"/><rect x="11" y="9.4" width="2" height="5" rx="1" fill="#e08a1c"/><circle cx="12" cy="16.4" r="1.2" fill="#e08a1c"/>',
 danger:'<circle cx="12" cy="12" r="8" fill="#fff"/><rect x="11" y="7" width="2" height="6.4" rx="1" fill="#d94048"/><circle cx="12" cy="16" r="1.3" fill="#d94048"/>',
 ok:'<path d="M6.2 12.6l3.8 3.8 7.8-8.2" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>',
 hold:'<rect x="7.2" y="6.5" width="3.3" height="11" rx="1.4" fill="#fff"/><rect x="13.5" y="6.5" width="3.3" height="11" rx="1.4" fill="#fff"/>',
 mid:'<circle cx="12" cy="12" r="7.6" fill="none" stroke="#fff" stroke-width="2.2"/><path d="M12 7.8v4.6l3 1.8" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>',
 target:'<circle cx="12" cy="12" r="7.4" fill="none" stroke="#fff" stroke-width="2"/><circle cx="12" cy="12" r="3.4" fill="none" stroke="#fff" stroke-width="2"/><circle cx="12" cy="12" r="1.2" fill="#fff"/>',
 up:'<path d="M12 6l6 8H6z" fill="#fff"/><rect x="10.6" y="13" width="2.8" height="5" rx="1" fill="#fff"/>',
 down:'<path d="M12 18l-6-8h12z" fill="#fff"/><rect x="10.6" y="6" width="2.8" height="5" rx="1" fill="#fff"/>',
 swap:'<path d="M5 9h11l-3-3M19 15H8l3 3" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
 money:'<text x="12" y="17" text-anchor="middle" font-size="14" font-weight="800" fill="#fff" font-family="Segoe UI,Arial,sans-serif">£</text>',
 tools:'<circle cx="12" cy="12" r="3.2" fill="none" stroke="#fff" stroke-width="2.2"/><path d="M12 4v2.4M12 17.6V20M4 12h2.4M17.6 12H20M6.3 6.3L8 8M16 16l1.7 1.7M17.7 6.3L16 8M8 16l-1.7 1.7" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>',
 star:'<path d="M12 4l2.5 5.2 5.7.8-4.1 4 1 5.6L12 16.9 6.900 19.600l1-5.600-4.100-4 5.700-.8z" fill="#fff"/>',
 compass:'<circle cx="12" cy="12" r="8" fill="none" stroke="#fff" stroke-width="2"/><path d="M15.800 8.200l-2 5.600-5.600 2 2-5.600z" fill="#fff"/>',
 info:'<circle cx="12" cy="7.8" r="1.4" fill="#fff"/><rect x="10.8" y="10.6" width="2.4" height="6.6" rx="1.2" fill="#fff"/>',
 injury:'<rect x="9.8" y="4.5" width="4.4" height="15" rx="1.8" fill="#fff"/><rect x="4.5" y="9.8" width="15" height="4.4" rx="1.8" fill="#fff"/>',
 /* газета: «Новости по составу» */
 news:'<path d="M16.6 8.4h1.9a1.5 1.5 0 0 1 1.5 1.5v6.9a1.9 1.9 0 0 1-3.8 0z" fill="#fff" fill-opacity=".7"/><rect x="4.2" y="5.2" width="12.8" height="13.6" rx="2.2" fill="#fff"/><rect x="6.3" y="7.4" width="8.6" height="3.6" rx="1" fill="#2a9fd6"/><rect x="6.3" y="12.6" width="8.6" height="1.5" rx=".75" fill="#2a9fd6" fill-opacity=".55"/><rect x="6.3" y="15.3" width="5.8" height="1.5" rx=".75" fill="#2a9fd6" fill-opacity=".55"/>',
 /* искра с галочкой: «Вердикт Claude» */
 claude:'<path d="M10.6 3.6c.55 3.75 2.2 5.4 5.95 5.95-3.75.55-5.4 2.2-5.95 5.95-.55-3.75-2.2-5.4-5.95-5.95 3.75-.55 5.4-2.2 5.95-5.95z" fill="#fff"/><path d="M18.4 3.8c.22 1.4.85 2.03 2.25 2.25-1.4.22-2.03.85-2.25 2.25-.22-1.4-.85-2.03-2.25-2.25 1.4-.22 2.03-.85 2.25-2.25z" fill="#fff" fill-opacity=".75"/><circle cx="16.9" cy="16.9" r="4.4" fill="#fff"/><path d="M14.9 17l1.4 1.4 2.6-2.8" fill="none" stroke="#6B5CE7" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
};
const CHIPKEY={'wildcard':'wildcard','free hit':'freehit','freehit':'freehit','bench boost':'bboost','bboost':'bboost','triple captain':'3xc','3xc':'3xc'};
function ic(name,sz){
  sz=sz||28; const g=ICG[name]||ICG.info, id='ig'+name.replace(/\W/g,'');
  return `<span class="ico" style="--s:${sz}px"><svg viewBox="0 0 24 24" width="${sz}" height="${sz}"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${g[0]}"/><stop offset="1" stop-color="${g[1]}"/></linearGradient></defs><rect x="0" y="0" width="24" height="24" rx="7" fill="url(#${id})"/>${ICP[name]||ICP.info}</svg></span>`;
}
const chipIc=(n,sz)=>ic(CHIPKEY[String(n).toLowerCase()]||'info',sz);
const SHIRT=(h)=>`<svg class="shirt" viewBox="0 0 40 40"><path d="M14 5l-9 4.500 3 7 4-1.500V35h16V15l4 1.500 3-7L26 5c-.5 3-3 4.500-6 4.500S14.500 8 14 5z" fill="hsl(${h} 62% 62%)"/><path d="M14 5c.5 3 3 4.500 6 4.500S25.500 8 26 5" fill="none" stroke="rgba(255,255,255,.7)" stroke-width="1.600"/></svg>`;
const TABS = [['over','Обзор'],['squad','Состав'],['moves','Трансферы и план'],['scout','Скаут-лист'],['players','Игроки'],['threat','Соперники и лига'],['market','Рынок'],['top','Топ-'+D.top.n],['chg','Изменения']];
const TAB_ALIAS={watch:'scout',plan:'moves',bl:'threat',league:'threat'};
let tab = location.hash.slice(1) || 'over'; if(TAB_ALIAS[tab]) tab=TAB_ALIAS[tab];
let state = {pos:'ALL', free:true, q:'', sort:'score', dir:-1, wide:false};


function toggleBL(id){ if(BL_LOCAL.has(id)) BL_LOCAL.delete(id); else BL_LOCAL.set(id,{id,owner:null}); saveBL(); openDrawer(id); render(); }
function addBL(){ const v=($('#blq')||{}).value||''; const m=D.players.find(p=>(p.name+' · '+p.tname+' £'+money(p.price))===v); const o=($('#blo')||{}).value||''; if(m&&!m.mine){BL_LOCAL.set(m.id,{id:m.id,owner:o||null});saveBL();render();} }
function rmBL(id){ BL_LOCAL.delete(id); saveBL(); render(); }
function pinBL(id){ const e=BL_LOCAL.get(id)||{id,owner:null}; e.pin=true; BL_LOCAL.set(id,e); saveBL(); render(); }
function setOwner(id,o){ const e=BL_LOCAL.get(id); if(e){e.owner=o||null; saveBL(); render();} }
function copyBL(){ const t=$('#blout'); t.select(); try{document.execCommand('copy');}catch(e){} }

/* ---------- Настройки (⚙ возле названия команды) ----------
   Работают, когда дашборд открыт через run.bat (адрес http://127.0.0.1:…): сервер в окне run.bat
   пишет ID в config.json и пересчитывает. Открыт как файл — только просмотр и подсказка. */
const SRV = window.FPL_SERVER || null;
let SET = null;
function curSettings(){
  const L=D.league||{}, N=D.league_names||{};
  return {me:{id:(L.me||{}).entry||'',name:N.me||''},
    rivals:Object.keys(L).filter(k=>k!=='me').map(k=>({key:k,id:L[k].entry||'',name:N[k]||k})),
    league_id:(D.meta&&D.meta.league_id)||'', max_rivals:5};
}
async function api(path,body){
  const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-FPL-Token':SRV.token},body:body?JSON.stringify(body):undefined});
  const js=await r.json().catch(()=>({error:'нет ответа — окно run.bat закрыто?'}));
  if(!r.ok) throw new Error(js.error||('ошибка '+r.status));
  return js;
}
async function openSettings(){
  SET=curSettings();
  if(SRV){ try{ SET=await api('/api/settings'); }catch(e){} }
  let bg=$('#setbg');
  if(!bg){ bg=document.createElement('div'); bg.id='setbg'; bg.className='modal-bg'; bg.onclick=e=>{if(e.target===bg)closeSettings()}; document.body.appendChild(bg); }
  drawSettings(); bg.classList.add('open');
}
function closeSettings(){ const bg=$('#setbg'); if(bg) bg.classList.remove('open'); }
function sRow(r,i){
  const ro=SRV?'':'readonly';
  return `<div class="srow"><input class="sid" type="text" inputmode="numeric" placeholder="ID" value="${esc(r.id||'')}" oninput="SET.rivals[${i}].id=this.value" onchange="checkId(this.value,'chk${i}')" ${ro}>
  <input class="snm" type="text" placeholder="имя (подтянется из FPL)" value="${esc(r.name||'')}" oninput="SET.rivals[${i}].name=this.value" ${ro}>
  ${SRV?`<button class="ibtn" title="убрать соперника" onclick="SET.rivals.splice(${i},1);drawSettings()">✕</button>`:''}</div><div class="schk" id="chk${i}"></div>`;
}
function drawSettings(){
  const s=SET, ro=!SRV, n=s.rivals.length, mx=s.max_rivals||5;
  $('#setbg').innerHTML=`<div class="modal" role="dialog" aria-label="Настройки">
   <button class="x" onclick="closeSettings()" aria-label="Закрыть">✕</button>
   <h2>Настройки</h2>
   <div class="sub">Кого анализируем. ID — число из адреса страницы «Очки» на fantasy.premierleague.com: …/entry/<b>1234567</b>/event/…</div>
   <label class="f">Мой ID</label>
   <div class="srow"><input class="sid" type="text" inputmode="numeric" placeholder="ID" value="${esc(s.me.id||'')}" oninput="SET.me.id=this.value" onchange="checkId(this.value,'chkme',true)" ${ro?'readonly':''}>
   <input class="snm" type="text" placeholder="имя (подтянется из FPL)" value="${esc(s.me.name||'')}" oninput="SET.me.name=this.value" ${ro?'readonly':''}></div>
   <div class="schk" id="chkme"></div>
   <label class="f">Соперники · ${n} из ${mx} · их игроков не будет в рекомендациях</label>
   ${s.rivals.map(sRow).join('')}
   ${!ro&&n<mx?`<button class="btn g" onclick="SET.rivals.push({id:'',name:''});drawSettings()">+ добавить соперника</button>`:''}
   <label class="f">Дизайн дашборда</label>
   <div class="dsw">${[[2,'Дизайн 2 · светлый','новый, по умолчанию'],[1,'Дизайн 1 · классический','прежний вид']].map(([n,t,s])=>`<button class="${(typeof DESIGN!=='undefined'?DESIGN:2)===n?'on':''}" onclick="setDesign(${n})"><b>${t}</b><span>${s}</span></button>`).join('')}</div>
   <label class="f">ID мини-лиги (необязательно)</label>
   <div class="srow"><input class="sid" type="text" inputmode="numeric" placeholder="ID лиги" value="${esc(s.league_id||'')}" oninput="SET.league_id=this.value" ${ro?'readonly':''}><span class="sub" id="lgpick"></span></div>
   ${ro?`<div class="sro"><b>Сейчас только просмотр.</b> Дашборд открыт как файл, а сохранять настройки умеет окно запуска. Запусти <b>run.bat</b> (или ярлык FPL Advisor) и не закрывай чёрное окно — дашборд откроется по адресу 127.0.0.1, и здесь появится кнопка «Сохранить и пересчитать».<br><span class="sub">Вручную: tool/config.json → entries, names, league_id.</span></div>`
     :`<div class="sact"><span class="sub">пересчёт ~30 секунд</span><button class="btn" onclick="closeSettings()" style="background:#e5e5ea;color:#1d1d1f">Отмена</button><button class="btn" id="setsave" onclick="saveSettings()">Сохранить и пересчитать</button></div>`}
   <div class="smsg" id="smsg"></div></div>`;
}
/* Выбор дизайна: оба файла уже собраны (out/dashboard_v1.html, out/dashboard_v2.html), пересчёт не нужен.
   Через run.bat выбор пишется в config.json → design (по умолчанию открывается он); как файл — просто переход. */
async function setDesign(n){
  const cur=(typeof DESIGN!=='undefined'?DESIGN:2); if(n===cur){ closeSettings(); return; }
  if(SRV){
    try{ await api('/api/design',{design:n}); location.href='/dashboard.html'+location.hash; }
    catch(e){ const m=$('#smsg'); if(m){ m.className='smsg bad'; m.textContent=e.message; } }
  } else location.href='dashboard_v'+n+'.html'+location.hash;
}
async function checkId(v,elId,isMe){
  const el=$('#'+elId); if(!el||!SRV) return; v=String(v||'').trim(); if(!v){el.textContent='';return}
  el.className='schk'; el.textContent='проверяю…';
  try{
    const r=await api('/api/check',{id:v}); el.className='schk ok'; el.textContent='✓ '+r.team+' · '+r.manager;
    if(isMe&&r.leagues&&r.leagues.length) $('#lgpick').innerHTML='его лиги: '+r.leagues.slice(0,6).map(l=>`<a href="#" onclick="event.preventDefault();SET.league_id='${l.id}';drawSettings()">${esc(l.name)}</a>`).join(', ');
  }catch(e){ el.className='schk bad'; el.textContent=e.message; }
}
async function saveSettings(){
  const m=$('#smsg'), b=$('#setsave'); m.className='smsg'; b.disabled=true;
  try{
    m.textContent='Сохраняю…';
    const r=await api('/api/settings',SET);
    m.textContent='Сохранено'+(r.dropped_pending.length?' (ручные составы до дедлайна для сменившихся менеджеров сброшены)':'')+'. Пересчитываю, ~30 секунд…';
    const run=await api('/api/run',{});
    if(run.ok){ m.className='smsg ok'; m.textContent='Готово, обновляю страницу…'; setTimeout(()=>location.reload(),600); }
    else { m.className='smsg bad'; m.textContent='Пересчёт не удался:\n'+run.log; b.disabled=false; }
  }catch(e){ m.className='smsg bad'; m.textContent=e.message; b.disabled=false; }
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSettings()});
if(SRV&&SRV.error){
  const bar=document.createElement('div'); bar.className='srvbar';
  bar.innerHTML=esc(SRV.error.join(' '))+' <button class="btn" style="margin-left:8px" onclick="openSettings()">Открыть настройки</button>';
  document.body.appendChild(bar);
}


document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});

/* Клик по игроку: открывается тот, по кому кликнули (самый внутренний [data-id]),
   а не вся строка/карточка. Кнопки, поля и ссылки внутри не перехватываются. */
document.addEventListener('click',e=>{
  if(e.target.closest('button,input,select,textarea,a,label')) return;
  const el=e.target.closest('[data-id]'); if(!el) return;
  e.preventDefault(); openDrawer(+el.dataset.id);
});
