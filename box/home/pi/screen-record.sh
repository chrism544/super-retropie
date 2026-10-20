#!/bin/bash
# Records the screen (small, 20 fps) for 14 s whenever a game is launched from the menu and 5 s when
# it closes, plus which window is on top every 50 ms - to see what flickers. Files in ~/screen-rec/
export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
D=/home/pi/screen-rec; mkdir -p $D
cls() { local w; w=$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null | awk '{print $NF}'); [ -n "$w" ] && [ "$w" != 0x0 ] && xprop -id "$w" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}'; }
top() { local w; w=$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null | awk '{print $NF}'); [ -n "$w" ] && xprop -id "$w" WM_CLASS 2>/dev/null | awk -F'"' '{print $4}'; }
rec() {   # $1 name, $2 seconds
    ffmpeg -loglevel error -y -f x11grab -framerate 20 -video_size 1920x1080 -i :0 -t "$2" -vf scale=640:-2 -c:v libx264 -preset ultrafast "$D/$1.mp4" &
    local end=$(( $(date +%s%N) + $2 * 1000000000 )) last=""
    while [ "$(date +%s%N)" -lt "$end" ]; do
        t="active=$(cls) top=$(top)"; [ "$t" != "$last" ] && echo "$(date +%T.%N | cut -c1-12) $t" >> "$D/$1.txt" && last=$t
        sleep 0.05
    done; wait
}
prev=$(cls); n=0
while :; do
    c=$(cls)
    if [ "$prev" = emulationstation ] && [ "$c" = XTerm ]; then n=$((n+1)); rec "launch-$n" 14
    elif [ "$c" = XTerm ] && [ -n "$prev" ] && [ "$prev" != emulationstation ] && [ "$prev" != XTerm ] && [ "$prev" != retropie-launchscreen ]; then rec "exit-$n" 5
    fi
    prev=$(cls); sleep 0.05
done
