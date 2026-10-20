#!/usr/bin/env python3
"""Install The Bezel Project artwork for every visible game (Oct 2026).

For each system: shallow-clone the bezel repo, match each visible game to a game bezel
(exact name, else same title - GoodTools "(U) [!]" vs No-Intro "(USA)" naming), copy the
PNG into RetroArch's overlay folder and write a per-game config for every RetroArch core
the system uses. Games without their own art get the console artwork via the system's
retroarch.cfg. Style / brightness come from retropie-bezels (RetroPie menu > Game Artwork).
"""
import os, re, shutil, subprocess, sys, xml.etree.ElementTree as ET

HOME = os.path.expanduser('~')
ROMS = HOME + '/RetroPie/roms'
SRC = HOME + '/bezelproject'
OVL = '/opt/retropie/configs/all/retroarch/overlay'
CFG = '/opt/retropie/configs/all/retroarch/config'
# system -> (repo, overlay subfolder in repo, our overlay folder, RetroArch core names, arcade?)
SYSTEMS = {
    'arcade':    ('bezelproject-MAME', 'ArcadeBezels', 'ArcadeBezels', ['MAME', 'FinalBurn Neo'], True),
    'snes':      ('bezelproject-SNES', 'GameBezels/SNES', 'GameBezels/SNES', ['Snes9x'], False),
    'megadrive': ('bezelproject-MegaDrive', 'GameBezels/MegaDrive', 'GameBezels/MegaDrive', ['Genesis Plus GX', 'PicoDrive'], False),
    'n64':       ('bezelproject-N64', 'GameBezels/N64', 'GameBezels/N64', ['Mupen64Plus-Next', 'Mupen64Plus GLES2', 'ParaLLEl N64'], False),
    'psx':       ('bezelproject-PSX', 'GameBezels/PSX', 'GameBezels/PSX', ['PCSX-ReARMed', 'Beetle PSX', 'Beetle PSX HW', 'SwanStation'], False),
    'dreamcast': ('bezelproject-Dreamcast', 'GameBezels/Dreamcast', 'GameBezels/Dreamcast', ['Flycast'], False),
    'gc':        ('bezelproject-GC', 'GameBezels/GC', 'GameBezels/GC', ['dolphin-emu'], False),
}
REGION = {'U': 'USA', 'E': 'Europe', 'J': 'Japan', 'W': 'World', 'UE': 'USA', 'JU': 'USA', 'JUE': 'USA',
          'NTSC-U': 'USA', 'PAL': 'Europe', 'F': 'France', 'G': 'Germany', 'S': 'Spain', 'I': 'Italy', 'A': 'Australia'}
ONLY = sys.argv[1:] or list(SYSTEMS)

def log(*a): print(*a, flush=True)

def title_key(name):
    t = re.split(r'\s[\(\[]', name, 1)[0].lower()
    t = re.sub(r'^the\s+|,\s*the\b', '', t)
    return re.sub(r'[^a-z0-9]', '', t)

def region_of(name):
    for tag in re.findall(r'\(([^)]*)\)', name):
        for part in re.split(r',\s*', tag):
            if part in REGION.values(): return part
            if part in REGION: return REGION[part]
    return ''

def visible_games(system):
    d = os.path.join(ROMS, system); base = d + '/'
    hidden = set()
    gl = os.path.join(d, 'gamelist.xml')
    if os.path.exists(gl):
        for g in ET.parse(gl).getroot().iter('game'):
            if g.findtext('hidden') == 'true':
                p = g.findtext('path') or ''
                hidden.add(p[len(base):] if p.startswith(base) else p[2:] if p.startswith('./') else p)
    out = []
    for r, ds, fs in os.walk(d):
        ds[:] = [x for x in ds if x not in ('media', 'images') and not x.startswith('.')]
        for f in fs:
            rel = os.path.relpath(os.path.join(r, f), d)
            if rel in hidden or f.endswith(('.xml', '.srm', '.state', '.auto', '.png', '.txt', '.cfg', '.dsv', '.sav', '.bak')) or '.state' in f:
                continue
            out.append(os.path.splitext(f)[0])
    return sorted(set(out))

def clone(repo):
    dst = os.path.join(SRC, repo)
    if not os.path.isdir(dst):
        log(f'  downloading {repo} ...')
        subprocess.run(['git', 'clone', '-q', '--depth', '1', f'https://github.com/thebezelproject/{repo}.git', dst], check=True)
    return dst

