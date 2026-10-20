#!/usr/bin/env python3
# Adds "Game Help" to the RetroPie menu (run with EmulationStation stopped: retropie-es-edit).
import os, shutil, time
MENU = os.path.expanduser('~/RetroPie/retropiemenu')
sh = MENU + '/gamehelp.sh'
open(sh, 'w').write('#!/bin/bash\nexec python3 /usr/local/bin/retropie-gamehelp\n'); os.chmod(sh, 0o755)
ENTRY = ('<game><path>./gamehelp.sh</path><name>Game Help</name><desc>Where to go next in Zelda - A Link to the Past, '
         'read from your save: next dungeon and how to get there, dungeon checklist and missing items.</desc>'
         '<image>/home/pi/RetroPie/retropiemenu/icons/showip.png</image></game>')
done = set()
for gl in (os.path.expanduser('~/.emulationstation/gamelists/retropie/gamelist.xml'),
           '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'):
    real = os.path.realpath(gl)
    if real in done or not os.path.exists(real): continue
    done.add(real)
    x = open(real).read()
    if './gamehelp.sh' in x: print('already in', real); continue
    shutil.copy2(real, real + '.before-gamehelp-' + time.strftime('%Y%m%d-%H%M'))
    open(real, 'w').write(x.replace('</gameList>', ENTRY + '</gameList>', 1))
    print('added to', real)
