// Super RetroPie web menu: console carousel -> game list -> play (run.html). Keyboard, mouse and game pads,
// with the same moves as EmulationStation on the TV.
'use strict';
const $ = id => document.getElementById(id);
const store = {get(k) { try { return localStorage.getItem(k) } catch (e) { return null } },
               set(k, v) { try { localStorage.setItem(k, v) } catch (e) {} }};
const device = /[?&]phone\b/.test(location.search) ||                        // ?phone forces it, for checking
  (matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) < 820) ? 'phone' : 'laptop';
const phone = device === 'phone';
document.body.classList.toggle('phone', phone);
const ROWS = 17;                                   // list lines that fit, like the TV (3.6% font, 1.5 spacing)
let systems = [], sel = 0, view = 'systems', games = [], gsys = '', gsel = 0, loading = 0, tv = {}, details = {}, detailTimer = null;
let query = '';                                    // phone search

async function api(path, opts = {}) {
  opts.headers = Object.assign({'X-SRP': '1'}, opts.headers || {});
  let r;
  try { r = await fetch(path, opts) } catch (e) { throw Object.assign(new Error("Can't reach the box"), {net: true}) }
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) throw Object.assign(new Error('pin'), {pin: true});
  if (!r.ok) throw new Error(j.error === 'off' ? 'The companion is switched off on the TV (RetroPie menu › Phone Companion)' : (j.error || 'Something went wrong'));
  return j;
}
function toast(text, ms = 3500) {
  $('toast').textContent = text; $('toast').classList.remove('hide');
  clearTimeout(toast.t); toast.t = setTimeout(() => $('toast').classList.add('hide'), ms);
}
function show(v) {
  view = v;
  for (const id of ['systems', 'gamelist', 'stream', 'login']) $(id).classList.toggle('hide', id !== v);
  const hints = {
    systems: [['← →', 'console'], ['enter', 'select']],
    gamelist: [['↑ ↓', 'choose'], ['← →', 'console'], ['enter', 'play'], ['esc', 'back']],
    stream: [['← →', 'console'], ['esc', 'back']],
    login: [['enter', 'connect']]}[v];
  $('hints').innerHTML = hints.map(([k, t]) => `<span><b>${k}</b>${t}</span>`).join('');
}

// ---------- start ----------
async function start() {
  if (!window.isSecureContext && location.protocol === 'http:' && !/[?&]http\b/.test(location.search)) {
    toast('Game pads need the secure page - switching to https', 2500);
    setTimeout(() => location.replace(`https://${location.hostname}:8443/play`), 1200);
  }
  try {
    const lib = await api('/api/play/library?device=' + device);
    systems = lib.systems; tv = lib.tv || {};
    if (!systems.length) { $('sysinfo').textContent = 'No games for this device yet'; show('systems'); return }
    const last = store.get('srp-play-sys'); sel = Math.max(0, systems.findIndex(s => s.id === last));
    drawCarousel(); show('systems');
    if (store.get('srp-play-open') === '1' && systems[sel].mode === 'browser') openSystem();
  } catch (e) {
    if (e.pin) { show('login'); $('pin').focus() } else { show('systems'); $('sysinfo').textContent = e.message }
  }
}
async function login() {
  try {
    await api('/api/login', {method: 'POST', body: JSON.stringify({pin: $('pin').value})});
    $('pin-msg').textContent = ''; start();
  } catch (e) { $('pin-msg').textContent = e.pin ? 'That PIN is not right - check the TV' : e.message }
}

