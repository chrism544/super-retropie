#!/bin/bash
# RetroPie menu > Game Settings (themed). Its "Advanced" row (exit 3) opens the Advanced Settings
# screen (advanced.sh - also on the main menu); B there comes back to Game Settings.
while true; do
    python3 /usr/local/bin/retropie-settings
    [ $? -eq 3 ] || exit 0
    bash /home/pi/RetroPie/retropiemenu/advanced.sh
done
