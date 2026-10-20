#!/usr/bin/env python3
"""Tidy the big game lists and fill in missing box art (Oct 2026).

  tidy-art.py plan            work out what to hide -> ~/tidy-art/<system>-hide.txt (changes nothing)
  tidy-art.py fetch           download box art / screenshots / info for games without them
                              -> ~/tidy-art/stage/<system>/{covers,screenshots,textual}  (ES keeps running)
  tidy-art.py apply           (run with EmulationStation held: retropie-es-edit) import the staged art into
                              Skyscraper's cache, rebuild those game lists, then mark the planned games hidden

Hiding keeps every file - it only sets <hidden>true</hidden>. Skyscraper keeps hidden flags on its nightly
rebuild, but only for games it has data for, so every file gets at least a title in the cache.

Art: libretro-thumbnails (thumbnails.libretro.com, matched by title + region), Wii info from GameTDB
(by disc ID), PS2 descriptions from Wikipedia.
"""
import collections, glob, html, io, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.expanduser('~'))

ROMS = os.path.expanduser('~/RetroPie/roms')
WORK = os.path.expanduser('~/tidy-art')
STAGE = WORK + '/stage'
SKY = '/opt/retropie/supplementary/skyscraper/Skyscraper'
IMPORT = os.path.expanduser('~/.skyscraper/import')
UA = {'User-Agent': 'SuperRetroPie-artwork/1.0 (home RetroPie box)'}
LIBRETRO = {'nds': 'Nintendo - Nintendo DS', 'snes': 'Nintendo - Super Nintendo Entertainment System',
            'megadrive': 'Sega - Mega Drive - Genesis', 'n64': 'Nintendo - Nintendo 64', 'psx': 'Sony - PlayStation',
            'psp': 'Sony - PlayStation Portable', 'ps2': 'Sony - PlayStation 2', 'dreamcast': 'Sega - Dreamcast',
            'gc': 'Nintendo - GameCube', 'wii': 'Nintendo - Wii'}
SYSTEMS = ['nds', 'snes', 'megadrive', 'n64', 'psx', 'psp', 'ps2', 'dreamcast', 'gc', 'wii']
SKIP_EXT = {'.xml', '.txt', '.cfg', '.nfo', '.srm', '.state', '.png', '.jpg', '.auto', '.bak', '.sav', '.dsv', '.pbp', '.cue'}
os.makedirs(WORK, exist_ok=True)

def ext_list(system):
    for s in ET.parse('/etc/emulationstation/es_systems.cfg').getroot().iter('system'):
        if s.findtext('name') == system:
            return {e.lower() for e in (s.findtext('extension') or '').split()}
    return set()

def rom_files(system):
    root = f'{ROMS}/{system}'; exts = ext_list(system)
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ('media', 'User', 'mame2003') and not x.startswith('.')]
        for f in files:
            e = os.path.splitext(f)[1].lower()
            if e in exts and not f.endswith('.state.auto'):
                yield os.path.relpath(os.path.join(d, f), root)

def gamelist(system):
    base = f'{ROMS}/{system}/'
    out = {}
    try:
        for g in ET.parse(base + 'gamelist.xml').getroot().iter('game'):
            p = g.findtext('path') or ''
            p = p[len(base):] if p.startswith(base) else p[2:] if p.startswith('./') else p
            out[p] = g
    except (OSError, ET.ParseError):
        pass
    return out

def stem(rel):
    b = os.path.basename(rel)
    return b[:b.rindex('.')] if '.' in b else b   # Skyscraper completeBaseName: up to the LAST dot

