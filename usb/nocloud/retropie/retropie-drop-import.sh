#!/bin/bash
# Imports games you drop into \\retropie\drop\<system>\ (your own dumps/rips) into RetroPie.
# Runs every 2 minutes (retropie-drop-import.timer). Log: /var/log/retropie-drop.log
#
# - Waits until a file has been unchanged for 2 minutes and isn't open (copy finished)
# - Disc games (PSX, PS2, Saturn, Dreamcast, Mega-CD): .cue+.bin / .gdi / .iso -> .chd
#   (smaller, one file per disc), verified before the originals are deleted.
#   .zip/.7z for those systems are unpacked first.
# - Everything else is moved as-is (cartridge zips stay zipped - the emulators read them)
# - Never overwrites a game already in roms\<system>; problems go to drop\_failed\<system>
#   with a .why.txt next to the file
# - Reloads EmulationStation afterwards (not while a game is running)
set -uo pipefail
exec 9>/run/retropie-drop-import.lock
flock -n 9 || exit 0

DROP=/home/pi/RetroPie/drop
ROMS=/home/pi/RetroPie/roms
FAILED=$DROP/_failed
WORK=/home/pi/RetroPie/.drop-work
SETTLE=120                 # seconds unchanged before a file counts as fully copied
LOG=/var/log/retropie-drop.log
DISC='psx ps2 saturn dreamcast segacd'
JUNK='txt nfo url jpg jpeg png sfv md5 db ini htm html pdf'

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
age() { echo $(( $(date +%s) - $(stat -c %Y "$1") )); }

# all files exist, unchanged for $SETTLE s, and nobody (Samba) has them open
settled() {
    local f
    for f in "$@"; do
        [ -f "$f" ] && (( $(age "$f") >= SETTLE )) || return 1
    done
    ! lsof -- "$@" >/dev/null 2>&1
}

fail() {  # system reason files...
    local s=$1 why=$2; shift 2
    mkdir -p "$FAILED/$s"
    echo "$why" > "$FAILED/$s/$(basename "$1").why.txt"
    mv -f -- "$@" "$FAILED/$s/"
    chown -R pi:pi "$FAILED"   # runs as root; you must be able to delete these over the share
    log "FAILED $s/$(basename "$1"): $why"
}

place() {  # system file  -> roms/<system>/ (caller has checked it isn't there already)
    local dest="$ROMS/$1/$(basename "$2")"
    mkdir -p "$ROMS/$1"
    mv -- "$2" "$dest" && chown pi:pi "$dest" && log "imported $1/$(basename "$2")" && imported=1 && imported_sys+=("$1")
}

to_chd() {  # system chdman-mode source extra-files...
    local s=$1 mode=$2 src=$3; shift 3
    local out="$WORK/$(basename "${src%.*}").chd"
    rm -f "$out"
    log "converting $s/$(basename "$src") to CHD ($mode)"
    if nice chdman "$mode" -i "$src" -o "$out" >> "$LOG" 2>&1 && chdman verify -i "$out" >/dev/null 2>&1; then
        place "$s" "$out" && rm -f -- "$src" "$@"
    else
        rm -f "$out"
        fail "$s" "chdman $mode failed - see $LOG" "$src" "$@"
    fi
}

disc_parts() {  # tracks referenced by a .cue or .gdi, as full paths
    local dir; dir=$(dirname "$1")
    case "${1,,}" in
        *.cue) tr -d '\r' < "$1" | grep -oP '^\s*FILE\s+(?:"\K[^"]+(?=")|\K\S+)' ;;
        *.gdi) tr -d '\r' < "$1" | awk 'NR > 1 && NF >= 5 { if ($5 ~ /^"/) { match($0, /"[^"]+"/); print substr($0, RSTART+1, RLENGTH-2) } else print $5 }' ;;
    esac | while IFS= read -r p; do echo "$dir/$p"; done
}

mkdir -p "$DROP" "$FAILED" "$WORK"
chown pi:pi "$DROP" "$FAILED"
# One folder per EmulationStation system (+ ps2), created as systems get installed
for s in $( { grep -ohP '<name>\K[^<]+' /etc/emulationstation/es_systems.cfg /opt/retropie/configs/all/emulationstation/es_systems.cfg 2>/dev/null; echo ps2; } | grep -vx retropie | sort -u); do
    [ -d "$DROP/$s" ] || { mkdir -p "$DROP/$s"; chown pi:pi "$DROP/$s"; }
done