def system_png(repo_dir):
    """The console artwork (single PNG directly in retroarch/overlay)."""
    d = os.path.join(repo_dir, 'retroarch', 'overlay')
    pngs = [f for f in os.listdir(d) if f.endswith('.png')]
    return os.path.join(d, pngs[0]) if pngs else None

def write_game_cfg(core, rom, overlay_cfg, arcade):
    os.makedirs(os.path.join(CFG, core), exist_ok=True)
    path = os.path.join(CFG, core, rom + '.cfg')
    keep = []
    if os.path.exists(path):          # keep anything else a game override already sets
        keep = [l for l in open(path).read().splitlines()
                if not re.match(r'(# bezel|input_overlay|aspect_ratio_index)', l)]
    lines = ['# bezel (The Bezel Project) - style set in RetroPie menu > Game Artwork',
             f'input_overlay = "{overlay_cfg}"', 'input_overlay_enable = "true"',
             'input_overlay_opacity = "0.500000"', 'input_overlay_hide_in_menu = "true"']
    if not arcade:
        lines.append('aspect_ratio_index = "0"')   # 4:3 - matches the artwork window
    open(path, 'w').write('\n'.join(lines + keep) + '\n')

total_game = total_sys = 0
for system in ONLY:
    repo, sub, ours, cores, arcade = SYSTEMS[system]
    games = visible_games(system)
    if not games:
        continue
    log(f'{system}: {len(games)} visible games')
    rd = clone(repo)
    src = os.path.join(rd, 'retroarch', 'overlay', sub)
    dst = os.path.join(OVL, ours); os.makedirs(dst, exist_ok=True)
    pngs = {os.path.splitext(f)[0]: f for f in os.listdir(src) if f.endswith('.png')}
    matched = 0
    if arcade:
        # arcade: config/MAME/<set>.cfg -> overlay cfg -> png (clones share the parent's art)
        cmap = {}
        cdir = os.path.join(rd, 'retroarch', 'config', 'MAME')
        for f in os.listdir(cdir):
            m = re.search(r'ArcadeBezels/([^"]+)\.cfg', open(os.path.join(cdir, f), errors='ignore').read())
            if m and m.group(1) in pngs:
                cmap[os.path.splitext(f)[0]] = m.group(1)
        for rom in games:
            art = cmap.get(rom) or (rom if rom in pngs else None)
            if not art:
                continue
            shutil.copy2(os.path.join(src, pngs[art]), os.path.join(dst, pngs[art]))
            for core in cores:
                write_game_cfg(core, rom, os.path.join(dst, art + '.cfg'), True)
            matched += 1
    else:
        by_title = {}
        for n in pngs:
            by_title.setdefault(title_key(n), []).append(n)
        for rom in games:
            art = rom if rom in pngs else None
            if not art:
                cands = by_title.get(title_key(rom), [])
                if cands:
                    reg = region_of(rom)
                    art = min(cands, key=lambda n: (region_of(n) != reg, region_of(n) not in ('Europe', 'USA', 'World'), len(n)))
            if not art:
                continue
            shutil.copy2(os.path.join(src, pngs[art]), os.path.join(dst, pngs[art]))
            for core in cores:
                write_game_cfg(core, rom, os.path.join(dst, art + '.cfg'), False)
            matched += 1
    # console artwork for every other game of this system
    sp = system_png(rd)
    if sp:
        sysdir = os.path.join(OVL, 'SystemBezels'); os.makedirs(sysdir, exist_ok=True)
        target = os.path.join(sysdir, system + '.png'); shutil.copy2(sp, target)
        rc = f'/opt/retropie/configs/{system}/retroarch.cfg'
        txt = [l for l in open(rc).read().splitlines() if not re.match(r'(# bezel|input_overlay|aspect_ratio_index)', l)]
        txt += ['# bezel (console artwork for games without their own) - RetroPie menu > Game Artwork',
                f'input_overlay = "{sysdir}/{system}.cfg"', 'input_overlay_enable = "true"',
                'input_overlay_opacity = "0.500000"', 'input_overlay_hide_in_menu = "true"']
        if not arcade:
            txt.append('aspect_ratio_index = "0"')
        open(rc, 'w').write('\n'.join(txt) + '\n')
        total_sys += 1
    log(f'  {matched} games with their own artwork, {len(games) - matched} use the console artwork')
    total_game += matched

log(f'done: {total_game} games with their own artwork, console artwork for {total_sys} systems')
r = subprocess.run(['/usr/local/bin/retropie-bezels', '--apply'], capture_output=True, text=True)
log('applied style:', r.stdout.strip(), r.stderr.strip()[-300:])
