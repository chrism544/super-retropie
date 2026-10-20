#!/bin/bash
set -e
# Wait for the player to finish; EmulationStation saves changed games on exit.
while pgrep -x 'retroarch|PPSSPPSDL|mupen64plus|pcsx2-qt|pcsx2|dolphin-emu|dolphin-emu-qt|flycast|redream' >/dev/null; do
 sleep 10
done
sleep 3
pkill -TERM -x emulationstatio || true
echo 'EmulationStation refresh requested'
