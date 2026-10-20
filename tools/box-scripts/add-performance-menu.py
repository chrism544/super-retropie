#!/usr/bin/env python3
# Adds "Performance" to the RetroPie menu (run with EmulationStation stopped: retropie-es-edit).
import os, shutil, time
MENU = os.path.expanduser('~/RetroPie/retropiemenu')
sh = MENU + '/performance.sh'
open(sh, 'w').write('#!/bin/bash\nexec python3 /usr/local/bin/retropie-performance\n'); os.chmod(sh, 0o755)
ENTRY = ('<game><path>./performance.sh</path><name>Performance</name><desc>Processor power mode (Cool, Standard, or '
         'Performance for faster Xbox, PS2 and Wii games), live temperature and fan speed, and automatic Xbox '
         'emulator updates.</desc><image>/home/pi/RetroPie/retropiemenu/icons/rpsetup.png</image></game>')
done = set()
for gl in (os.path.expanduser('~/.emulationstation/gamelists/retropie/gamelist.xml'),
           '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'):
    real = os.path.realpath(gl)
    if real in done or not os.path.exists(real): continue
    done.add(real)
    x = open(real).read()
    if './performance.sh' in x: print('already in', real); continue
    shutil.copy2(real, real + '.before-performance-' + time.strftime('%Y%m%d-%H%M'))
    open(real, 'w').write(x.replace('</gameList>', ENTRY + '</gameList>', 1))
    print('added to', real)
