#!/usr/bin/env python3
"""Build the file list for copying one system to the new box (runs on the OLD box).

Usage: python3 - <system>   (stdin = this file)
       With /tmp/<system>-keep.txt (curate-gamelists.py <system>, no --apply) only those games
       count as visible; without it, every game not marked hidden in gamelist.xml does.

Copies: visible games, plus any game that has a save
(even if normally hidden, so no save loses its game), all saves, artwork for the
copied games only, and a gamelist with hidden entries removed.

Writes /tmp/<system>-files.lst (NUL separated, relative to /) and /tmp/<system>-gamelist.xml
"""
import os, re, sys, collections
import xml.etree.ElementTree as ET

SYS = sys.argv[1]
HOME = '/home/pi'
ROMS = f'{HOME}/RetroPie/roms/{SYS}'
SAVE = re.compile(r'(\.(srm|sav|mcd|dsv|eep|fla|mpk|sra|rtc|nv)|\.state(\d+|\.auto)?)$', re.I)
ART_DIRS = ('media', 'images')

stem = lambda p: os.path.splitext(p)[0]
gl = os.path.join(ROMS, 'gamelist.xml')
abspath = lambda p: os.path.normpath(p if p.startswith('/') else os.path.join(ROMS, p))

# Every ROM file on disk, keyed by full path without extension
roms_by_stem = {}
saves = []
for d, ds, fs in os.walk(ROMS):
    ds[:] = [x for x in ds if os.path.relpath(os.path.join(d, x), ROMS) not in ART_DIRS]
    for f in fs:
        p = os.path.join(d, f)
        if SAVE.search(f):
            saves.append(p)
        elif f != 'gamelist.xml' and not f.startswith('gamelist.xml'):
            roms_by_stem.setdefault(stem(p), []).append(p)

KEEP = f'/tmp/{SYS}-keep.txt'
if os.path.isfile(KEEP):
    keep = {l.strip() for l in open(KEEP) if l.strip()}
    mode = 'curated'
else:  # everything except what the gamelist hides (a hidden <folder> hides all inside it)
    hidden = set()
    if os.path.isfile(gl):
        for g in ET.parse(gl).getroot():
            if (g.findtext('hidden') or '').strip() == 'true' and g.findtext('path'):
                hidden.add(abspath(g.findtext('path')))
    under = lambda p: any(p == h or p.startswith(h + '/') for h in hidden)
    keep = {p for ps in roms_by_stem.values() for p in ps if not under(p)}
    mode = f'gamelist ({len(hidden)} hidden)'

# Games with a save are copied even if hidden
games = set(keep)
rescued = set()
for s in saves:
    for r in roms_by_stem.get(SAVE.sub('', s), []):
        if r not in games:
            rescued.add(r)
games |= rescued
missing = [g for g in games if not os.path.isfile(g)]
games -= set(missing)

# Gamelist: only copied games, never hidden
art = set()
out = ET.Element('gameList')
dropped = collections.Counter()
if os.path.isfile(gl):
    for g in ET.parse(gl).getroot():
        if g.tag not in ('game', 'folder'):
            continue
        p = abspath(g.findtext('path') or '')
        copied = p in games or (g.tag == 'folder' and any(x.startswith(p + '/') for x in games))
        if not copied:
            dropped['hidden' if (g.findtext('hidden') or '').strip() == 'true' else 'not copied'] += 1
            continue
        for h in g.findall('hidden'):
            g.remove(h)
        for tag in ('image', 'thumbnail', 'marquee', 'video', 'texture'):
            a = g.findtext(tag)
            if a:
                a = abspath(a)
                # Artwork inside Skyscraper's cache (~/.skyscraper -> /opt/retropie/configs) comes
                # with the settings copy; copying it again failed through the new box's symlink
                # ("Invalid cross-device link") and stopped SNES/arcade before their gamelists (Oct 2026)
                if not a.startswith(ROMS + '/'):
                    continue
                if os.path.isfile(a):
                    art.add(a)
        out.append(g)
# Artwork named after a copied game (scraped but not referenced)
names = {os.path.basename(stem(g)) for g in games}
for sub in ART_DIRS:
    for d, ds, fs in os.walk(os.path.join(ROMS, sub)):
        for f in fs:
            if stem(f) in names:
                art.add(os.path.join(d, f))

ET.indent(out, '  ')
ET.ElementTree(out).write(f'/tmp/{SYS}-gamelist.xml', encoding='utf-8', xml_declaration=True)

files = sorted(games) + sorted(saves) + sorted(art)
with open(f'/tmp/{SYS}-files.lst', 'wb') as fh:
    for f in files:
        fh.write(f.lstrip('/').encode() + b'\0')

size = lambda l: sum(os.path.getsize(f) for f in l)
print(f'{SYS} [{mode}]: games {len(games)} ({size(games)/1e9:.2f} GB) incl. {len(rescued)} hidden-but-saved, '
      f'saves {len(saves)}, artwork {len(art)} ({size(art)/1e6:.0f} MB), '
      f'gamelist entries {len(out)} (dropped {dict(dropped)}), missing {len(missing)}')
for r in sorted(rescued):
    print('  kept for its save:', os.path.relpath(r, ROMS))
print(f'TOTAL_FILES={len(files)} TOTAL_BYTES={size(files)}')
