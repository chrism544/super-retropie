#!/bin/bash
# Overnight game check: boots every Xbox game for 90 s, and Crazy Taxi with the Dreamcast BIOS
# skipped (flycast HLE BIOS) plus Crazy Taxi 2 for comparison. Screenshots at 45 s and 85 s.
# Sound is muted while it runs; no save states or settings are written.
# Results: ~/night-check/results.json (shown on Play Stats > Problems) and ~/night-check/*.png
export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority XDG_RUNTIME_DIR=/run/user/$(id -u)
OUT=/home/pi/night-check; mkdir -p $OUT; rm -f $OUT/*.png $OUT/*.txt
R=/home/pi/RetroPie/roms
RA=/opt/retropie/emulators/retroarch/bin/retroarch
while retropie-game-running; do sleep 60; done

# Menu changes (need EmulationStation stopped): Game Help, tidied lists + box art, no mame-libretro
# tile, open on Last Played. Waits for the box-art download to finish first.
while systemctl is-active -q retropie-tidy-fetch; do sleep 60; done
while retropie-game-running; do sleep 60; done
shot() {   # ffmpeg grab (xwd output here is packed 24-bit and came out squashed to 3/4 width)
    ffmpeg -loglevel error -f x11grab -video_size "$(xdpyinfo | awk '/dimensions:/{print $2}')" -i :0.0 -frames:v 1 -y /tmp/nc-shot.png &&
    python3 -c "
import sys; from PIL import Image, ImageStat
im=Image.open('/tmp/nc-shot.png').convert('RGB'); im.resize((960,540)).save(sys.argv[1])
st=ImageStat.Stat(im.convert('L')); print(round(st.mean[0],1), round(st.stddev[0],1))" "$1"; }

retropie-es-edit bash /home/pi/night-ui.sh >> $OUT/log.txt 2>&1
sleep 60
shot "$OUT/menu-after.png" >/dev/null

python3 /usr/local/bin/retropie-music pause
SINK=$(pactl get-default-sink 2>/dev/null); pactl set-sink-mute "$SINK" 1 2>/dev/null

RES=$OUT/results.tsv; : > $RES
# busiest single thread over 10 s, in % of one core (an emulator at ~100% can't keep full speed)
busiest() { top -b -H -n 2 -d 10 | awk '/^top -/{n++} n==2 && $1 ~ /^[0-9]+$/ {print int($9); exit}'; }
# run <label> <seconds> <command...>: start, screenshot twice, note whether it was still running
run() {
    local label=$1 secs=$2; shift 2
    while retropie-game-running; do sleep 60; done
    local t0=$(date +%s)
    timeout -k 10 $secs "$@" >/dev/null 2>&1 &
    local pid=$!
    sleep 45; local a=$(shot "$OUT/$label-45s.png")
    sleep $((secs - 62)); local c=$(busiest)
    local b=$(shot "$OUT/$label-end.png")
    kill -0 $pid 2>/dev/null && alive=1 || alive=0
    wait $pid; local ran=$(( $(date +%s) - t0 ))
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$alive" "$ran" "$a" "$b" "$c" >> $RES
    LASTCPU=$c
    sleep 5
}

# --- Xbox: every game, with the box's normal xemu settings (2x, widescreen, 480p)
for g in "$R"/xbox/*.iso "$R"/xbox/*.xiso; do
    [ -f "$g" ] || continue
    n=$(basename "$g"); n=${n%%.xiso*}; n=${n%.iso}
    PG=/opt/retropie/configs/xbox/per-game-scale.cfg
    if grep -qiF "$n" "$PG" 2>/dev/null || awk -F' *= *' -v g="$(basename "$g")" '!/^#/ && NF==2 && index(tolower(g), tolower($1)) {f=1} END{exit !f}' "$PG"; then
        cfg=/tmp/nc-xemu.toml; read -r sc rd < <(awk -F' *= *' -v g="$(basename "$g")" '!/^#/ && NF==2 && index(tolower(g), tolower($1)) {print $2; exit}' "$PG")
        xemu-set-scale /home/pi/.local/share/xemu/xemu/xemu.toml $cfg "$sc" "$rd"; tag=" (own settings: $sc ${rd:-vulkan})"
    else
        cfg=/home/pi/.local/share/xemu/xemu/xemu.toml; tag=""
    fi
    run "xbox-$n$tag" 90 /opt/retropie/emulators/xemu-appimage/app/AppRun -config_path $cfg -full-screen -dvd_path "$g"
    if [ -z "$tag" ] && [ "${LASTCPU:-0}" -ge 95 ]; then
        first=$LASTCPU
        xemu-set-scale /home/pi/.local/share/xemu/xemu/xemu.toml /tmp/nc-xemu.toml 1 opengl
        run "xbox-$n (1x OpenGL)" 90 /opt/retropie/emulators/xemu-appimage/app/AppRun -config_path /tmp/nc-xemu.toml -full-screen -dvd_path "$g"
        if [ "${LASTCPU:-100}" -le $((first - 5)) ]; then
            echo "$n = 1 opengl" >> "$PG"; echo "xbox $n: 2x Vulkan ${first}% -> 1x OpenGL ${LASTCPU}%, saved" >> $OUT/log.txt
        fi
    fi
done

# --- Crazy Taxi with the Dreamcast start-up skipped (throw-away core options)
sed 's/^reicast_hle_bios = .*/reicast_hle_bios = "enabled"/' /opt/retropie/configs/all/retroarch-core-options.cfg > /tmp/nc-hle.opt
printf 'savestate_auto_save = "false"\nsavestate_auto_load = "false"\ncore_options_path = "/tmp/nc-hle.opt"\ngame_specific_options = "false"\nconfig_save_on_exit = "false"\n' > /tmp/nc-hle.cfg
printf 'savestate_auto_save = "false"\nsavestate_auto_load = "false"\nconfig_save_on_exit = "false"\n' > /tmp/nc-plain.cfg
FC=/opt/retropie/libretrocores/lr-flycast-dev/flycast_libretro.so
run "dc-Crazy Taxi (skip BIOS)" 90 $RA -L $FC --config /opt/retropie/configs/dreamcast/retroarch.cfg --appendconfig /tmp/nc-hle.cfg "$R/dreamcast/Crazy Taxi.cdi"
run "dc-Crazy Taxi 2" 90 $RA -L $FC --config /opt/retropie/configs/dreamcast/retroarch.cfg --appendconfig /tmp/nc-plain.cfg "$R/dreamcast/Crazy Taxi 2.cdi"

