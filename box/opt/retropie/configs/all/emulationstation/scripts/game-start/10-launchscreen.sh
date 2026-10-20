#!/bin/bash
# EmulationStation game-start event: show the console's loading screen at once (the launch screen
# daemon draws it in ~0.1 s) and minimise runcommand's black full-screen terminal so it can't flash
# up while the game starts. Errors runcommand prints there are in the launch logs (Game Settings >
# Advanced: game launch logs). RetroPie menu screens, Search and Surprise Me are left alone.
export DISPLAY=${DISPLAY:-:0}
rom=$(printf '%s' "$1" | sed 's/\\\(.\)/\1/g')   # ES passes the path shell-escaped: "Beyond\ Good\ \&\ Evil"
echo "$(date +%T.%N | cut -c1-12) game-start $rom" >> /tmp/es-events.log
sys=${rom#$HOME/RetroPie/roms/}; sys=${sys%%/*}
case "$sys" in
    retropie|searchgames|surprise|kodi|"$rom")
        for w in $(xdotool search --class xterm 2>/dev/null); do xdotool windowmap "$w"; done
        exit 0 ;;
esac
[ -p /tmp/retropie-launchscreen.fifo ] &&
    timeout 0.5 sh -c 'printf "show\t%s\n" "$1" > /tmp/retropie-launchscreen.fifo' _ "$rom"
for w in $(xdotool search --class xterm 2>/dev/null); do xdotool windowminimize "$w"; done
exit 0