// ---------- system carousel ----------
function drawCarousel() {
  $('carousel').innerHTML = systems.map((s, i) =>
    `<div class="card" data-i="${i}" role="option" aria-label="${esc(s.name)}"><img src="/play/theme/card/${s.id}.png" alt="">${s.mode === 'stream' ? '<span class="tag">Stream</span>' : ''}</div>`).join('');
  $('carousel').querySelectorAll('.card').forEach(c => {
    c.onclick = () => { const i = +c.dataset.i; if (i === sel) openSystem(); else { sel = i; placeCards() } };
    c.querySelector('img').onerror = e => e.target.replaceWith(Object.assign(document.createElement('div'),
      {className: 'noart', textContent: systems[+c.dataset.i].name}));
  });
  placeCards();
}
function placeCards() {
  const n = systems.length;
  $('carousel').querySelectorAll('.card').forEach(c => {
    let d = +c.dataset.i - sel;
    if (n > (phone ? 2 : 5)) { if (d > n / 2) d -= n; if (d < -n / 2) d += n }   // wrap round, like the TV
    c.style.transform = `translateX(calc(var(--mid) + ${d} * var(--slot)))`;   // the picked card sits in the middle
    c.style.opacity = Math.abs(d) > (phone ? 2 : 3) ? 0 : 1;
    c.classList.toggle('on', d === 0); c.setAttribute('aria-selected', d === 0);
  });
  const s = systems[sel];
  $('sysinfo').textContent = s.mode === 'stream' ? 'Play by streaming the TV' : `${s.count} games available`;
  store.set('srp-play-sys', s.id);
}
function moveSystem(step) {
  if (!systems.length) return;
  sel = (sel + step + systems.length) % systems.length; placeCards();
  if (view === 'gamelist' || view === 'stream') openSystem();
}

