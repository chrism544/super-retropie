"""Super RetroPie web play - the game menu in a laptop (later phone) browser, games run in EmulatorJS.

  Plugged into retropie-companion (same PIN, same home-network-only rule):
      import webplay; webplay.install(Handler)      # adds the /play routes and the HTTPS listener (port 8443)

  /play                      the menu (static files in /usr/local/share/super-retropie/webplay)
  /play/ejs/...              EmulatorJS 4.2.3 (retropie-webplay-setup puts it there)
  /play/theme/...            the TV theme's console cards, backgrounds and font (bluray)
  /play/ca.crt               the box's certificate authority - install once per laptop for no HTTPS warning
  /api/play/library          consoles for this device; ?sys= its games
  /api/play/art|rom|bios|save/<system>/<game id>[/<file name>]

  Saves: the game's .srm next to the ROM, the same file the TV uses. Before the laptop overwrites one,
  retropie-saves takes a snapshot (Save Manager can put it back) and the TV resume point is set aside.
"""
import glob, hashlib, hmac, ipaddress, json, os, re, socket, ssl, struct, subprocess, threading, time, zlib
import xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote, unquote

HOME = os.path.expanduser('~')
ROMS = HOME + '/RetroPie/roms'
BIOS = HOME + '/RetroPie/BIOS'
THEME = '/etc/emulationstation/themes/bluray'
STATIC = '/usr/local/share/super-retropie/webplay'
EJS = STATIC + '/emulatorjs'
CERTS = HOME + '/.config/retropie-webplay'
CUR = '/tmp/retropie-playtime-current.json'
HTTPS_PORT = int(os.environ.get('WEBPLAY_HTTPS_PORT', 8443))
SAVE_MAX = 16 * 1024 * 1024