def title_key(name):
    t = re.sub(r'^\d{4}\s+', '', name)                                    # DS release numbers "0001 "
    t = re.sub(r'\[?www\.[^\]\s]+\]?|\bUsa-Fix\b|\bGLOBE\b', ' ', t, flags=re.I)
    t = re.split(r'\s*[\(\[]', t, 1)[0]
    t = re.sub(r'^(.*), (the|a|an)\b', r'\2 \1', t.strip(), flags=re.I)
    t = re.sub(r'\b(ii)\b', '2', t, flags=re.I); t = re.sub(r'\b(iii)\b', '3', t, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', t.lower())

def region_of(name):
    tags = ' '.join(re.findall(r'[\(\[]([^\)\]]*)[\)\]]', name)).upper()
    if re.search(r'\b(EUROPE|EU|E|UK|PAL|EUR)\b', tags): return 'Europe'
    if re.search(r'\b(USA|US|U|NTSC|JU|UE)\b', tags): return 'USA'
    if re.search(r'\b(WORLD|W|JUE)\b', tags): return 'World'
    if re.search(r'\b(JAPAN|JP|J|NTSC-J)\b', tags): return 'Japan'
    return ''

def disc_no(name):
    m = re.search(r'(disc|cd|dvd)[\s\-_]*([0-9])', name, re.I)
    side = re.search(r'\b(claire|leon)\b', name, re.I)                   # Resident Evil 2 has a disc per hero
    return (m.group(2) if m else '') + (side.group(1).lower() if side else '')

# ------------------------------------------------------------------ plan: what to hide
def plan_nds(files, gl):
    """One copy per game, English versions only: EU/UK > US > AU > multi-language; hide demos/kiosks."""
    def rank(n):
        tags = re.findall(r'\(([^)]*)\)', n)
        regions = {t.upper() for t in tags}
        if regions & {'EU', 'UK', 'EUR', 'EUROPE'}: return 0
        if regions & {'US', 'USA'}: return 1
        if regions & {'AU', 'AUS'}: return 2
        if any(re.fullmatch(r'M\d+', t, re.I) for t in tags): return 3
        return 9                                                          # JP / FR / DE / KS ... only
    groups = collections.defaultdict(list)
    hide = []
    for rel in files:
        n = os.path.basename(rel)
        if re.search(r'\b(demo|kiosk|trial)\b', n, re.I): hide.append(rel); continue
        groups[title_key(n)].append(rel)
    for rels in groups.values():
        best = min(rels, key=lambda r: (rank(os.path.basename(r)), '(M' not in r, len(r)))
        if rank(os.path.basename(best)) == 9: hide += rels; continue
        hide += [r for r in rels if r != best]
    return hide

def plan_dupes(files, gl):
    """Same game twice (a tidy '(Region)' copy and a download-site copy): keep the tidy one. Discs stay apart."""
    groups = collections.defaultdict(list)
    for rel in files:
        n = os.path.basename(rel)
        if rel.lower().endswith('.m3u'): continue
        groups[(title_key(n), disc_no(n))].append(rel)
    hide = []
    for rels in groups.values():
        if len(rels) < 2: continue
        def score(r):
            n = os.path.basename(r)
            return ('www' in n.lower() or '[' in n, not re.search(r'\((Europe|USA|World|Japan)', n),
                    region_of(n) not in ('Europe', 'USA', 'World'),
                    not (gl.get(r) is not None and gl[r].findtext('image')), n.upper() == n, len(n))
        best = min(rels, key=score)
        hide += [r for r in rels if r != best]
    return hide

def plan():
    import importlib.util
    spec = importlib.util.spec_from_file_location('curate', os.path.expanduser('~/curate-gamelists.py'))
    curate = importlib.util.module_from_spec(spec); spec.loader.exec_module(curate)
    report = {}
    for s in SYSTEMS:
        files = sorted(rom_files(s)); gl = gamelist(s)
        already = {p for p, g in gl.items() if g.findtext('hidden') == 'true'}
        if s == 'nds': hide = plan_nds(files, gl)
        elif s in ('snes', 'megadrive'): hide = curate.curate_goodtools(s)[1]
        elif s == 'n64': hide = []          # names too mixed to pair safely (e.g. three different Majora's Mask names)
        else: hide = plan_dupes(files, gl)
        hide = sorted(set(h for h in hide if not h.endswith('/')))
        open(f'{WORK}/{s}-hide.txt', 'w').write('\n'.join(hide) + '\n')
        visible = len(set(files) - set(hide) - already)
        report[s] = {'files': len(files), 'hidden_before': len(already & set(files)), 'hide_now': len(set(hide) - already),
                     'visible_after': visible}
        print(f"{s:10} files {len(files):5}  hidden now {len(already & set(files)):5}  newly hidden {len(set(hide) - already):5}  visible after {visible:5}")
    json.dump(report, open(f'{WORK}/plan.json', 'w'), indent=1)

# ------------------------------------------------------------------ fetch: art for visible games that lack it
def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def listing(system, kind):
    cache = f'{WORK}/list-{system}-{kind}.json'
    if os.path.exists(cache): return json.load(open(cache))
    url = f'https://thumbnails.libretro.com/{urllib.parse.quote(LIBRETRO[system])}/{kind}/'
    page = get(url)
    names = [html.unescape(urllib.parse.unquote(h))[:-4] for h in re.findall(r'href="([^"?/]+\.png)"', (page or b'').decode('utf-8', 'replace'))]
    json.dump(names, open(cache, 'w'))
    return names

def best_match(name, index):
    cands = index.get(title_key(name))
    if not cands: return None
    want = region_of(name)
    order = [want, 'Europe', 'USA', 'World', '']
    def score(c):
        r = region_of(c)
        return (order.index(r) if r in order else 5, '(Beta' in c or '(Proto' in c or '(Demo' in c, len(c))
    return min(cands, key=score)

def wii_id(path):
    with open(path, 'rb') as f:
        if path.lower().endswith('.wbfs'): f.seek(0x200)
        return f.read(6).decode('ascii', 'replace')

def wiitdb():
    p = f'{WORK}/wiitdb.xml'
    if not os.path.exists(p):
        z = get('https://www.gametdb.com/wiitdb.zip?LANG=EN')
        open(p, 'wb').write(zipfile.ZipFile(io.BytesIO(z)).read('wiitdb.xml'))
    db = {}
    for g in ET.parse(p).getroot().iter('game'):
        gid = g.findtext('id'); loc = g.find("locale[@lang='EN']")
        if gid and loc is not None:
            d = g.find('date')
            db[gid] = {'title': loc.findtext('title'), 'desc': (loc.findtext('synopsis') or '').strip(),
                       'developer': g.findtext('developer'), 'publisher': g.findtext('publisher'),
                       'genre': (g.findtext('genre') or '').split(',')[0].title(),
                       'players': (g.find('input').get('players') if g.find('input') is not None else ''),
                       'date': (f"{d.get('year')}{(d.get('month') or '1').zfill(2)}{(d.get('day') or '1').zfill(2)}" if d is not None and d.get('year') else '')}
    return db

def wiki_desc(title):
    q = get('https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=8&srsearch=' +
            urllib.parse.quote(title + ' PlayStation 2 video game'))
    try:
        hits = [h['title'] for h in json.loads(q)['query']['search']]
        key = title_key(title)
        # the game's own article ("God of War (2005 video game)"), not the series
        page = next((h for h in hits if title_key(h) == key and 'video game' in h), None) or \
               next((h for h in hits if title_key(h) == key), None) or hits[0]
        s = json.loads(get('https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(page.replace(' ', '_'))))
        return s.get('extract', '')
    except Exception:
        return ''

def textual(info):
    esc = lambda v: html.escape(str(v or ''), quote=False)
    return ('<game>\n' + ''.join(f'  <{k}>{esc(info.get(k2))}</{k}>\n' for k, k2 in
            (('title', 'title'), ('description', 'desc'), ('developer', 'developer'), ('publisher', 'publisher'),
             ('players', 'players'), ('genre', 'genre'), ('releasedate', 'date'))) + '</game>\n')

def fetch(only=None):
    tdb = None
    for s in (only or SYSTEMS):
        files = sorted(rom_files(s)); gl = gamelist(s)
        hide = set(open(f'{WORK}/{s}-hide.txt').read().split('\n')) if os.path.exists(f'{WORK}/{s}-hide.txt') else set()
        st = f'{STAGE}/{s}'
        for k in ('covers', 'screenshots', 'textual'): os.makedirs(f'{st}/{k}', exist_ok=True)
        need_art = [r for r in files if r not in hide and not (gl.get(r) is not None and gl[r].findtext('image')
                    and gl[r].findtext('hidden') != 'true')]
        need_title = [r for r in files if r not in gl]                     # no entry at all -> title only
        idx = {}
        for kind in ('Named_Boxarts', 'Named_Snaps', 'Named_Titles'):
            d = collections.defaultdict(list)
            for n in listing(s, kind): d[title_key(n)].append(n)
            idx[kind] = d
        got = 0
        if s == 'wii' and tdb is None: tdb = wiitdb()
        for rel in need_art:
            n = os.path.basename(rel); b = stem(rel); info = {}
            # title screen stands in for a missing box
            for kind, dest in (('Named_Boxarts', 'covers'), ('Named_Snaps', 'screenshots'), ('Named_Titles', 'covers')):
                if os.path.exists(f'{st}/{dest}/{b}.png'): continue
                m = best_match(n, idx[kind])
                if m:
                    img = get(f'https://thumbnails.libretro.com/{urllib.parse.quote(LIBRETRO[s])}/{kind}/{urllib.parse.quote(m)}.png')
                    if img: open(f'{st}/{dest}/{b}.png', 'wb').write(img); got += kind == 'Named_Boxarts'
                    info.setdefault('title', re.split(r'\s*\(', m, 1)[0])
            if s == 'wii':
                gid = wii_id(f'{ROMS}/{s}/{rel}')
                info.update({k: v for k, v in (tdb.get(gid) or {}).items() if v})
                if not os.path.exists(f'{st}/covers/{b}.png'):
                    for reg in ('EN', 'US', 'JA'):
                        img = get(f'https://art.gametdb.com/wii/cover/{reg}/{gid}.png')
                        if img: open(f'{st}/covers/{b}.png', 'wb').write(img); got += 1; break
            if s == 'ps2' and not info.get('desc'):
                info['desc'] = wiki_desc(info.get('title') or re.split(r'\s*[\(\[]', re.sub(r'\.chd$', '', n), 1)[0])
            if s == 'ps2' or s == 'wii' or rel in need_title:
                info.setdefault('title', re.split(r'\s*[\(\[]', re.sub(r'^\d{4}\s+', '', b), 1)[0].strip())
                open(f'{st}/textual/{b}.xml', 'w').write(textual(info))
        for rel in need_title:                                              # hidden or art-less: title only
            b = stem(rel)
            if not os.path.exists(f'{st}/textual/{b}.xml'):
                open(f'{st}/textual/{b}.xml', 'w').write(textual({'title': re.split(r'\s*[\(\[]', re.sub(r'^\d{4}\s+', '', b), 1)[0].strip()}))
        print(f'{s:10} needed art {len(need_art):5}  covers found {got:5}  titles staged {len(os.listdir(st + "/textual")):5}', flush=True)

# ------------------------------------------------------------------ apply (EmulationStation held stopped)
def apply(only=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location('curate', os.path.expanduser('~/curate-gamelists.py'))
    curate = importlib.util.module_from_spec(spec); spec.loader.exec_module(curate)
    saved = IMPORT + '.saved-' + time.strftime('%Y%m%d-%H%M%S')
    os.rename(IMPORT, saved)
    try:
        for s in (only or SYSTEMS):
            st = f'{STAGE}/{s}'
            if not os.path.isdir(st): continue
            shutil.rmtree(IMPORT, ignore_errors=True); os.makedirs(IMPORT)
            shutil.copy(saved + '/definitions.dat', IMPORT)
            for k in ('covers', 'screenshots', 'textual'): shutil.copytree(f'{st}/{k}', f'{IMPORT}/{k}')
            # the bluray theme shows the screenshot - use the box when there is no screenshot
            for c in os.listdir(f'{IMPORT}/covers'):
                if not os.path.exists(f'{IMPORT}/screenshots/{c}'): shutil.copy(f'{IMPORT}/covers/{c}', f'{IMPORT}/screenshots/{c}')
            gl = f'{ROMS}/{s}/gamelist.xml'
            if os.path.exists(gl): shutil.copy2(gl, gl + '.before-tidy-art')
            r1 = subprocess.run([SKY, '-p', s, '-s', 'import', '--flags', 'unattend,nohints'], cwd='/tmp', capture_output=True, text=True)
            r2 = subprocess.run([SKY, '-p', s, '--flags', 'unattend,nohints'], cwd='/tmp', capture_output=True, text=True)
            hide = [h for h in open(f'{WORK}/{s}-hide.txt').read().split('\n') if h]
            curate.apply_hidden(s, hide)
            print(f'{s}: import rc {r1.returncode}, generate rc {r2.returncode}, hidden {len(hide)}', flush=True)
    finally:
        shutil.rmtree(IMPORT, ignore_errors=True); os.rename(saved, IMPORT)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'plan'
    only = sys.argv[2:] or None
    {'plan': lambda: plan(), 'fetch': lambda: fetch(only), 'apply': lambda: apply(only)}[cmd]()
