/* FPL Advisor — мобильный прототип. Данные: data.js (build_data.py режет их из tool/out/data.json). */
(function () {
'use strict';
const F = window.FPL, PL = F.players;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const P = id => PL[id] || { id, name: '#' + id, pos: '', tname: '' };
const pr = v => '£' + (v / 10).toFixed(1);
const f1 = v => (v == null ? '—' : (+v).toFixed(1));
const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1);
const POS = { GK: 'Вратарь', DEF: 'Защитник', MID: 'Полузащитник', FWD: 'Нападающий' };
const KEYS = { 1000001: 'me', 1000002: 'roma', 1000003: 'stas' };
const NAMES = F.names, COL = { me: 'var(--me)', roma: 'var(--roma)', stas: 'var(--stas)' };

const IC = {
  home: '<path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  squad: '<path d="M8.5 3 3 6l2 4.2 3-1.2V21h8V9l3 1.2L21 6l-5.5-3a3.6 3.6 0 0 1-7 0z"/>',
  moves: '<path d="M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4"/>',
  league: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  scout: '<circle cx="12" cy="12" r="9"/><path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1z"/>',
  news: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.6 2.2H4.4zM10 21h4"/>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  inj: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12V4h8l10 10-8 8zM7.5 8.5h.01"/></svg>',
  swap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.2 6.3L21 10l-6.8 1.7L12 18l-2.2-6.3L3 10l6.8-1.7zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2 20h20zM12 10v4M12 17.5v.01"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  up: '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4 3 17h18z"/></svg>',
  dn: '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 20 3 7h18z"/></svg>',
};
const CHIPS = { wildcard: ['Wildcard', 'chip_wildcard'], freehit: ['Free Hit', 'chip_free_hit'], bboost: ['Bench Boost', 'chip_bench_boost'], '3xc': ['Triple Captain', 'chip_triple_captain'] };

/* ---------- мелкие компоненты ---------- */
const hue = t => ((t || 3) * 47) % 360;
const ini = n => String(n).replace(/^[A-Z]\./, '').slice(0, 2).toUpperCase();
function av(p, s = 44, o = {}) {
  const ph = p.pcode ? `https://resources.premierleague.com/premierleague/photos/players/110x140/p${p.pcode}.png` : '';
  const bd = p.tcode ? `https://resources.premierleague.com/premierleague/badges/70/t${p.tcode}.png` : '';
  const st = o.status !== false && p.status && p.status !== 'a' ? `<i class="st ${p.status === 'd' ? '' : 'r'}" role="img" aria-label="${p.status === 'd' ? 'под вопросом' : 'не играет'}"></i>` : '';
  return `<span class="av" style="--s:${s}px;--h:${hue(p.tcode)}"${o.pid === false ? '' : ` data-pid="${p.id}"`}><span class="f"><b>${esc(ini(p.name))}</b>${ph ? `<img class="ph" loading="lazy" src="${ph}" onload="this.closest('.av').classList.add('has')" onerror="this.remove()" alt="">` : ''}</span>${bd ? `<img class="bd" loading="lazy" src="${bd}" onerror="this.remove()" alt="">` : ''}${st}</span>`;
}
const fc = f => 'f' + Math.min(5, Math.max(1, Math.round(f || 3)));
const FDRT = ['', 'очень лёгкий', 'лёгкий', 'средний', 'сложный', 'очень сложный'];
const fx = f => f ? `<span class="fx ${fc(f.fdr)}">${esc(f.opp)} ${f.h ? '(Д)' : '(Г)'}</span>` : '<span class="fx f3">—</span>';
const lg = (t, sub) => `<div class="lg"><h1>${t}</h1>${sub ? `<p>${sub}</p>` : ''}</div>`;
const sh = (a, b) => `<div class="sh"><b role="heading" aria-level="2">${a}</b>${b ? `<span>${b}</span>` : ''}</div>`;
const doubt = p => p.status && p.status !== 'a' || (p.chance != null && p.chance < 100);

const ST = { moves: 'plan', league: 'table', top: 'in', news: 'all' };
const seg = (k, items, cls) => `<div class="seg ${cls || ''}" role="group">${items.map(([v, t]) => `<button data-seg data-k="${k}" data-v="${v}" aria-pressed="${ST[k] === v}" class="${ST[k] === v ? 'on' : ''}">${t}</button>`).join('')}</div>`;
const chips = (k, items) => `<div class="chs" role="group">${items.map(([v, t, n]) => `<button data-seg data-k="${k}" data-v="${v}" aria-pressed="${ST[k] === v}" class="${ST[k] === v ? 'on' : ''}">${t}${n ? `<i class="num">${n}</i>` : ''}</button>`).join('')}</div>`;
const fmtD = iso => { try { return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso)); } catch (e) { return iso || ''; } };
const swap = (o, i) => { const a = P(o), b = P(i), d = (b.price || 0) - (a.price || 0);
  return `<div class="mv"><div class="who out" data-pid="${o}">${av(a, 40, { pid: false })}<div style="min-width:0"><b>${esc(a.name)}</b><span>${esc(a.tname)} · ${pr(a.price || 0)}</span></div></div><span class="ar">${IC.arrow}</span><div class="who" data-pid="${i}">${av(b, 40, { pid: false })}<div style="min-width:0"><b>${esc(b.name)}</b><span>${esc(b.tname)} · ${pr(b.price || 0)}</span></div></div></div>`; };
const mineSet = new Set(F.me.squad.map(s => s.id));
const ownTag = p => mineSet.has(p.id) ? '<span class="pill ac">у тебя</span>' : p.taken_by ? `<span class="pill bad">у ${esc(NAMES[p.taken_by] || p.taken_by)}</span>` : '<span class="pill ok">свободен</span>';
const INJ = { 'Unspecified injury': 'травма (уточняется)', 'Hip injury': 'травма бедра', 'Hamstring injury': 'травма задней поверхности бедра', 'Knee injury': 'травма колена', 'Ankle injury': 'травма голеностопа', 'Calf injury': 'травма икры', 'Groin injury': 'травма паха', 'Foot injury': 'травма стопы', 'Back injury': 'травма спины', 'Thigh injury': 'травма бедра', 'Muscle injury': 'мышечная травма', 'Shoulder injury': 'травма плеча', 'Arm injury': 'травма руки', 'Head injury': 'травма головы', 'Rib injury': 'травма рёбер', 'Knock': 'лёгкий ушиб', 'Illness': 'болезнь', 'Suspended': 'дисквалификация' };
function ruNews(t) {
  if (!t) return '';
  const parts = String(t).split(/\s+-\s+/).map(x => x.trim()).filter(Boolean), out = [];
  parts.forEach((p, i) => {
    let m;
    if (i === 0) { const r = INJ[p] || (/^(\w+) injury$/i.test(p) ? 'травма (' + p.split(' ')[0].toLowerCase() + ')' : p); out.push(r.charAt(0).toUpperCase() + r.slice(1)); }
    else if ((m = /(\d+)% chance of playing/i.exec(p))) out.push('шанс сыграть ' + m[1] + '%');
    else if (/unknown return date/i.test(p)) out.push('срок возврата неизвестен');
    else if ((m = /expected back (.+)/i.exec(p))) out.push('вернётся ~' + m[1]);
    else out.push(p);
  });
  return out.join(' · ');
}

/* ---------- Цены ---------- */
const arrow = up => up ? '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 4 3 17h18z"/></svg>' : '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 20 3 7h18z"/></svg>';
const nk = n => (n > 0 ? '+' : '−') + (Math.abs(n) >= 1e6 ? (Math.abs(n) / 1e6).toFixed(1) + 'M' : Math.round(Math.abs(n) / 1000) + 'k');
function pRow(id, from, to, sub, badge) {
  const p = P(id), up = to > from;
  return `<div class="pr" data-pid="${id}">${av(p, 42, { pid: false })}<div class="nm"><b>${esc(p.name)}</b><span>${sub}</span></div><div class="pc2 ${up ? 'u' : 'd'}"><div class="pcv"><s class="num">${pr(from)}</s><b class="num">${pr(to)}</b></div>${badge}</div></div>`;
}
function pricesBlock() {
  const mode = ST.price || (ST.price = 'soon');
  const M = F.market, uniq = a => { const s = new Set(); return a.filter(x => !s.has(x.id) && s.add(x.id)); };
  const up = uniq(M.my_gain.filter(x => x.tier.startsWith('up'))), dn = uniq(M.my_risk.filter(x => x.tier.startsWith('dn')));
  const lim = (arr, f, n = 3) => arr.slice(0, n).map(f).join('') + (arr.length > n ? `<details class="more-d"><summary class="more2">Ещё ${arr.length - n}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></summary>${arr.slice(n).map(f).join('')}</details>` : '');
  const byStr = a => [...a].sort((x, y) => (y.tier.endsWith('2') ? 1 : 0) - (x.tier.endsWith('2') ? 1 : 0));
  const sec = (ttl, cls, arr, up_) => `<div class="psec ${cls}"><div class="ph3">${arrow(up_)}<b>${ttl}</b><span>${arr.length ? arr.length : ''}</span></div>${arr.length ? lim(byStr(arr), m => pRow(m.id, m.price, m.price + (up_ ? 1 : -1), (up_ ? 'покупок больше на ' : 'продаж больше на ') + nk(m.net).replace(/[+−]/, '').replace('k', ' тыс.').replace('M', ' млн'), `<span class="pcb ${m.tier.endsWith('2') ? 'st' : ''}">${arrow(up_)}${m.tier.endsWith('2') ? 'почти точно' : 'возможно'}</span>`)) : '<div class="empty" style="padding:12px 0">Среди твоих игроков — никого</div>'}</div>`;
  const done = F.changes.price.slice().sort((a, b) => (mineSet.has(b.id) ? 1 : 0) - (mineSet.has(a.id) ? 1 : 0));
  const body = mode === 'soon'
    ? sec('Подорожают', 'up', up, true) + sec('Подешевеют', 'dn', dn, false)
    : `<div class="psec">${done.length ? lim(done, c => pRow(c.id, c.from, c.to, (mineSet.has(c.id) ? '<span style="color:var(--ac);font-weight:700">твой игрок</span>' : P(c.id).tname), `<span class="pcb st">${arrow(c.to > c.from)}${c.to > c.from ? '+' : '−'}${(Math.abs(c.to - c.from) / 10).toFixed(1)}</span>`), 4) : '<div class="empty">Изменений не было</div>'}</div>`;
  return `${sh('Цены', mode === 'soon' ? 'твои игроки · следующей ночью' : 'с ' + esc(fmtD(F.changes.prev_ts)))}
  <div class="card pcard">${seg('price', [['soon', 'Ожидаются'], ['done', 'Уже изменились']], 'sm')}${body}</div>`;
}