# Which consoles run in a browser, on what, with which EmulatorJS core.
#   tier 'all' = laptop and phone, 'laptop' = laptop only. Anything else on the box is 'stream' (Moonlight).
#   sync = the browser core writes the same .srm as the box's core, so saves go both ways.
#   bios = files from ~/RetroPie/BIOS handed to the core (sent as one zip, unpacked next to the game).
#   ejs = the console name to give EmulatorJS when the core is shared (genesis_plus_gx alone reads as
#         Master System, so a Mega Drive game would get a two-button pad).
CART = ['zip', '7z']
SYSTEMS = {
    'nes':          dict(core='fceumm',          tier='all',    sync=True,  ext=['nes', 'unf', 'unif'] + CART),
    'fds':          dict(core='nestopia',        tier='all',    sync=True,  ext=['fds'] + CART, bios=['disksys.rom']),
    'snes':         dict(core='snes9x',          tier='all',    sync=True,  ext=['smc', 'sfc', 'fig', 'swc', 'bs'] + CART),
    'gb':           dict(core='gambatte',        tier='all',    sync=True,  ext=['gb'] + CART),
    'gbc':          dict(core='gambatte',        tier='all',    sync=True,  ext=['gbc', 'gb'] + CART),
    'gba':          dict(core='mgba',            tier='all',    sync=True,  ext=['gba'] + CART),
    'megadrive':    dict(core='genesis_plus_gx', ejs='segaMD', tier='all',    sync=True,  ext=['md', 'gen', 'bin', 'smd'] + CART),
    'mastersystem': dict(core='genesis_plus_gx', tier='all',    sync=True,  ext=['sms'] + CART),
    'gamegear':     dict(core='genesis_plus_gx', tier='all',    sync=True,  ext=['gg'] + CART),
    'sg-1000':      dict(core='genesis_plus_gx', tier='all',    sync=True,  ext=['sg'] + CART),
    'segacd':       dict(core='genesis_plus_gx', ejs='segaCD', tier='all',    sync=True,  ext=['chd', 'cue', 'iso', 'm3u'],
                         bios=['bios_CD_E.bin', 'bios_CD_U.bin', 'bios_CD_J.bin']),
    'sega32x':      dict(core='picodrive',       ejs='sega32x', tier='all',    sync=True,  ext=['32x'] + CART),
    'pcengine':     dict(core='mednafen_pce',    tier='all',    sync=True,  ext=['pce'] + CART),
    'atari2600':    dict(core='stella2014',      tier='all',    sync=False, ext=['a26', 'bin'] + CART),
    'atari5200':    dict(core='a5200',           tier='all',    sync=False, ext=['a52', 'bin'] + CART, bios=['5200.rom']),
    'atari7800':    dict(core='prosystem',       tier='all',    sync=True,  ext=['a78', 'bin'] + CART),
    'atarilynx':    dict(core='handy',           tier='all',    sync=False, ext=['lnx'] + CART, bios=['lynxboot.img']),
    'ngp':          dict(core='mednafen_ngp',    tier='all',    sync=True,  ext=['ngp'] + CART),
    'ngpc':         dict(core='mednafen_ngp',    tier='all',    sync=True,  ext=['ngc', 'ngpc'] + CART),
    'coleco':       dict(core='gearcoleco',      tier='all',    sync=False, ext=['col', 'rom'] + CART, bios=['colecovision.rom']),
    'zxspectrum':   dict(core='fuse',            tier='all',    sync=False, ext=['tzx', 'tap', 'z80', 'sna'] + CART),
    'amstradcpc':   dict(core='cap32',           tier='all',    sync=False, ext=['dsk', 'cdt', 'sna'] + CART),
    'arcade':       dict(core='fbneo',           tier='all',    sync=False, ext=CART, bios=['neogeo.zip']),
    'fba':          dict(core='fbneo',           tier='all',    sync=False, ext=CART, bios=['neogeo.zip']),
    'neogeo':       dict(core='fbneo',           tier='all',    sync=False, ext=CART, bios=['neogeo.zip']),
    'psx':          dict(core='pcsx_rearmed',    tier='all',    sync=True,  ext=['chd', 'cue', 'pbp', 'iso', 'img', 'm3u'],
                         bios=['scph5501.bin', 'scph5500.bin', 'scph5502.bin', 'scph1001.bin']),
    'n64':          dict(core='mupen64plus_next', tier='laptop', sync=True, ext=['z64', 'n64', 'v64'] + CART),
    'nds':          dict(core='melonds',         tier='laptop', sync=False, ext=['nds'] + CART,
                         bios=['bios7.bin', 'bios9.bin', 'firmware.bin']),
}
TIERS = {'laptop': {'all', 'laptop'}, 'phone': {'all'}}
DISC_TRACKS = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', re.I | re.M)
TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json',
         '.wasm': 'application/wasm', '.data': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.ttf': 'font/ttf', '.svg': 'image/svg+xml', '.zip': 'application/zip',
         '.crt': 'application/x-x509-ca-cert'}

COMPANION = None                                    # the companion module, set by install()

def names():
    return getattr(COMPANION, 'NAMES', {})

# ---------- library ----------
_lib, _lib_lock = {}, threading.Lock()

def gid(rel):
    return hashlib.sha1(rel.encode()).hexdigest()[:16]

def resolve(base, p):
    p = p or ''
    return os.path.normpath(os.path.join(base, p[2:]) if p.startswith('./') else os.path.join(base, p))

def inside(path, base):
    real = os.path.realpath(path)
    return real == base or real.startswith(base.rstrip('/') + '/')

def year(d):
    return d[:4] if d and d[:4].isdigit() else ''

