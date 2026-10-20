#!/bin/bash
# RetroPie menu > File Manager: Midnight Commander, which only quits with F10 on a keyboard.
# A small watcher closes it when View + Menu are held on the controller (same as quitting a game).
python3 - $$ <<'PY' &
import glob, os, select, signal, struct, subprocess, sys, time
VIEW, MENU = 6, 7
pads, held = {}, set()
START = time.time()
while True:
    for p in glob.glob('/dev/input/js*'):
        if p not in pads:
            try: pads[p] = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
            except OSError: pass
    r, _, _ = select.select(list(pads.values()), [], [], 1)
    for fd in r:
        try: data = os.read(fd, 512)
        except OSError: continue
        for i in range(0, len(data) - 7, 8):
            _, v, kind, n = struct.unpack('IhBB', data[i:i + 8])
            if kind == 1:
                (held.add if v else held.discard)(n)
    if {VIEW, MENU} <= held:
        subprocess.run(['pkill', '-x', 'mc']); sys.exit(0)
    if subprocess.run(['pgrep', '-x', 'mc'], capture_output=True).returncode and time.time() > START + 5:
        sys.exit(0)
PY
watcher=$!
mc
kill $watcher 2>/dev/null
exit 0
