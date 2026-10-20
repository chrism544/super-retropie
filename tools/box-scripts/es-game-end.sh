#!/bin/bash
# EmulationStation game-end event: close the loading screen, bring runcommand's terminal back
# (minimised by game-start) and make sure the menu stays in front of it.
export DISPLAY=${DISPLAY:-:0}
echo "$(date +%T.%N | cut -c1-12) game-end es-window=$(xdotool search --class emulationstation 2>/dev/null | head -1)" >> /tmp/es-events.log
/usr/local/bin/retropie-launchscreen-hide
for w in $(xdotool search --class xterm 2>/dev/null); do xdotool windowmap "$w"; done
( for d in 0.3 1 2; do
      sleep $d
      es=$(xdotool search --class emulationstation 2>/dev/null | tail -1)
      [ -n "$es" ] && xprop -id "$(xprop -root _NET_ACTIVE_WINDOW | awk '{print $NF}')" WM_CLASS 2>/dev/null | grep -q XTerm &&
          xdotool windowactivate "$es"
  done ) </dev/null >/dev/null 2>&1 &
exit 0
