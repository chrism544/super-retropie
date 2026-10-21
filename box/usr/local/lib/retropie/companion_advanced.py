"""Control Center > Advanced: the TV's Advanced Settings tools on the web page.

Boot screen, performance, network (read-only - an address change belongs on the TV, where the
60-second safety revert can be confirmed), RetroArch Net Play and game launch logs. retropie-companion
calls install(Handler); everything lives under /api/adv/ behind the same home-network + PIN checks.
RetroPie Setup and the full RetroArch configuration editor are text menus and stay on the TV.
"""
import glob, io, ipaddress, json, os, re, socket, subprocess, sys
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, '/usr/local/lib/retropie')

HOME = os.path.expanduser('~')
SPLASH = '/usr/local/share/retropie-splash'
SPLASH_CFG = HOME + '/.config/retropie-splash.json'
THUMBS = HOME + '/.cache/retropie-companion/boot'
STYLES = [('super', 'Super RetroPie'), ('consoles', 'Consoles'), ('minimal', 'Minimal'), ('playstation', 'PlayStation'),
          ('n64', 'Nintendo 64'), ('gamecube', 'GameCube'), ('ps2', 'PlayStation 2'), ('ps3', 'PlayStation 3'),
          ('xbox', 'Xbox'), ('wii', 'Wii'), ('wiiu', 'Wii U'), ('xbox360', 'Xbox 360'), ('off', 'Off')]
PL1 = '/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw'
MODES = [(25, 'Cool & quiet', 'Lowest heat and fan noise. Fine for older consoles; PS2, GameCube, Wii and Xbox run slower.'),
         (35, 'Standard', 'What the PC came set to.'),
         (50, 'Performance', 'Faster for demanding games (Xbox, PS2, Wii). The fan runs harder; tested safe at 75 C.')]
XEMU = '/opt/retropie/emulators/xemu-appimage'
NETPLAY = '/opt/retropie/configs/all/retronetplay.cfg'
LOGS = HOME + '/.local/share/retropie-launch-logs'
PROBLEM = re.compile(r"error|fail|fatal|not found|missing|unable|cannot|can't|denied|segmentation|abort|invalid|no such", re.I)
NICK = re.compile(r'^[A-Za-z0-9_-]{1,16}$')          # runcommand puts it unquoted on the command line

def read(p, default=''):
    try: return open(p).read().strip()
    except OSError: return default

def run(*cmd, timeout=10):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception: return ''

def busy():
    return subprocess.run(['/usr/local/bin/retropie-game-running']).returncode == 0

def write_atomic(path, text):
    tmp = path + '.tmp'
    open(tmp, 'w').write(text)
    if os.path.exists(path): os.chmod(tmp, os.stat(path).st_mode & 0o777)
    os.replace(tmp, path)

# ---------------------------------------------------------------- boot screen
def boot():
    import importlib, retropie_boot_sound as bs
    importlib.reload(bs)                                 # sounds can be fetched while the server runs
    try: c = json.load(open(SPLASH_CFG))
    except (OSError, ValueError): c = {}
    return {'style': c.get('style', 'super'), 'sound': c.get('sound', 'console'), 'volume': c.get('volume', 50),
            'when': c.get('sound_when', 'startup'),
            'styles': [{'id': v, 'name': n} for v, n in STYLES if v == 'off' or os.path.isfile(f'{SPLASH}/{v}.png')],
            'sounds': [{'id': v, 'name': n} for v, n in bs.CHOICES]}