def games(system):
    """Every game ES would show for this console (gamelist + loose files), hidden ones left out. Cached."""
    base = f'{ROMS}/{system}'
    gl = base + '/gamelist.xml'
    try: stamp = (os.path.getmtime(gl) if os.path.exists(gl) else 0, os.path.getmtime(base))
    except OSError: return []
    with _lib_lock:
        if _lib.get(system, (None,))[0] == stamp: return _lib[system][1]
    ext = {'.' + e for e in SYSTEMS[system]['ext']}
    out, seen, hidden = [], set(), set()
    try: root = ET.parse(gl).getroot() if os.path.exists(gl) else None
    except ET.ParseError: root = None
    for g in (root.iter('game') if root is not None else []):
        path = resolve(base, g.findtext('path'))
        if g.findtext('hidden') == 'true': hidden.add(path); continue
        if os.path.splitext(path)[1].lower() not in ext or not os.path.isfile(path) or not inside(path, os.path.realpath(base)):
            continue
        img = resolve(base, g.findtext('image') or g.findtext('thumbnail') or '')
        has_img = bool(g.findtext('image') or g.findtext('thumbnail')) and img.lower().endswith(('.png', '.jpg', '.jpeg')) \
                  and os.path.isfile(img) and inside(img, os.path.realpath(ROMS))
        rel = os.path.relpath(path, base); seen.add(path)
        out.append({'id': gid(rel), 'rel': rel, 'path': path, 'img': img if has_img else None,
                    'name': g.findtext('name') or os.path.splitext(os.path.basename(path))[0],
                    'desc': (g.findtext('desc') or '').strip(), 'year': year(g.findtext('releasedate') or ''),
                    'genre': g.findtext('genre') or '', 'players': g.findtext('players') or '',
                    'developer': g.findtext('developer') or '', 'publisher': g.findtext('publisher') or '',
                    'rating': g.findtext('rating') or '', 'fav': g.findtext('favorite') == 'true',
                    'kid': g.findtext('kidgame') == 'true'})
    # files ES lists that the scraper never named (top level only, like most of the library)
    for f in sorted(os.listdir(base)):
        path = os.path.join(base, f)
        if path in seen or path in hidden or f.startswith('.') or os.path.splitext(f)[1].lower() not in ext or not os.path.isfile(path):
            continue
        out.append({'id': gid(f), 'rel': f, 'path': path, 'img': None, 'name': os.path.splitext(f)[0], 'desc': '',
                    'year': '', 'genre': '', 'players': '', 'developer': '', 'publisher': '', 'rating': '',
                    'fav': False, 'kid': False})
    # discs that only make sense as part of an .m3u / .cue are not separate games
    parts = set()
    for g in out:
        if g['path'].lower().endswith(('.m3u', '.cue')):
            parts.update(p for p in disc_files(g['path'])[1:])
    out = [g for g in out if g['path'] not in parts]
    out.sort(key=lambda g: (not g['fav'], g['name'].lower()))
    with _lib_lock: _lib[system] = (stamp, out)
    return out

def find(system, game_id):
    if system not in SYSTEMS or not re.fullmatch('[0-9a-f]{16}', game_id or ''): return None
    return next((g for g in games(system) if g['id'] == game_id), None)

def disc_files(path):
    """The game file plus everything it points at (.m3u -> discs, .cue -> tracks), all in the console folder."""
    base = os.path.dirname(path)
    out = [path]
    def refs(f):
        try: text = open(f, errors='replace').read(1 << 20)
        except OSError: return []
        if f.lower().endswith('.m3u'):
            items = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]
        else:
            items = [a or b for a, b in DISC_TRACKS.findall(text)]
        return [os.path.normpath(os.path.join(os.path.dirname(f), i)) for i in items]
    for r in refs(path):
        if r not in out: out.append(r)
        if r.lower().endswith('.cue'):
            out += [t for t in refs(r) if t not in out]
    real = os.path.realpath(base)
    return [f for f in out if os.path.isfile(f) and inside(f, real)]