/* ---------- Обзор ---------- */
function dlText() {
  try { return new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Kyiv' }).format(new Date(F.meta.deadline)) + ' (Киев)'; }
  catch (e) { return F.meta.deadline; }
}
function cdParts() {
  let s = Math.floor((new Date(F.meta.deadline) - Date.now()) / 1000);
  if (s <= 0) return null;
  return { d: Math.floor(s / 86400), h: Math.floor(s % 86400 / 3600), m: Math.floor(s % 3600 / 60) };
}
/* аватар менеджера: эмблема любимого клуба с сайта Премьер-лиги, пока грузится или нет сети — плитка с буквой */
const mgrAv = k => { const code = F[k].fav, u = code ? 'https://resources.premierleague.com/premierleague/badges/70/t' + code + '.png' : ''; return `<span class="mav" style="--c:${COL[k]}">${mgr(k)}${u ? `<img src="${u}" alt="${esc(F[k].fav_name || '')}" loading="lazy" onload="this.parentNode.classList.add('has')" onerror="this.remove()">` : ''}</span>`; };
/* плитки для блока «Сделай до дедлайна» */
const T_OUT = (cls) => tile('tgs', '<circle cx="12" cy="8.4" r="3.5" fill="#fff"/><path d="M5 20c.3-3.9 3.2-6 7-6s6.7 2.1 7 6z" fill="#fff"/><path d="M4.6 4.6l14.8 14.8" stroke="#F4655F" stroke-width="4.2" stroke-linecap="round"/><path d="M4.6 4.6l14.8 14.8" stroke="#fff" stroke-width="1.7" stroke-linecap="round"/>', '', cls || 'td-i');
const T_CHANCE = (pct, cls) => { const L = 2 * Math.PI * 7.4, d = Math.max(.01, pct / 100) * L; return tile(pct <= 50 ? 'tgo' : 'tgw', `<circle cx="12" cy="12" r="7.4" fill="none" stroke="#fff" stroke-opacity=".38" stroke-width="2.8"/><circle cx="12" cy="12" r="7.4" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-dasharray="${d.toFixed(2)} ${L.toFixed(2)}" transform="rotate(-90 12 12)"/><text x="12" y="14.6" text-anchor="middle" font-size="7.4" font-weight="800" fill="#fff" style="font-family:inherit">${pct}</text>`, '', cls || 'td-i'); };
const T_CARD = (cls) => tile('tgs', '<rect x="7.4" y="4.6" width="9.4" height="13.4" rx="1.9" fill="#fff" transform="rotate(8 12 11.3)"/><rect x="9.6" y="7" width="3.2" height="1.6" rx=".8" fill="#F4655F" transform="rotate(8 12 11.3)" opacity=".0"/>', '', cls || 'td-i');
const T_LOCK = (k, cls) => tile({ roma: 'tgr', stas: 'tgst', me: 'tgme' }[k] || 'tgk', '<rect x="6.4" y="10.6" width="11.2" height="8.8" rx="2.4" fill="#fff"/><path d="M8.9 10.6V8.4a3.1 3.1 0 0 1 6.2 0v2.2" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="14.6" r="1.4" fill="#5B6B8C"/><path d="M12 15.2v1.8" stroke="#5B6B8C" stroke-width="1.5" stroke-linecap="round"/>', '', cls || 'td-i');
const T_SPARK = (cls) => tile('tgme', '<path d="M12 3.4l2 5.5 5.6 1.9-5.6 1.9-2 5.5-2-5.5-5.6-1.9 5.6-1.9z" fill="#fff"/><path d="M18.4 15.6l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" fill="#fff" fill-opacity=".8"/>', '', cls || 'td-i');
const T_CLOCK = (cls) => tile('tgb', '<circle cx="12" cy="12.6" r="7.6" fill="#fff"/><path d="M12 8v4.8l3.2 1.9" fill="none" stroke="#4C7DF0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M9.6 3.8h4.8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>', '', cls || 'td-i');
const T_PLUS = (cls) => tile('tgs', '<rect x="9.4" y="4.2" width="5.2" height="15.6" rx="1.8" fill="#fff"/><rect x="4.2" y="9.4" width="15.6" height="5.2" rx="1.8" fill="#fff"/>', '', cls || 'td-i');
const T_OFF = (cls) => tile('tgw', '<path d="M4.4 9.6a11 11 0 0 1 15.2 0M7.4 12.7a6.6 6.6 0 0 1 9.2 0M10.4 15.8a2.4 2.4 0 0 1 3.2 0" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round"/><path d="M4.8 4.8l14.4 14.4" stroke="#F5A524" stroke-width="4" stroke-linecap="round"/><path d="M4.8 4.8l14.4 14.4" stroke="#fff" stroke-width="1.7" stroke-linecap="round"/>', '', cls || 'td-i');
const ban = (k, ico, ttl, txt) => `<div class="ban ${k}">${ico}<div><b>${ttl}</b>${txt ? `<p>${txt}</p>` : ''}</div></div>`;
function statusBan(p, sm) {
  if (!(p.news || (p.status && p.status !== 'a'))) return '';
  const ch = p.chance, c = sm ? 'td-i sm' : 'td-i', tx = esc(ruNews(p.news) || '');
  if (p.status === 's') return ban('bad' + (sm ? ' sm' : ''), T_CARD(c), 'Дисквалификация', tx);
  if (ch != null && ch >= 1 && ch <= 99) return ban((ch <= 50 ? 'bad' : 'warn') + (sm ? ' sm' : ''), T_CHANCE(ch, c), ch + '% сыграет', tx);
  if (ch === 0 || p.status === 'i' || p.status === 'u' || p.status === 'n') return ban('bad' + (sm ? ' sm' : ''), T_OUT(c), 'Не сыграет', tx);
  return ban('warn' + (sm ? ' sm' : ''), T_WARN(c), 'Статус под вопросом', tx);
}
const T_TRADE = () => tile('tgg', '<path d="M5 8.4h11.2M13 5l3.4 3.4L13 11.8M19 15.6H7.8M11 12.2l-3.4 3.4L11 19" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>', '', 'td-i');
const T_WARN = (cls) => tile('tgw', '<path d="M12 4.2 21 19.4H3z" fill="#fff" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 9.6v4.2" stroke="#E57D0F" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="16.5" r="1.1" fill="#E57D0F"/>', '', cls || 'td-i');
const T_PRICE = () => tile('tgb', '<path d="M3.8 12.4V4.8a1 1 0 0 1 1-1h7.6l8 8-8.6 8.6z" fill="#fff"/><circle cx="8.3" cy="8.3" r="1.5" fill="#4C7DF0"/><path d="M13.2 14.6l2.4-2.4 2.4 2.4" fill="none" stroke="#4C7DF0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" transform="translate(-1.4 .8)"/>', '', 'td-i');
const T_OK = () => tile('tgg', '<path d="m6 12.6 4 4L18.2 8" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>', '', 'td-i');
const T_CHIP = c => `<img class="ti td-i" src="assets/${(CHIPS[c] || ['', ''])[1]}.svg" alt="">`;
const chev = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const tdRow = (ico, ttl, sub, attr, done) => `<div class="td${done ? ' dn' : ''}" ${attr}>${ico}<div class="tdt"><b>${ttl}</b>${sub ? `<span>${sub}</span>` : ''}</div>${chev}</div>`;

/* список дел до дедлайна: только то, что действительно есть в данных, максимум 5 строк */
function todo(al) {
  const N = newsData();
  if (N.todo && N.todo.length) {
    const ico = t => ({ ok: T_OK, cap: T_CAP, warn: T_WARN, trade: T_TRADE, price: T_PRICE, out: T_OUT, chip: () => T_CHIP(t.chip) }[t.k] || T_WARN)();
    const open = N.todo.filter(t => t.k !== 'ok').length;
    return `${sh('Сделай до дедлайна', open ? 'осталось ' + open : 'всё готово')}<div class="card tdl">${N.todo.map(t => tdRow(ico(t), esc(t.title), esc(t.sub || ''), `data-go="${t.go || 'news'}" role="button" tabindex="0"`, t.k === 'ok')).join('')}</div>`;
  }
  const cl = F.claude, cap = P(cl.captain), vice = P(cl.vice), rows = [];
  const st = F.plan.steps[0];
  if (st && st.gw === F.meta.gw_next) {
    const ms = st.moves.map(([o, i]) => `${esc(P(o).name)} → ${esc(P(i).name)}`);
    rows.push(tdRow(T_TRADE(), ms.length ? (ms.length > 1 ? ms.length + ' замены: ' : 'Замена: ') + ms.join(', ') : 'Трансферы не нужны',
      ms.length ? (st.hit ? `хит −${st.hit} — только если апгрейд того стоит · по модели` : 'без хита · по модели') : `копим трансферы · трансферов ${F.me.ft}`, 'data-go="moves" role="button" tabindex="0"'));
    const rise = new Set(F.market.rising.filter(x => x.tier === 'up2').map(x => x.id)), buy = st.moves.map(m => m[1]).filter(id => rise.has(id));
    if (buy.length) rows.push(tdRow(T_PRICE(), `Купи сегодня: ${esc(buy.map(id => P(id).name).join(', '))}`, 'подорожает ближайшей ночью', 'data-go="news" role="button" tabindex="0"'));
  }
  rows.push(tdRow(T_CAP(), `Капитан — ${esc(cap.name)}`, `вице ${esc(vice.name)}${doubt(cap) ? ' · капитан под вопросом!' : ''}`, 'data-go="squad" role="button" tabindex="0"'));
  if (al.length) rows.push(tdRow(T_WARN(), 'Проверить новости: ' + esc(al.slice(0, 2).map(p => p.name).join(', ')) + (al.length > 2 ? ' и ещё ' + (al.length - 2) : ''), al.slice(0, 3).map(p => esc(p.name) + (p.chance != null ? ' ' + p.chance + '%' : '')).join(' · '), 'data-go="news" role="button" tabindex="0"'));
  const rc = F.chips.recommend.find(r => r.gw === F.meta.gw_next);
  if (rc) rows.push(tdRow(T_CHIP(rc.chip), `Фишка ${esc((CHIPS[rc.chip] || [rc.chip])[0])}: этот тур — лучший`, `+${rc.gain.toFixed(1)} ожид. очков по модели`, 'data-go="moves" role="button" tabindex="0"'));
  return `${sh('Сделай до дедлайна', rows.length + ' · по модели')}<div class="card tdl">${rows.join('')}</div>`;
}

function home() {
  const L = F.live.managers, cl = F.claude, al = [...cl.xi, ...cl.bench].map(P).filter(doubt), c = cdParts(), win = F.race.players;
  const tot = {}; F.table.forEach(t => { tot[KEYS[t.entry]] = t.total; });
  const rows = ['me', 'roma', 'stas'].sort((x, y) => tot[y] - tot[x]);
  const liveCard = `<div class="card">
    <div class="vd-h"><b style="font-size:19px;letter-spacing:-.03em;display:flex;align-items:center;gap:8px">Тур ${F.live.gw} <span class="pill ${F.live.state === 'live' ? 'live' : ''}">${F.live.state === 'live' ? '<i class="livedot"></i> LIVE' : 'сыгран'}</span></b></div>
    <div style="margin-top:6px">${rows.map(k => `<div class="mrow">${mgrAv(k)}<div class="nm"><b>${esc(NAMES[k])}${k === 'me' ? ' <span style="color:var(--faint);font-weight:500">· ты</span>' : ''}</b><span>в туре <b class="num" style="display:inline;font-size:inherit;color:var(--ink)">${L[k].pts}</b>${L[k].hit ? ` · хит −${L[k].hit}` : ''}</span></div><div style="text-align:right"><span class="big num" style="display:block;line-height:1.1">${tot[k]}</span><span class="num" style="font-size:14px;font-weight:700;color:${win[k].p_win > 0 ? COL[k] : 'var(--mut)'}">${Math.round(win[k].p_win * 100)}% на 1 место</span></div></div>`).join('')}</div></div>`;
  const verdict = `<div class="card">
    <div class="vd-h"><b><span class="spark">${IC.spark}</span>Вердикт Claude</b><span class="pill ac">на GW${cl.gw} · ${esc(cl.updated.slice(5).split('-').reverse().join('.'))}</span></div>
    <p class="sum open" style="margin-top:12px">${esc(newsData().headline || cl.summary)}</p><button class="more" data-go="news">Все новости и заметки →</button></div>`;
  const cdh = c ? `<div class="cd" role="timer" aria-label="До дедлайна: ${c.d} дн ${c.h} ч ${c.m} мин"><div><b class="num" id="cd-d">${c.d}</b><span>дн</span></div><div><b class="num" id="cd-h">${c.h}</b><span>ч</span></div><div><b class="num" id="cd-m">${c.m}</b><span>мин</span></div></div>` : '<div class="cd"><div><b>Дедлайн прошёл</b></div></div>';
  const stale = Date.now() - new Date(F.meta.generated) > 864e5;
  const fresh = `<p class="fresh${stale ? ' old' : ''}">${stale ? '<span class="fi">' + T_WARN('td-i xs') + '</span>Данные устарели · ' : 'Данные от '}${esc(fmtD(F.meta.generated))}</p>`;
  const GI = {
    coin: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="6.5" rx="7" ry="3" fill="currentColor"/><path d="M5 10.2c0 1.7 3.1 3 7 3s7-1.3 7-3v3.3c0 1.7-3.1 3-7 3s-7-1.3-7-3z" fill="currentColor" fill-opacity=".8"/><path d="M5 15.6c0 1.7 3.1 3 7 3s7-1.3 7-3v2.9c0 1.7-3.1 3-7 3s-7-1.3-7-3z" fill="currentColor" fill-opacity=".6"/></svg>',
    swap: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h13M14 4.5 17.5 8 14 11.5M20 16H7M10 12.5 6.5 16 10 19.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    bars: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="12.5" width="4.4" height="8" rx="1.3" fill="currentColor" fill-opacity=".7"/><rect x="9.8" y="8" width="4.4" height="12.5" rx="1.3" fill="currentColor" fill-opacity=".85"/><rect x="16.1" y="3.5" width="4.4" height="17" rx="1.3" fill="currentColor"/></svg>',
    shirt: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 3 3 6l2 4.2 3-1.2V21h8V9l3 1.2L21 6l-5.5-3a3.6 3.6 0 0 1-7 0z" fill="currentColor"/></svg>',
    chev: '<svg class="hc" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>' };
  const hero = `<div class="hero"><div class="h-top"><span class="tpill">Тур ${F.meta.gw_next}</span></div>
    <div class="h-lbl">${c ? 'До дедлайна' : 'Дедлайн тура ' + F.meta.gw_next}</div>${cdh}<div class="h-dl">${esc(dlText())}</div>
    <div class="hst"><div>${GI.coin}<p><b class="num">${pr(F.me.bank)}</b><span>банк</span></p></div><div class="noi"><p><b class="num">${F.me.ft}</b><span>свободных трансферов</span></p></div><div>${GI.bars}<p><b class="num">${pr(F.me.value)}</b><span>стоимость состава</span></p></div></div>
    <div class="h-cta"><button class="hb p" data-go="squad"><span>Состав на тур</span>${GI.chev}</button><button class="hb g" data-go="moves"><span>Ходы</span>${GI.chev}</button></div></div>`;
  /* порядок зависит от состояния: до дедлайна — действия, дедлайн прошёл — ход тура */
  const body = c ? `${hero}${todo(al)}${F.live.state === 'live' ? liveCard : ''}${verdict}` : `${F.live.state === 'live' ? liveCard : ''}${hero}${verdict}`;
  return `${lg('Привет, <span class="gn">Женя</span>', esc(F.me.team) + ' · общий ранг ' + (F.me.rank / 1e6).toFixed(2) + ' млн')}${body}${fresh}`;
}

/* ---------- Состав ---------- */
function squad() {
  const cl = F.claude, xi = cl.xi.map(P), by = pos => xi.filter(p => p.pos === pos);
  const rows = ['FWD', 'MID', 'DEF', 'GK'].map(pos => by(pos));
  const card = p => { const f = (p.fix || [])[0], isC = p.id === cl.captain, isV = p.id === cl.vice;
    return `<div class="pc" data-pid="${p.id}">${cl.notes[p.id] ? `<span class="nt" title="Есть заметка Claude">${IC.spark}</span>` : ''}${isC ? '<span class="badge">C</span>' : isV ? '<span class="badge v">V</span>' : ''}${av(p, 46, { pid: false })}<div class="nmx"><b>${esc(p.name.replace(/^[A-Z]\./, ''))}</b><span>${f ? esc(f.opp) + ' ' + (f.h ? '(Д)' : '(Г)') : '—'} · <i>${f1(p.xp1)}</i></span></div></div>`; };
  const tot = xi.reduce((s, p) => s + (p.xp1 || 0), 0) + (P(cl.captain).xp1 || 0);
  const bench = cl.bench.map((id, i) => { const p = P(id); return `<div class="bn" data-pid="${id}"><span class="o">${i + 1}</span>${av(p, 38, { pid: false })}<b>${esc(p.name.replace(/^[A-Z]\./, ''))}</b>${fx((p.fix || [])[0])}</div>`; }).join('');
  return `${lg('Состав <span>GW' + cl.gw + '</span>', 'обновлено ' + esc(cl.updated.slice(5).split('-').reverse().join('.')))}
  <div class="kpis"><div><b class="num">${esc(cl.formation)}</b><span>схема</span></div><div><b class="num">${tot.toFixed(1)}</b><span>ожид. очки</span></div><div><b>${esc(P(cl.captain).name)}</b><span>капитан ×2</span></div></div>
  <div class="pitch"><span class="box t"></span><span class="box b"></span>${rows.map(r => `<div class="pl">${r.map(card).join('')}</div>`).join('')}</div>
  ${sh('Скамейка', 'автозамена по номерам 1→4')}<div class="bench">${bench}</div>
  <button class="lnk" data-go="news"><span class="spark">${IC.spark}</span><span class="lt"><b>Заметки Claude по игрокам</b><span>${Object.keys(cl.notes).length} заметок · игроки с заметкой отмечены на поле</span></span>${'<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'}</button>`;
}

/* ---------- Ходы ---------- */
const moreRows = (arr, f, n = 3) => arr.slice(0, n).map(f).join('') + (arr.length > n ? `<details class="more-d"><summary class="more2">Ещё ${arr.length - n}<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></summary>${arr.slice(n).map(f).join('')}</details>` : '');
const fold = (t, sub, body) => `<details class="fold"><summary>${t}<span>${sub}</span></summary><div class="fb">${body}</div></details>`;
function movesNow() {
  const pl = F.plan;
  const mv = ([o, i]) => { const a = P(o), b = P(i), d = (b.price || 0) - (a.price || 0);
    return `<div class="mv"><div class="who out" data-pid="${o}">${av(a, 44, { pid: false })}<div style="min-width:0"><b>${esc(a.name)}</b><span>${esc(a.tname)} · ${pr(a.price || 0)}</span></div></div><span class="ar">${IC.arrow}</span><div class="who" data-pid="${i}">${av(b, 44, { pid: false })}<div style="min-width:0"><b>${esc(b.name)}</b><span>${esc(b.tname)} · ${pr(b.price || 0)} <span style="color:${d > 0 ? 'var(--bad)' : 'var(--ok)'};font-weight:700">${d ? (d > 0 ? '+' : '−') + (Math.abs(d) / 10).toFixed(1) : ''}</span></span></div></div></div>`; };
  const steps = pl.steps.map(s => `<div class="step"><div class="step-h"><span class="gw">GW${s.gw}</span><span class="pill ${s.hit ? 'bad' : 'ok'}">${s.hit ? 'хит −' + s.hit : 'бесплатно'}</span><span class="pill">трансферов ${s.ft_before}</span><span class="mut" style="margin-left:auto;font-size:13.5px">кап. ${esc(P(s.captain).name)}</span></div>${s.moves.length ? s.moves.map(mv).join('') : '<div class="mut" style="padding:6px 2px 8px;font-size:15px">Без трансферов — копим</div>'}</div>`).join('');
  const alts = pl.alts.slice(1).map((a, i) => `<div class="prow"><span class="rk" style="border-radius:50%">${'БВГ'[i]}</span><div class="nm"><b>${a.first.slice(0, 2).map(m => esc(P(m.out).name) + ' → ' + esc(P(m.in).name)).join(', ')}</b><span>${a.first.length} хода в первых 4 турах</span></div><div class="chg u num">+${a.gain.toFixed(1)}</div></div>`).join('');
  const sgl = F.single, best = sgl[0];
  const more = sgl.slice(1, 4).map(s => `<div class="step" style="padding-bottom:6px"><div class="step-h"><span class="pill ok num">+${s.gain.toFixed(1)} очк.</span><span class="pill ${s.hit ? 'bad' : ''}">${s.hit ? 'хит −' + s.hit : 'без хита'}</span><span class="mut" style="margin-left:auto;font-size:13.5px">банк после ${pr(s.bank_after)}</span></div>${mv([s.out, s.inn])}</div>`).join('');
  const thr = F.intercept.map(t => { const p = P(t.id); return `<div class="prow" data-pid="${t.id}">${av(p, 42, { pid: false })}<div class="nm"><b>${esc(p.name)}</b><span>Рома ${Math.round(t.who.roma * 100)}% · Стас ${Math.round(t.who.stas * 100)}% · цель на +${t.gain.toFixed(1)} очк.</span><div class="risk" style="margin-top:7px"><i style="width:${t.who.roma * 100 * 2.5}%;background:var(--roma)"></i><i style="width:${t.who.stas * 100 * 2.5}%;background:var(--stas)"></i></div></div><span class="pill ${t.risk > .2 ? 'bad' : 'warn'} num">${Math.round(t.risk * 100)}%</span></div>`; }).join('');
  const sched = F.chips.schedule.map(c => { const k = CHIPS[c.chip] || [c.chip, '']; return `<div class="chipc" style="width:160px"><img src="assets/${k[1]}.svg" alt=""><b>${k[0]}</b><span class="g num" style="font-size:22px">GW${c.gw}</span><span>+${c.gain.toFixed(1)} очк.</span></div>`; }).join('');
  const bestCard = best ? `<div class="best"><div class="vd-h"><b style="font-size:19px;letter-spacing:-.03em">Лучший ход на тур ${F.meta.gw_next}</b><span class="pill ac">по модели</span></div>
    <div style="margin:8px 0 4px">${mv([best.out, best.inn])}</div>
    <div class="chipl"><span class="pill ok num">+${best.gain.toFixed(1)} очк.</span><span class="pill ${best.hit ? 'bad' : 'ok'}">${best.hit ? 'хит −' + best.hit : 'без хита'}</span><span class="pill">банк после ${pr(best.bank_after)}</span></div>
    <p class="mut" style="font-size:14.5px;line-height:1.5;margin:12px 0 0">Модель не знает новостей. Финальное решение — после пресс-конференций.</p></div>` : '<div class="best"><b>Трансферы не нужны</b></div>';
  const D = newsData().decision;
  const decCard = D ? `<div class="best"><div class="vd-h"><b style="font-size:19px;letter-spacing:-.03em">Решение на тур ${F.meta.gw_next}</b><span class="pill ac">от Claude</span></div><div class="ban cl" style="margin-top:12px;background:transparent;padding:0">${T_OK()}<div><b>${esc(D.title)}</b><p>${esc(D.text)}</p></div></div></div>` : '';
  return `${D ? decCard : bestCard}
  ${D ? fold('Что считает модель', 'идея, не решение', bestCard.replace('class="best"', 'class="best" style="box-shadow:none;background:var(--card2)"') + (more ? '<div class="tl" style="margin-top:2px">' + more + '</div>' : '')) : fold('Ещё ходы на тур', sgl.slice(1, 4).length, more)}
  ${fold('План на ' + pl.horizon + ' туров', '+' + pl.gain.toFixed(1) + ' очк.', `<div class="hero2" style="box-shadow:none;background:var(--card2)"><div class="mut" style="font-size:14.5px">Выигрыш плана против «ничего не делать»</div><div class="gain num" style="margin-top:6px;font-size:44px">+${pl.gain.toFixed(1)}<span style="font-size:22px"> очк.</span></div><div class="leg" style="margin-top:10px"><span>База <b class="num">${pl.baseline.toFixed(0)}</b></span><span>С планом <b class="num">${pl.best_total.toFixed(0)}</b></span><span>Банк в конце <b class="num">${pr(pl.bank_end)}</b></span></div></div><div class="tl">${steps}</div>`)}
  ${fold('Запасные планы', pl.alts.length - 1, `<div style="padding:0 4px">${alts}</div>`)}
  ${fold('Фишки по расписанию', F.chips.schedule.length, `<div class="hs" style="margin:0 -14px;padding-left:14px">${sched}</div>`)}
  ${fold('Могут забрать друзья', F.intercept.length, `<div style="padding:0 4px">${thr}</div>`)}`;
}

function moves() {
  const m = ST.moves;
  const sub = m === 'scout' ? F.watch.length + ' игроков под наблюдением' : m === 'top' ? 'что делают лучшие менеджеры мира' : 'что менять на этот тур';
  return `${lg('Ходы', sub)}${seg('moves', [['plan', 'Сейчас'], ['top', 'Топ-50'], ['scout', 'Скаут']])}${m === 'scout' ? scout() : m === 'top' ? topScreen() : movesNow()}`;
}

/* ---------- Лига ---------- */
/* плитки-иконки в стиле «фишек»: скруглённый квадрат, диагональный градиент, белый знак */
const tile = (g, body, label, cls) => `<svg class="ti ${cls || ''}" viewBox="0 0 24 24"${label ? ` role="img" aria-label="${label}"` : ' aria-hidden="true"'}><rect width="24" height="24" rx="7" fill="url(#${g})"/>${body}</svg>`;
const RANKC = ['#B86E00', '#56627F', '#8F4818'];
const medal = r => tile('tg' + r, `<path d="M7.6 2.6h3.4l1.5 5.2-3.4 1.2z" fill="#fff" fill-opacity=".55"/><path d="M16.4 2.6H13l-1.5 5.2 3.4 1.2z" fill="#fff" fill-opacity=".9"/><circle cx="12" cy="14.4" r="6.6" fill="#fff"/><circle cx="12" cy="14.4" r="5.1" fill="none" stroke="${RANKC[r - 1]}" stroke-opacity=".28" stroke-width=".9"/><text x="12" y="17.6" text-anchor="middle" font-size="8.6" font-weight="800" fill="${RANKC[r - 1]}" style="font-family:inherit">${r}</text>`, r + '-е место', 'rank');
const rankN = n => tile('tgn', `<text x="12" y="16.4" text-anchor="middle" font-size="11" font-weight="800" fill="#fff" style="font-family:inherit">${n}</text>`, n + '-е место', 'rank');
const T_CAP = () => tile('tgc', `<path d="M12 2.8l1.2 2.5 2.7.3-2 1.9.5 2.7L12 9l-2.4 1.2.5-2.7-2-1.9 2.7-.3z" fill="#fff" fill-opacity=".9" transform="translate(0 -.4) scale(.85) translate(2.1 .6)"/><rect x="3.6" y="10.4" width="16.8" height="9" rx="2.6" fill="#fff"/><rect x="3.6" y="10.4" width="3.2" height="9" rx="1.6" fill="#F26B3A" fill-opacity=".25"/><text x="12.6" y="17.5" text-anchor="middle" font-size="8.4" font-weight="800" fill="#E4601F" style="font-family:inherit">C</text>`, '', 'ins');
const T_SELL = () => tile('tgs', `<rect x="4.6" y="9.2" width="3.4" height="10.6" rx="1.2" fill="#fff" fill-opacity=".38"/><rect x="10.3" y="12.6" width="3.4" height="7.2" rx="1.2" fill="#fff" fill-opacity=".38"/><rect x="16" y="15.6" width="3.4" height="4.2" rx="1.2" fill="#fff" fill-opacity=".38"/><path d="M4.6 6.4l5 3.4 3.2-2.4 5.8 5.2M18.6 9.2v3.4h-3.5" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>`, '', 'ins');
const T_MISS = () => tile('tgm', `<g transform="translate(12 12) scale(.82) translate(-12 -12)"><path d="M1.8 12C4.2 7.6 7.8 5.4 12 5.4s7.8 2.2 10.2 6.6c-2.4 4.4-6 6.6-10.2 6.6S4.2 16.4 1.8 12z" fill="#fff"/><circle cx="12" cy="12" r="3.9" fill="#6D5CF0"/><circle cx="12" cy="12" r="1.5" fill="#fff"/><circle cx="13.3" cy="10.7" r="1" fill="#fff" fill-opacity=".9"/></g>`, '', 'ins');
const SHIRT = 'M8.5 3 3 6l2 4.2 3-1.2V21h8V9l3 1.2L21 6l-5.5-3a3.6 3.6 0 0 1-7 0z';
const mgr = k => tile({ me: 'tgme', roma: 'tgr', stas: 'tgst' }[k], `<g transform="translate(12 12.4) scale(.78) translate(-12 -12)"><path d="${SHIRT}" fill="#fff"/></g><text x="12" y="15.6" text-anchor="middle" font-size="7.6" font-weight="800" fill="${{ me: '#0B7F54', roma: '#E4601F', stas: '#1F62C4' }[k]}" style="font-family:inherit">${esc((NAMES[k] || '?')[0].toUpperCase())}</text>`, esc(NAMES[k] || k), 'mgr');

function smooth(pts) {
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2, t = .18;
    d += `C${p1[0] + (p2[0] - p0[0]) * t},${p1[1] + (p2[1] - p0[1]) * t} ${p2[0] - (p3[0] - p1[0]) * t},${p2[1] - (p3[1] - p1[1]) * t} ${p2[0]},${p2[1]}`;
  }
  return d;
}
function series(k) {
  const m = F[k], live = F.live, o = {};
  m.gw_points.forEach(g => o[g.gw] = g.pts - 0);
  if (live.state === 'live' && live.managers[k]) o[live.gw] = live.managers[k].pts;
  return o;
}
function chart() {
  const W = 358, H = 200, L = 26, R = 8, T = 14, B = 22, S = { me: series('me'), roma: series('roma'), stas: series('stas') };
  const gws = Object.keys(S.me).map(Number).sort((a, b) => a - b), all = ['me', 'roma', 'stas'].flatMap(k => gws.map(g => S[k][g] || 0));
  const mx = Math.ceil(Math.max(...all) / 20) * 20, x = i => L + i * (W - L - R) / (gws.length - 1), y = v => T + (1 - v / mx) * (H - T - B);
  let g = '';
  for (let v = 0; v <= mx; v += 20) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${y(v) + 3}" text-anchor="end">${v}</text>`;
  const xs = gws.map((gw, i) => `<text x="${x(i)}" y="${H - 5}" text-anchor="middle">${gw}</text>`).join('');
  const ln = ['stas', 'roma', 'me'].map(k => { const pts = gws.map((gw, i) => [x(i), y(S[k][gw] || 0)]); const last = pts[pts.length - 1];
    return `<path d="${smooth(pts)}" fill="none" stroke="${COL[k]}" stroke-width="${k === 'me' ? 3.2 : 2.2}" stroke-linecap="round"/>${pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="${k === 'me' ? 3.4 : 2.6}" fill="var(--card)" stroke="${COL[k]}" stroke-width="2"/>`).join('')}<circle cx="${last[0]}" cy="${last[1]}" r="5.5" fill="${COL[k]}"/>`; }).join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Очки по турам">${g}${xs}${ln}</svg>`;
}
let friendTab = 'roma';
function friends() {
  const k = friendTab, fr = F.friends[k], hold = F.holdings[k].map(P), order = { GK: 0, DEF: 1, MID: 2, FWD: 3 };
  hold.sort((a, b) => order[a.pos] - order[b.pos]);
  const sellP = Object.fromEntries(fr.sells.map(s => [s.id, s.prob]));
  const left = F.race.chips_left[k] || [];
  return `<div class="seg" id="fseg"><button data-f="roma" aria-pressed="${k === 'roma'}" class="${k === 'roma' ? 'on' : ''}">Рома</button><button data-f="stas" aria-pressed="${k === 'stas'}" class="${k === 'stas' ? 'on' : ''}">Стас</button></div>
  <div class="card">
    <div class="kpis" style="grid-template-columns:repeat(3,1fr)"><div style="box-shadow:none;background:var(--card2)"><b class="num">${pr(fr.bank)}</b><span>банк</span></div><div style="box-shadow:none;background:var(--card2)"><b class="num">${fr.ft}</b><span>трансферы</span></div><div style="box-shadow:none;background:var(--card2)"><b class="num">${fr.exp_moves.toFixed(1)}</b><span>ходов ждём</span></div></div>
    <div class="chipl">${left.map(c => `<span class="pill ac">${esc(c)}</span>`).join('')}</div>
    <div style="margin-top:6px">${moreRows([...hold].sort((a, b) => (sellP[b.id] || 0) - (sellP[a.id] || 0) || (b.price || 0) - (a.price || 0)), p => `<div class="fr" data-pid="${p.id}">${av(p, 36, { pid: false })}<div><b>${esc(p.name)}</b><span>${esc(p.tname)} · ${p.pos} · ${pr(p.price || 0)}</span></div>${sellP[p.id] ? `<span class="pill warn num">продаст ${Math.round(sellP[p.id] * 100)}%</span>` : '<span></span>'}</div>`, 5)}</div></div>
  ${sh('Вероятные покупки', esc(NAMES[k]))}<div class="hs">${fr.buys.slice(0, 6).map(b => { const p = P(b.id); return `<div class="alert" style="width:200px" data-pid="${p.id}">${av(p, 42, { pid: false })}<div><b>${esc(p.name)}</b><span><span class="pill bad num" style="padding:2px 8px">${Math.round(b.prob * 100)}%</span> ${esc(p.tname)}</span></div></div>`; }).join('')}</div>`;
}

