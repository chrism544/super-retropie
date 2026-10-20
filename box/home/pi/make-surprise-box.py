#!/usr/bin/env python3
"""Bluray-theme box for the "Surprise Me" tile, built on the Search box's case (same frame,
reflection and fade): purple starfield, two dice, SURPRISE ME title. Usage: make-surprise-box.py <out.png>"""
import math, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC = '/etc/emulationstation/themes/bluray/searchgames/_inc/system.png'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
case = Image.open(SRC).convert('RGBA')
W, H = case.size
X0, Y0, X1, Y1 = 16, 96, W - 16, 1004                  # artwork area inside the case
aw, ah = X1 - X0, Y1 - Y0
random.seed(7)

art = Image.new('RGB', (aw, ah))
d = ImageDraw.Draw(art)
for y in range(ah):                                     # deep purple -> blue
    t = y / ah
    d.line([(0, y), (aw, y)], fill=(int(40 + 30 * t), int(10 + 25 * t), int(90 + 70 * t)))
glow = Image.new('RGB', (aw, ah)); g = ImageDraw.Draw(glow)
g.ellipse((aw * 0.08, ah * 0.25, aw * 0.92, ah * 0.85), fill=(150, 60, 220))
art = Image.blend(art, glow.filter(ImageFilter.GaussianBlur(90)), 0.45)
d = ImageDraw.Draw(art)
for _ in range(90):                                     # pixel stars
    x, y, s = random.randrange(aw), random.randrange(ah), random.choice((3, 4, 6))
    c = random.choice([(255, 255, 255), (190, 160, 255), (120, 200, 255)])
    d.rectangle((x, y, x + s, y + s), fill=c)
for x, y in ((80, 330), (aw - 120, 300), (110, 760), (aw - 90, 720)):   # sparkles
    for r, w in ((26, 4), (12, 8)):
        d.line((x - r, y, x + r, y), fill=(255, 255, 255), width=w); d.line((x, y - r, x, y + r), fill=(255, 255, 255), width=w)

def die(size, pips, angle, colour=(250, 250, 255)):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); dd = ImageDraw.Draw(im)
    dd.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 6, fill=colour, outline=(120, 90, 200), width=6)
    p = size // 4; r = size // 11
    spots = {1: [(2, 2)], 2: [(1, 1), (3, 3)], 3: [(1, 1), (2, 2), (3, 3)], 4: [(1, 1), (3, 1), (1, 3), (3, 3)],
             5: [(1, 1), (3, 1), (2, 2), (1, 3), (3, 3)], 6: [(1, 1), (3, 1), (1, 2), (3, 2), (1, 3), (3, 3)]}[pips]
    for cx, cy in spots:
        dd.ellipse((cx * p - r, cy * p - r, cx * p + r, cy * p + r), fill=(200, 30, 70) if pips == 1 else (40, 30, 80))
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)

shadow = Image.new('RGBA', (aw, ah), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
sd.ellipse((aw * 0.18, ah * 0.70, aw * 0.85, ah * 0.78), fill=(0, 0, 0, 150))
art = art.convert('RGBA'); art.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(25)))
for size, pips, ang, pos in ((270, 5, 18, (90, 380)), (250, 3, -14, (380, 430))):
    dimg = die(size, pips, ang)
    halo = Image.new('RGBA', dimg.size, (0, 0, 0, 0)); halo.putalpha(dimg.getchannel('A').filter(ImageFilter.GaussianBlur(18)))
    hl = Image.new('RGBA', dimg.size, (170, 120, 255, 0)); hl.putalpha(halo.getchannel('A'))
    art.alpha_composite(hl, pos); art.alpha_composite(dimg, pos)
d = ImageDraw.Draw(art)
def centred(text, size, y, fill, stroke=0, sfill=None):
    f = ImageFont.truetype(BOLD, size)
    w = d.textlength(text, font=f)
    d.text(((aw - w) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
centred('SURPRISE', 128, 40, (255, 255, 255), 6, (90, 40, 170))
centred('ME!', 128, 175, (255, 220, 90), 6, (120, 60, 20))
centred('?', 120, 610, (255, 255, 255, 120))
centred('LET THE BOX PICK A GAME', 40, ah - 100, (225, 215, 255))
art = art.convert('RGB')

out = case.copy()
out.paste(art, (X0, Y0))
# reflection: mirrored artwork, darkened, under the box (alpha = the existing fade)
refl = art.transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: int(v * 0.55))
gap = 2 * int(H * 0.497) - Y1 - 2                       # mirror line used by fade-reflections.py
a = out.getchannel('A')
out.paste(refl, (X0, gap))
out.putalpha(a)
out.save(sys.argv[1])
print('saved', sys.argv[1], out.size)