def device_systems(device):
    want = TIERS.get(device, TIERS['laptop'])
    nm = names(); out = []
    for d in sorted(os.listdir(ROMS)):
        p = f'{ROMS}/{d}'
        if not os.path.isdir(p) or os.path.islink(p) or d in ('searchgames', 'surprise') or d.startswith('.'): continue
        s = SYSTEMS.get(d)
        if s and s['tier'] in want:
            n = len(games(d))
            if n: out.append({'id': d, 'name': nm.get(d, d), 'count': n, 'mode': 'browser', 'core': s['core'], 'sync': s['sync']})
        elif device == 'laptop' and (not s or s['tier'] not in want):
            if any(not f.startswith(('.', 'gamelist', 'media')) and os.path.splitext(f)[1] not in ('.txt', '.xml', '.srm', '.sav')
                   for f in os.listdir(p)):
                out.append({'id': d, 'name': nm.get(d, d), 'count': None, 'mode': 'stream'})
    order = list(nm)
    out.sort(key=lambda s: (s['mode'] == 'stream', order.index(s['id']) if s['id'] in order else 999, s['name']))
    return out

# ---------- zips made on the fly (multi-file discs, BIOS sets) ----------
_crc = {}
def crc_of(path):
    st = os.stat(path); key = (path, st.st_size, st.st_mtime)
    if key not in _crc:
        c = 0
        with open(path, 'rb') as f:
            while True:
                b = f.read(1 << 20)
                if not b: break
                c = zlib.crc32(b, c)
        _crc[key] = c
    return _crc[key]

def zip_plan(files):
    """[(arcname, path, size)] -> total length of an uncompressed zip of them."""
    total = 22
    for name, _, size in files:
        n = len(name.encode())
        total += 30 + n + size + 46 + n
    return total

def zip_stream(wfile, files):
    central, off = [], 0
    for name, path, size in files:
        n = name.encode(); crc = crc_of(path)
        hdr = struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0x800, 0, 0, 0x21, crc, size, size, len(n), 0) + n
        wfile.write(hdr)
        with open(path, 'rb') as f:
            while True:
                b = f.read(1 << 20)
                if not b: break
                wfile.write(b)
        central.append(struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 20, 20, 0x800, 0, 0, 0x21, crc, size, size, len(n),
                                   0, 0, 0, 0, 0, off) + n)
        off += len(hdr) + size
    cd = b''.join(central)
    wfile.write(cd + struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, len(files), len(files), len(cd), off, 0))

# ---------- HTTP ----------
def raw(h, code, ctype, length, headers=(), cache=False):
    h.send_response(code)
    h.send_header('Content-Type', ctype)
    h.send_header('Content-Length', str(length))
    h.send_header('Cache-Control', 'public, max-age=86400' if cache else 'no-store')
    h.send_header('X-Content-Type-Options', 'nosniff')
    for k, v in headers: h.send_header(k, v)
    h.end_headers()

def send_file(h, path, head, cache=False, name=None):
    try: size = os.path.getsize(path)
    except OSError: return h.send(404, {'error': 'not found'})
    hdrs = [('Content-Disposition', f'attachment; filename="{name}"')] if name else []
    raw(h, 200, TYPES.get(os.path.splitext(path)[1].lower(), 'application/octet-stream'), size, hdrs, cache)
    if head: return
    try:
        with open(path, 'rb') as f:
            while True:
                b = f.read(1 << 20)
                if not b: break
                h.wfile.write(b)
    except (BrokenPipeError, ConnectionResetError):
        pass

def static(h, base, rel, head, cache=True):
    rel = unquote(rel)
    path = os.path.normpath(os.path.join(base, rel))
    if not rel or '..' in rel.split('/') or not inside(path, os.path.realpath(base)) or not os.path.isfile(path):
        return h.send(404, {'error': 'not found'})
    send_file(h, path, head, cache=cache)

def tv_rom():
    try: return os.path.normpath(json.load(open(CUR)).get('rom', ''))
    except Exception: return None