function league() {
  const T = [...F.table].sort((a, b) => b.total - a.total), top = T[0].total;
  const table = `<div class="card"><div style="margin-top:-6px">${T.map((t, i) => { const k = KEYS[t.entry], g = t.total - top; return `<div class="lrow">${i < 3 ? medal(i + 1) : rankN(i + 1)}<div class="nm"><b>${esc(NAMES[k])}</b><span>${esc(F[k].team)}</span></div><div class="pt"><b class="num">${t.total}</b><span>${g ? '−' + Math.abs(g) + ' от лидера' : 'лидер'}</span></div></div>`; }).join('')}</div></div>
  ${sh('Очки по турам')}<div class="card" style="padding:16px 12px 8px">${chart()}<div class="leg" style="padding:0 6px 8px">${['me', 'roma', 'stas'].map(k => `<span><i class="dot" style="background:${COL[k]};width:8px;height:8px"></i>${esc(NAMES[k])}</span>`).join('')}</div></div>`;
  const body = ST.league === 'rivals' ? `<div id="fr" style="display:flex;flex-direction:column;gap:14px">${friends()}</div>` : table;
  return `${lg('Лига', 'Pupa vs Run Rice Run vs U\'r möm')}${seg('league', [['table', 'Таблица'], ['rivals', 'Соперники']])}${body}`;
}

