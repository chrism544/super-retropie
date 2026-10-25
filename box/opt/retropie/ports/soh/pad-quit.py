#!/usr/bin/env python3
"""Ship of Harkinian: hold View + Menu on the controller to quit back to EmulationStation - the
same combo as the RetroArch games (SoH has no controller quit of its own). Run by soh.sh."""
import glob, os, struct, subprocess, time

VIEW, MENU = 6, 7          # Xbox Wireless Controller (xpadneo) joystick buttons


def quit_soh():
    subprocess.run(['pkill', '-TERM', '-f', '[s]oh.elf'])
    time.sleep(3)
    subprocess.run(['pkill', '-KILL', '-f', '[s]oh.elf'])


held = set()
while True:
    js = [j for j in sorted(glob.glob('/dev/input/js*'))
          if 'Xbox' in open('/sys/class/input/%s/device/name' % os.path.basename(j)).read()]
    if not js:
        time.sleep(2)
        continue
    try:
        with open(js[0], 'rb') as f:
            while True:
                t, v, ty, n = struct.unpack('IhBB', f.read(8))
                if ty & 0x01:
                    (held.add if v else held.discard)(n)
                    if {VIEW, MENU} <= held:
                        quit_soh()
                        raise SystemExit
    except OSError:
        held.clear()               # the pad went to sleep - wait for it to come back
        time.sleep(2)
