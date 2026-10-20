#!/usr/bin/env python3
# CRT scanlines (crt-easymode) by default for the 8/16-bit and arcade consoles - the same setting as
# RetroPie menu > Configuration Editor > <console> > Screen effect. Consoles that already have a
# screen effect chosen are left alone. Handhelds and 3D consoles stay clean.
import os, re, sys
sys.path.insert(0, '/usr/local/lib/retropie')
import racfg

SHADER = '/opt/retropie/configs/all/retroarch/shaders/crt/crt-easymode.glslp'
SYSTEMS = ['nes', 'fds', 'snes', 'megadrive', 'mastersystem', 'sg-1000', 'sega32x', 'segacd', 'pcengine',
           'neogeo', 'arcade', 'fba', 'mame-libretro', 'atari2600', 'atari7800', 'coleco']
if not os.path.exists(SHADER): sys.exit(f'missing {SHADER}')
for s in SYSTEMS:
    cfg = f'/opt/retropie/configs/{s}/retroarch.cfg'
    if not os.path.exists(cfg): continue
    if re.search(r'^video_shader\s*=', open(cfg).read(), re.M):
        print(f'{s}: has its own screen effect - left alone'); continue
    racfg.set_keys(cfg, {'video_shader_enable': 'true', 'video_shader': SHADER})
    print(f'{s}: CRT scanlines on')
