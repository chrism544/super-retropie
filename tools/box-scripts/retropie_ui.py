"""Shared look and controls for the Super RetroPie menu screens (bluray EmulationStation theme).

    import sys; sys.path.insert(0, '/usr/local/lib/retropie'); import retropie_ui as ui
    ui.options_screen('SETTINGS', 'Screensaver', rows, on_change, preview=fn)

rows: list of dicts  {'label', 'choices': [(value, label)], 'value', 'desc'}  or
                     {'label', 'action': callable, 'desc'}           (A runs it)
on_change(row_index, new_value) is called when a value changes; return a message or None.
preview(row_index, value) -> pygame.Surface or None, shown on the right.
"""
import os, sys, time
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame

THEME = '/etc/emulationstation/themes/bluray'
FONT = THEME + '/_inc/fonts/Roboto-Medium.ttf'
ACCENT, ACCENT_LT, TEXT, DIM, PANEL, GOOD, BAD = (17, 106, 157), (64, 170, 230), (247, 247, 247), (150, 165, 180), (14, 22, 32), (90, 200, 120), (230, 110, 110)

pygame.init()
SHOT = os.environ.get('UI_SHOT')
screen = pygame.display.set_mode((1920, 1080)) if SHOT else pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)

try:
    import subprocess as _sp
    _sp.Popen(['bash', '-c', 'sleep 0.4; for w in $(xdotool search --pid %d); do xdotool windowactivate "$w"; done' % os.getpid()],
              stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
except Exception:
    pass
W, H = screen.get_size(); S = H / 1080
def px(v): return int(v * S)
_fonts = {}
def font(n):
    if n not in _fonts:
        _fonts[n] = pygame.font.Font(FONT, px(n)) if os.path.exists(FONT) else pygame.font.SysFont('dejavusans', px(n))
    return _fonts[n]
def text(t, n, c, pos, anchor='topleft', maxw=None):
    f = font(n)
    if maxw and f.size(t)[0] > maxw:
        while t and f.size(t + '…')[0] > maxw: t = t[:-1]
        t += '…'
    s = f.render(t, True, c); r = s.get_rect(**{anchor: pos}); screen.blit(s, r); return r
def pill(r, c=ACCENT, rad=None):
    rad = r.h // 2 if rad is None else rad
    pygame.draw.rect(screen, c, r, border_radius=rad)
    g = pygame.Surface(r.size, pygame.SRCALPHA)
    pygame.draw.rect(g, (255, 255, 255, 45), (0, 0, r.w, r.h // 2), border_radius=rad); screen.blit(g, r.topleft)
def wrap(t, n, w):
    out = []
    for para in t.split('\n'):
        cur = ''
        for word in para.split():
            x = (cur + ' ' + word).strip()
            if font(n).size(x)[0] <= w: cur = x
            else: out.append(cur); cur = word
        out.append(cur)
    return out
try:
    BG = pygame.transform.smoothscale(pygame.image.load(THEME + '/_inc/ingame-global-bg.png').convert(), (W, H))
except Exception:
    BG = None
def background():
    screen.blit(BG, (0, 0)) if BG else screen.fill((0, 0, 0))
def header(section, title, sub=''):
    text(section, 30, ACCENT_LT, (px(80), px(60)))
    text(title, 56, TEXT, (px(80), px(95)))
    if sub: text(sub, 26, DIM, (px(80), px(170)))
def hints(items):
    x = px(80)
    for b, l in items:
        r = pygame.Rect(x, H - px(75), max(px(46), font(22).size(b)[0] + px(24)), px(46)); pill(r)
        text(b, 22, TEXT, r.center, 'center')
        x = text(l, 26, DIM, (r.right + px(12), r.centery), 'midleft').right + px(40)
def message(title, body, seconds=None):
    """Simple full-screen message; returns when a button is pressed (or after seconds)."""
    inp = Input(); end = time.time() + seconds if seconds else None
    while True:
        if any(a in ('a', 'b') for a in inp.read()) or (end and time.time() > end): return
        background(); header('SUPER RETROPIE', title)
        y = px(220)
        for line in wrap(body, 32, W - px(160)):
            text(line, 32, (215, 225, 235), (px(80), y)); y += px(48)
        hints([('A', 'OK')]); pygame.display.flip(); pygame.time.wait(30)

class Input:
    """Controller (and keyboard when no controller) -> actions with auto-repeat."""
    BTN = {0: 'a', 1: 'b', 2: 'x', 3: 'y', 4: 'lb', 5: 'rb', 7: 'start'}
    def __init__(self):
        pygame.joystick.init()
        self.pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        self.ignore = time.time() + 0.6               # the A press that opened the screen
        self.held, self.rep, self.axes = None, 0, {}
    def _dir(self, d, out):
        if d != self.held:
            self.held, self.rep = d, time.time() + 0.45
            if d: out.append(d)
    def read(self):
        out = []
        for e in pygame.event.get():
            if e.type == pygame.QUIT: sys.exit(0)
            if e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                self.pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
            if time.time() < self.ignore: continue
            if e.type == pygame.JOYBUTTONDOWN and e.button in self.BTN:
                out.append(self.BTN[e.button])
            elif e.type == pygame.JOYHATMOTION:
                x, y = e.value
                self._dir('left' if x < 0 else 'right' if x > 0 else 'up' if y > 0 else 'down' if y < 0 else None, out)
            elif e.type == pygame.JOYAXISMOTION and e.axis in (0, 1):
                self.axes[e.axis] = e.value
                x, y = self.axes.get(0, 0), self.axes.get(1, 0)
                d = None
                if max(abs(x), abs(y)) > 0.6:
                    d = ('left' if x < 0 else 'right') if abs(x) > abs(y) else ('up' if y < 0 else 'down')
                self._dir(d, out)
            elif e.type == pygame.KEYDOWN and not self.pads:
                k = {pygame.K_UP: 'up', pygame.K_DOWN: 'down', pygame.K_LEFT: 'left', pygame.K_RIGHT: 'right',
                     pygame.K_RETURN: 'a', pygame.K_ESCAPE: 'b'}.get(e.key)
                if k: out.append(k)
        if self.held and time.time() > self.rep:
            out.append(self.held); self.rep = time.time() + 0.15
        return out

def options_screen(section, title, rows, on_change=None, preview=None, sub='', footer_note=''):
    inp = Input(); sel, msg, top = 0, '', 0
    clock = pygame.time.Clock()
    while True:
        for a in inp.read():
            row = rows[sel]
            if a == 'up': sel = (sel - 1) % len(rows); msg = ''
            elif a == 'down': sel = (sel + 1) % len(rows); msg = ''
            elif a == 'b': return
            elif 'action' in row:
                if a == 'a':
                    msg = row['action']() or ''
                    if msg == 'EXIT': return
            elif a in ('a', 'right', 'left'):
                vals = [v for v, _ in row['choices']]
                i = vals.index(row['value']) if row['value'] in vals else 0
                row['value'] = vals[(i + (-1 if a == 'left' else 1)) % len(vals)]
                if on_change:
                    msg = on_change(sel, row['value']) or ''
        background(); header(section, title, sub)
        y = px(225)
        # long lists (save editor) scroll; short ones are drawn as before
        fit = max(3, (H - px(225) - px(170)) // px(80))
        top = 0 if len(rows) <= fit else min(max(top, sel - fit + 1), sel, len(rows) - fit)
        for i, row in enumerate(rows):
            if i < top or i >= top + fit: continue
            r = pygame.Rect(px(80), y, px(800), px(68))
            if i == sel: pill(r, rad=px(14))
            else: pygame.draw.rect(screen, PANEL, r, border_radius=px(14))
            text(row['label'], 30, TEXT, (r.x + px(28), r.centery), 'midleft')
            if 'choices' in row:
                shown = dict(row['choices']).get(row['value'], str(row['value']))
                text(('‹  ' if i == sel else '') + shown + ('  ›' if i == sel else ''), 28,
                     TEXT if i == sel else ACCENT_LT, (r.right - px(28), r.centery), 'midright')
            y += px(80) + (px(20) if row.get('gap') else 0)
        if len(rows) > fit:
            text(f'{sel + 1} / {len(rows)}', 24, DIM, (px(880), H - px(130)), 'topright')
        row = rows[sel]
        dx = px(960); dw = W - dx - px(80)
        yy = px(225)
        img = preview(sel, row.get('value')) if preview else None
        if img:
            ir = img.get_rect(topleft=(dx, yy)); screen.blit(img, ir)
            pygame.draw.rect(screen, ACCENT, ir.inflate(px(6), px(6)), width=px(3), border_radius=px(6))
            yy = ir.bottom + px(30)
        text(row['label'], 36, ACCENT_LT, (dx, yy)); yy += px(52)
        for line in wrap(row.get('desc', ''), 28, dw):
            text(line, 28, (215, 225, 235), (dx, yy)); yy += px(40)
        if msg:
            for line in wrap(msg, 28, dw):
                text(line, 28, GOOD, (dx, yy + px(20))); yy += px(40)
        if footer_note:
            text(footer_note, 24, DIM, (px(80), H - px(130)))
        hints([('A', 'Change' if 'choices' in row else 'Select'), ('B', 'Back')])
        pygame.display.flip()
        if SHOT:
            pygame.image.save(screen, SHOT); sys.exit(0)
        clock.tick(60)
