#!/bin/bash
# GameCube widescreen hack on (fills a 16:9 TV instead of 4:3 with black bars).
while retropie-game-running; do sleep 20; done
F=/opt/retropie/configs/all/retroarch-core-options.cfg
cp $F ~/retroarch-core-options.cfg.bak-widescreen
sed -i "s/^dolphin_widescreen_hack = .*/dolphin_widescreen_hack = \"enabled\"/" $F
grep "^dolphin_widescreen" $F