def save_path(g):
    return os.path.splitext(g['path'])[0] + '.srm'

def handle_get(h, head=False):
    u = urlparse(h.path); path = u.path
    if path in ('/play', '/play/'):
        if h.guard(need_auth=False): send_file(h, STATIC + '/index.html', head)
        return True
    if path == '/play/ca.crt':
        if h.guard(need_auth=False): send_file(h, CERTS + '/ca.crt', head, name='super-retropie-ca.crt')
        return True
    for prefix, base in (('/play/ejs/', EJS), ('/play/static/', STATIC + '/static')):
        if path.startswith(prefix):
            if h.guard(need_auth=False): static(h, base, path[len(prefix):], head, cache=base == EJS)
            return True
    if path.startswith('/play/theme/'):
        if not h.guard(need_auth=False): return True
        rel = path[len('/play/theme/'):]
        files = {'bg-system.png': '_inc/system-global-bg.png', 'bg-games.png': '_inc/ingame-global-bg.png',
                 'font.ttf': '_inc/fonts/Roboto-Medium.ttf', 'star-on.png': '_inc/images/star_filled.png',
                 'star-off.png': '_inc/images/star_empty.png'}
        m = re.fullmatch(r'card/([a-z0-9-]+)\.png', rel)
        if m: return static(h, THEME, m.group(1) + '/_inc/system.png', head) or True
        if rel in files: return static(h, THEME, files[rel], head) or True
        h.send(404, {'error': 'not found'}); return True
    if not path.startswith('/api/play/'): return False
    if not h.guard(): return True
    q = parse_qs(u.query)
    parts = path[len('/api/play/'):].split('/')
    if parts == ['library']:
        system = q.get('sys', [''])[0]
        if system:
            if system not in SYSTEMS: return h.send(404, {'error': 'not found'}) or True
            keep = ('id', 'name', 'year', 'genre', 'players', 'developer', 'publisher', 'rating', 'fav', 'kid')
            return h.send(200, {'games': [{k: g[k] for k in keep} | {'art': bool(g['img'])} for g in games(system)]}) or True
        device = q.get('device', ['laptop'])[0]
        return h.send(200, {'systems': device_systems(device), 'tv': tv_state(h)}) or True
    if parts == ['game']:
        system, g = q.get('sys', [''])[0], find(q.get('sys', [''])[0], q.get('id', [''])[0])
        if not g: return h.send(404, {'error': 'That game is not on the box any more - reload the list'}) or True
        s = SYSTEMS[system]; files = disc_files(g['path'])
        rom = os.path.basename(g['path']) if len(files) == 1 else os.path.splitext(os.path.basename(g['path']))[0] + '.zip'
        has_bios = any(os.path.isfile(f'{BIOS}/{b}') for b in s.get('bios', []))
        return h.send(200, {k: v for k, v in g.items() if k not in ('path', 'rel', 'img')} | {
            'art': bool(g['img']), 'system': system, 'system_name': names().get(system, system), 'core': s.get('ejs', s['core']),
            'tier': s['tier'], 'sync': s['sync'], 'size': sum(os.path.getsize(f) for f in files),
            'rom': f'/api/play/rom/{system}/{g["id"]}/{quote(rom)}',
            'bios': f'/api/play/bios/{system}/{system}-bios.zip' if has_bios else '',
            'on_tv': tv_rom() == os.path.normpath(g['path'])}) or True
    if len(parts) >= 3 and parts[0] in ('art', 'rom', 'save', 'bios'):
        kind, system, game_id = parts[0], parts[1], parts[2]
        if kind == 'bios':
            s = SYSTEMS.get(system)
            files = [(b, f'{BIOS}/{b}', os.path.getsize(f'{BIOS}/{b}')) for b in (s or {}).get('bios', []) if os.path.isfile(f'{BIOS}/{b}')]
            if not files: return h.send(404, {'error': 'no BIOS'}) or True
            raw(h, 200, 'application/zip', zip_plan(files))
            if not head: zip_stream(h.wfile, files)
            return True
        g = find(system, game_id)
        if not g: return h.send(404, {'error': 'That game is not on the box any more - reload the list'}) or True
        if kind == 'art':
            return (send_file(h, g['img'], head, cache=True) if g['img'] else h.send(404, {'error': 'no artwork'})) or True
        if kind == 'save':
            if not SYSTEMS[system]['sync']: return h.send(404, {'error': 'not synced'}) or True
            sp = save_path(g)
            return (send_file(h, sp, head) if os.path.isfile(sp) else h.send(404, {'error': 'no save yet'})) or True
        # rom: the last part of the URL is the file name (EmulatorJS names the game and its cache after it)
        files = disc_files(g['path'])
        want = unquote(parts[3]) if len(parts) > 3 else ''
        if len(files) == 1:
            if want != os.path.basename(g['path']): return h.send(404, {'error': 'not found'}) or True
            return send_file(h, g['path'], head) or True
        if want != os.path.splitext(os.path.basename(g['path']))[0] + '.zip': return h.send(404, {'error': 'not found'}) or True
        plan = [(os.path.relpath(f, os.path.dirname(g['path'])), f, os.path.getsize(f)) for f in files]
        total = zip_plan(plan)
        if total >= 0xFFFFFFFF: return h.send(413, {'error': 'This disc set is too big to send to a browser'}) or True
        raw(h, 200, 'application/zip', total)
        if not head:
            try: zip_stream(h.wfile, plan)
            except (BrokenPipeError, ConnectionResetError): pass
        return True
    h.send(404, {'error': 'not found'}); return True

