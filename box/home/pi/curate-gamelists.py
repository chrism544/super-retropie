#!/usr/bin/env python3
"""Hide clutter in big EmulationStation game lists (nothing is deleted).

SNES / Mega Drive (GoodTools names): hide hacks, pirates, bad/over/alt dumps,
trainers, betas/protos/demos/samples, public-domain demos, and keep ONE copy
per game (USA > Europe/World > other > Japan). Japan-only games keep the
Japanese original plus the best English fan translation.

Arcade (FinalBurn Neo dat): hide clones, BIOS/device sets, CHD folders and sets
FBNeo can't run; if a parent is missing, keep one clone instead.

Usage: curate-gamelists.py <system> [--apply]
  Without --apply: prints counts and writes keep/hide lists to /tmp only.
  --apply: adds <hidden>true</hidden> entries to roms/<system>/gamelist.xml.
"""
import os, re, sys, collections
import xml.etree.ElementTree as ET

ROMS = os.path.expanduser('~/RetroPie/roms')
FBNEO_DAT = '/opt/retropie/libretrocores/lr-fbneo/dats/FinalBurn Neo (ClrMame Pro XML, Arcade only).dat'
SKIP_EXT = {'.xml', '.txt', '.cfg', '.nfo', '.srm', '.state', '.png', '.jpg'}

# GoodTools junk tags are lowercase ([h1] hack, [t1] trainer...); uppercase [T+Eng] is a translation
JUNK_TAG = re.compile(r'\[(h|b|p|o|t|a)\d*[^\]]*\]')
JUNK_PAREN = re.compile(r'\([^)]*\b(beta|proto|prototype|sample|demo|hack|pirate|pd|trained)\b[^)]*\)', re.I)
JUNK_TITLE = re.compile(r'\b(sample|demo|beta|prototype|trainer|hack)\b|^BS ', re.I)  # "Gunstar Heroes Sample", "Sonic 1 - Mighty Hack", BS-X
# whole folders that are clutter by definition (GoodSNES-style layouts)
JUNK_DIRS = ('betas', 'pd', 'hacks', 'unlicensed-pirate', 'japan/bs-x', 'japan/sufami_turbo', 'snes-arcade',
             'europe/french', 'europe/german', 'europe/italy', 'europe/spain', 'europe/swedish',
             'dutch', 'canada/french')
TRANS = re.compile(r'\[T([+-])([A-Za-z]+)', re.I)
REGION_RANK = {'U': 0, 'USA': 0, 'W': 1, 'WORLD': 1, 'E': 1, 'EUROPE': 1, 'UK': 1,
               'J': 4, 'JAPAN': 4}

def base_title(name):
    t = re.split(r'\s[\(\[]', name, 1)[0]
    return re.sub(r'[^a-z0-9]', '', t.lower())

def region_rank(name):
    ranks = []  # 0 USA, 1 Europe/World, 3 other/unknown, 4 Japan
    for grp in re.findall(r'\(([^)]*)\)', name):
        g = grp.upper().replace(' ', '')
        if re.fullmatch(r'[JUEWKBACFGS]+', g):            # GoodTools letter codes like (JUE)
            ranks += [REGION_RANK.get(c, 3) for c in g]
        else:
            ranks += [REGION_RANK[p] for p in re.split(r'[,/]', g) if p in REGION_RANK]
    return min(ranks) if ranks else 3

def rom_files(system):
    root = os.path.join(ROMS, system)
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != 'media']
        for f in files:
            if os.path.splitext(f)[1].lower() not in SKIP_EXT:
                yield os.path.relpath(os.path.join(d, f), root)

def curate_goodtools(system):
    groups = collections.defaultdict(list)
    keep, hide = [], []
    for rel in rom_files(system):
        name = os.path.basename(rel)
        folder = os.path.dirname(rel).lower().replace(os.sep, '/')
        if any(folder == d or folder.startswith(d + '/') for d in JUNK_DIRS):
            hide.append(rel); continue
        groups[base_title(name)].append(rel)
    for title, rels in groups.items():
        cands, eng = [], []
        for rel in rels:
            n = os.path.basename(rel)
            tr = TRANS.search(n)
            if tr:
                if (tr.group(2).lower().startswith('eng') and not JUNK_TAG.search(n)
                        and not JUNK_PAREN.search(n) and not JUNK_TITLE.search(re.split(r'\s[\(\[]', n, 1)[0])):
                    eng.append(rel)
                continue
            if JUNK_TAG.search(n) or JUNK_PAREN.search(n) or JUNK_TITLE.search(re.split(r'\s[\(\[]', n, 1)[0]):
                continue
            cands.append(rel)
        def score(rel):
            n = os.path.basename(rel)
            lang_variant = 1 if re.search(r'\((french|german|spanish|italian|dutch|swedish|portuguese)', n, re.I) else 0
            return (region_rank(n), lang_variant, 0 if '[!]' in n else 1, 1 if re.search(r'\[f\d*', n) else 0, len(n))
        def tscore(rel):  # newest-style [T+], emulator build over copier build, fewest extra tags
            n = os.path.basename(rel)
            return (0 if '[T+' in n else 1, 0 if '-emu' in n.lower() else 1, n.count('['), len(n))
        chosen = []
        if cands:
            best = min(cands, key=score)
            chosen.append(best)
            if region_rank(os.path.basename(best)) == 4 and eng:      # Japan-only: add English translation
                chosen.append(min(eng, key=tscore))
        elif eng:
            chosen.append(min(eng, key=tscore))
        groups[title] = (rels, chosen)
    # Japanese releases often carry a subtitle, e.g. "Super Mario World - Super Mario Bros. 4 (J)":
    # hide a Japan-only pick when its main title matches a game already kept from another region
    western = {t for t, (_, ch) in groups.items() if any(region_rank(os.path.basename(c)) < 4 for c in ch)}
    for title, (rels, chosen) in groups.items():
        if chosen and all(region_rank(os.path.basename(c)) == 4 for c in chosen if '[T' not in c):
            main = base_title(os.path.basename(chosen[0]).split(' - ')[0])
            if main != title and main in western:
                chosen = []
        keep += chosen
        hide += [r for r in rels if r not in chosen]
    return keep, hide

