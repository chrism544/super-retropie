"""Write settings into RetroArch config files - a console's /opt/retropie/configs/<system>/retroarch.cfg
or a per-game override.

RetroArch keeps the FIRST value it reads for a key, and a console file pulls in the global
all/retroarch.cfg at its #include line - so a setting below that line is ignored whenever the global
file has the same key. These helpers always write above the #include. (Oct 2026: rewind on 15 consoles,
per-console Resume/Smooth choices and some bezel switches had silently done nothing because they were
appended at the end.)

  set_keys(path, {'key': 'value'}, remove=('other_key',))
  lift(path)  -> number of settings moved up from below the #include line
"""
import os, re

KEY = re.compile(r'\s*([a-z0-9_]+)\s*=')
INCLUDE = re.compile(r'#include\s+"')

def _include(lines):
    return next((i for i, l in enumerate(lines) if INCLUDE.match(l)), None)

def _write(path, lines):
    tmp = path + '.tmp'
    open(tmp, 'w').write('\n'.join(lines) + '\n')
    if os.path.exists(path): os.chmod(tmp, os.stat(path).st_mode & 0o777)
    os.replace(tmp, path)

def set_keys(path, updates, remove=()):
    lines = open(path).read().splitlines() if os.path.exists(path) else []
    drop = set(updates) | set(remove)
    kept = [l for l in lines if not ((m := KEY.match(l)) and m.group(1) in drop)]
    new = [f'{k} = "{v}"' for k, v in updates.items()]
    inc = _include(kept)
    _write(path, kept[:inc] + new + kept[inc:] if inc is not None else kept + new)

def lift(path):
    lines = open(path).read().splitlines()
    inc = _include(lines)
    if inc is None: return 0
    tail = [l for l in lines[inc + 1:] if l.strip()]
    below = {m.group(1) for l in tail if (m := KEY.match(l))}                   # the lower copy was written last
    if not below: return 0
    above = [l for l in lines[:inc] if not ((m := KEY.match(l)) and m.group(1) in below)]
    _write(path, above + tail + [lines[inc]])                                  # comments travel with their keys
    return len(below)

if __name__ == '__main__':                  # python3 racfg.py --lift : repair every console file
    import glob, sys
    if '--lift' in sys.argv:
        for f in sorted(glob.glob('/opt/retropie/configs/*/retroarch.cfg')):
            n = lift(f)
            if n: print(f'{f}: {n} settings moved above #include')