def tv_state(h):
    try: busy = COMPANION.game_running()
    except Exception: busy = None
    return {'busy': busy, 'moonlight': 'Super RetroPie'}

def handle_put(h):
    path = urlparse(h.path).path
    m = re.fullmatch(r'/api/play/save/([a-z0-9-]+)/([0-9a-f]{16})', path)
    if not m: return False
    if not h.guard(write=True): return True
    g = find(m.group(1), m.group(2))
    if not g or not SYSTEMS[m.group(1)]['sync']: return h.send(404, {'error': 'not found'}) or True
    n = int(h.headers.get('Content-Length') or 0)
    if not 0 < n <= SAVE_MAX: return h.send(400, {'error': 'bad save'}) or True
    data = h.rfile.read(n)
    if len(data) != n: return True
    if tv_rom() == os.path.normpath(g['path']):
        return h.send(409, {'error': 'This game is open on the TV - the save is kept in this browser and sent later'}) or True
    sp = save_path(g)
    if os.path.isfile(sp) and open(sp, 'rb').read() == data: return h.send(200, {'ok': True, 'same': True}) or True
    subprocess.run(['/usr/local/bin/retropie-saves', 'snapshot', g['path']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tmp = sp + '.webplay-tmp'
    with open(tmp, 'wb') as f: f.write(data)
    os.replace(tmp, sp)
    auto = os.path.splitext(g['path'])[0] + '.state.auto'
    if os.path.exists(auto):                       # else the TV resumes from memory and ignores the new save
        os.replace(auto, auto + '.before-laptop-' + time.strftime('%Y%m%d-%H%M%S'))
    return h.send(200, {'ok': True}) or True

# ---------- HTTPS ----------
def local_ips():
    out = set()
    try:
        for line in subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.split():
            ip = ipaddress.ip_address(line)
            if ip.version == 4: out.add(line)
    except Exception: pass
    return sorted(out)

def ensure_cert():
    """A small certificate authority of the box's own (install ca.crt once per laptop), and a server
    certificate for its names and addresses - remade when the address changes."""
    os.makedirs(CERTS, mode=0o700, exist_ok=True)
    host = socket.gethostname()
    sans = [f'DNS:{host}', f'DNS:{host}.local', 'DNS:localhost', 'IP:127.0.0.1'] + [f'IP:{i}' for i in local_ips()]
    want = ','.join(sans)
    ca, cakey, crt, key, have = (CERTS + f for f in ('/ca.crt', '/ca.key', '/server.crt', '/server.key', '/server.sans'))
    run = lambda *a: subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not (os.path.exists(ca) and os.path.exists(cakey)):
        run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '3650', '-keyout', cakey, '-out', ca,
            '-subj', '/CN=Super RetroPie home CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    if not (os.path.exists(crt) and os.path.exists(have) and open(have).read() == want):
        csr = CERTS + '/server.csr'
        run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', key, '-out', csr, '-subj', f'/CN={host}')
        ext = CERTS + '/server.ext'
        open(ext, 'w').write(f'subjectAltName={want}\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
        run('openssl', 'x509', '-req', '-in', csr, '-CA', ca, '-CAkey', cakey, '-CAcreateserial', '-days', '825',
            '-out', crt, '-extfile', ext)
        open(have, 'w').write(want)
        os.remove(csr); os.remove(ext)
    for f in (cakey, key): os.chmod(f, 0o600)
    return crt, key

class TLSServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, addr, handler, ctx):
        self.ctx = ctx
        super().__init__(addr, handler)
    def get_request(self):
        sock, addr = self.socket.accept()
        sock.settimeout(30)
        return sock, addr
    def finish_request(self, sock, addr):
        """In the request's own thread: TLS as normal, but a browser that came in on plain http
        (typing 10.5.0.19:8443 without https:// in Firefox) is sent to the https address."""
        try: first = sock.recv(1, socket.MSG_PEEK)
        except OSError: return
        if first == b'\x16':                         # TLS handshake
            try: tls = self.ctx.wrap_socket(sock, server_side=True)
            except (OSError, ssl.SSLError): return
            try: return super().finish_request(tls, addr)
            finally:
                try: tls.close()                     # the plain socket was handed over to it
                except OSError: pass
        try:
            head = sock.recv(8192).decode('latin-1')
            path = (head.split(' ', 2) + ['', ''])[1] or '/'
            m = re.search(r'^host:\s*([^\r\n]+)', head, re.I | re.M)
            host = m.group(1).strip() if m else ''
            if not path.startswith('/') or not re.fullmatch(r'[A-Za-z0-9.\-\[\]:]+', host): path, host = '/play', ''
            if not host: host = f'{local_ips()[0] if local_ips() else "localhost"}:{HTTPS_PORT}'
            sock.sendall((f'HTTP/1.1 301 Moved Permanently\r\nLocation: https://{host}{path}\r\n'
                          'Content-Length: 0\r\nConnection: close\r\n\r\n').encode())
        except OSError:
            pass
    def handle_error(self, request, client_address):
        pass                                         # half-open / plain-http-on-https connections are not worth a trace

def serve_https(handler):
    try:
        crt, key = ensure_cert()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        srv = TLSServer(('', HTTPS_PORT), handler, ctx)
    except Exception as e:
        print('webplay: HTTPS not started:', e, flush=True); return
    threading.Thread(target=srv.serve_forever, daemon=True).start()

def install(handler):
    """Wire the /play routes into the companion's request handler."""
    global COMPANION
    import sys
    COMPANION = sys.modules[handler.__module__]
    get, put = handler.do_GET, getattr(handler, 'do_PUT', None)
    def do_GET(self):
        if not handle_get(self): get(self)
    def do_HEAD(self):
        if not handle_get(self, head=True): self.send(404, {'error': 'not found'})
    def do_PUT(self):
        if not handle_put(self):
            if put: put(self)
            else: self.send(404, {'error': 'not found'})
    handler.do_GET, handler.do_HEAD, handler.do_PUT = do_GET, do_HEAD, do_PUT
