#!/bin/bash
# Scrape artwork + game info for every system that has games (Skyscraper).
# Runs as pi: nightly 03:30 (retropie-scrape.timer), after drop-folder imports, or by hand:
#   sudo systemctl start retropie-scrape          Log: ~/retropie-scrape.log
#   retropie-scrape snes psx                      (only those systems)
# Report of artwork coverage per system: ~/retropie-scrape-report.txt
#
# 1. Gather (EmulationStation keeps running): only games with nothing in Skyscraper's cache
#    are looked up. Arcade: ArcadeDB first (matches MAME set names), then ScreenScraper.
#    Everything else: ScreenScraper first, then TheGamesDB for whatever it couldn't find.
# 2. Generate: game lists rebuilt from the cache (Skyscraper keeps favourites/hidden/play counts)
#    while EmulationStation is held stopped, so it can't save its old lists over the new ones.
# 3. EmulationStation starts again - never while someone is in a game.
set -uo pipefail
exec 9>/tmp/retropie-scrape.lock
flock -n 9 || { echo "already running"; exit 0; }
exec >> "$HOME/retropie-scrape.log" 2>&1

SKY=/opt/retropie/supplementary/skyscraper/Skyscraper
ROMS=$HOME/RetroPie/roms

FLAGS=unattend,nohints
log() { echo "[$(date '+%F %T')] $*"; }

sources() {
    case $1 in
        arcade|fba|mame-*|neogeo|naomi|atomiswave) echo "arcadedb screenscraper" ;;
        *) echo "screenscraper thegamesdb" ;;
    esac
}

# Systems with at least one game file (not just artwork / gamelist / saves)
has_games() {
    find "$1" -path "$1/media" -prune -o -type f ! -name 'gamelist.xml*' ! -iname '*.srm' \
        ! -iname '*.state*' ! -iname '*.png' ! -iname '*.jpg' -print -quit | grep -q .
}
if (( $# )); then
    systems=("$@")
else
    systems=()
    for d in "$ROMS"/*/; do
        s=$(basename "$d"); [ -L "${d%/}" ] || [ "$s" = retropie ] && continue
        has_games "$d" && systems+=("$s")
    done
fi
log "start: ${systems[*]}"

# 1. Gather
for s in "${systems[@]}"; do
    for src in $(sources "$s"); do
        log "gather $s from $src"
        nice "$SKY" -p "$s" -s "$src" --flags "onlymissing,$FLAGS" >/dev/null 2>&1 \
            || log "  $s/$src: finished with errors (platform not covered, or daily limit reached)"
    done
done

# 2. Generate, with EmulationStation held stopped (wait for anyone playing to finish first)
while retropie-game-running; do sleep 60; done
touch /tmp/es-hold                     # openbox autostart waits while this exists
pkill -TERM -x emulationstatio && for i in $(seq 1 20); do pgrep -x emulationstatio >/dev/null || break; sleep 1; done
for s in "${systems[@]}"; do
    log "generate $s"
    "$SKY" -p "$s" --flags "$FLAGS" >/dev/null 2>&1 || log "  $s: generate failed"
done
# Skyscraper may list the single discs behind a multi-disc .m3u again - hide them
/usr/local/bin/retropie-multidisc --hide || log "  multi-disc hide failed"
# Keep arcade tidy (BIOS sets, bootlegs, mahjong/quiz) - hidden flags survive, but re-apply anyway
[ -x "$HOME/curate-gamelists.py" ] && [[ " ${systems[*]} " == *" arcade "* ]] && python3 "$HOME/curate-gamelists.py" arcade --apply >/dev/null

# 3. Start EmulationStation with the new lists. An autostart loop that doesn't know es-hold
#    restarts ES straight away with the old lists - kill -9 that one so it can't save them.
pgrep -x emulationstatio >/dev/null && stale=1 || stale=0
rm -f /tmp/es-hold
(( stale )) && pkill -9 -x emulationstatio

# Report: how many games have artwork, per system
{
    echo "Artwork coverage - $(date '+%F %T')"
    printf '%-14s %7s %9s %8s\n' system games artwork missing
    for d in "$ROMS"/*/; do
        s=$(basename "$d"); g="$d/gamelist.xml"; [ -f "$g" ] || continue
        n=$(grep -c '<game' "$g"); a=$(grep -c '<image>' "$g")
        (( n )) && printf '%-14s %7d %9d %8d\n' "$s" "$n" "$a" $((n - a))
    done
} > "$HOME/retropie-scrape-report.txt"
log "done - report in ~/retropie-scrape-report.txt"
