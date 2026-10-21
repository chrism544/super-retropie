// Super RetroPie web play: one game in EmulatorJS. The box's .srm is loaded when the game starts and
// sent back every 30 seconds when it changes, and on the way out. If the box can't take it (game open on
// the TV, no connection) the save stays in this browser and is sent next time.
'use strict';
const q = new URLSearchParams(location.search), sys = q.get('sys'), id = q.get('id');
const PENDING = `srp-pending-${sys}-${id}`;
const H = {'X-SRP': '1'};
let game = null, last = null, busy = null;
const pending = {get() { try { return localStorage.getItem(PENDING) === '1' } catch (e) { return false } },
                 set(v) { try { v ? localStorage.setItem(PENDING, '1') : localStorage.removeItem(PENDING) } catch (e) {} }};

function status(text) { document.getElementById('sync').textContent = text }
function fail(text) {
  const e = document.getElementById('err'); e.hidden = false;
  e.innerHTML = '<div><p></p><p><a href="/play" style="color:#40aae6">Back to the game menu</a></p></div>';
  e.querySelector('p').textContent = text;
}
const hhmm = () => new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);

function gm() { return window.EJS_emulator && EJS_emulator.gameManager }
function writeSave(data) {
  const m = gm(), path = m.getSaveFilePath();
  let dir = '';
  for (const part of path.split('/').slice(0, -1)) {
    if (!part) continue; dir += '/' + part;
    if (!m.FS.analyzePath(dir).exists) m.FS.mkdir(dir);
  }
  if (m.FS.analyzePath(path).exists) m.FS.unlink(path);
  m.FS.writeFile(path, data);
  m.loadSaveFiles();
}
async function push(leaving) {
  if (!game || !game.sync || !gm()) return;
  if (busy) return busy;
  busy = (async () => {
    let data;
    try { data = gm().getSaveFile() } catch (e) { return }
    if (!data || !data.length || same(data, last)) return;
    data = data.slice();
    try {
      const r = await fetch(`/api/play/save/${sys}/${id}`, {method: 'PUT', body: data, keepalive: leaving && data.length < 60000,
        headers: Object.assign({'Content-Type': 'application/octet-stream'}, H)});
      if (r.ok) { last = data; pending.set(false); status('Saved to the box · ' + hhmm()) }
      else { pending.set(true); status(r.status === 409 ? 'Saved here - goes to the box when the game is closed on the TV' : 'Saved here - will go to the box later') }
    } catch (e) { pending.set(true); status('Saved here - will go to the box later') }
  })();
  try { await busy } finally { busy = null }
}
async function onStart() {
  if (!game.sync) { status('Saves stay in this browser'); return }
  if (pending.get()) { await push(); }               // this browser has newer progress than the box
  else {
    try {
      const r = await fetch(`/api/play/save/${sys}/${id}`, {headers: H});
      if (r.ok) { last = new Uint8Array(await r.arrayBuffer()); writeSave(last); status('Save loaded from the box') }
      else status('No save on the box yet');
    } catch (e) { status('Could not load the save from the box') }
  }
  setInterval(() => push(), 30000);
}
async function leave() {
  status('Saving…');
  await push(true);
  location.href = '/play';
}

async function main() {
  if (!sys || !id) return fail('No game chosen.');
  let r;
  try { r = await fetch(`/api/play/game?sys=${encodeURIComponent(sys)}&id=${encodeURIComponent(id)}`, {headers: H}) }
  catch (e) { return fail("Can't reach the box.") }
  if (r.status === 401) { location.href = '/play'; return }
  game = await r.json().catch(() => ({}));
  if (!r.ok) return fail(game.error || 'That game could not be started.');
  document.title = game.name + ' · Super RetroPie';
  Object.assign(window, {
    EJS_player: '#game', EJS_core: game.core, EJS_gameUrl: game.rom, EJS_pathtodata: '/play/ejs/',
    EJS_gameName: game.name, EJS_startOnLoaded: true, EJS_color: '#116a9d', EJS_backgroundColor: '#000000',
    EJS_language: 'en-US', EJS_disableAutoLang: false, EJS_onGameStart: onStart,
    EJS_CacheLimit: matchMedia('(pointer: coarse)').matches ? 3e8 : 1.5e9,    // games kept in the browser for next time
  });
  if (game.bios) window.EJS_biosUrl = game.bios;
  const s = document.createElement('script'); s.src = '/play/ejs/loader.js';
  s.onload = () => { const t = setInterval(() => { if (window.EJS_emulator) { clearInterval(t); EJS_emulator.on('exit', leave) } }, 200) };
  document.body.appendChild(s);
}

// The core waits on sound, and a browser keeps sound off until the page gets a key or click (a game pad
// press doesn't count) - so until then the game sits on its first frames. Ask for one, then wake it.
function audio() { try { return EJS_emulator.Module.AL.currentCtx.audioCtx } catch (e) { return null } }
setInterval(() => { const a = audio(); document.getElementById('wake').hidden = !a || a.state === 'running' }, 300);
const touch = matchMedia('(pointer: coarse)').matches;
const resume = () => {
  const a = audio(); if (a && a.state !== 'running') a.resume(); document.getElementById('wake').hidden = true;
  // phone: full screen and sideways on the first tap (Android; iPhone Safari ignores both)
  if (touch && !document.fullscreenElement && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen({navigationUI: 'hide'})
      .then(() => screen.orientation?.lock?.('landscape')).catch(() => {});
  }
};
addEventListener('keydown', resume, true); addEventListener('pointerdown', resume, true);
if (touch) document.querySelector('#wake b').textContent = 'Tap to start';

document.getElementById('menu').onclick = leave;
let idle;
const wake = () => { const b = document.getElementById('bar'); b.classList.remove('idle'); clearTimeout(idle); idle = setTimeout(() => b.classList.add('idle'), 3000) };
addEventListener('mousemove', wake); addEventListener('touchstart', wake, {passive: true}); wake();
addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') push(true) });
addEventListener('pagehide', () => push(true));
main();