imported=0
imported_sys=()
for d in "$DROP"/*/; do
    s=$(basename "$d")
    [ "$s" = _failed ] && continue

    if [[ " $DISC " == *" $s "* ]]; then
        # Unpack archives first (their files keep old timestamps, so they're ready at once)
        while IFS= read -r -d '' a; do
            settled "$a" || continue
            if 7z x -y -o"$d" -- "$a" >/dev/null 2>&1; then log "unpacked $s/$(basename "$a")"; rm -f -- "$a"
            else fail "$s" "could not unpack" "$a"; fi
        done < <(find "$d" -maxdepth 3 -type f \( -iname '*.zip' -o -iname '*.7z' \) -print0)

        # .cue / .gdi / .iso -> .chd
        while IFS= read -r -d '' src; do
            settled "$src" || continue
            if [ -e "$ROMS/$s/$(basename "${src%.*}").chd" ]; then
                mapfile -t parts < <(disc_parts "$src")
                fail "$s" "already in roms/$s" "$src" "${parts[@]}"; continue
            fi
            case "${src,,}" in
                *.iso) if [ "$s" = ps2 ]; then to_chd "$s" createdvd "$src"; else to_chd "$s" createcd "$src"; fi ;;
                *)  mapfile -t parts < <(disc_parts "$src")
                    missing=0; for p in "${parts[@]}"; do [ -f "$p" ] || missing=1; done
                    if (( missing )); then
                        # give a slow copy an hour to deliver the track files
                        (( $(age "$src") > 3600 )) && fail "$s" "track file(s) listed in it are missing" "$src"
                        continue
                    fi
                    settled "${parts[@]}" && to_chd "$s" createcd "$src" "${parts[@]}" ;;
            esac
        done < <(find "$d" -maxdepth 3 -type f \( -iname '*.cue' -o -iname '*.gdi' -o -iname '*.iso' \) -print0)
    fi

    # Everything else: ready-made game files are moved as they are
    while IFS= read -r -d '' f; do
        ext=${f##*.}; ext=${ext,,}
        if [[ " $DISC " == *" $s "* ]] && [[ " bin raw cue gdi iso zip 7z " == *" $ext "* ]]; then
            continue   # still part of a disc set being copied / converted above
        fi
        settled "$f" || continue
        if [[ " $JUNK " == *" $ext "* ]]; then fail "$s" "not a game file - ignored" "$f"; continue; fi
        # GoodTools tags: [b] bad dump, [h] hack, [o] overdump, [t] trainer, [f] fix, [a] alt, [p] pirate
        # (upper-case [T+Eng] translations are kept). Oct 2026: a dropped full set added ~9,600 of these.
        if basename "$f" | grep -qE '\[(b|h|o|t|f|a|p)[0-9]*[^]]*\]|\((Beta|Proto|Prototype|Hack|Sample|Demo)[^)]*\)'; then
            fail "$s" "hack / bad dump / beta - not imported" "$f"; continue
        fi
        # Same file name anywhere in the system (sub)folders = already have it. Oct 2026: a flat
        # copy of a whole set slipped past a same-path check and doubled every game.
        # (exact text compare - names are full of [ ] that find -name would treat as wildcards)
        if find "$ROMS/$s" -type f -printf '%f\n' 2>/dev/null | grep -Fxq -- "$(basename "$f")"; then
            fail "$s" "already in roms/$s" "$f"; continue
        fi
        place "$s" "$f"
    done < <(find "$d" -maxdepth 3 -type f -print0)

    find "$d" -mindepth 1 -type d -empty -delete
done

# Show the new games (EmulationStation rescans its folders when it starts), then fetch their
# artwork - retropie-scrape only looks up games it has nothing for, and reloads ES itself
if (( imported )); then
    # Multi-disc games -> one .m3u entry each (edits game lists, so EmulationStation is held;
    # retropie-es-edit also waits for anyone playing and reloads ES afterwards)
    disc_sys=$(printf '%s\n' "${imported_sys[@]}" | sort -u | grep -xE 'psx|dreamcast|segacd|saturn')
    if [ -n "$disc_sys" ]; then
        retropie-es-edit retropie-multidisc $disc_sys >> "$LOG" 2>&1 && log "multi-disc games grouped ($(echo $disc_sys))"
    elif ! retropie-game-running; then
        pkill -x emulationstatio && log "EmulationStation reloaded"
    fi
    systemctl start --no-block retropie-scrape.service && log "artwork scrape started"
fi
