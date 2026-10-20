#!/bin/bash
# RetroPie menu > Game Settings (themed). Its "Advanced" row (exit 3) opens Game Settings > Advanced,
# which holds the less-used tools taken off the main menu; each comes back to Advanced, B goes back.
M=/home/pi/RetroPie/retropiemenu
rp() { sudo /home/pi/RetroPie-Setup/retropie_packages.sh retropiemenu launch "$1"; }
while true; do
    python3 /usr/local/bin/retropie-settings
    [ $? -eq 3 ] || exit 0
    while true; do
        python3 /usr/local/bin/retropie-advanced
        case $? in
            10) rp /home/pi/RetroPie/retropiemenu-replaced/configedit.rp ;;
            11) python3 /usr/local/bin/retropie-logs ;;
            12) python3 /usr/local/bin/retropie-network ;;
            13) python3 /usr/local/bin/retropie-performance ;;
            14) rp $M/retronetplay.rp ;;
            15) rp $M/rpsetup.rp ;;
            *) break ;;
        esac
    done
done
