"""Game Genie-style cheats for the Save Manager (RetroArch consoles).

Cheat lists come from the libretro cheat database (~/.../retroarch/cheats-db, from buildbot
cheats.zip). Switched-on cheats are written to RetroArch's per-game cheat file
  /opt/retropie/configs/all/retroarch/cheats/<core name>/<game file name>.cht
which RetroArch loads with the game and applies straight away (apply_cheats_after_load = true).

  available(system, rom) -> list of matching .cht files ([] = no cheats / not a RetroArch console)
  cheats_screen(system, rom, name)   the on-screen picker (needs retropie_ui initialised)
"""
import ctypes, glob, os, re

DB = '/opt/retropie/configs/all/retroarch/cheats-db'
OUT = '/opt/retropie/configs/all/retroarch/cheats'
CFG = '/opt/retropie/configs'
FOLDERS = {
    'snes': ['Nintendo - Super Nintendo Entertainment System', 'Nintendo - Satellaview'],
    'sfc': ['Nintendo - Super Nintendo Entertainment System'],
    'nes': ['Nintendo - Nintendo Entertainment System'], 'fds': ['Nintendo - Family Computer Disk System'],
    'megadrive': ['Sega - Mega Drive - Genesis'], 'genesis': ['Sega - Mega Drive - Genesis'],
    'mastersystem': ['Sega - Master System - Mark III'], 'gamegear': ['Sega - Game Gear'],
    'segacd': ['Sega - Mega-CD - Sega CD'], 'sega32x': ['Sega - 32X'], 'sg-1000': ['Sega - SG-1000'],
    'n64': ['Nintendo - Nintendo 64'], 'gb': ['Nintendo - Game Boy'], 'gbc': ['Nintendo - Game Boy Color'],
    'gba': ['Nintendo - Game Boy Advance'], 'nds': ['Nintendo - Nintendo DS'], 'virtualboy': ['Nintendo - Virtual Boy'],
    'psx': ['Sony - PlayStation'], 'psp': ['Sony - PlayStation Portable'],
    'dreamcast': ['Sega - Dreamcast'], 'saturn': ['Sega - Saturn'],
    'pcengine': ['NEC - PC Engine - TurboGrafx 16', 'NEC - PC Engine CD - TurboGrafx-CD'],
    'atari2600': ['Atari - 2600'], 'atari7800': ['Atari - 7800'], 'atarilynx': ['Atari - Lynx'],
    'ngp': ['SNK - Neo Geo Pocket'], 'ngpc': ['SNK - Neo Geo Pocket Color'],
    'arcade': ['FBNeo - Arcade Games'], 'fba': ['FBNeo - Arcade Games'], 'neogeo': ['FBNeo - Arcade Games'],
    'colecovision': ['Coleco - ColecoVision'], 'msx': ['Microsoft - MSX', 'Microsoft - MSX2'],
}