/* ---------- Топ-50 мира ---------- */
function topScreen() {
  const T = F.top, n = T.n, cp = P(T.caps[0][0]);
  const row = (id, c, kind) => { const p = P(id), w = c / T[kind === 'out' ? 'outs' : kind === 'in' ? 'ins' : 'owned'][0][1] * 100;
    const warn = kind === 'out' && mineSet.has(id), miss = kind === 'own' && !mineSet.has(id) && c / n >= .6;
    return `<div class="trow" data-pid="${id}">${av(p, 42, { pid: false })}<div class="nm"><b>${esc(p.name)}</b><span>${esc(p.tname)} · ${POS[p.pos] || p.pos} · ${pr(p.price || 0)}</span><div class="tbar"><i style="width:${Math.max(4, w)}%;background:${kind === 'out' ? 'var(--bad)' : kind === 'in' ? 'var(--ok)' : 'var(--ac)'}"></i></div></div><div class="tr-r"><b class="num">${c}<span>/${n}</span></b>${warn ? '<span class="pill warn">у тебя</span>' : miss ? '<span class="pill bad">нет у тебя</span>' : ownTag(p)}</div></div>`; };
  const lists = { in: ['Купили', T.ins, 'in'], out: ['Продали', T.outs, 'out'], own: ['Владение', T.owned, 'own'] };
  const [ttl, arr, kind] = lists[ST.top];
  const outsMine = T.outs.filter(([id]) => mineSet.has(id)), missing = T.owned.filter(([id, c]) => !mineSet.has(id) && c / n >= .6).slice(0, 3);
  const capsTot = T.caps.reduce((s, c) => s + c[1], 0);
  const ins = [
    `<div class="ins">${T_CAP()}<p><b>${esc(cp.name)}</b> — капитан у ${T.caps[0][1]} из ${n} (${Math.round(T.caps[0][1] / n * 100)}%). ${mineSet.has(cp.id) ? 'Он у тебя.' : 'У тебя его нет — играешь против поля.'}</p></div>`,
    outsMine.length ? `<div class="ins">${T_SELL()}<p>Топ продаёт твоих: ${outsMine.slice(0, 3).map(([id, c]) => `<b>${esc(P(id).name)}</b> (${c})`).join(', ')}.</p></div>` : '',
    missing.length ? `<div class="ins">${T_MISS()}<p>Нет у тебя, но есть у большинства топа: ${missing.map(([id, c]) => `<b>${esc(P(id).name)}</b> (${Math.round(c / n * 100)}%)`).join(', ')}. Риск провала в рейтинге, если они выстрелят.</p></div>` : '',
  ].join('');
  const chp = Object.entries(T.chips || {}).map(([k, v]) => `${(CHIPS[k] || [k])[0]}: ${v}`).join(' · ');
  return `<div class="card"><div class="vd-h"><b style="font-size:19px;letter-spacing:-.03em">Что делает топ-${n} мира</b><span class="mut" style="font-size:14.5px">${esc(fmtD(F.meta.generated))}</span></div>
    <div class="insl">${ins}</div><p class="mut" style="font-size:13.5px;margin:12px 0 0;line-height:1.45">Выводы считаются по составам топа этого тура. Это ориентир, а не совет.</p>${chp ? `<div class="mut" style="font-size:14.5px;margin-top:10px">Фишки в этом туре — ${esc(chp)}</div>` : ''}</div>
  ${seg('top', [['in', 'Пришло'], ['out', 'Ушло'], ['own', 'Владение']])}
  <div class="card" style="padding:6px 16px"><div class="mut" style="font-size:14.5px;padding:10px 0 2px">${ttl} · игроков из ${n} менеджеров</div>${arr.map(([id, c]) => row(id, c, kind)).join('')}</div>
  ${sh('Капитаны топа', capsTot + ' из ' + n)}<div class="card" style="padding:6px 16px">${T.caps.map(([id, c]) => { const p = P(id); return `<div class="trow" data-pid="${id}">${av(p, 40, { pid: false })}<div class="nm"><b>${esc(p.name)}</b><div class="tbar"><i style="width:${c / T.caps[0][1] * 100}%;background:var(--ac)"></i></div></div><div class="tr-r"><b class="num">${c}<span>/${n}</span></b></div></div>`; }).join('')}</div>`;
}

