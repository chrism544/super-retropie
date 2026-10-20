#!/usr/bin/env python3
"""Bluray theme: give every system box the same long, smooth reflection fade (Oct 2026).

The original boxes faded out too soon (gone at ~72% of the image); the newer high-res boxes
(xbox, wiiu, gc, search) had a solid reflection right to the bottom. Now every reflection starts at
TOP opacity just under the box and fades gradually until the end of the mirrored picture (END).
The reflection's shape comes from mirroring the box's own transparency, so rounded case corners stay.

  fade-reflections.py <preview_dir> [system ...]    write previews only
  fade-reflections.py --apply [system ...]          overwrite the theme images (backup first!)
"""
import glob, os, sys
from PIL import Image

T = '/etc/emulationstation/themes/bluray'
START, END, TOP, CURVE = 0.497, 0.88, 0.50, 1.4

def fade(path):
    orig = Image.open(path)
    # high-res boxes were made without transparency and with an already darkened reflection
    top = TOP if orig.mode == 'RGBA' else 0.85
    im = orig.convert('RGBA')
    w, h = im.size
    a = im.getchannel('A')
    src = a.load()
    new = a.copy(); dst = new.load()
    s, e = int(h * START), int(h * END)
    for y in range(s, h):
        f = max(0.0, 1 - (y - s) / (e - s)) ** CURVE
        my = max(0, 2 * s - y - 2)                     # matching row of the box, mirrored
        for x in range(w):
            dst[x, y] = int(src[x, my] * top * f)
    im.putalpha(new)
    return im

if __name__ == '__main__':
    out, names = sys.argv[1], sys.argv[2:]
    paths = [f'{T}/{n}/_inc/system.png' for n in names] if names else sorted(glob.glob(f'{T}/*/_inc/system.png'))
    for p in paths:
        im = fade(p)
        if out == '--apply':
            im.save(p)
        else:
            os.makedirs(out, exist_ok=True)
            im.save(os.path.join(out, p.split('/')[-3] + '.png'))
    print(len(paths), 'done')