def title_key(name):
    t = re.sub(r'^\d{4}\s+', '', name)
    t = re.split(r'\s*[\(\[]', t, 1)[0]
    t = re.sub(r'^(.*), (the|a|an)\b', r'\2 \1', t.strip(), flags=re.I)
    t = re.sub(r'\bii\b', '2', t, flags=re.I); t = re.sub(r'\biii\b', '3', t, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', t.lower())

def regions(name):
    """Regions in a file name: GoodTools letters (E) (JUE), No-Intro words (USA, Europe), DS (EU)(US)."""
    out = set()
    for grp in re.findall(r'[\(\[]([^\)\]]*)[\)\]]', name):
        g = grp.upper().replace(' ', '')
        if re.fullmatch(r'[JUEWKBACFGS]+', g) and len(g) <= 4:
            out |= {{'J': 'Japan', 'U': 'USA', 'E': 'Europe', 'W': 'World'}.get(c, '') for c in g}
        for word, reg in (('USA', 'USA'), ('US', 'USA'), ('EUROPE', 'Europe'), ('EU', 'Europe'), ('UK', 'Europe'),
                          ('WORLD', 'World'), ('JAPAN', 'Japan'), ('JP', 'Japan')):
            if word in re.split(r'[,/]', g): out.add(reg)
    out.discard('')
    if 'World' in out: out |= {'USA', 'Europe', 'Japan'}
    return out

NOT_CHEATS = re.compile(r'\((Rumbles?|Demo|Kiosk|Beta|Proto|Prototype|Sample)\b', re.I)

GECKO_CACHE = os.path.expanduser('~/.cache/retropie-gecko')
GECKO_URL = 'https://codes.rc24.xyz/txt.php?txt={}'          # GameHacking.org mirror Dolphin itself uses

def disc_id(path):
    """6-character GameCube/Wii disc ID (GZLE01) from .iso/.gcm/.wbfs/.rvz/.wia, or None."""
    try:
        with open(path, 'rb') as f:
            head = f.read(0x300)
    except OSError:
        return None
    for off in (0, 0x200, 0x58):                         # plain image, WBFS, RVZ/WIA disc-header copy
        s = head[off:off + 6].decode('ascii', 'replace')
        if re.fullmatch(r'[A-Z0-9]{6}', s):
            return s
    return None

def gecko_file(rom):
    """Cached GameHacking code list for this disc (downloaded once; '' file = no codes)."""
    gid = disc_id(rom)
    if not gid: return None
    p = f'{GECKO_CACHE}/{gid}.txt'
    if not os.path.exists(p):
        import urllib.request
        os.makedirs(GECKO_CACHE, exist_ok=True)
        try:
            req = urllib.request.Request(GECKO_URL.format(gid), headers={'User-Agent': 'SuperRetroPie-cheats/1.0 (home RetroPie box)'})
            with urllib.request.urlopen(req, timeout=8) as r:
                txt = r.read().decode('utf-8', 'replace')
            open(p, 'w').write(txt if txt.startswith(gid) else '')
        except Exception:
            return None                                   # offline: try again next time
    return p if os.path.getsize(p) else None

def parse_gecko(path):
    """GameHacking text: blocks separated by blank lines - name line, then 'XXXXXXXX XXXXXXXX' code lines.
    Codes that need typing in a value (contain X/Y placeholders) are left out."""
    out = []
    for block in re.split(r'\n\s*\n', open(path, errors='replace').read())[1:]:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines: continue
        codes = [l for l in lines[1:] if re.fullmatch(r'[0-9A-Fa-f]{8} [0-9A-Fa-f]{8}', l)]
        if codes and not any(re.fullmatch(r'[0-9A-Fa-fXYZxyz]{8} [0-9A-Fa-fXYZxyz]{8}', l) and l not in codes for l in lines[1:]):
            out.append({'desc': re.sub(r'\s*\[[^\]]*\]\s*$', '', lines[0]) or lines[0], 'code': '+'.join(codes)})
    return out

_index = {}
def available(system, rom):
    if system in ('gc', 'wii'):
        if not core_name(system, rom): return []
        g = gecko_file(rom)
        return [g] if g else []
    return _available(system, rom)

def _available(system, rom):
    """Cheat files for this game, for ONE region only (codes are memory addresses, which can differ
    between the USA and Europe versions): the game's own region if there is a list for it, else the
    closest other one. Plain list first, then its Game Genie / Action Replay / GameShark lists."""
    if system not in FOLDERS or not core_name(system, rom):
        return []
    rb = os.path.basename(rom)
    key = title_key(rb)
    found = []
    for folder in FOLDERS[system]:
        if folder not in _index:
            idx = {}
            for p in glob.glob(f'{DB}/{glob.escape(folder)}/*.cht'):
                if not NOT_CHEATS.search(os.path.basename(p)):
                    idx.setdefault(title_key(os.path.basename(p)), []).append(p)
            _index[folder] = idx
        found += _index[folder].get(key, [])
    if not found: return []
    mine = regions(rb)
    for want in ([r for r in ('Europe', 'USA', 'Japan') if r in mine] + ['USA', 'Europe', 'Japan']):
        pick = [p for p in found if want in regions(os.path.basename(p))]
        if pick: break
    else:
        pick = found                                         # lists with no region in the name
    return sorted(pick, key=lambda p: (bool(re.search(r'Game Genie|Action Replay|GameShark|Game Buster|Code Breaker', p)), len(p)))

def emulator(system, rom):
    """The emulator this game launches with: per-game choice, else the console default."""
    stem = re.sub(r'[^A-Za-z0-9]', '_', os.path.basename(rom))
    try:
        for line in open(f'{CFG}/all/emulators.cfg'):
            k, _, v = line.partition('=')
            if k.strip() in (f'{system}_{stem}', f'{system}_{os.path.splitext(os.path.basename(rom))[0]}'):
                return v.strip().strip('"')
    except OSError:
        pass
    default = None; cmds = {}
    for line in open(f'{CFG}/{system}/emulators.cfg'):
        k, _, v = line.partition('=')
        k, v = k.strip(), v.strip().strip('"')
        if k == 'default': default = v
        else: cmds[k] = v
    return cmds.get(default, '')

_names = {}
def core_name(system, rom):
    """RetroArch's name for the core (its cheat folder), read from the core itself."""
    m = re.search(r'-L\s+(\S+\.so)', emulator(system, rom))
    if not m: return None
    so = m.group(1)
    if so not in _names:
        class Info(ctypes.Structure):
            _fields_ = [('library_name', ctypes.c_char_p), ('library_version', ctypes.c_char_p),
                        ('valid_extensions', ctypes.c_char_p), ('need_fullpath', ctypes.c_bool), ('block_extract', ctypes.c_bool)]
        try:
            lib = ctypes.CDLL(so); info = Info(); lib.retro_get_system_info(ctypes.byref(info))
            _names[so] = info.library_name.decode()
        except Exception:
            _names[so] = None
    return _names[so]

def parse(path):
    if path.endswith('.txt'): return parse_gecko(path)
    txt = open(path, errors='replace').read()
    vals = dict(re.findall(r'(?m)^(cheat\d+_(?:desc|code|enable))\s*=\s*"?(.*?)"?\s*$', txt))
    out = []
    i = 0
    while f'cheat{i}_code' in vals or f'cheat{i}_desc' in vals:
        code = vals.get(f'cheat{i}_code', '')
        if code: out.append({'desc': vals.get(f'cheat{i}_desc', '') or code, 'code': code})
        i += 1
    return out

def out_path(system, rom):
    return f'{OUT}/{core_name(system, rom)}/{os.path.splitext(os.path.basename(rom))[0]}.cht'

def enabled(system, rom):
    p = out_path(system, rom)
    return {(c['desc'], c['code']) for c in parse(p)} if os.path.exists(p) else set()

def save(system, rom, chosen):
    p = out_path(system, rom)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not chosen:
        if os.path.exists(p): os.remove(p)
        return
    esc = lambda s: s.replace('"', "'")
    lines = [f'cheats = {len(chosen)}', '']
    for i, c in enumerate(chosen):
        lines += [f'cheat{i}_desc = "{esc(c["desc"])}"', f'cheat{i}_code = "{esc(c["code"])}"', f'cheat{i}_enable = true', '']
    open(p, 'w').write('\n'.join(lines))

FILTERS = [('All', None),
           ('Lives', r'\blives?\b|\bcontinues?\b|\b1-?ups?\b'),
           ('Health', r'health|energy|\bhp\b|hearts?|life bar|invinc|invulner|damage|\bgod\b'),
           ('Weapons & ammo', r'weapon|ammo|arrows?|bombs?|missiles?|bullets?|grenade|sword|gun|shots?|magic|power'),
           ('Money', r'money|rupees?|gold|cash|coins?|\$|points|score|gems?|rings?'),
           ('Items', r'\bitems?\b|have all|have .*key|keys?|inventory|equipment|potion|bottle'),
           ('Switched on', 'ON')]

def cheats_screen(system, rom, name):
    import pygame, retropie_ui as ui
    files = available(system, rom)
    lists = []
    seen = set()
    for f in files:
        for c in parse(f):
            k = (c['desc'], c['code'])
            if k not in seen:
                seen.add(k); c['src'] = os.path.splitext(os.path.basename(f))[0]; lists.append(c)
    on = enabled(system, rom)
    for c in lists: c['on'] = (c['desc'], c['code']) in on
    # cheats switched on earlier that are no longer in the list (keep them)
    for d, code in on - seen: lists.insert(0, {'desc': d, 'code': code, 'on': True, 'src': 'saved'})
    inp = ui.Input(); clock = pygame.time.Clock()
    flt, sel, top, ROWS, changed, msg = 0, 0, 0, 10, False, ''
    while True:
        rx = FILTERS[flt][1]
        shown = [c for c in lists if rx is None or (c['on'] if rx == 'ON' else re.search(rx, c['desc'], re.I))]
        sel = min(sel, max(0, len(shown) - 1))
        for a in inp.read():
            if a == 'up': sel = max(0, sel - 1)
            elif a == 'down': sel = min(len(shown) - 1, sel + 1)
            elif a == 'lb': sel = max(0, sel - ROWS)
            elif a == 'rb': sel = min(len(shown) - 1, sel + ROWS)
            elif a in ('left', 'right'):
                flt = (flt + (1 if a == 'right' else -1)) % len(FILTERS); sel = top = 0
            elif a == 'a' and shown:
                shown[sel]['on'] = not shown[sel]['on']; changed = True; msg = ''
            elif a == 'x':
                for c in lists: c['on'] = False
                changed = True; msg = 'All cheats switched off'
            elif a == 'b':
                if changed:
                    save(system, rom, [c for c in lists if c['on']])
                return sum(c['on'] for c in lists)
        top = min(max(top, sel - ROWS + 1), sel)
        ui.background()
        n_on = sum(c['on'] for c in lists)
        ui.header('CHEATS', name, f'{len(lists)} cheats  -  {n_on} switched on  -  they work the next time you start the game')
        x = ui.px(80); y = ui.px(222)
        for i, (label, _) in enumerate(FILTERS):
            r = ui.text(label, 26, ui.TEXT if i == flt else ui.DIM, (x + ui.px(18), y + ui.px(8)))
            box = r.inflate(ui.px(30), ui.px(14))
            if i == flt:
                ui.pill(box, rad=ui.px(12)); ui.text(label, 26, ui.TEXT, (x + ui.px(18), y + ui.px(8)))
            x = box.right + ui.px(12)
        y += ui.px(72)
        if not shown:
            ui.text('No cheats in this group - press left/right for another group.', 30, ui.DIM, (ui.px(80), y + ui.px(20)))
        for i in range(top, min(len(shown), top + ROWS)):
            c = shown[i]
            r = pygame.Rect(ui.px(80), y, ui.W - ui.px(160), ui.px(58))
            if i == sel: ui.pill(r, rad=ui.px(12))
            else: pygame.draw.rect(ui.screen, ui.PANEL, r, border_radius=ui.px(12))
            tag = pygame.Rect(r.x + ui.px(16), r.y + ui.px(12), ui.px(70), ui.px(34))
            pygame.draw.rect(ui.screen, ui.GOOD if c['on'] else (60, 70, 80), tag, border_radius=ui.px(8))
            ui.text('ON' if c['on'] else 'OFF', 22, (10, 20, 10) if c['on'] else ui.DIM, tag.center, 'center')
            ui.text(c['desc'], 28, ui.TEXT, (r.x + ui.px(110), r.centery), 'midleft', maxw=r.w - ui.px(420))
            ui.text(c['code'][:22], 22, ui.TEXT if i == sel else ui.DIM, (r.right - ui.px(22), r.centery), 'midright')
            y += ui.px(64)
        if lists:
            ui.text(f'{sel + 1} / {len(shown)}', 24, ui.DIM, (ui.W - ui.px(80), ui.px(190)), 'topright')
        ui.text(msg or 'Tip: switch on only a few at a time - some cheats clash or stop a game from loading.', 24,
                ui.GOOD if msg else ui.DIM, (ui.px(80), ui.H - ui.px(130)))
        ui.hints([('A', 'On / off'), ('LEFT/RIGHT', 'Group'), ('LB/RB', 'Page'), ('X', 'All off'), ('B', 'Save & back')])
        pygame.display.flip()
        if ui.SHOT:
            pygame.image.save(ui.screen, ui.SHOT); return 0
        clock.tick(30)