/* ---------- Новости: простая сводка из news.json (позже — raw-ссылка на GitHub) ---------- */
const NEWS_URL = (window.FPL_REMOTE ? FPL_REMOTE.base : '') + 'news.json';
let NEWS = null, newsErr = false, newsLoading = true;
function newsData() {
  if (NEWS) return NEWS;
  const cl = F.claude;
  return { updated: cl.updated, summary: cl.status, tags: cl.tags, items: Object.entries(cl.notes).map(([id, t]) => ({ date: cl.updated, pid: +id, title: P(+id).name, text: t })) };
}
function fetchNews(u) { return fetch(u + (u.includes('?') ? '&' : '?') + 't=' + Date.now(), { cache: 'no-store' }).then(r => { if (!r.ok) throw 0; return r.json(); }); }
function loadNews() {
  fetchNews(NEWS_URL).catch(() => fetchNews('news.json'))
    .then(j => { NEWS = j; newsErr = false; newsLoading = false; render(cur); })
    .catch(() => { newsErr = true; newsLoading = false; if (cur === 'news') render('news'); });
}
const dmy = iso => String(iso || '').slice(5, 10).split('-').reverse().join('.');
function news() {
  const N = newsData(), by = {};
  (N.items || []).forEach(it => { (by[it.date || N.updated] = by[it.date || N.updated] || []).push(it); });
  const days = Object.keys(by).sort().reverse();
  const row = it => { const p = it.pid ? P(it.pid) : null; return `<div class="note"${p ? ` data-pid="${p.id}"` : ''}>${p ? av(p, 36, { pid: false }) : `<span class="nic n" style="width:36px;height:36px;flex:none;border-radius:50%">${IC.spark}</span>`}<div><b>${esc(it.title || (p && p.name) || '')}</b><p>${esc(it.text)}</p></div></div>`; };
  return `${lg('Новости', 'обновлено ' + esc(dmy(N.updated)))}
  <div class="card"><div class="vd-h"><b style="font-size:19px;letter-spacing:-.03em;display:flex;gap:8px;align-items:center"><span class="spark">${IC.spark}</span>Сводка Claude</b><span class="pill ac">${esc(dmy(N.updated))}</span></div>
    <p class="sum open" style="margin-top:12px">${esc(N.summary || '')}</p></div>
  ${pricesBlock()}
  ${newsLoading && !NEWS ? '<div class="skel"></div><div class="skel"></div>' : days.map(d => `${days.length > 1 ? sh(d === N.updated ? 'Последнее' : dmy(d), by[d].length) : sh('Заметки Claude', by[d].length)}<div class="card" style="padding:6px 18px">${moreRows(by[d], row, 4)}</div>`).join('')}
  ${newsErr && !NEWS ? '<p class="mut" style="font-size:14.5px;padding:0 6px;margin:0">Не удалось загрузить свежую сводку — показана последняя сохранённая.</p>' : ''}`;
}
const newsMineCount = () => 0;

/* ---------- Скаут ---------- */
let scoutF = 'all';
const mine = mineSet;
function scout() {
  const W = F.watch.filter(w => scoutF === 'all' || (scoutF === 'p1' ? w.prio === 1 : w.prio > 1));
  const cards = W.map(w => { const p = P(w.id), tk = p.taken_by, ch = p.chance;
    const own = mine.has(w.id) ? '<span class="pill ac">у тебя</span>' : tk ? `<span class="pill bad">занят: ${esc(NAMES[tk] || tk)}</span>` : '<span class="pill ok">свободен</span>';
    const st = p.status && p.status !== 'a' ? `<span class="pill ${ch != null && ch <= 50 ? 'bad' : 'warn'}">${ch != null ? ch + '% сыграет' : 'под вопросом'}</span>` : '';
    return `<details class="sc"><summary><div class="sc-h">${av(p, 48, { pid: false })}<div class="nm"><b>${esc(p.name)}</b><span>${esc(p.tname)} · ${POS[p.pos] || p.pos} · ${pr(p.price || 0)}</span><div class="chipl">${own}${st}</div></div><span class="pill ${w.prio === 1 ? 'ac' : ''}">P${w.prio}</span></div></summary>
      <div class="scb"><div class="mini"><div><b class="num">${pr(p.price || 0)}</b><span>цена</span></div><div><b class="num">${f1(p.form)}</b><span>форма</span></div><div><b class="num">${f1(p.xp5)}</b><span>ожид. очки, 5 туров</span></div><div><b class="num">${p.own != null ? p.own + '%' : '—'}</b><span>владение</span></div></div>
      ${statusBan(p, true)}
      <p>${esc(w.note)}</p>${w.trigger ? `<div class="trg"><b>План:</b> ${esc(w.trigger)}</div>` : ''}
      <button class="btn s" data-pid="${w.id}" style="flex:none;height:48px;width:100%">Карточка игрока</button></div></details>`; }).join('');
  return `<div class="seg" id="sseg"><button data-s="all" aria-pressed="${scoutF === 'all'}" class="${scoutF === 'all' ? 'on' : ''}">Все</button><button data-s="p1" aria-pressed="${scoutF === 'p1'}" class="${scoutF === 'p1' ? 'on' : ''}">P1</button><button data-s="p2" aria-pressed="${scoutF === 'p2'}" class="${scoutF === 'p2' ? 'on' : ''}">P2 и ниже</button></div>
  <div style="display:flex;flex-direction:column;gap:10px" id="sc">${cards || '<div class="empty">Пусто</div>'}</div>`;
}

/* ---------- Стандарты: пенальти, штрафные, угловые ---------- */
const T_PEN = (cls) => tile('tgc', '<circle cx="12" cy="12" r="7.4" fill="#fff"/><path d="M12 8.2l3 2.2-1.1 3.5h-3.8L9 10.4z" fill="#F26B3A"/>', '', cls || 'td-i');
const T_FK = (cls) => tile('tgb', '<path d="M4.5 17.5c3.2-9 9.6-11.2 15-7.2" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><circle cx="17.4" cy="14.4" r="2.6" fill="#fff"/>', '', cls || 'td-i');
const T_COR = (cls) => tile('tgg', '<path d="M7 20V5.2" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><path d="M7 5.6l10 2.8-10 3.2z" fill="#fff"/>', '', cls || 'td-i');
const ORD = ['', '1-й', '2-й', '3-й', '4-й', '5-й', '6-й', '7-й', '8-й', '9-й'];
function spBlock(p) {
  const sp = p.sp || ((window.FPL_LOCAL && FPL_LOCAL.players[p.id]) || {}).sp || {}, items = [['pen', T_PEN, 'Пенальти'], ['fk', T_FK, 'Штрафные'], ['cor', T_COR, 'Угловые']].filter(x => sp[x[0]]);
  if (!items.length) return '';
  return `<div class="card"><div class="vd-h"><b style="font-size:18px;letter-spacing:-.03em">Стандарты</b><span class="mut" style="font-size:14px">очередь исполнителей</span></div><div class="spl">${items.map(([k, ic, t]) => `<div class="spi${sp[k] === 1 ? ' first' : ''}">${ic('td-i')}<b>${ORD[sp[k]] || sp[k] + '-й'}</b><span>${t}</span></div>`).join('')}</div></div>`;
}

