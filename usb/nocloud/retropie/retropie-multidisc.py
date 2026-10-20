#!/usr/bin/env python3
"""One menu entry per multi-disc game (PSX, Dreamcast, Mega-CD, Saturn).

  retropie-multidisc            convert + group every disc system
  retropie-multidisc psx        just one system
  retropie-multidisc --hide     only re-hide disc entries in the game lists (after a scrape)

- PSX .ccd/.img/.sub -> .chd (chdman has no .ccd reader, so a .cue is written for it first);
  originals go to ~/RetroPie/duplicates-removed/converted/<system>/
- Discs named "... (Disc 1)", "CD2", "CD-2", "Disk 3" are moved into <system>/.multidisc/
  (ES hides dot-folders) and "<game>.m3u" lists them; swap discs in RetroArch's Disc Control.
- Disc 1's saves are copied to the .m3u name and its gamelist entry is reused for the .m3u.
- Edits game lists: run through retropie-es-edit (or with EmulationStation stopped).
"""
import os, re, sys, shutil, subprocess, collections, xml.etree.ElementTree as ET

HOME = os.path.expanduser('~pi')
ROMS = f'{HOME}/RetroPie/roms'
AWAY = f'{HOME}/RetroPie/duplicates-removed/converted'
SYSTEMS = ['psx', 'dreamcast', 'segacd', 'saturn']
DISC_EXT = {'.chd', '.cue', '.cdi', '.gdi', '.iso', '.pbp'}
SAVE = re.compile(r'\.(srm|sav|state\d*|state\.auto|auto)$', re.I)
# "(Disc 1)", "CD2", "CD-2", "[Disc1of2]", "PARASITE_EVE_DISC1" (no \b: "_" counts as a letter)
TOKEN = re.compile(r'[\s_-]*[\(\[]?(?<![A-Za-z])(?:disc|disk|cd)[\s_-]*(\d)(?:\s*of\s*\d)?(?!\d)[\)\]]?', re.I)
# per-disc serials differ between discs ("[SLUS-00845]" / "[SLUS-00858]") - ignore them
SERIAL = re.compile(r'\s*[\[\(](?:S[CL][EUPK][SMDA]?|PAPX|PBPX)[-_ ]?\d{3}\.?\d{2}[\]\)]', re.I)
base_of = lambda stem: re.sub(r'\s{2,}', ' ', SERIAL.sub('', TOKEN.sub('', stem))).strip(' -_')
HIDDEN_DIR = '.multidisc'
PLAN = '--plan' in sys.argv   # list what would happen, change nothing
log = lambda *a: print(*a, flush=True)


def chown(p):
    try: shutil.chown(p, 'pi', 'pi')
    except (PermissionError, LookupError): pass


def cue_parts(cue):
    d = os.path.dirname(cue)
    out = []
    for line in open(cue, errors='replace'):
        m = re.match(r'\s*FILE\s+(?:"([^"]+)"|(\S+))', line)
        if m: out.append(os.path.join(d, m.group(1) or m.group(2)))
    return out