// ---------- game list ----------
async function openSystem() {
  const s = systems[sel];
  store.set('srp-play-open', '1');
  if (s.mode === 'stream') {
    $('stream-card').src = `/play/theme/card/${s.id}.png`; $('stream-title').textContent = s.name;
    const url = `https://${location.hostname}:47990`; $('sunshine').href = url; $('sunshine').textContent = url;
    $('stream-busy').textContent = tv.busy ? 'Someone is playing on the TV right now - streaming would take over their screen.' : '';
    if (view === 'systems') nav('stream');
    show('stream'); return;
  }
  $('boxart').src = `/play/theme/card/${s.id}.png`; $('list-title').textContent = s.name;
  if (view === 'systems') nav('gamelist');
  query = ''; $('search').value = '';
  games = []; gsys = ''; drawList(); show('gamelist');
  const ticket = ++loading;                        // a quicker console change makes this answer stale
  try {
    const list = (await api('/api/play/library?sys=' + s.id)).games;
    if (ticket !== loading) return;
    games = list; gsys = s.id;
    const last = store.get('srp-play-game-' + s.id); gsel = Math.max(0, games.findIndex(g => g.id === last));
  } catch (e) { if (ticket === loading) toast(e.message); return }
  drawList(); pick();
}
function drawList() {
  if (!games.length) { $('list').innerHTML = '<li class="empty">Loading…</li>'; return }
  if (phone) return drawPhoneList();
  const top = Math.max(0, Math.min(gsel - Math.floor(ROWS / 2), games.length - ROWS));
  $('list').innerHTML = games.slice(top, top + ROWS).map((g, k) =>
    `<li data-i="${top + k}" role="option" class="${top + k === gsel ? 'on' : ''}${g.fav ? ' fav' : ''}" aria-selected="${top + k === gsel}">${esc(g.name)}</li>`).join('');
  $('list').querySelectorAll('li[data-i]').forEach(li => {
    li.onclick = () => { const i = +li.dataset.i; if (i === gsel) play(); else { gsel = i; drawList(); pick() } };
  });
}
// Phone: the whole list (filtered by the search box) in a normal scrolling page; a tap opens the details.
function drawPhoneList() {
  const q = query.trim().toLowerCase();
  const rows = [];
  games.forEach((g, i) => { if (!q || g.name.toLowerCase().includes(q)) rows.push(
    `<li data-i="${i}" role="option" class="${i === gsel ? 'on' : ''}${g.fav ? ' fav' : ''}">${esc(g.name)}</li>`) });
  $('list').innerHTML = rows.join('') || '<li class="empty">No games match that search.</li>';
  $('list').querySelectorAll('li[data-i]').forEach(li => li.onclick = () => {
    $('list').querySelector('li.on')?.classList.remove('on'); li.classList.add('on');
    gsel = +li.dataset.i; pick(); openDetail();
  });
  const on = $('list').querySelector('li.on'); if (on && !q) on.scrollIntoView({block: 'center'});
}
function openDetail() {
  $('detail-title').textContent = games[gsel]?.name || ''; $('detail').classList.add('open'); $('detail').scrollTop = 0;
  if (history.state?.v !== 'detail') nav('detail');
}
function closeDetail() { $('detail').classList.remove('open') }
// The phone's own back button / gesture walks back through console -> list -> details.
function nav(v) { if (phone) history.pushState({v}, '') }
addEventListener('popstate', () => {
  if ($('detail').classList.contains('open')) closeDetail();
  else if (view === 'gamelist' || view === 'stream') back(true);
});
function moveGame(step) {
  if (!games.length) return;
  const n = games.length;
  gsel = Math.abs(step) === 1 ? (gsel + step + n) % n : Math.max(0, Math.min(n - 1, gsel + step));
  drawList(); pick();
}
function pick() {
  const g = games[gsel]; if (!g) return;
  store.set('srp-play-game-' + gsys, g.id);
  $('md-players').textContent = g.players || '-'; $('md-year').textContent = g.year || '-';
  $('md-genre').textContent = g.genre || '-'; $('md-dev').textContent = g.developer || g.publisher || '-';
  const r = Math.round((parseFloat(g.rating) || 0) * 5);
  $('rating').innerHTML = g.rating ? Array.from({length: 5}, (_, i) => `<img src="/play/theme/star-${i < r ? 'on' : 'off'}.png" alt="">`).join('') : '';
  $('art').src = g.art ? `/api/play/art/${gsys}/${g.id}` : '';
  $('desc').textContent = details[g.id]?.desc ?? ''; $('desc').scrollTop = 0; $('note').textContent = '';
  clearTimeout(detailTimer);
  detailTimer = setTimeout(async () => {
    const sys = gsys;
    try {
      const d = details[g.id] || (details[g.id] = await api(`/api/play/game?sys=${sys}&id=${g.id}`));
      if (games[gsel] !== g) return;
      $('desc').textContent = d.desc;
      const notes = [];
      if (d.on_tv) notes.push('Open on the TV right now - your save goes to the box once it is closed there.');
      if (!d.sync) notes.push('Saves for this console stay in this browser.');
      if (d.size > 300e6) notes.push(`${(d.size / 1e9).toFixed(1)} GB - the first start takes a little while.`);
      $('note').textContent = notes.join(' ');
    } catch (e) {}
  }, 120);
}
function play() {
  const g = games[gsel]; if (!g) return;
  location.href = `/play/static/run.html?sys=${encodeURIComponent(gsys)}&id=${g.id}`;
}
function back(fromHistory) {
  if (phone && !fromHistory && history.state?.v) { history.back(); return }   // keep the phone's history in step
  closeDetail();
  if (view === 'gamelist' || view === 'stream') { store.set('srp-play-open', '0'); show('systems'); placeCards() }
}
function jump(letter) {
  const n = games.length;
  for (let k = 1; k <= n; k++) {
    const i = (gsel + k) % n;
    if (games[i].name.toUpperCase().startsWith(letter)) { gsel = i; drawList(); pick(); return }
  }
}

