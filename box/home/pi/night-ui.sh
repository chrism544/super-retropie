#!/bin/bash
# Menu changes that need EmulationStation stopped - run by night-check.sh through retropie-es-edit.
#   Game Help menu entry, tidied game lists + new box art (tidy-art.py apply), the 1-file
#   "mame-libretro" tile removed, and the menu opening on Last Played.
cd /home/pi
python3 /home/pi/add-gamehelp-menu.py
python3 /home/pi/tidy-retropie-menu.py
python3 /home/pi/add-surprise-system.py

python3 /home/pi/tidy-art.py apply

# mame-libretro only holds ym2413.zip (a sound-chip ROM, not a game; Arcade has its own copy) and
# loose CHDs that are not game files for ES - moving the zip out removes the empty-looking tile
if [ -f RetroPie/roms/mame-libretro/ym2413.zip ]; then
    mkdir -p RetroPie/BIOS/mame && mv -n RetroPie/roms/mame-libretro/ym2413.zip RetroPie/BIOS/mame/ && echo "mame-libretro tile removed"
fi

# open on the Last Played collection
S=/home/pi/.emulationstation/es_settings.cfg
cp -p $S $S.before-startup-recent
if grep -q 'name="StartupSystem"' $S; then
    sed -i 's|<string name="StartupSystem" value="[^"]*" />|<string name="StartupSystem" value="recent" />|' $S
else
    sed -i 's|</config>|<string name="StartupSystem" value="recent" />\n</config>|' $S
fi
grep StartupSystem $S
