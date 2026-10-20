#!/usr/bin/env python3
"""Quit the emulator (pid argv[1]) when View + Menu are held on any controller.
Reads /dev/input/js* directly (xpadneo/xpad numbering: View = 6, Menu = 7)."""
import glob, os, select, signal, struct, sys, time
pid, BACK, START = int(sys.argv[1]), 6, 7
pads = {}
while True:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.exit(0)
    for path in glob.glob('/dev/input/js*'):          # controllers can connect mid-game
        if path not in pads:
            try:
                pads[path] = (os.open(path, os.O_RDONLY | os.O_NONBLOCK), set())
            except OSError:
                pass
    ready, _, _ = select.select([fd for fd, _ in pads.values()], [], [], 1.0)
    for path, (fd, held) in list(pads.items()):
        if fd not in ready:
            continue
        try:
            data = os.read(fd, 8 * 64)
        except OSError:                                # controller switched off
            os.close(fd); del pads[path]; continue
        for i in range(0, len(data) - 7, 8):
            _, value, kind, number = struct.unpack('IhBB', data[i:i + 8])
            if kind & 0x01:                            # button (0x80 = initial state)
                (held.add if value else held.discard)(number)
        if BACK in held and START in held:
            os.kill(pid, signal.SIGTERM)
            time.sleep(4)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            sys.exit(0)
