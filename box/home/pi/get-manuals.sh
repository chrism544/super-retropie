#!/bin/bash
# Game manuals (PDF, ScreenScraper) for favourites + famous games; written into the lists together
# with the videos. Waits for the famous-videos job so EmulationStation reloads only once.
SKY=/opt/retropie/supplementary/skyscraper/Skyscraper
R=$HOME/RetroPie/roms
while systemctl is-active -q retropie-famous-videos; do sleep 30; done
[ -d /tmp/famous ] || python3 $HOME/find-famous.py --write /tmp/famous
mkdir -p /tmp/manuals
for d in "$R"/*/; do
    s=$(basename "$d"); [ -L "${d%/}" ] && continue
    case $s in retropie|searchgames|ports|wiiu|ps2|nds) continue;; esac
    [ -f "$d/gamelist.xml" ] || continue
    python3 - "$R/$s" > /tmp/manuals/$s.txt <<"PY"
import os, sys, xml.etree.ElementTree as ET
d = sys.argv[1]
for g in ET.parse(d + "/gamelist.xml").getroot().iter("game"):
    if g.findtext("hidden") == "true" or g.findtext("manual"): continue
    if g.findtext("favorite") != "true": continue
    p = g.findtext("path") or ""; p = os.path.join(d, p[2:]) if p.startswith("./") else p
    if os.path.exists(p): print(p)
PY
    [ -f /tmp/famous/$s.txt ] && cat /tmp/famous/$s.txt >> /tmp/manuals/$s.txt
    sort -u -o /tmp/manuals/$s.txt /tmp/manuals/$s.txt
    [ -s /tmp/manuals/$s.txt ] || { rm -f /tmp/manuals/$s.txt; continue; }
    nice $SKY -p $s -s screenscraper --includefrom /tmp/manuals/$s.txt --flags manuals,unattend,nohints >/dev/null 2>&1
    echo "$(date +%T) $s manuals: $(ls $HOME/.skyscraper/cache/$s/manuals/screenscraper 2>/dev/null | wc -l) in cache"
done
cat > /tmp/manuals-apply.sh <<EOS
for s in $(ls /tmp/manuals | sed "s/.txt//" | tr "\n" " "); do
    G=\$HOME/RetroPie/roms/\$s/gamelist.xml; cp \$G \$G.bak-manuals
    python3 /usr/local/bin/retropie-flags save \$G /tmp/flags-\$s.json
    $SKY -p \$s --flags videos,manuals,unattend,nohints >/dev/null 2>&1
    python3 /usr/local/bin/retropie-flags restore \$G /tmp/flags-\$s.json
done
python3 \$HOME/curate-gamelists.py arcade --apply >/dev/null 2>&1
/usr/local/bin/retropie-multidisc --hide >/dev/null 2>&1
EOS
retropie-es-edit bash /tmp/manuals-apply.sh
for s in $(ls /tmp/manuals | sed "s/.txt//"); do echo "$s: $(grep -c "<manual>" $R/$s/gamelist.xml) manuals, $(grep -c "<video>" $R/$s/gamelist.xml) videos"; done
