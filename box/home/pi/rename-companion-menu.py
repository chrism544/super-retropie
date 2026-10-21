#!/usr/bin/env python3
# Renames the RetroPie menu entry "Phone Companion" to "Control Center" (run with EmulationStation
# stopped: retropie-es-edit). Safe to run again.
GL = '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'
x = open(GL).read()
new = x.replace('<name>Phone Companion</name>', '<name>Control Center</name>').replace(
    'Use your phone on the home Wi-Fi to', 'Super RetroPie Control Center - from a phone, tablet or computer on the home network:')
if new != x: open(GL, 'w').write(new); print('renamed')
else: print('already renamed')
