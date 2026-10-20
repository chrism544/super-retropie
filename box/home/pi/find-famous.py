#!/usr/bin/env python3
"""Find famous games in the visible lists; print 'system<TAB>name<TAB>full path<TAB>has video'.
With --write <dir>: write one Skyscraper include list per system (games still without video)."""
import os, re, sys, xml.etree.ElementTree as ET
R = os.path.expanduser('~/RetroPie/roms')
WANT = {
    'snes': [r'Link to the Past', r'^Super Mario World( \(|$)', r'^Super Mario Kart', r'^Donkey Kong Country( \(|$)',
             r'^Super Metroid', r'^Street Fighter II Turbo', r'^Donkey Kong Country 2', r'Super Mario All.Stars'],
    'n64': [r'Super.Mario.64', r'Ocarina of Time', r'^Mario Kart 64', r'GoldenEye', r'Donkey Kong 64', r'Majora'],
    'megadrive': [r'^Sonic The Hedgehog 2', r'^Sonic The Hedgehog( \(|$)', r'Streets of Rage 2|Bare Knuckle II'],
    'arcade': [r'^(Pac-Man|Puck ?Man)( \(|$)', r'^Donkey Kong \(US set 1', r'^Street Fighter II: The World Warrior',
               r'^Galaga \(', r'^Mortal Kombat \(', r'^Space Invaders( \(|$)'],
    'psx': [r'Crash Bandicoot', r'Final Fantasy VII', r'^Tekken 3', r'Metal Gear Solid', r'Gran Turismo'],
    'gc': [r'Super Smash Bros', r'Wind Waker', r'Mario Kart.*Double', r'Super Mario Sunshine', r"Luigi's Mansion"],
}
JP = re.compile(r'\(J[)V ,]|Japan|^Super Donkey', re.I)
out = {}
for s, pats in WANT.items():
    d = f'{R}/{s}'
    games = [g for g in ET.parse(d + '/gamelist.xml').getroot().iter('game') if g.findtext('hidden') != 'true']
    for p in pats:
        def text(g): return (g.findtext('name') or '') + ' | ' + os.path.basename(g.findtext('path') or '')
        hits = [g for g in games if re.search(p, g.findtext('name') or '', re.I) or
                re.search(p, os.path.basename(g.findtext('path') or ''), re.I)]
        hits.sort(key=lambda g: (bool(JP.search(text(g))), g.findtext('favorite') != 'true', len(g.findtext('name') or '')))
        if not hits:
            print(f'{s}\t-- not found: {p}'); continue
        g = hits[0]
        path = g.findtext('path') or ''
        path = os.path.join(d, path[2:]) if path.startswith('./') else path
        print(f"{s}\t{g.findtext('name')}\t{path}\t{'has video' if g.findtext('video') else ''}")
        if not g.findtext('video'):
            out.setdefault(s, []).append(path)
if '--write' in sys.argv:
    od = sys.argv[sys.argv.index('--write') + 1]; os.makedirs(od, exist_ok=True)
    for s, paths in out.items():
        open(f'{od}/{s}.txt', 'w').write('\n'.join(dict.fromkeys(paths)) + '\n')
