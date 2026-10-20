#!/bin/bash
# RetroPie menu > Advanced Settings (also Game Settings > Advanced): the less-used tools taken off the
# main menu. Each one comes back here; B goes back.
M=/home/pi/RetroPie/retropiemenu
rp() { sudo /home/pi/RetroPie-Setup/retropie_packages.sh retropiemenu launch "$1"; }
while true; do
    python3 /usr/local/bin/retropie-advanced
    case $? in
        10) rp /home/pi/RetroPie/retropiemenu-replaced/configedit.rp ;;
        11) python3 /usr/local/bin/retropie-logs ;;
        12) python3 /usr/local/bin/retropie-network ;;
        13) python3 /usr/local/bin/retropie-performance ;;
        14) rp $M/retronetplay.rp ;;
        15) rp $M/rpsetup.rp ;;
        16) python3 /usr/local/bin/retropie-bootscreen-ui ;;
        *) exit 0 ;;
    esac
done
