#!/usr/bin/env python3
"""Controller helper for Cemu (argv[1] = Cemu's pid). Reads /dev/input/js* directly
(xpadneo numbering: A0 B1 X2 Y3 LB4 RB5 View6 Menu7; axes LX0 LY1 LT2 RX3 RY4 RT5,
D-pad = axes 6/7).

  View + Menu   quit the game, back to EmulationStation (Cemu has no such hotkey)
  LT + RT       keyboard mode on/off (View + Y works too). Cemu's on-screen keyboard
                (names in Zelda...) only takes a mouse, and Cemu hides the pointer in
                full screen - so this jumps the (invisible) pointer from key to key and
                the key under it lights up. D-pad / left stick move, A presses the key,
                B leaves keyboard mode. Switches itself off after 60 s without use.
"""
import ctypes, glob, os, select, signal, struct, sys, time

pid = int(sys.argv[1])
A, B, Y, VIEW, MENU = 0, 1, 3, 6, 7
LX, LY, LT, RT, HX, HY = 0, 1, 2, 5, 6, 7

X11 = ctypes.cdll.LoadLibrary('libX11.so.6')
XTST = ctypes.cdll.LoadLibrary('libXtst.so.6')
X11.XOpenDisplay.restype = ctypes.c_void_p
X11.XOpenDisplay.argtypes = [ctypes.c_char_p]
X11.XFlush.argtypes = [ctypes.c_void_p]
X11.XDefaultScreen.argtypes = [ctypes.c_void_p]
X11.XDisplayWidth.argtypes = X11.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
XTST.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
XTST.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
dpy = X11.XOpenDisplay(None)
SW = X11.XDisplayWidth(dpy, X11.XDefaultScreen(dpy)) if dpy else 1920

# Key centres of Cemu 2.6's keyboard, measured at 1920x1080 (it is drawn at a fixed
# size, centred horizontally): 11 keys a row 54.5 px apart, backspace/OK on the right.
OX = SW // 2 - 960
def _row(y, extra=()):
    return [(OX + int(656 + 54.5 * c), y) for c in range(11)] + [(OX + x, y) for x in extra]
KEYS = [_row(456, (1256,)),                  # 1 2 3 4 5 6 7 8 9 0 -  <-
        _row(490), _row(524), _row(558),     # q..p /   a..l : '   z..m , . ? !
        [(OX + 656, 592), (OX + 956, 592), (OX + 1256, 592)]]   # shift, space, OK

def move_to(x, y):
    XTST.XTestFakeMotionEvent(dpy, -1, x, y, 0); X11.XFlush(dpy)
def click(down):
    XTST.XTestFakeButtonEvent(dpy, 1, bool(down), 0); X11.XFlush(dpy)

pads = {}            # path -> (fd, held buttons, axes)
kbd, last_used, row, col = False, 0.0, 1, 0
held_dir, next_rep = None, 0.0

def log(msg):
    print(f"{time.strftime('%T')} {msg}", flush=True)

def show():
    x, y = KEYS[row][col]
    move_to(x, y)

def set_kbd(on):
    global kbd, last_used, row, col
    kbd, last_used = on, time.time()
    log('keyboard mode ' + ('ON' if on else 'off'))
    if on:
        row, col = 1, 0                            # start on "q"
        show()
    else:
        move_to(SW - 1, 0)                         # park the pointer out of the way

def step(d):
    global row, col
    x = KEYS[row][col][0]
    if d in ('up', 'down'):
        row = (row + (-1 if d == 'up' else 1)) % len(KEYS)
        col = min(range(len(KEYS[row])), key=lambda c: abs(KEYS[row][c][0] - x))  # nearest key
    else:
        col = (col + (-1 if d == 'left' else 1)) % len(KEYS[row])
    show()

def direction():
    """Current D-pad / left stick direction over all pads (None if centred)."""
    for _, _, axes in pads.values():
        for ax, ay, dead in ((HX, HY, 16000), (LX, LY, 20000)):
            x, y = axes.get(ax, 0), axes.get(ay, 0)
            if max(abs(x), abs(y)) > dead:
                return ('left' if x < 0 else 'right') if abs(x) > abs(y) else ('up' if y < 0 else 'down')
    return None

while True:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.exit(0)
    for path in glob.glob('/dev/input/js*'):          # controllers can connect mid-game
        if path not in pads:
            try:
                pads[path] = (os.open(path, os.O_RDONLY | os.O_NONBLOCK), set(), {})
            except OSError:
                pass
    ready, _, _ = select.select([p[0] for p in pads.values()], [], [], 0.03 if kbd else 1.0)
    for path, (fd, held, axes) in list(pads.items()):
        if fd not in ready:
            continue
        try:
            data = os.read(fd, 8 * 64)
        except OSError:                                # controller switched off
            os.close(fd); del pads[path]; continue
        for i in range(0, len(data) - 7, 8):
            _, value, kind, number = struct.unpack('IhBB', data[i:i + 8])
            init = kind & 0x80                         # initial state, not a press
            if kind & 0x02:
                axes[number] = value
                if number in (LT, RT) and not init and dpy:
                    # one switch per pull: arm again only once both are let go (they jitter)
                    lt, rt = axes.get(LT, -32767), axes.get(RT, -32767)
                    if lt > 16000 and rt > 16000 and not axes.get('both'):
                        axes['both'] = True
                        set_kbd(not kbd)
                    elif lt < -16000 and rt < -16000:
                        axes['both'] = False
            elif kind & 0x01:
                was = number in held
                (held.add if value else held.discard)(number)
                if init or was == bool(value):
                    continue
                if value and VIEW in held and number == MENU:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(4)
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    sys.exit(0)
                if value and VIEW in held and number == Y and dpy:
                    set_kbd(not kbd)
                elif kbd and number == A:
                    show()                             # make sure ImGui sees the pointer on the key
                    click(value); last_used = time.time()
                elif kbd and number == B and value:
                    set_kbd(False)
    if kbd:
        d = direction()
        now = time.time()
        if d != held_dir:                              # new direction: move once, then repeat
            held_dir = d
            if d:
                step(d); last_used = now; next_rep = now + 0.35
        elif d and now >= next_rep:
            step(d); last_used = now; next_rep = now + 0.12
        if now - last_used > 60:
            set_kbd(False)