def set_boot(d):
    b = boot()
    try: c = json.load(open(SPLASH_CFG))
    except (OSError, ValueError): c = {}
    if d.get('sound') in [s['id'] for s in b['sounds']]: c['sound'] = d['sound']
    if d.get('volume') in (25, 50, 75, 100): c['volume'] = d['volume']
    if d.get('when') in ('startup', 'always'): c['sound_when'] = d['when']
    write_atomic(SPLASH_CFG, json.dumps(c) + '\n')
    style = d.get('style')
    if style and style != b['style'] and style in [s['id'] for s in b['styles']]:
        if busy(): return 409, {'error': 'Someone is using the TV - change the picture when they have finished'}
        # rebuilds the boot image (about a minute of work) - same as the TV's Boot Screen menu
        subprocess.Popen(['sudo', '-n', 'systemd-run', '--collect', '--unit=retropie-bootscreen-apply',
                          '/usr/local/bin/retropie-bootscreen', style], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 200, {'ok': True, 'message': 'Saved. The new picture is being set up - it shows from the next start-up.'}
    return 200, {'ok': True, 'message': 'Saved.'}

def thumb(style):
    if style not in [v for v, _ in STYLES if v != 'off']: return None
    src = f'{SPLASH}/{style}.png'
    if not os.path.isfile(src): return None
    out = f'{THUMBS}/{style}.jpg'
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        from PIL import Image
        os.makedirs(THUMBS, exist_ok=True)
        im = Image.open(src).convert('RGB'); im.thumbnail((640, 360)); im.save(out, quality=82)
    return open(out, 'rb').read()

# ---------------------------------------------------------------- performance
def perf():
    t = next((read(z + '/temp') for z in glob.glob('/sys/class/thermal/thermal_zone*') if read(z + '/type') == 'x86_pkg_temp'), '')
    fan = next((read(h + '/fan1_input') for h in glob.glob('/sys/class/hwmon/hwmon*') if read(h + '/name') == 'dell_smm'), '')
    mhz = [float(l.split(':')[1]) for l in open('/proc/cpuinfo') if l.startswith('cpu MHz')]
    last = [l for l in read('/var/log/retropie-update-xemu.log').splitlines() if l]
    return {'watts': round(int(read(PL1, '35000000')) / 1e6), 'modes': [{'w': w, 'name': n, 'desc': d} for w, n, d in MODES],
            'temp': int(t) // 1000 if t else None, 'fan': int(fan) if fan else None,
            'ghz': round(sum(mhz) / len(mhz) / 1000, 1) if mhz else None,
            'xemu_auto': run('systemctl', 'is-enabled', 'retropie-update-xemu.timer').strip() == 'enabled',
            'xemu_version': read(f'{XEMU}/VERSION', 'unknown'), 'xemu_checked': last[-1][:16] if last else ''}

def set_perf(d):
    if d.get('watts') not in (25, 35, 50) and not isinstance(d.get('xemu_auto'), bool):
        return 400, {'error': 'Choose a power mode'}
    if d.get('watts') in (25, 35, 50):
        r = subprocess.run(['sudo', '-n', '/usr/local/bin/retropie-power-set', str(d['watts'])], capture_output=True)
        if r.returncode: return 500, {'error': 'Could not change the power mode'}
    if isinstance(d.get('xemu_auto'), bool):
        r = subprocess.run(['sudo', '-n', 'systemctl', 'enable' if d['xemu_auto'] else 'disable', '--now',
                            'retropie-update-xemu.timer'], capture_output=True)
        if r.returncode: return 500, {'error': 'Could not change Xbox emulator updates'}
    return 200, {'ok': True, 'message': 'Saved.'}

# ---------------------------------------------------------------- network (read-only)
def net():
    dev = ip = None; prefix = 0
    for line in run('ip', '-4', '-o', 'addr', 'show', 'scope', 'global').splitlines():
        m = re.match(r'\d+:\s+(\S+)\s+inet\s+([\d.]+)/(\d+)', line)
        if m and not m.group(1).startswith(('tailscale', 'docker', 'lo', 'veth', 'br-')):
            dev, ip, prefix = m.group(1), m.group(2), int(m.group(3)); break
    try: cfg = json.loads(run('sudo', '-n', '/usr/local/bin/retropie-netcfg', 'show'))
    except ValueError: cfg = {}
    gw = re.search(r'default via ([\d.]+)', run('ip', 'route'))
    dns = re.findall(r'DNS Servers?: (\S+)', run('resolvectl', 'status', dev)) if dev else []
    ts = re.search(r'inet ([\d.]+)', run('ip', '-4', 'addr', 'show', 'tailscale0'))
    internet = False
    for target in (('1.1.1.1', 443), ('8.8.8.8', 53), ('9.9.9.9', 443)):     # one slow reply is not "offline"
        try:
            socket.create_connection(target, timeout=3).close(); internet = True; break
        except OSError:
            pass
    speed = read(f'/sys/class/net/{dev}/speed') if dev else ''
    return {'iface': dev, 'kind': 'Wired' if dev and dev.startswith(('en', 'eth')) else 'Wi-Fi',
            'address': ip, 'mask': str(ipaddress.ip_network(f'0.0.0.0/{prefix}').netmask) if ip else None,
            'mode': 'Fixed address' if cfg.get('mode') == 'static' else 'Automatic (DHCP)',
            'gateway': gw.group(1) if gw else None, 'dns': dns[0] if dns else ', '.join(cfg.get('dns', [])) or None,
            'speed': int(speed) if speed.lstrip('-').isdigit() and int(speed) > 0 else None,
            'mac': read(f'/sys/class/net/{dev}/address') if dev else None,
            'tailscale': ts.group(1) if ts else None, 'internet': internet}

# ---------------------------------------------------------------- RetroArch Net Play
def netplay():
    v = {'mode': 'H', 'port': '55435', 'host': '192.168.0.1', 'nick': 'RetroPie'}
    for line in read(NETPLAY).splitlines():
        m = re.match(r'__netplay(mode|port|hostip|nickname)="(.*)"$', line.strip())
        if m: v[{'hostip': 'host', 'nickname': 'nick'}.get(m.group(1), m.group(1))] = m.group(2)
    return v

def set_netplay(d):
    mode, port, host, nick = d.get('mode'), str(d.get('port', '')), str(d.get('host', '')).strip(), str(d.get('nick', '')).strip()
    if mode not in ('H', 'C'): return 400, {'error': 'Choose Host or Join'}
    if not port.isdigit() or not 1024 <= int(port) <= 65535: return 400, {'error': 'The port must be a number from 1024 to 65535'}
    try: ipaddress.ip_address(host)
    except ValueError: return 400, {'error': "The host address must be an IP address, like 192.168.1.20"}
    if not NICK.match(nick): return 400, {'error': 'Nickname: up to 16 letters, numbers, - or _ (no spaces)'}
    write_atomic(NETPLAY, f'__netplaymode="{mode}"\n__netplayport="{port}"\n__netplayhostip="{host}"\n'
                          f'__netplayhostip_cfile="{host if mode == "C" else ""}"\n__netplaynickname="{nick}"\n')
    return 200, {'ok': True, 'message': 'Saved. Start a game with Net Play from its launch options (A while it loads).'}

# ---------------------------------------------------------------- game launch logs
def logs():
    out = []
    for f in sorted(glob.glob(LOGS + '/*.log'), reverse=True)[:25]:
        head, _, body = read(f).partition('\n---\n')
        h = dict(l.split('=', 1) for l in head.splitlines() if '=' in l)
        name = re.sub(r'\s*[\(\[].*$', '', os.path.splitext(os.path.basename(h.get('rom', '')))[0]) or '?'
        probs = [l.strip()[:160] for l in body.splitlines() if PROBLEM.search(l)][:3]
        out.append({'file': os.path.basename(f), 'game': name, 'system': h.get('system', ''), 'emulator': h.get('emulator', ''),
                    'ended': h.get('ended', ''), 'problems': probs})
    return out

def log_text(name):
    if not re.fullmatch(r'\d{8}-\d{6}\.log', name or ''): return None
    p = f'{LOGS}/{name}'
    return read(p)[-200000:] if os.path.isfile(p) else None

# ---------------------------------------------------------------- game settings (Configuration Editor)
CONF = '/opt/retropie/configs'
CORE = CONF + '/all/retroarch-core-options.cfg'
SH = CONF + '/all/retroarch/shaders/crt/'
ROMS = HOME + '/RetroPie/roms'
CNAMES = {'all': 'All consoles', 'arcade': 'Arcade', 'snes': 'Super Nintendo', 'nes': 'NES', 'megadrive': 'Mega Drive',
          'mastersystem': 'Master System', 'gamegear': 'Game Gear', 'n64': 'Nintendo 64', 'psx': 'PlayStation',
          'gb': 'Game Boy', 'gbc': 'Game Boy Color', 'gba': 'Game Boy Advance', 'dreamcast': 'Dreamcast',
          'gc': 'GameCube', 'nds': 'Nintendo DS', 'psp': 'PSP', 'pcengine': 'PC Engine', 'neogeo': 'Neo Geo',
          'segacd': 'Mega-CD', 'sega32x': '32X', 'saturn': 'Saturn', 'atari2600': 'Atari 2600', 'mame-libretro': 'MAME'}
ON_OFF = [('on', 'On'), ('off', 'Off')]
# (id, label, choices, description, keys written per choice, shared core option?) - the same list as retropie-settings
GAME = [
    ('effect', 'Screen effect', [('none', 'Off'), ('scan', 'CRT scanlines'), ('curve', 'Curved CRT TV')],
     'Makes old games look like they did on a tube TV. Scanlines are subtle; the curved TV adds curve and glow.',
     {'none': {'video_shader_enable': 'false'}, 'scan': {'video_shader_enable': 'true', 'video_shader': SH + 'crt-easymode.glslp'},
      'curve': {'video_shader_enable': 'true', 'video_shader': SH + 'crt-geom.glslp'}}, False),
    ('smooth', 'Smooth picture', ON_OFF, 'Softens the picture. Off keeps crisp, blocky pixels.',
     {'on': {'video_smooth': 'true'}, 'off': {'video_smooth': 'false'}}, False),
    ('integer', 'Pixel-perfect size', ON_OFF, 'Scales by whole steps so every pixel is the same size - the picture gets a little smaller, with a border.',
     {'on': {'video_scale_integer': 'true'}, 'off': {'video_scale_integer': 'false'}}, False),
    ('resume', 'Resume where you left off', ON_OFF, 'Saves your exact place when you quit a game and puts you back there next time (X on the launch screen starts fresh).',
     {'on': {'savestate_auto_save': 'true', 'savestate_auto_load': 'true'}, 'off': {'savestate_auto_save': 'false', 'savestate_auto_load': 'false'}}, False),
    ('runahead', 'Reduce input lag', ON_OFF, 'Run-ahead: buttons respond a frame sooner. Uses more power - best for 8 and 16-bit consoles and arcade.',
     {'on': {'run_ahead_enabled': 'true', 'run_ahead_frames': '1', 'run_ahead_secondary_instance': 'false'}, 'off': {'run_ahead_enabled': 'false'}}, False),
    ('fps', 'Show frame rate', ON_OFF, 'Shows frames per second in the corner while you play.',
     {'on': {'fps_show': 'true'}, 'off': {'fps_show': 'false'}}, False),
    ('psxlogo', 'PlayStation start-up', ON_OFF, 'PlayStation games start with the Sony logo and start-up chime, like the real console. Off starts the game straight away.',
     {'on': {'pcsx_rearmed_show_bios_bootlogo': 'enabled'}, 'off': {'pcsx_rearmed_show_bios_bootlogo': 'disabled'}}, True),
]

def cfg_vals(path):
    vals = {}
    for line in read(path).splitlines():
        m = re.match(r'\s*([a-z0-9_]+)\s*=\s*"?([^"\n]*)"?', line)
        if m and m.group(1) not in vals: vals[m.group(1)] = m.group(2)        # first value wins, as in RetroArch
    return vals

def matching(opt, vals):
    for value, keys in opt[4].items():
        if all(vals.get(k) == v for k, v in keys.items()): return value
    if opt[0] == 'effect' and vals.get('video_shader_enable') == 'true' and vals.get('video_shader'): return 'other'
    return None

def consoles():
    out = ['all']
    for s in sorted(os.listdir(CONF)):
        emu = f'{CONF}/{s}/emulators.cfg'
        if s in ('all', 'ports') or not os.path.exists(f'{CONF}/{s}/retroarch.cfg') or not os.path.exists(emu) \
           or 'retroarch' not in read(emu): continue
        d = f'{ROMS}/{s}'
        if os.path.isdir(d) and any(not f.endswith(('.xml', '.txt')) and not f.startswith('.') for f in os.listdir(d)):
            out.append(s)
    return out

def game(scope):
    if scope not in consoles(): scope = 'all'
    allv, own, core = cfg_vals(f'{CONF}/all/retroarch.cfg'), cfg_vals(f'{CONF}/{scope}/retroarch.cfg'), cfg_vals(CORE)
    opts = []
    for oid, label, choices, desc, keys, shared in GAME:
        if shared and scope != 'all': continue
        opt = (oid, label, choices, desc, keys)
        default = choices[-1][0] if choices[-1][0] == 'off' else choices[0][0]   # unset = RetroArch default
        base = matching(opt, core if shared else allv) or default
        if scope == 'all' or shared: value = base
        else: value = matching(opt, own) if any(k in own for v in keys.values() for k in v) else 'same'
        ch = [{'v': v, 'l': l} for v, l in choices]
        if scope != 'all' and not shared: ch.insert(0, {'v': 'same', 'l': 'Same as all (' + dict(choices).get(base, 'Other') + ')'})
        if value == 'other': ch.append({'v': 'other', 'l': 'Other (set elsewhere)'})
        opts.append({'id': oid, 'label': label, 'desc': desc, 'value': value or 'other', 'choices': ch})
    return {'scope': scope, 'consoles': [{'id': c, 'name': CNAMES.get(c, c)} for c in consoles()], 'options': opts}

def set_game(d):
    import racfg
    scope, oid, value = d.get('scope'), d.get('id'), d.get('value')
    if scope not in consoles(): return 400, {'error': 'Unknown console'}
    opt = next((o for o in GAME if o[0] == oid), None)
    if not opt or (opt[5] and scope != 'all'): return 400, {'error': 'Unknown setting'}
    every = {k for v in opt[4].values() for k in v}
    path = CORE if opt[5] else f'{CONF}/{scope}/retroarch.cfg'
    if value == 'same' and scope != 'all': racfg.set_keys(path, {}, remove=every)
    elif value in opt[4]: racfg.set_keys(path, opt[4][value], remove=every - set(opt[4][value]))
    else: return 400, {'error': 'Unknown choice'}
    return 200, {'ok': True, 'message': 'Saved - from the next game you start.'}

# ---------------------------------------------------------------- game artwork (bezels)
BEZEL = HOME + '/.config/retropie-bezels.json'
def artwork():
    try: s = json.load(open(BEZEL))
    except (OSError, ValueError): s = {}
    return {'style': s.get('style', 'fit'), 'bright': s.get('bright', 'dim')}

def set_artwork(d):
    if d.get('style') not in ('fit', 'original', 'off') and d.get('bright') not in ('dim', 'full'):
        return 400, {'error': 'Unknown choice'}
    s = artwork()
    if d.get('style') in ('fit', 'original', 'off'): s['style'] = d['style']
    if d.get('bright') in ('dim', 'full'): s['bright'] = d['bright']
    os.makedirs(os.path.dirname(BEZEL), exist_ok=True); write_atomic(BEZEL, json.dumps(s))
    # re-points every game's artwork setting - a few seconds of work, done in the background
    subprocess.Popen(['nice', '/usr/local/bin/retropie-bezels', '--apply'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 200, {'ok': True, 'message': 'Saved - from the next game you start.'}

# ---------------------------------------------------------------- screensaver (EmulationStation)
ES = HOME + '/.emulationstation/es_settings.cfg'
SAVER = [('ScreenSaverBehavior', 'string', 'dim', ['dim', 'black', 'slideshow', 'random video']),
         ('ScreenSaverTime', 'int', '300000', ['60000', '180000', '300000', '600000', '900000', '1800000', '0']),
         ('ScreenSaverSwapMediaTimeout', 'int', '10000', ['5000', '10000', '20000', '30000']),
         ('ScreenSaverGameInfo', 'string', 'never', ['never', 'start & end', 'always']),
         ('ScreenSaverVideoMute', 'bool', 'false', ['false', 'true'])]
def linked_videos():
    return sum(read(g).count('<video>') for g in glob.glob(ROMS + '/*/gamelist.xml'))

def screensaver():
    import html
    s = read(ES)
    get = lambda k, d: (html.unescape(m.group(1)) if (m := re.search(r'name="' + re.escape(k) + r'" value="([^"]*)"', s)) else d)
    return {**{k: get(k, d) for k, _, d, _ in SAVER}, 'videos': linked_videos()}

def set_screensaver(d):
    pairs = []
    for k, typ, _, allowed in SAVER:
        v = str(d[k]) if k in d else None
        if v is None: continue
        if v not in allowed: return 400, {'error': 'Unknown choice'}
        if k == 'ScreenSaverBehavior' and v == 'random video' and not linked_videos(): v = 'slideshow'   # no videos: ES would spin
        pairs.append(f'{k}={typ}:{v}')                    # retropie-es-set escapes it for the XML file
    if not pairs: return 400, {'error': 'Nothing to change'}
    if busy(): return 409, {'error': 'Someone is using the TV - try again when they have finished'}
    subprocess.run(['/usr/local/bin/retropie-es-set', '--now'] + pairs)
    return 200, {'ok': True, 'message': 'Saved - the TV menu reloads with the new screensaver.'}

# ---------------------------------------------------------------- menu music
MUSIC_CFG = HOME + '/.config/retropie-music.json'
def music():
    try: c = {'on': True, 'volume': 35, **json.load(open(MUSIC_CFG))}
    except (OSError, ValueError): c = {'on': True, 'volume': 35}
    exts = ('.mp3', '.ogg', '.wav', '.flac', '.m4a', '.opus')
    c['tracks'] = sum(1 for f in glob.glob(HOME + '/RetroPie/music/**/*', recursive=True) if f.lower().endswith(exts))
    return c

def set_music(d):
    if not isinstance(d.get('on'), bool) and d.get('volume') not in (10, 20, 35, 50, 70, 100):
        return 400, {'error': 'Unknown choice'}
    c = {k: v for k, v in music().items() if k in ('on', 'volume')}
    if isinstance(d.get('on'), bool): c['on'] = d['on']
    if d.get('volume') in (10, 20, 35, 50, 70, 100): c['volume'] = d['volume']
    os.makedirs(os.path.dirname(MUSIC_CFG), exist_ok=True); write_atomic(MUSIC_CFG, json.dumps(c))
    return 200, {'ok': True, 'message': 'Saved - the music changes within a few seconds.'}

def settings(scope='all'):
    return {'game': game(scope), 'artwork': artwork(), 'screensaver': screensaver(), 'music': music()}

# ---------------------------------------------------------------- web
def handle(h):
    u = urlparse(h.path)
    if not u.path.startswith('/api/adv/'): return False
    if not h.guard(write=h.command != 'GET'): return True
    q = parse_qs(u.query); p = u.path[9:]
    try:
        if h.command == 'GET':
            if p == 'all': h.send(200, {'boot': boot(), 'perf': perf(), 'net': net(), 'netplay': netplay(), 'logs': logs()})
            elif p == 'settings': h.send(200, settings(q.get('scope', ['all'])[0]))
            elif p == 'log':
                t = log_text(q.get('f', [''])[0])
                h.send(200, t.encode(), 'text/plain') if t is not None else h.send(404, {'error': 'No such log'})
            elif p == 'bootpic':
                img = thumb(q.get('s', [''])[0])
                h.send(200, img, 'image/jpeg') if img else h.send(404, {'error': 'No picture'})
            else: h.send(404, {'error': 'not found'})
        elif h.command == 'POST':
            fn = {'boot': set_boot, 'perf': set_perf, 'netplay': set_netplay, 'game': set_game, 'artwork': set_artwork,
                  'screensaver': set_screensaver, 'music': set_music}.get(p)
            if not fn: h.send(404, {'error': 'not found'})
            else: h.send(*fn(h.body_json()))
        else: h.send(405, {'error': 'not allowed'})
    except Exception as e:
        h.send(500, {'error': f'Something went wrong: {e}'})
    return True

def install(Handler):
    """Mount /api/adv/ on the companion's request handler (keeps whatever do_GET/do_POST it already has)."""
    get, post = Handler.do_GET, Handler.do_POST
    def do_GET(self):
        if not handle(self): get(self)
    def do_POST(self):
        if not handle(self): post(self)
    Handler.do_GET, Handler.do_POST = do_GET, do_POST
