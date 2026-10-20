#!/usr/bin/env python3
"""Tidy the DS list (ADVANsCEne names: "0123 Title (EU)(M5).zip"). Only sets hidden flags.

Keeps ONE copy per game: a copy you have saves for, else a favourite, else the best
region (EU > UK > AU > US > other English > multi-language) and the newest version.
Hides demos, and games only released in a language other than English (Japanese,
German-only, ...). Prints counts; --apply writes roms/nds/gamelist.xml.
"""
import os, re, sys, xml.etree.ElementTree as ET

D = os.path.expanduser('~/RetroPie/roms/nds'); BASE = D + '/'
G = D + '/gamelist.xml'
EXT = ('.zip', '.nds', '.7z')
RANK = {'EU': 0, 'UK': 1, 'AU': 2, 'US': 3, 'EN': 4}
NON_EN = {'JP', 'KR', 'CN', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'DK', 'NO', 'FI', 'PT', 'PL', 'RU', 'BR', 'HK', 'TW', 'GR', 'CZ', 'HU'}

def rel(p):
    return p[len(BASE):] if p.startswith(BASE) else p[2:] if p.startswith('./') else p

tree = ET.parse(G) if os.path.exists(G) else ET.ElementTree(ET.Element('gameList'))
root = tree.getroot()
ent = {rel(g.findtext('path') or ''): g for g in root.iter('game')}

files = [f for f in os.listdir(D) if f.lower().endswith(EXT)]
saves = {os.path.splitext(f)[0] for f in os.listdir(D) if f.endswith(('.srm', '.dsv', '.sav', '.state', '.state.auto'))}
saves |= {f.split('.state')[0] for f in os.listdir(D) if '.state' in f}

def info(f):
    stem = os.path.splitext(f)[0]
    name = re.sub(r'^(\d{4}|xxxx)\s+', '', stem)
    tags = re.findall(r'\(([^)]*)\)', name)
    title = re.sub(r'\s*\([^)]*\)', '', name).strip().lower()
    title = re.sub(r'\s+version$', '', title)        # "Pokemon Diamond Version" = "Pokemon Diamond"
    title = re.sub(r'[^a-z0-9]', '', title)
    regions = [t for t in tags if re.fullmatch(r'[A-Z]{2}(,\s*[A-Z]{2})*', t)]
    region = regions[-1].split(',')[0].strip() if regions else '??'
    multi = any(re.fullmatch(r'M\d+', t) for t in tags)
    ver = max([int(m) for t in tags for m in re.findall(r'^v(\d+)$', t)] or [0])
    demo = stem.startswith('xxxx') or any(re.search(r'demo|kiosk|trial|preview', t, re.I) for t in tags)
    return stem, title, region, multi, ver, demo

groups, hide, demos, foreign = {}, set(), 0, 0
for f in files:
    stem, title, region, multi, ver, demo = info(f)
    if demo:
        hide.add(f); demos += 1; continue
    if region in NON_EN and not multi:
        hide.add(f); foreign += 1; continue
    groups.setdefault(title, []).append(f)

def fav(f):
    g = ent.get(f)
    return g is not None and g.findtext('favorite') == 'true'

for title, fs in groups.items():
    def score(f):
        stem, _, region, multi, ver, _ = info(f)
        return (stem not in saves, not fav(f), RANK.get(region, 5 if multi else 6), -ver, f)
    keep = min(fs, key=score)
    hide.update(x for x in fs if x != keep)

# never hide a favourite or a game with saves
hide = {f for f in hide if not fav(f) and os.path.splitext(f)[0] not in saves}
shown = len(files) - len(hide)
print(f"nds: {len(files)} files -> showing {shown}, hiding {len(hide)} "
      f"({demos} demos, {foreign} non-English only, {len(hide) - demos - foreign} duplicates)")

if '--apply' in sys.argv:
    for f in files:
        g = ent.get(f)
        if g is None:
            g = ET.SubElement(root, 'game')
            ET.SubElement(g, 'path').text = './' + f
            ET.SubElement(g, 'name').text = os.path.splitext(f)[0]
            ent[f] = g
        h = g.find('hidden')
        if h is None:
            h = ET.SubElement(g, 'hidden')
        h.text = 'true' if f in hide else 'false'
    ET.indent(tree)
    tree.write(G, encoding='utf-8', xml_declaration=True)
    with open('/tmp/nds-shown.txt', 'w') as fh:
        fh.writelines(os.path.join(D, f) + '\n' for f in files if f not in hide)
    print('gamelist updated; shown list in /tmp/nds-shown.txt')