/* ---------- Шторка игрока ---------- */
function sheet(id) {
  const p = P(id), cl = F.claude.notes[id];
  if (p.min) return `<div class="ph-h">${av(p, 76, { pid: false })}<div><h2>${esc(p.name)}</h2><p>${esc(p.tname)} · ${POS[p.pos] || ''} · ${pr(p.price)}</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div><div class="empty">Подробной карточки для этого игрока нет в прототипе.</div>`;
  const ser = (p.series || []).slice(-7), mx = Math.max(8, ...ser.map(s => s.pts));
  const news = statusBan(p);
  const claude = cl ? ban('cl', T_SPARK(), 'Claude', esc(cl)) : '';
  const taken = p.taken_by ? ban('lk', T_LOCK(p.taken_by), 'Занят: ' + esc(NAMES[p.taken_by] || p.taken_by), 'Игрок есть у соперника — купить его нельзя.') : '';
  return `<div class="ph-h">${av(p, 76, { pid: false })}<div style="min-width:0"><h2>${esc(p.full || p.name)}</h2><p>${esc(p.tname)} · ${POS[p.pos] || p.pos}</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div>
  ${news}${taken}${claude}
  <div class="kv"><div class="ac"><b class="num">${pr(p.price)}</b><span>цена${p.price_start && p.price !== p.price_start ? ' (' + (p.price > p.price_start ? '+' : '−') + (Math.abs(p.price - p.price_start) / 10).toFixed(1) + ')' : ''}</span></div><div><b class="num">${f1(p.form)}</b><span>форма</span></div><div><b class="num">${f1(p.ppg)}</b><span>очков за матч</span></div><div class="ac"><b class="num">${f1(p.xp1)}</b><span>ожид. очки на тур</span></div><div><b class="num">${f1(p.xp5)}</b><span>ожид. очки, 5 туров</span></div><div><b class="num">${p.own != null ? p.own + '%' : '—'}</b><span>владение</span></div></div>
  ${spBlock(p)}
  ${ser.length ? `<div class="card"><div class="vd-h"><b style="font-size:18px;letter-spacing:-.03em">Очки по турам</b><span class="mut" style="font-size:13.5px">${p.pts} за сезон</span></div><div class="bars">${ser.map((s, i) => `<div><b class="num">${s.pts}</b><i style="height:${Math.max(3, s.pts / mx * 70)}px;animation-delay:${i * 45}ms;${s.min < 60 ? 'opacity:.45' : ''}"></i><span>${s.gw}</span></div>`).join('')}</div></div>` : ''}
  ${(p.fix || []).length ? `<div class="card"><div class="vd-h"><b style="font-size:18px;letter-spacing:-.03em">Календарь</b><span class="mut" style="font-size:14px">сложность · ожид. очки</span></div><div class="fxl" style="margin-top:12px">${p.fix.map((f, i) => `<div class="fc ${fc(f.fdr)}" role="group" aria-label="GW${f.gw}: ${esc(f.opp)}, ${f.h ? 'дома' : 'в гостях'}, сложность ${f.fdr} из 5, ожидаемые очки ${p.xpg && p.xpg[i] != null ? f1(p.xpg[i]) : 'нет данных'}"><span class="gwl">GW${f.gw}</span><b class="op">${esc(f.opp)}</b><span class="ha">${f.h ? '(Д)' : '(Г)'}</span><i class="dd">${Math.round(f.fdr)}</i><u class="xv num">${p.xpg && p.xpg[i] != null ? f1(p.xpg[i]) : '—'}</u></div>`).join('')}</div>
    <div class="fleg" aria-hidden="true">${[1, 2, 3, 4, 5].map(n => `<span><i class="fc f${n}"></i>${n}</span>`).join('')}<em>1 — легко, 5 — тяжело</em></div></div>` : ''}
  <div class="kv"><div><b class="num">${p.goals ?? '—'}+${p.assists ?? '—'}</b><span>голы + передачи</span></div><div><b class="num">${f1(p.xgi90)}</b><span>голы+пасы (ожид.) / 90</span></div><div><b class="num">${f1(p.dc90)}</b><span>защитные действия / 90</span></div></div>`;
}

/* ---------- Настройки ---------- */
const SK = 'fpl-settings';
const DEF = () => ({ me: { id: String((F.defaults.entries.me) || ''), name: NAMES.me || '' }, leagueId: String(F.defaults.league_id || ''), rivals: [{ name: NAMES.roma, id: String(F.defaults.entries.roma || '') }, { name: NAMES.stas, id: String(F.defaults.entries.stas || '') }], topN: F.defaults.top_n || 50, notif: { deadline: true, injury: true, price: false, rivals: true, claude: true }, theme: 'system' });
function loadSet() { let v = DEF(); try { const x = JSON.parse(localStorage.getItem(SK)); if (x && x.me) v = Object.assign(v, x); } catch (e) {} try { const t = localStorage.getItem('fpl-theme'); v.theme = t === 'light' || t === 'dark' ? t : 'system'; } catch (e) {} return v; }
const NOTIF = [['deadline', 'Дедлайн', 'за сутки и за 2 часа'], ['injury', 'Травмы и возвраты', 'мои игроки и скаут'], ['price', 'Изменения цен', 'мои и скаут-лист'], ['rivals', 'Ходы соперников', 'после смены составов'], ['claude', 'Новости Claude', 'вердикт и заметки']];
function setHtml(v, err) {
  err = err || {};
  const fld = (id, lbl, val, extra) => `<label class="fld"><span>${lbl}</span><input id="${id}" value="${esc(val)}" ${extra || ''} ${err[id] ? 'aria-invalid="true" aria-describedby="e-' + id + '"' : ''}>${err[id] ? `<em class="err" id="e-${id}">${err[id]}</em>` : ''}</label>`;
  return `<div class="ph-h"><div><h2>Настройки</h2><p>Аккаунты, лига, что отслеживать</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div>
  <form id="setf" novalidate>
  <div class="card sg"><h3>Мой аккаунт</h3>${fld('f-me-name', 'Имя', v.me.name, 'autocomplete="off"')}${fld('f-me-id', 'Мой ID в FPL', v.me.id, 'inputmode="numeric" autocomplete="off"')}<p class="hint">ID виден в адресе: fantasy.premierleague.com/entry/<b>ID</b>/event/…</p></div>
  <div class="card sg"><h3>Лига</h3>${fld('f-league', 'ID лиги', v.leagueId, 'inputmode="numeric" autocomplete="off"')}</div>
  <div class="card sg"><h3>Соперники <span class="mut">${v.rivals.length} из 5</span></h3>
    ${v.rivals.map((r, i) => `<div class="rv"><div class="rvh"><i class="dot" style="background:${['var(--roma)', 'var(--stas)', '#C9A227', '#2E8BC0', '#C0508A'][i]}"></i><b>Соперник ${i + 1}</b><button type="button" class="rm" data-act="del" data-i="${i}" aria-label="Удалить соперника ${i + 1}">${IC.x}</button></div>${fld('f-rn-' + i, 'Имя', r.name, 'autocomplete="off"')}${fld('f-ri-' + i, 'ID менеджера', r.id, 'inputmode="numeric" autocomplete="off"')}</div>`).join('')}
    ${v.rivals.length < 5 ? '<button type="button" class="btn s add" data-act="add"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg> Добавить соперника</button>' : ''}</div>
  <div class="card sg"><h3>Топ мира</h3><p class="hint" style="margin:0 0 10px">Чьи составы разбирать для экрана «Топ-50»</p><div class="seg" role="group">${[10, 30, 50].map(n => `<button type="button" data-act="topn" data-v="${n}" aria-pressed="${v.topN === n}" class="${v.topN === n ? 'on' : ''}">Топ-${n}</button>`).join('')}</div></div>
  <div class="card sg"><h3>Что отслеживать</h3>${NOTIF.map(([k, t, d]) => `<div class="swr">${({ deadline: T_CLOCK, injury: T_PLUS, price: T_PRICE, rivals: T_TRADE, claude: T_SPARK })[k]()}<div><b>${t}</b><span>${d}</span></div><button type="button" class="sw ${v.notif[k] ? 'on' : ''}" role="switch" aria-checked="${!!v.notif[k]}" aria-label="${t}" data-act="sw" data-k="${k}"><i></i></button></div>`).join('')}</div>
  <div class="card sg"><h3>Справка</h3><button type="button" class="btn s" data-act="demo" style="flex:none;height:48px;width:100%;margin-bottom:8px">Показать пример уведомления</button><button type="button" class="btn s" data-act="glossary" style="flex:none;height:48px;width:100%;margin-bottom:8px">Справка по терминам</button><button type="button" class="btn s" data-act="whatsnew" style="flex:none;height:48px;width:100%">Что нового</button><button type="button" class="btn s" data-act="upd-check" style="flex:none;height:48px;width:100%;margin-top:8px">Проверить обновления</button><p class="hint" style="text-align:center;margin-top:10px">Версия ${esc(APPVER || (CHANGELOG && CHANGELOG.versions[0].version) || '')}</p></div>
  <div class="card sg"><h3>Оформление</h3><div class="seg" role="group">${[['system', 'Система'], ['light', 'Светлая'], ['dark', 'Тёмная']].map(([t, n]) => `<button type="button" data-act="theme" data-v="${t}" aria-pressed="${v.theme === t}" class="${v.theme === t ? 'on' : ''}">${n}</button>`).join('')}</div></div>
  <button type="submit" class="btn p" style="flex:none;height:52px;width:100%">Сохранить</button>
  <button type="button" class="btn s" data-act="reset" style="flex:none;height:48px;width:100%">Сбросить к умолчаниям</button>
  <p class="hint" style="text-align:center">Прототип: настройки хранятся на этом устройстве. Загрузка данных по ID заработает в версии приложения.</p></form>`;
}
function readSet() {
  const g = id => ($('#' + id) || { value: '' }).value.trim(), cur = loadSet(), v = JSON.parse(JSON.stringify(cur));
  v.me = { name: g('f-me-name'), id: g('f-me-id') }; v.leagueId = g('f-league');
  const n = $$('.rv').length; v.rivals = []; for (let i = 0; i < n; i++) v.rivals.push({ name: g('f-rn-' + i), id: g('f-ri-' + i) });
  v.topN = +(($('[data-act=topn][aria-pressed=true]') || {}).dataset || {}).v || cur.topN;
  $$('.sw').forEach(b => { v.notif[b.dataset.k] = b.getAttribute('aria-checked') === 'true'; });
  v.theme = (($('[data-act=theme][aria-pressed=true]') || {}).dataset || {}).v || 'system';
  return v;
}
function validate(v) {
  const e = {}, ok = x => /^\d{1,10}$/.test(x);
  if (!ok(v.me.id)) e['f-me-id'] = 'ID — только цифры'; if (!ok(v.leagueId)) e['f-league'] = 'ID — только цифры';
  const ids = new Set([v.me.id]);
  v.rivals.forEach((r, i) => { if (!r.name) e['f-rn-' + i] = 'Укажи имя'; if (!ok(r.id)) e['f-ri-' + i] = 'ID — только цифры'; else if (ids.has(r.id)) e['f-ri-' + i] = 'Этот ID уже есть'; ids.add(r.id); });
  return e;
}
function showSet(v, err) { const sb = $('#sb'), y = sb.scrollTop; sb.innerHTML = setHtml(v, err); sb.scrollTop = y; const bad = $('[aria-invalid=true]'); if (bad) bad.focus(); }
function openSettings() { openSheetHtml(setHtml(loadSet()), 'Настройки'); }
function toast(t) { const el = $('#toast'); el.textContent = t; el.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove('on'), 2200); }
function settingsClick(e) {
  const b = e.target.closest('[data-act]'); if (!b) return false;
  const a = b.dataset.act, v = readSet();
  if (a === 'add') { v.rivals.push({ name: '', id: '' }); showSet(v); $('#f-rn-' + (v.rivals.length - 1)).focus(); }
  else if (a === 'del') { v.rivals.splice(+b.dataset.i, 1); showSet(v); }
  else if (a === 'topn') { v.topN = +b.dataset.v; showSet(v); }
  else if (a === 'theme') { v.theme = b.dataset.v; applyTheme(v.theme, false); showSet(v); }
  else if (a === 'sw') { v.notif[b.dataset.k] = !v.notif[b.dataset.k]; showSet(v); $('[data-act=sw][data-k=' + b.dataset.k + ']').focus(); }
  else if (a === 'demo') { closeSheet(); setTimeout(demoNotif, 450); }
  else if (a === 'glossary') { openGlossary(); }
  else if (a === 'whatsnew') { openWhatsNew(); }
  else if (a === 'whatsnew-ok') { closeSheet(); }
  else if (a === 'upd-check') { checkUpdate(true); }
  else if (a === 'upd-go') { startUpdate(); }
  else if (a === 'upd-later') { try { localStorage.setItem('fpl-upd-snooze', JSON.stringify({ v: UPD && UPD.version, ts: Date.now() })); } catch (x) {} closeSheet(); }
  else if (a === 'welcome-ok') { try { localStorage.setItem('fpl-seen', '1'); } catch (x) {} closeSheet(); }
  else if (a === 'reset') { const d = DEF(); try { localStorage.removeItem(SK); } catch (x) {} applyTheme('system', true); showSet(d); toast('Сброшено'); }
  return true;
}

