#!/bin/bash
# Overnight test: GameCube (lr-dolphin) and PS2 (PCSX2) games at 2x resolution, frame rate on screen,
# screenshot after 45 s. Uses throw-away settings - no save states or settings are written.
# Results: /home/pi/hires-test/<system>-<game>.png  (read the FPS / speed counter in the corner)
export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
OUT=/home/pi/hires-test; mkdir -p $OUT
R=/home/pi/RetroPie/roms
while retropie-game-running; do sleep 60; done
python3 /usr/local/bin/retropie-music pause
shot() { xwd -root -silent | python3 -c "
import sys, struct; from PIL import Image
d=sys.stdin.buffer.read(); h=struct.unpack('>25I',d[:100]); hs,w,ht,bpl,nc=h[0],h[4],h[5],h[12],h[19]; off=hs+nc*12
Image.frombuffer('RGBX',(w,ht),d[off:off+bpl*ht],'raw','BGRX',bpl,1).convert('RGB').save(sys.argv[1])" "$1"; }

# --- GameCube at 2x: copy of the core options with dolphin_efb_scale = 2
grep "^dolphin_" /opt/retropie/configs/all/retroarch-core-options.cfg | sed 's/^dolphin_efb_scale = .*/dolphin_efb_scale = "2"/' > /tmp/hires.opt
printf 'fps_show = "true"\nsavestate_auto_save = "false"\nsavestate_auto_load = "true"\ncore_options_path = "/tmp/hires.opt"\ngame_specific_options = "false"\nconfig_save_on_exit = "false"\n' > /tmp/hires.cfg
for g in "Legend of Zelda, The - The Wind Waker (USA).iso" "Super Mario Sunshine (USA).iso" "Luigi's Mansion (USA).iso" \
         "Mario Kart - Double Dash!! (USA).iso" "Super Smash Bros. Melee (USA).iso" "Metroid Prime (USA) (v1.02).iso" \
         "Resident Evil 4 (USA) (Disc 1).gcm"; do
    [ -f "$R/gc/$g" ] || continue
    while retropie-game-running; do sleep 60; done
    timeout -k 10 60 /opt/retropie/emulators/retroarch/bin/retroarch -L /opt/retropie/libretrocores/lr-dolphin/dolphin_libretro.so \
        --config /opt/retropie/configs/gc/retroarch.cfg --appendconfig /tmp/hires.cfg "$R/gc/$g" >/dev/null 2>&1 &
    sleep 45; shot "$OUT/gc-${g%.*}.png"; wait
done

# --- PS2 at 2x: throw-away PCSX2 settings with the speed counter on
for g in "God of War II (USA).chd" "Ratchet & Clank - Up Your Arsenal.chd" "Resident Evil 4 (Europe).chd" \
         "Tekken 5.chd" "Killzone (Spain).chd" "Prince of Persia - The Two Thrones.chd"; do
    [ -f "$R/ps2/$g" ] || continue
    while retropie-game-running; do sleep 60; done
    B=/tmp/pcsx2hires; rm -rf $B; mkdir -p $B; cp -a /home/pi/.config/PCSX2 $B/; I=$B/PCSX2/inis/PCSX2.ini
    sed -i 's/^upscale_multiplier = .*/upscale_multiplier = 2/' $I
    sed -i "/^\[EmuCore\/GS\]/a OsdShowSpeed = true\nOsdShowFPS = true\nOsdShowGPU = true" $I
    XDG_CONFIG_HOME=$B timeout -k 10 70 /opt/retropie/emulators/pcsx2-appimage/app/AppRun -fullscreen -nogui -batch -- "$R/ps2/$g" >/dev/null 2>&1 &
    sleep 60; shot "$OUT/ps2-${g%.*}.png"; wait
    rm -rf $B
done
python3 /usr/local/bin/retropie-music resume
echo "done $(date)" > $OUT/done.txt
