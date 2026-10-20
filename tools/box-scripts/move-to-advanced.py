#!/usr/bin/env python3
# Hides Network, Performance, RetroArch Net Play and RetroPie Setup on the RetroPie menu - they now live
# in Game Settings > Advanced (run with EmulationStation stopped: retropie-es-edit).
import re, shutil, time
GL = '/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml'
MOVED = ('./showip.sh', './performance.sh', './retronetplay.rp', './rpsetup.rp')
s = open(GL).read()
shutil.copy2(GL, GL + '.before-advanced-' + time.strftime('%Y%m%d-%H%M'))
for path in MOVED:
    m = re.search(r'<game>(?:(?!</game>).)*?<path>' + re.escape(path) + r'</path>.*?</game>', s, re.S)
    if not m: print('not found', path); continue
    g = m.group(0)
    if '<hidden>' in g: g2 = re.sub(r'<hidden>[^<]*</hidden>', '<hidden>true</hidden>', g)
    else: g2 = g.replace('</game>', '<hidden>true</hidden></game>')
    s = s[:m.start()] + g2 + s[m.end():]
    print('hidden', path)
# Game Settings' description mentions the new Advanced section
s = re.sub(r'(<path>\./configedit\.sh</path>.*?<desc>)(.*?)(</desc>)',
           lambda m: m.group(1) + ('Common game settings for all consoles or one console. Advanced: game launch logs, '
                                   'network, performance, RetroPie Netplay, RetroPie Setup and every RetroArch setting.') + m.group(3),
           s, count=1, flags=re.S)
open(GL, 'w').write(s)
