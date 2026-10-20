#!/usr/bin/env python3
# Adds "Advanced Settings" to the RetroPie menu, next to Game Settings (run with EmulationStation
# stopped: retropie-es-edit). Safe to run again.
import os, shutil, time
GL = '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'
sh = os.path.expanduser('~/RetroPie/retropiemenu/advanced.sh'); os.chmod(sh, 0o755)
ENTRY = ('<game><path>./advanced.sh</path><name>Advanced Settings</name><desc>Boot Screen, Network, Performance, '
         'RetroArch Net Play, game launch logs, RetroPie Setup and every RetroArch setting.</desc>'
         '<image>./icons/rpsetup.png</image><genre>Settings</genre></game>')
x = open(GL).read()
if './advanced.sh' in x: print('already there')
else:
    shutil.copy2(GL, GL + '.before-advanced-menu-' + time.strftime('%Y%m%d-%H%M'))
    open(GL, 'w').write(x.replace('</gameList>', ENTRY + '</gameList>', 1)); print('added')