// ---------- input: keyboard, wheel, game pads ----------
function act(a) {
  if (view === 'login') { if (a === 'ok') login(); return }
  if (view === 'systems') ({left: () => moveSystem(-1), right: () => moveSystem(1), ok: openSystem}[a] || (() => {}))();
  else if (view === 'stream') ({left: () => moveSystem(-1), right: () => moveSystem(1), back}[a] || (() => {}))();
  else ({up: () => moveGame(-1), down: () => moveGame(1), pgup: () => moveGame(-ROWS + 1), pgdn: () => moveGame(ROWS - 1),
         left: () => moveSystem(-1), right: () => moveSystem(1), ok: play, back}[a] || (() => {}))();
}
addEventListener('keydown', e => {
  if (view === 'login') { if (e.key === 'Enter') login(); return }
  if (e.target.matches('input')) { if (e.key === 'Escape') e.target.blur(); return }   // typing in the search box
  const a = {ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Enter: 'ok', ' ': 'ok',
             Escape: 'back', Backspace: 'back', PageUp: 'pgup', PageDown: 'pgdn'}[e.key];
  if (a) { e.preventDefault(); act(a) }
  else if (e.key === 'Home' && view === 'gamelist') { gsel = 0; drawList(); pick() }
  else if (e.key === 'End' && view === 'gamelist') { gsel = games.length - 1; drawList(); pick() }
  else if (view === 'gamelist' && /^[a-z0-9]$/i.test(e.key) && !e.ctrlKey && !e.metaKey) jump(e.key.toUpperCase());
});
addEventListener('wheel', e => {
  if (phone) return;                               // the phone list scrolls by itself
  if (view === 'gamelist') moveGame(Math.sign(e.deltaY) * (Math.abs(e.deltaY) > 200 ? 5 : 1));
  else if (view === 'systems') moveSystem(Math.sign(e.deltaY || e.deltaX));
}, {passive: true});
addEventListener('contextmenu', e => { if (view !== 'systems') { e.preventDefault(); back() } });

const held = {};
function padLoop(t) {
  const pads = navigator.getGamepads ? [...navigator.getGamepads()].filter(Boolean) : [];
  const now = {};
  for (const p of pads) {
    const b = i => p.buttons[i]?.pressed, ax = p.axes || [];
    if (b(12) || ax[1] < -.6) now.up = 1; if (b(13) || ax[1] > .6) now.down = 1;
    if (b(14) || ax[0] < -.6) now.left = 1; if (b(15) || ax[0] > .6) now.right = 1;
    if (b(0) || b(9)) now.ok = 1; if (b(1)) now.back = 1;
    if (b(4) || b(6)) now.pgup = 1; if (b(5) || b(7)) now.pgdn = 1;
  }
  for (const a of ['up', 'down', 'left', 'right', 'ok', 'back', 'pgup', 'pgdn']) {
    if (!now[a]) { delete held[a]; continue }
    const repeat = !['ok', 'back'].includes(a);
    if (!held[a]) { held[a] = t + 380; act(a) }                  // first press, then repeat like the TV
    else if (repeat && t >= held[a]) { held[a] = t + 70; act(a) }
  }
  requestAnimationFrame(padLoop);
}
requestAnimationFrame(padLoop);

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])) }
// swipe the carousel (finger or mouse drag); a short tap still counts as a click on the card
let swipe = null;
$('carousel').addEventListener('pointerdown', e => { swipe = {x: e.clientX, y: e.clientY, moved: false} });
$('carousel').addEventListener('pointermove', e => {
  if (!swipe) return;
  const dx = e.clientX - swipe.x;
  if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(e.clientY - swipe.y)) {
    moveSystem(dx < 0 ? 1 : -1); swipe = {x: e.clientX, y: e.clientY, moved: true};
  }
});
addEventListener('pointerup', () => { if (swipe?.moved) setTimeout(() => swipe = null); else swipe = null });
$('carousel').addEventListener('click', e => { if (swipe?.moved) e.stopPropagation() }, true);

$('pin-go').onclick = login;
$('list-back').onclick = $('stream-back').onclick = () => back();
$('detail-close').onclick = () => history.state?.v === 'detail' ? history.back() : closeDetail();
$('play-btn').onclick = play;
$('search').addEventListener('input', () => { query = $('search').value; drawList() });
start();