def ccd_to_chd(sysdir, s):
    """Convert .ccd/.img(/.sub) sets: write a .cue from the .ccd track table, then chdman."""
    done = 0
    for ccd in sorted(p for p in os.listdir(sysdir) if p.lower().endswith('.ccd')):
        ccd = os.path.join(sysdir, ccd)
        stem = os.path.splitext(ccd)[0]
        img = next((stem + e for e in ('.img', '.IMG', '.bin', '.BIN') if os.path.exists(stem + e)), None)
        chd = stem + '.chd'
        if not img or os.path.exists(chd):
            continue
        if PLAN:
            log(f'  {s}: would convert {os.path.basename(ccd)} -> {os.path.basename(chd)}'); continue
        tracks, cur = [], None
        for line in open(ccd, errors='replace'):
            line = line.strip()
            m = re.match(r'\[TRACK\s+(\d+)\]', line, re.I)
            if m: cur = {'n': int(m.group(1)), 'mode': 2, 'idx': {}}; tracks.append(cur); continue
            if cur is None: continue
            k, _, v = line.partition('=')
            if k.upper() == 'MODE': cur['mode'] = int(v)
            m = re.match(r'INDEX\s+(\d+)', k, re.I)
            if m: cur['idx'][int(m.group(1))] = int(v)
        if not tracks:
            continue
        msf = lambda lba: '%02d:%02d:%02d' % (lba // 4500, lba // 75 % 60, lba % 75)
        mode = {0: 'AUDIO', 1: 'MODE1/2352', 2: 'MODE2/2352'}
        cue = stem + '.ccdconv.cue'
        with open(cue, 'w') as fh:
            fh.write(f'FILE "{os.path.basename(img)}" BINARY\n')
            for t in tracks:
                fh.write(f"  TRACK {t['n']:02d} {mode.get(t['mode'], 'MODE2/2352')}\n")
                for i, lba in sorted(t['idx'].items()):
                    fh.write(f'    INDEX {i:02d} {msf(lba)}\n')
        tmp = chd + '.tmp'
        ok = subprocess.run(['nice', 'chdman', 'createcd', '-i', cue, '-o', tmp, '-f'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 and \
             subprocess.run(['chdman', 'verify', '-i', tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        os.remove(cue)
        if not ok:
            if os.path.exists(tmp): os.remove(tmp)
            log(f'  {s}: could not convert {os.path.basename(ccd)} - left as it is')
            continue
        os.rename(tmp, chd); chown(chd)
        os.makedirs(f'{AWAY}/{s}', exist_ok=True)
        for p in (ccd, img, stem + '.sub', stem + '.SUB'):
            if os.path.exists(p): shutil.move(p, f'{AWAY}/{s}/')
        # saves keep working: the .chd has the same name as the .ccd it replaced
        done += 1
        log(f'  {s}: converted {os.path.basename(ccd)} -> {os.path.basename(chd)}')
    return done


def group_discs(sysdir, s, gl_root):
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(sysdir)):
        p = os.path.join(sysdir, f)
        stem, ext = os.path.splitext(f)
        if not os.path.isfile(p) or ext.lower() not in DISC_EXT:
            continue
        m = TOKEN.search(stem)
        if not m:
            continue
        base = base_of(stem)
        n = int(m.group(1))
        rank = 0 if ext.lower() == '.chd' else 1
        cur = groups[base.casefold()].get(n)
        if cur is None or (rank, len(f)) < cur[0]:
            groups[base.casefold()][n] = ((rank, len(f)), p, base)
    made = 0
    entries = {}
    if gl_root is not None:
        for g in gl_root.findall('game'):
            entries[os.path.normpath(os.path.join(sysdir, g.findtext('path') or ''))] = g
    hidden = os.path.join(sysdir, HIDDEN_DIR)
    for key, discs in groups.items():
        if len(discs) < 2:
            continue
        base = next(iter(discs.values()))[2]
        m3u = os.path.join(sysdir, base + '.m3u')
        if os.path.exists(m3u):
            continue
        if PLAN:
            log(f'  {s}: would make {base}.m3u <- ' + ', '.join(os.path.basename(discs[n][1]) for n in sorted(discs)))
            continue
        os.makedirs(hidden, exist_ok=True); chown(hidden)
        lines, first = [], None
        # every disc file of this game (incl. duplicate rips of the same disc) goes into hiding
        members = [os.path.join(sysdir, f) for f in os.listdir(sysdir)
                   if os.path.isfile(os.path.join(sysdir, f)) and os.path.splitext(f)[1].lower() in DISC_EXT
                   and TOKEN.search(os.path.splitext(f)[0])
                   and base_of(os.path.splitext(f)[0]).casefold() == key]
        chosen = {n: p for n, (_, p, _) in discs.items()}
        for p in members:
            parts = [p] + (cue_parts(p) if p.lower().endswith('.cue') else [])
            for q in parts:
                if os.path.exists(q): shutil.move(q, os.path.join(hidden, os.path.basename(q)))
        for n in sorted(chosen):
            lines.append(f'{HIDDEN_DIR}/{os.path.basename(chosen[n])}')
        first = chosen[min(chosen)]
        with open(m3u, 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        chown(m3u)
        # disc 1's saves -> the .m3u name (never overwrite)
        st1 = os.path.splitext(os.path.basename(first))[0]
        for f in os.listdir(sysdir):
            if f.startswith(st1 + '.') and SAVE.search(f):
                dst = os.path.join(sysdir, base + f[len(st1):])
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(sysdir, f), dst); chown(dst)
        # reuse disc 1's gamelist entry for the .m3u
        if gl_root is not None:
            src = entries.get(os.path.normpath(first))
            new = ET.SubElement(gl_root, 'game')
            if src is not None:
                for c in src:
                    if c.tag not in ('path', 'hidden'):
                        new.append(c)
            ET.SubElement(new, 'path').text = m3u
            if new.find('name') is None or src is None:
                (new.find('name') if new.find('name') is not None else ET.SubElement(new, 'name')).text = base
            else:
                new.find('name').text = TOKEN.sub('', new.find('name').text or base).strip(' -_') or base
        made += 1
        log(f'  {s}: {base}.m3u <- {len(chosen)} discs' + (f' (+{len(members) - len(chosen)} duplicate rips hidden)' if len(members) > len(chosen) else ''))
    return made


def hide_disc_entries(sysdir, gl_root):
    """Disc files inside .multidisc must not show (Skyscraper may list them again)."""
    n = 0
    for g in gl_root.findall('game'):
        p = g.findtext('path') or ''
        if f'/{HIDDEN_DIR}/' in p or p.startswith(f'./{HIDDEN_DIR}/') or p.startswith(f'{HIDDEN_DIR}/'):
            h = g.find('hidden')
            if h is None: h = ET.SubElement(g, 'hidden')
            if h.text != 'true': h.text = 'true'; n += 1
    return n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only_hide = '--hide' in sys.argv
    if '--convert' in sys.argv:   # slow part, no game lists touched - EmulationStation can keep running
        if 'psx' in (args or SYSTEMS):
            ccd_to_chd(os.path.join(ROMS, 'psx'), 'psx')
        return 0
    for s in (args or SYSTEMS):
        sysdir = os.path.join(ROMS, s)
        if not os.path.isdir(sysdir):
            continue
        gl = os.path.join(sysdir, 'gamelist.xml')
        tree = ET.parse(gl) if os.path.exists(gl) else None
        root = tree.getroot() if tree is not None else None
        changed = 0
        if not only_hide:
            if s == 'psx':
                ccd_to_chd(sysdir, s)
            changed += group_discs(sysdir, s, root)
        if root is not None and not PLAN:
            changed += hide_disc_entries(sysdir, root)
            if changed:
                ET.indent(tree, '  ')
                tree.write(gl, encoding='utf-8', xml_declaration=True); chown(gl)
    return 0


if __name__ == '__main__':
    sys.exit(main())
