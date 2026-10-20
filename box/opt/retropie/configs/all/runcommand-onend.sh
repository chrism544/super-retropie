#!/bin/bash
# Some emulators (standalone mupen64plus) change the screen mode and don't restore it
# (whichever output the TV is on - it moved from HDMI-1 to DP-1 in Oct 2026)
DISPLAY=:0 /usr/local/bin/retropie-display-mode
# Resume any paused RetroPie package build
sudo -n pkill -CONT -f '[R]etroPie-Setup/tmp/build' 2>/dev/null
rm -f /tmp/retropie-manual-request /tmp/retropie-fresh-request; /usr/local/bin/retropie-launchscreen-hide
# keep this launch's log (runcommand's terminal is hidden while games start; read them in
# Game Settings > Advanced: game launch logs). Last 60 kept.
L=$HOME/.local/share/retropie-launch-logs; mkdir -p "$L"
{ printf 'system=%s\nemulator=%s\nrom=%s\nended=%s\n---\n' "$1" "$2" "$3" "$(date '+%F %T')"; cat /dev/shm/runcommand.log 2>/dev/null; } \
    > "$L/$(date +%Y%m%d-%H%M%S).log"
ls -1t "$L"/*.log 2>/dev/null | tail -n +61 | xargs -r rm -f
# keep a dated copy of this game's saves (Save Manager)
python3 /usr/local/bin/retropie-saves snapshot "$3" >/dev/null 2>&1 &
python3 /usr/local/bin/retropie-music resume >/dev/null 2>&1   # menu music back on
python3 /usr/local/bin/retropie-playtime end >/dev/null 2>&1   # play-time stats
