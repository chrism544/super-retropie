#!/bin/bash
# GameCube artwork under the new names + gameplay videos for famous games (screensaver).
SKY=/opt/retropie/supplementary/skyscraper/Skyscraper
log() { echo "$(date +%T) $*"; }
[ -d /tmp/famous ] || python3 $HOME/find-famous.py --write /tmp/famous
for src in screenscraper thegamesdb; do nice $SKY -p gc -s $src --flags onlymissing,unattend,nohints >/dev/null 2>&1; log "gc art $src done"; done
for f in /tmp/famous/*.txt; do
    s=$(basename $f .txt)
    nice $SKY -p $s -s screenscraper --includefrom $f --flags videos,unattend,nohints >/dev/null 2>&1
    log "$s videos: $(ls ~/.skyscraper/cache/$s/videos/screenscraper 2>/dev/null | wc -l) in cache"
done
cat > /tmp/famous-apply.sh <<EOS
for s in $(ls /tmp/famous | sed "s/.txt//" | tr "\n" " "); do
    G=\$HOME/RetroPie/roms/\$s/gamelist.xml; cp \$G \$G.bak-videos
    python3 /usr/local/bin/retropie-flags save \$G /tmp/flags-\$s.json
    $SKY -p \$s --flags videos,unattend,nohints >/dev/null 2>&1
    python3 /usr/local/bin/retropie-flags restore \$G /tmp/flags-\$s.json
done
python3 \$HOME/curate-gamelists.py arcade --apply >/dev/null 2>&1
/usr/local/bin/retropie-multidisc --hide >/dev/null 2>&1
EOS
[ -n "$SKIP_APPLY" ] || retropie-es-edit bash /tmp/famous-apply.sh
for s in $(ls /tmp/famous | sed "s/.txt//"); do log "$s: $(grep -c "<video>" ~/RetroPie/roms/$s/gamelist.xml) videos, $(grep -c "<game" ~/RetroPie/roms/$s/gamelist.xml) games in list"; done
log done