while retropie-game-running; do sleep 60; done
mkdir -p /tmp/nc-saves
printf 'savestate_auto_save = "false"\nsavestate_auto_load = "false"\nconfig_save_on_exit = "false"\nsavefile_directory = "/tmp/nc-saves"\n' > /tmp/nc-iso.cfg
Z="$(ls "$R"/snes/Europe/*"Link to the Past (E)"*.smc | head -1)"
timeout -k 5 25 $RA --verbose -L /opt/retropie/libretrocores/lr-snes9x/snes9x_libretro.so --config /opt/retropie/configs/snes/retroarch.cfg \
    --appendconfig /tmp/nc-iso.cfg "$Z" > $OUT/snes-rewind.log 2>&1
L="$R/gc/Luigi's Mansion (USA).iso"; CH="/opt/retropie/configs/all/retroarch/cheats/dolphin-emu/Luigi's Mansion (USA).cht"
if [ -f "$L" ] && [ ! -e "$CH" ]; then
    code=$(python3 -c "import sys; sys.path.insert(0,'/usr/local/lib/retropie'); import cheats; print([c['code'] for c in cheats.parse(cheats.available('gc', sys.argv[1])[0]) if 'Health' in c['desc']][0])" "$L" 2>/dev/null)
    if [ -n "$code" ]; then
        mkdir -p "$(dirname "$CH")"; printf 'cheats = 1\ncheat0_desc = "Infinite Health (night test)"\ncheat0_code = "%s"\ncheat0_enable = true\n' "$code" > "$CH"
        timeout -k 5 60 $RA --verbose -L /opt/retropie/libretrocores/lr-dolphin/dolphin_libretro.so --config /opt/retropie/configs/gc/retroarch.cfg \
            --appendconfig /tmp/nc-iso.cfg "$L" > $OUT/gc-cheat.log 2>&1
        rm -f "$CH"
    fi
fi
pactl set-sink-mute "$SINK" 0 2>/dev/null
python3 /usr/local/bin/retropie-music resume

# results.json for Play Stats: still running at the end and not a black/flat picture = OK
python3 - "$RES" "$OUT/results.json" <<'EOF'
import json, sys, time
games = []
for l in open(sys.argv[1]):
    label, alive, ran, a, b, *cpu = l.rstrip('\n').split('\t')
    cpu = cpu[0] if cpu and cpu[0] else '?'
    mean, sd = (float(x) for x in b.split()) if b.strip() else (0, 0)
    sysname, name = label.split('-', 1)
    if alive != '1':      ok, note = False, f'closed after {ran} s'
    elif sd < 6:          ok, note = False, 'blank screen'
    else:                 ok, note = True, f'running, main thread {cpu}%' + (' - may be slow' if cpu.isdigit() and int(cpu) >= 95 else '')
    games.append({'name': {'xbox': 'Xbox', 'dc': 'Dreamcast'}[sysname] + ' - ' + name, 'ok': ok, 'note': note,
                  'shot': label + '-end.png', 'mean': mean, 'sd': sd})
json.dump({'when': time.strftime('%a %d %b %H:%M'), 'games': games}, open(sys.argv[2], 'w'), indent=1)
EOF
echo "done $(date)" > $OUT/done.txt
