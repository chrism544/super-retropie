#!/bin/bash
# Pause any RetroPie package build while a game runs (2-core CPU -> stutter)
sudo -n pkill -STOP -f '[R]etroPie-Setup/tmp/build' 2>/dev/null
python3 /usr/local/bin/retropie-music pause >/dev/null 2>&1   # menu music off while playing
python3 /usr/local/bin/retropie-playtime start "$1" "$3" >/dev/null 2>&1   # play-time stats
