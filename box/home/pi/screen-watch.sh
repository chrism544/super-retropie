#!/bin/bash
# Logs every screen-mode change (RandR) and every newly mapped full-screen window with a timestamp,
# to find what makes the TV flicker between the menu and games. Output: ~/screen-watch.log
export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
LOG=/home/pi/screen-watch.log
{
  xev -root -event randr | while read -r l; do
      case "$l" in
          *RRScreenChangeNotify*|*RRNotify_CrtcChange*|*RRNotify*) echo "$(date +%T.%N | cut -c1-12) RANDR $l $(xrandr | awk '/ connected/{print $1, $3}')";;
      esac
  done &
  # which program is on screen, sampled 5x a second (only changes are logged)
  last=""
  while :; do
      w=$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null | awk '{print $NF}')
      n=$( [ -n "$w" ] && [ "$w" != "0x0" ] && xprop -id "$w" WM_CLASS 2>/dev/null | cut -d= -f2)
      p=$(pgrep -af "[r]etroarch |[x]emu-appimage/app/usr|[p]csx2|[d]olphin-emu|[m]upen64plus|[f]lycast|[r]etropie-launchscreen|[e]mulationstation --no" | awk '{print $2}' | xargs -n1 basename 2>/dev/null | sort -u | tr "\n" " ")
      cur="window=$n | running=$p"
      [ "$cur" != "$last" ] && echo "$(date +%T.%N | cut -c1-12) $cur" && last=$cur
      sleep 0.2
  done
} >> $LOG 2>&1
