#!/bin/bash
python3 "$HOME/.local/bin/retropie-update-wiiu-keys.py" --if-needed >> "$HOME/RetroPie/BIOS/wiiu/key-update.log" 2>&1 || true
# Cemu fullscreen + pad helper (View+Menu quit, LT+RT keyboard mode).
# If Cemu stops at its "Error" window while starting (usually a missing disc key for a
# .wux/.wud), close it and explain on a themed screen instead of leaving a blank dialog.
D=/opt/retropie/emulators/cemu-appimage
# Default pad for every game = Pro Controller. Cemu deletes controller0.xml when a game
# profile (gameProfiles/<titleid>.ini, e.g. Splatoon -> GamePad) picks another one.
P=$HOME/.config/Cemu/controllerProfiles
[ -f "$P/Xbox as Pro Controller.xml" ] && cp "$P/Xbox as Pro Controller.xml" "$P/controller0.xml"
# right stick up/down = GamePad tilt (Splatoon...). Started first: Cemu asks for it only once, at start
python3 "$D/stick-gyro.py" $$ &
gyro=$!
sleep 0.5
"$D/app/AppRun" -f -g "$1" &
pid=$!
python3 "$D/pad-helper.py" $pid &
watcher=$!
(
    for i in $(seq 1 90); do
        sleep 1
        kill -0 $pid 2>/dev/null || exit 0
        if xdotool search --name "^Error$" >/dev/null 2>&1; then
            touch /tmp/cemu-start-error; kill $pid; sleep 3; kill -9 $pid 2>/dev/null; exit 0
        fi
    done
) &
errwatch=$!
wait $pid
kill $watcher $errwatch $gyro 2>/dev/null
if [ -e /tmp/cemu-start-error ]; then
    rm -f /tmp/cemu-start-error
    name=$(basename "${1%.*}")
    art=$(ls "$(dirname "$1")/media/screenshots/$name".* 2>/dev/null | head -1)
    case "$1" in
        *.wux|*.wud|*.WUX|*.WUD)
            why="This is an encrypted disc copy (.${1##*.}). It needs the key for this exact disc, including its revision (Rev 1, Rev 2 ...), added to keys.txt:\n\n\\\\\\\\10.5.0.19\\\\bios\\\\wiiu\\\\keys.txt" ;;
        *)
            why="Cemu could not load this game file. It may be incomplete or in a format Cemu does not support." ;;
    esac
    /usr/local/bin/retropie-message "Wii U game could not start" "$name\n\n$why" 15 "$art"
fi
