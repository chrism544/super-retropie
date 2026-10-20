#!/usr/bin/env python3
# Adds the "Surprise Me" tile next to Search (run with EmulationStation stopped: retropie-es-edit).
import os, shutil, time
CFG = '/etc/emulationstation/es_systems.cfg'
ENTRY = '''  <system>
    <name>surprise</name>
    <fullname>Surprise Me</fullname>
    <path>/home/pi/RetroPie/surprise</path>
    <extension>.sh</extension>
    <command>bash %ROM%</command>
    <platform>surprise</platform>
    <theme>surprise</theme>
  </system>
'''
s = open(CFG).read()
if '<name>surprise</name>' in s:
    print('already there')
else:
    shutil.copy2(CFG, CFG + '.before-surprise-' + time.strftime('%Y%m%d-%H%M'))
    i = s.index('  <system>\n    <name>searchgames</name>')
    open(CFG + '.new', 'w').write(s[:i] + ENTRY + s[i:])
    os.replace(CFG + '.new', CFG)
    print('Surprise Me tile added')
