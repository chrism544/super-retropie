#!/bin/bash
# EmulationStation "Search" tile: full-screen search, then run the chosen game.
C=/tmp/retropie-search-choice
rm -f $C
python3 /usr/local/bin/retropie-search-ui
[ -s $C ] || exit 0
IFS=$'\t' read -r sys rom < $C
rm -f $C
exec /opt/retropie/supplementary/runcommand/runcommand.sh 0 _SYS_ "$sys" "$rom"