/* имена из настроек (если ID совпадают с исходными) */
(function () { try { const v = loadSet(), d = F.defaults.entries; if (v.me.name) NAMES.me = v.me.name; (v.rivals || []).forEach(r => { if (String(r.id) === String(d.roma) && r.name) NAMES.roma = r.name; if (String(r.id) === String(d.stas) && r.name) NAMES.stas = r.name; }); } catch (e) {} })();

/* ---------- Справка и приветствие ---------- */
const GLOS = [['Банк', 'деньги на трансферы, которые остались после покупок.'], ['Трансферы', 'бесплатные замены игроков на этот тур. Лишние стоят −4 очка (хит).'], ['Хит', 'штраф −4 очка за каждый трансфер сверх бесплатных.'], ['Капитан ×2', 'его очки удваиваются. Вице-капитан заменяет, если капитан не сыграл.'], ['Ожидаемые очки', 'прогноз модели на тур. Это оценка, не новости.'], ['Сложность 1–5', 'цвет матча: 1 — лёгкий соперник, 5 — очень сложный.'], ['Автозамена', 'если стартовый не сыграл, на его место входит игрок скамейки по порядку 1→4.'], ['Фишки', 'Wildcard, Free Hit, Bench Boost и Triple Captain: разовые усиления. Доступность по правилам сезона.'], ['«У тебя / у Ромы»', 'в лиге игроки не повторяются: если игрок у соперника, купить его нельзя.']];
function openGlossary() { openSheetHtml(`<div class="ph-h"><div><h2>Справка</h2><p>Термины простыми словами</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div><div class="card" style="padding:6px 18px">${GLOS.map(([t, d]) => `<div class="gl"><b>${esc(t)}</b><span>${esc(d)}</span></div>`).join('')}</div>`, 'Справка'); }
/* ---------- Что нового ---------- */
let CHANGELOG = null;
const T_NEW = () => T_SPARK();
const T_UP = () => tile('tgb', '<path d="M12 19.2V6M6.4 11.4 12 5.8l5.6 5.6" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>', '', 'td-i');
const T_FIX = () => tile('tgo', '<path d="M15.2 4.6a4.6 4.6 0 0 0-5.2 6.2L4.6 16.2a2 2 0 0 0 2.8 2.8l5.4-5.4a4.6 4.6 0 0 0 6.2-5.2l-3 3-2.4-.6-.6-2.4z" fill="#fff"/>', '', 'td-i');
const WN = { new: ['Новое', T_NEW, 'var(--ac)'], improve: ['Улучшено', T_UP, 'var(--stas)'], fix: ['Исправлено', T_FIX, 'var(--warn)'] };
const fmtDay = iso => { try { return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(iso)); } catch (e) { return iso; } };
function verBlock(v) {
  return ['new', 'improve', 'fix'].map(t => { const it = (v.items || []).filter(x => x.type === t); if (!it.length) return ''; const [lbl, ic, col] = WN[t];
    return `<div class="wn-h" style="color:${col}">${lbl}</div>${it.map(x => `<div class="td wn" style="cursor:default">${ic()}<div class="tdt"><b>${esc(x.title)}</b><span>${esc(x.text)}</span></div></div>`).join('')}`; }).join('');
}
function openWhatsNew() {
  if (!CHANGELOG || !CHANGELOG.versions || !CHANGELOG.versions.length) { toast('История обновлений пока недоступна'); return; }
  const V = CHANGELOG.versions, cur = V[0];
  try { localStorage.setItem('fpl-ver', cur.version); } catch (e) {}
  openSheetHtml(`<div class="ph-h"><div><h2>Что нового</h2><p>Версия ${esc(cur.version)} · ${esc(fmtDay(cur.date))}</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div>
  ${cur.title ? `<p class="wn-t">${esc(cur.title)}</p>` : ''}
  <div class="card" style="padding:4px 16px 8px">${verBlock(cur)}</div>
  ${V.slice(1).map(v => fold('Версия ' + esc(v.version), esc(fmtDay(v.date)), `<div style="padding:0 4px">${verBlock(v)}</div>`)).join('')}
  <button class="btn p" data-act="whatsnew-ok" style="flex:none;height:54px;width:100%">Понятно</button>`, 'Что нового');
}
function loadChangelog() {
  fetch('changelog.json?t=' + Date.now(), { cache: 'no-store' }).then(r => { if (!r.ok) throw 0; return r.json(); }).then(j => {
    CHANGELOG = j; try { const latest = j.versions[0].version, seen = localStorage.getItem('fpl-ver'), first = !localStorage.getItem('fpl-seen');
      if (first) { localStorage.setItem('fpl-ver', latest); return; }
      if (seen !== latest) setTimeout(() => { if (!sheetEl.classList.contains('on')) openWhatsNew(); }, 900); } catch (e) {}
  }).catch(() => {});
}
/* ---------- Обновление приложения (APK, v1.3) ----------
   version.json в сборке — версия ЭТОГО приложения; version.json в репо данных — последняя выпущенная.
   Новее — окно «Доступно обновление» с описанием и кнопкой «Скачать» (APK качается в браузере, ставит сам пользователь). */
