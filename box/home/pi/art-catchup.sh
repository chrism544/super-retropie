#!/bin/bash
# DS tidy + artwork catch-up for DS, GameCube, PS2, Wii (Oct 2026).
SKY=/opt/retropie/supplementary/skyscraper/Skyscraper
R=~/RetroPie/roms
log() { echo "$(date +%T) $*"; }
cp $R/nds/gamelist.xml $R/nds/gamelist.xml.bak-before-tidy
# 1. tidy DS and write the artwork already in the cache
retropie-es-edit bash -c "python3 ~/nds-tidy.py --apply; $SKY -p nds --flags unattend,nohints >/dev/null 2>&1; python3 ~/nds-tidy.py --apply" | tail -2
log "DS tidied"
# 2. fetch missing artwork (no need to stop EmulationStation for this)
python3 - > /tmp/nds-need.txt <<"PY"
import os, xml.etree.ElementTree as ET
d = os.path.expanduser("~/RetroPie/roms/nds"); base = d + "/"
art = set()
for g in ET.parse(d + "/gamelist.xml").getroot().iter("game"):
    p = g.findtext("path") or ""; p = os.path.join(d, p[2:]) if p.startswith("./") else p
    if g.findtext("image"): art.add(p)
for l in open("/tmp/nds-shown.txt"):
    if l.strip() not in art: print(l.strip())
PY
log "DS games still without artwork: $(wc -l < /tmp/nds-need.txt)"
for src in screenscraper thegamesdb; do
    nice $SKY -p nds -s $src --includefrom /tmp/nds-need.txt --flags onlymissing,unattend,nohints >/dev/null 2>&1; log "nds $src done"
    for s in gc ps2 wii; do nice $SKY -p $s -s $src --flags onlymissing,unattend,nohints >/dev/null 2>&1; log "$s $src done"; done
done
# 3. write it all into the lists (waits for nobody to be playing)
retropie-es-edit bash -c "for s in nds gc ps2 wii; do $SKY -p \$s --flags unattend,nohints >/dev/null 2>&1; done; python3 ~/nds-tidy.py --apply; /usr/local/bin/retropie-multidisc --hide >/dev/null 2>&1" | tail -1
log "done"