def curate_arcade(system):
    dat = ET.parse(FBNEO_DAT).getroot()
    info = {}
    for g in dat.iter('game'):
        info[g.get('name')] = (g.get('cloneof'), g.get('isbios') == 'yes' or g.get('isdevice') == 'yes',
                               (g.findtext('description') or ''))
    root = os.path.join(ROMS, system)
    present = {}
    keep, hide = [], []
    for rel in rom_files(system):
        if os.sep in rel:                 # files inside CHD / helper folders
            continue
        present[os.path.splitext(rel)[0]] = rel
    folders = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and d != 'media']
    hide += [d + '/' for d in folders]   # folder entries
    # Group a clone with its parent only when it is the same game (same title before the
    # bracketed region/revision): "Street Fighter II (US 910206)" joins its parent, but
    # "Street Fighter II' - Champion Edition" stays a game of its own.
    title = lambda short: re.split(r'\s*[\(\[]', info[short][2], 1)[0].strip().lower()
    by_game = collections.defaultdict(list)
    for short, rel in present.items():
        if short not in info:
            # Not in the FBNeo list. The arcade default is lr-mame (Oct 2026), which runs many
            # sets FBNeo doesn't, so keep these visible rather than guess.
            keep.append(rel); continue
        clone, isbios, desc = info[short]
        if isbios:
            hide.append(rel); continue
        # Clutter: bootlegs/hacks, and mahjong/quiz/gambling machines (mostly Japanese-only)
        if re.search(r'bootleg|hack|mahjong|mah-jong|quiz|poker|casino|slot|pachi|hanafuda|bingo|roulette', desc, re.I):
            hide.append(rel); continue
        parent = clone if clone in info else short
        by_game[(parent, title(short))].append(short)
    for (parent, _), shorts in by_game.items():
        if parent in shorts:
            pick = parent
        else:  # parent missing: prefer a World/US clone
            pick = min(shorts, key=lambda s: (0 if re.search(r'world|us', info[s][2], re.I) else 1, s))
        keep.append(present[pick])
        hide += [present[s] for s in shorts if s != pick]
    return keep, hide

def apply_hidden(system, hide):
    path = os.path.join(ROMS, system, 'gamelist.xml')
    tree = ET.parse(path) if os.path.exists(path) else ET.ElementTree(ET.Element('gameList'))
    gl = tree.getroot()
    index = {}
    base = os.path.join(ROMS, system) + '/'
    for e in gl:
        p = e.findtext('path') or ''
        # Skyscraper/ES write absolute paths, older lists "./x" - match both, or every
        # hide would add a second entry for the same game
        p = p[len(base):] if p.startswith(base) else p[2:] if p.startswith('./') else p
        index[p.rstrip('/')] = e
    for rel in hide:
        is_folder = rel.endswith('/')
        p = rel.rstrip('/')
        e = index.get(p)
        if e is None:
            e = ET.SubElement(gl, 'folder' if is_folder else 'game')
            ET.SubElement(e, 'path').text = './' + p
            ET.SubElement(e, 'name').text = os.path.splitext(os.path.basename(p))[0]
        h = e.find('hidden')
        if h is None:
            h = ET.SubElement(e, 'hidden')
        h.text = 'true'
    ET.indent(tree)
    tree.write(path, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    system = sys.argv[1]
    keep, hide = curate_arcade(system) if system == 'arcade' else curate_goodtools(system)
    with open(f'/tmp/{system}-keep.txt', 'w') as f:
        f.write('\n'.join(os.path.join(ROMS, system, r) for r in sorted(keep)) + '\n')
    with open(f'/tmp/{system}-hide.txt', 'w') as f:
        f.write('\n'.join(sorted(hide)) + '\n')
    print(f'{system}: visible {len(keep)}, hidden {len(hide)}')
    if '--apply' in sys.argv:
        apply_hidden(system, hide)
        print(f'{system}: gamelist updated')