let APPVER = null, UPD = null;
const verNum = v => String(v || '0').split('.').map(n => parseInt(n, 10) || 0);
function verCmp(a, b) { const x = verNum(a), y = verNum(b); for (let i = 0; i < Math.max(x.length, y.length); i++) { const d = (x[i] || 0) - (y[i] || 0); if (d) return d > 0 ? 1 : -1; } return 0; }
function getJson(u) { return fetch(u, { cache: 'no-store' }).then(r => { if (!r.ok) throw 0; return r.json(); }); }
function checkUpdate(manual) {
  const base = window.FPL_REMOTE ? FPL_REMOTE.base : '';
  const bust = '?t=' + (manual ? Date.now() : Math.floor(Date.now() / 3e5));
  Promise.all([getJson('version.json?t=' + Date.now()).catch(() => null), getJson(base + 'version.json' + bust).catch(() => null)]).then(([loc, rem]) => {
    if (loc && loc.version) APPVER = loc.version;
    if (!rem || !rem.version || !APPVER) { if (manual) toast(rem ? 'Версия приложения неизвестна' : 'Не удалось проверить обновления'); return; }
    if (verCmp(rem.version, APPVER) <= 0) { if (manual) toast('У вас последняя версия ' + APPVER); return; }
    UPD = rem;
    if (!manual) { try { const sn = JSON.parse(localStorage.getItem('fpl-upd-snooze') || 'null'); if (sn && sn.v === rem.version && Date.now() - sn.ts < 864e5) return; } catch (e) {} if (sheetEl.classList.contains('on')) return; }
    openUpdate();
  });
}
function openUpdate() {
  const u = UPD; if (!u) return;
  openSheetHtml(`<div class="ph-h"><div><h2>Доступно обновление</h2><p>Версия ${esc(u.version)}${u.date ? ' · ' + esc(fmtDay(u.date)) : ''} (у вас ${esc(APPVER)})</p></div><button class="ib ph-x" data-close aria-label="Закрыть">${IC.x}</button></div>
  ${u.title ? `<p class="wn-t">${esc(u.title)}</p>` : ''}
  <div class="card" style="padding:4px 16px 8px">${verBlock(u)}</div>
  <p class="hint" style="margin:0 4px">Нажмите «Скачать»: файл загрузится в браузере. Откройте его, и Android предложит обновить приложение. Данные и настройки сохранятся. Если установка запрещена, разрешите её для браузера в настройках телефона.</p>
  <button class="btn p" data-act="upd-go" style="flex:none;height:54px;width:100%">Скачать обновление</button>
  <button class="btn s" data-act="upd-later" style="flex:none;height:48px;width:100%">Позже</button>`, 'Доступно обновление');
}
function startUpdate() { if (!UPD) return; window.location.href = UPD.apk_url || UPD.page_url; }
function openWelcome() {
  openSheetHtml(`<div class="ph-h"><div><h2>Добро пожаловать</h2><p>Помощник перед каждым дедлайном</p></div></div>
  <div class="card" style="padding:6px 16px">
    <div class="td" style="cursor:default">${T_WARN()}<div class="tdt"><b>Обзор</b><span>главный список: что сделать до дедлайна</span></div></div>
    <div class="td" style="cursor:default">${T_SPARK()}<div class="tdt"><b>Новости</b><span>заметки Claude и цены на ночь</span></div></div>
    <div class="td" style="cursor:default">${T_TRADE()}<div class="tdt"><b>Ходы</b><span>решение на тур, топ-50 мира, скаут</span></div></div>
    <div class="td" style="cursor:default">${T_CLOCK()}<div class="tdt"><b>Настройки</b><span>ваш ID, соперники, что отслеживать</span></div></div></div>
  <button class="btn p" data-act="welcome-ok" style="flex:none;height:54px;width:100%">Понятно</button>
  <button class="btn s" data-act="glossary" style="flex:none;height:48px;width:100%">Справка по терминам</button>`, 'Приветствие');
}
function demoNotif() {
  const N = newsData(), open = (N.todo || []).filter(t => t.k !== 'ok');
  let el = $('#hn'); if (!el) { el = document.createElement('div'); el.id = 'hn'; el.className = 'hn'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
  el.innerHTML = `<div class="nh2"><img src="assets/icon.svg" alt=""><b>FPL Advisor</b><span>пример</span></div><div class="nt3">${open.length ? 'Дедлайн через 2 ч. Не сделано: ' + open.length : 'Всё готово. Дедлайн через 2 ч'}</div><div class="nb3">${esc(open.map(t => t.title).slice(0, 2).join(' · ') || 'Состав и капитан на месте')}</div>`;
  el.classList.add('on'); clearTimeout(demoNotif.t); demoNotif.t = setTimeout(() => el.classList.remove('on'), 4200);
}

/* ---------- каркас, навигация, шторка ---------- */
const TABS = [['home', 'Обзор', home], ['squad', 'Состав', squad], ['moves', 'Ходы', moves], ['news', 'Новости', news], ['league', 'Лига', league]];
const TITLES = { home: 'Обзор', squad: 'Состав на тур', moves: 'Ходы', news: 'Новости', league: 'Лига' };
const nbad = [...F.claude.xi, ...F.claude.bench].map(P).filter(doubt).length, nnews = newsMineCount();
const BADGE = { squad: nbad };
$('#tabbar').innerHTML = TABS.map(t => { const n = BADGE[t[0]]; return `<button class="tab" data-tab="${t[0]}" aria-label="${t[1]}${n ? ', новых: ' + n : ''}"><svg viewBox="0 0 24 24" aria-hidden="true">${IC[t[0]]}</svg><span>${t[1]}</span>${n ? `<i class="nb" aria-hidden="true">${n}</i>` : ''}</button>`; }).join('');
const scroll = {}; let cur = 'home';
function a11y(root) { $$('[data-pid]', root).forEach(e => { e.tabIndex = 0; e.setAttribute('role', 'button'); }); }
function render(id) { const t = TABS.find(x => x[0] === id); const r = $('#s-' + id); r.innerHTML = t[2](); a11y(r); }
function go(id, push = true) {
  if (id === 'top') { ST.moves = 'top'; id = 'moves'; }
  if (id === 'scout') { ST.moves = 'scout'; id = 'moves'; }
  if (!TITLES[id]) id = 'home';
  scroll[cur] = window.scrollY; cur = id;
  $$('.scr').forEach(s => s.classList.toggle('on', s.id === 's-' + id));
  $$('.tab').forEach(t => { const on = t.dataset.tab === id; t.classList.toggle('on', on); on ? t.setAttribute('aria-current', 'page') : t.removeAttribute('aria-current'); });
  document.title = 'FPL Advisor — ' + TITLES[id];
  $('#tbt').textContent = TITLES[id];
  render(id);
  if (push) history.replaceState(null, '', '#' + id);
  window.scrollTo(0, scroll[id] || 0);
  bindSum();
}
function bindSum() { const b = $('#sumBtn'); if (b) b.onclick = () => { const s = $('#sum'); s.classList.toggle('open'); const o = s.classList.contains('open'); b.textContent = o ? 'Свернуть' : 'Читать полностью'; b.setAttribute('aria-expanded', o); }; }
document.addEventListener('click', e => {
  if (settingsClick(e)) return;
  if (e.target.closest('#settingsBtn')) return openSettings();
  const sg = e.target.closest('[data-seg]'); if (sg) { ST[sg.dataset.k] = sg.dataset.v; render(cur); const k = sg.dataset.k, v = sg.dataset.v; const nb = $('[data-seg][data-k="' + k + '"][data-v="' + v + '"]'); if (nb) nb.focus({ preventScroll: true }); return; }
  const t = e.target.closest('[data-tab]'); if (t) return go(t.dataset.tab);
  const g = e.target.closest('[data-go]'); if (g) return go(g.dataset.go);
  const f = e.target.closest('#fseg [data-f]'); if (f) { friendTab = f.dataset.f; $('#fr').innerHTML = friends(); a11y($('#fr')); const nb = $('#fseg [data-f="' + friendTab + '"]'); if (nb) nb.focus({ preventScroll: true }); return; }
  const s = e.target.closest('#sseg [data-s]'); if (s) { scoutF = s.dataset.s; render('moves'); const nb = $('#sseg [data-s="' + scoutF + '"]'); if (nb) nb.focus({ preventScroll: true }); return; }
  if (e.target.closest('[data-close]') || e.target.id === 'ov') return closeSheet();
  const p = e.target.closest('[data-pid]'); if (p) openSheet(+p.dataset.pid);
});
const sheetEl = $('#sheet');
$('#skip').addEventListener('click', e => { e.preventDefault(); $('#main').focus(); });
let lastFocus = null;
let sheetPushed = false;
function openSheet(id) { openSheetHtml(sheet(id), P(id).name); }
function openSheetHtml(html, label) { lastFocus = document.activeElement; $('#sb').innerHTML = html; sheetEl.setAttribute('aria-label', label || 'Карточка'); if (!sheetPushed) { try { history.pushState({ sh: 1 }, ''); sheetPushed = true; } catch (e) {} } $('#sb').scrollTop = 0; sheetEl.style.setProperty('--dy', '0px'); $('#ov').classList.add('on'); sheetEl.classList.add('on'); sheetEl.removeAttribute('aria-hidden'); $('#app').inert = true; document.documentElement.style.overflow = 'hidden'; setTimeout(() => ($('[data-close]', sheetEl) || sheetEl).focus(), 50); }
function closeSheet() { if (!sheetEl.classList.contains('on')) return; doClose(); if (sheetPushed) { sheetPushed = false; try { history.back(); } catch (e) {} } }
window.addEventListener('popstate', () => { sheetPushed = false; if (sheetEl.classList.contains('on')) doClose(); });
function doClose() { try { localStorage.setItem('fpl-seen', '1'); } catch (e) {} $('#ov').classList.remove('on'); sheetEl.classList.remove('on'); sheetEl.setAttribute('aria-hidden', 'true'); $('#app').inert = false; document.documentElement.style.overflow = ''; if (lastFocus && lastFocus.focus) lastFocus.focus(); }
document.addEventListener('submit', e => {
  if (e.target.id !== 'setf') return; e.preventDefault();
  const v = readSet(), er = validate(v);
  if (Object.keys(er).length) { showSet(v, er); return; }
  try { localStorage.setItem(SK, JSON.stringify(v)); } catch (x) {}
  applyTheme(v.theme, true); closeSheet(); toast('Настройки сохранены');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') return closeSheet();
  if (e.key === 'Tab' && sheetEl.classList.contains('on')) { /* ловушка фокуса внутри шторки */
    const f = $$('button,[tabindex="0"],input', sheetEl).filter(x => !x.closest('[aria-hidden="true"]'));
    if (!f.length) { e.preventDefault(); return; }
    const a = f[0], z = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === a || document.activeElement === sheetEl)) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    return;
  }
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('[role=button]')) { e.preventDefault(); e.target.click(); }
});
(function drag() {
  let y0 = null;
  const g = $('#grab');
  g.addEventListener('pointerdown', e => { y0 = e.clientY; g.setPointerCapture(e.pointerId); sheetEl.classList.add('drag'); });
  g.addEventListener('pointermove', e => { if (y0 == null) return; sheetEl.style.setProperty('--dy', Math.max(0, e.clientY - y0) + 'px'); });
  const end = e => { if (y0 == null) return; const d = e.clientY - y0; y0 = null; sheetEl.classList.remove('drag'); if (d > 110) closeSheet(); else sheetEl.style.setProperty('--dy', '0px'); };
  g.addEventListener('pointerup', end); g.addEventListener('pointercancel', end);
})();
window.addEventListener('scroll', () => $('#topbar').classList.toggle('sc', window.scrollY > 70), { passive: true });
setInterval(() => { const c = cdParts(); if (c && $('#cd-d')) { $('#cd-d').textContent = c.d; $('#cd-h').textContent = c.h; $('#cd-m').textContent = c.m; } }, 20000);
/* тема: data-theme уже выставлен в <head>; режимы system / light / dark, система отслеживается, пока не выбрано явно */
const root = document.documentElement, tcMeta = $('#tc'), mq = matchMedia('(prefers-color-scheme:dark)');
function applyTheme(mode, save) {
  const t = mode === 'system' ? (mq.matches ? 'dark' : 'light') : mode;
  root.dataset.theme = t; tcMeta.content = t === 'dark' ? '#0B1311' : '#F3F8F5';
  if (save) { try { localStorage.setItem('fpl-theme', mode); } catch (e) {} }
}
(function () { let m = null; try { m = localStorage.getItem('fpl-theme'); } catch (e) {} if (m !== 'light' && m !== 'dark') m = 'system'; applyTheme(m, false); })();
mq.addEventListener && mq.addEventListener('change', () => { let m = null; try { m = localStorage.getItem('fpl-theme'); } catch (e) {} if (m !== 'light' && m !== 'dark') applyTheme('system', false); });
/* офлайн-плашка */
const offEl = $('#offline'); offEl.innerHTML = T_OFF('td-i xs') + '<span>Нет сети — показаны сохранённые данные</span>';
const setOff = () => { offEl.hidden = navigator.onLine; };
addEventListener('online', setOff); addEventListener('offline', setOff); setOff();
/* обновление свайпом вниз у верха страницы */
function refreshAll() {
  const p = $('#ptr'); p.classList.add('on', 'spin');
  const done = () => setTimeout(() => location.reload(), 300);
  if (window.FPL_REMOTE && navigator.onLine) FPL_REMOTE.fetch(true).then(d => { if (!d) toast('Данные уже свежие'); }).catch(() => toast('Не удалось обновить — показаны сохранённые')).then(() => setTimeout(done, 900));
  else done();
}
/* фоновая проверка свежих данных: при запуске — тихая перезагрузка один раз, позже — подсказка */
function checkData() {
  if (!window.FPL_REMOTE || !navigator.onLine) return;
  FPL_REMOTE.fetch(false).then(d => {
    if (!d) return;
    let seen = false; try { seen = sessionStorage.getItem('fpl-rl'); if (!seen && performance.now() < 5000) sessionStorage.setItem('fpl-rl', '1'); } catch (e) {}
    if (!seen && performance.now() < 5000) location.reload(); else toast('Есть свежие данные — потяните вниз');
  }).catch(() => {});
}
(function () {
  let y0 = null, dy = 0; const p = $('#ptr');
  addEventListener('touchstart', e => { if (window.scrollY > 0 || sheetEl.classList.contains('on') || e.target.closest('.hs,.chs')) return; y0 = e.touches[0].clientY; dy = 0; }, { passive: true });
  addEventListener('touchmove', e => { if (y0 == null) return; dy = e.touches[0].clientY - y0; if (dy > 8) { p.classList.add('on'); p.style.transform = 'translate(-50%,' + (Math.min(dy, 120) - 56) + 'px) rotate(' + dy * 3 + 'deg)'; } }, { passive: true });
  addEventListener('touchend', () => { if (y0 == null) return; const ok = dy > 90; y0 = null; if (ok) refreshAll(); else { p.classList.remove('on'); p.style.transform = ''; } });
})();
loadNews();
checkData();
loadChangelog();
setTimeout(() => checkUpdate(false), 2500);
try { if (!localStorage.getItem('fpl-seen')) setTimeout(openWelcome, 600); } catch (e) {}
document.documentElement.style.overflow = ''; $('#app').inert = false;
go((location.hash || '#home').slice(1), false);
window.addEventListener('hashchange', () => go(location.hash.slice(1), false));
})();
