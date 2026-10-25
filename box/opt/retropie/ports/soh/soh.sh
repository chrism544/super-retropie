#!/bin/bash
# Ship of Harkinian (Ocarina of Time PC port) - EmulationStation > Ports. Oct 2026
# Game data (oot.o2r, oot-mq.o2r) was built from the box's own N64 copies; saves and settings in home/.
S=/opt/retropie/ports/soh
export SHIP_HOME=$S/home DISPLAY=${DISPLAY:-:0}
cd "$SHIP_HOME" || exit 1
python3 $S/pad-quit.py & Q=$!
$S/app/AppRun
kill $Q 2>/dev/null
