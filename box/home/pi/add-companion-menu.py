#!/usr/bin/env python3
# Adds "Phone Companion" to the RetroPie menu (run with EmulationStation stopped: retropie-es-edit).
import os, shutil, time
MENU = os.path.expanduser('~/RetroPie/retropiemenu')
sh = MENU + '/companion.sh'
open(sh, 'w').write('#!/bin/bash\nexec python3 /usr/local/bin/retropie-companion-ui\n'); os.chmod(sh, 0o755)
ENTRY = ('<game><path>./companion.sh</path><name>Phone Companion</name><desc>Use your phone on the home Wi-Fi to '
         'see what is playing, Play Stats, add games, switch Kid mode and reload the menu. Shows the address, '
         'QR code and PIN.</desc><image>./icons/wifi.png</image><genre>Settings</genre></game>')
done = set()
for gl in (os.path.expanduser('~/.emulationstation/gamelists/retropie/gamelist.xml'),
           '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'):
    real = os.path.realpath(gl)
    if real in done or not os.path.exists(real): continue
    done.add(real)
    x = open(real).read()
    if './companion.sh' in x: print('already in', real); continue
    shutil.copy2(real, real + '.before-companion-' + time.strftime('%Y%m%d-%H%M'))
    open(real, 'w').write(x.replace('</gameList>', ENTRY + '</gameList>', 1))
    print('added to', real)
