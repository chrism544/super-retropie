#!/usr/bin/env bash
# RetroPie add-on module: Wii U emulator Cemu from the official Linux AppImage.
# Install with:  sudo ~/RetroPie-Setup/retropie_packages.sh cemu-appimage depends install_bin configure
# (this file lives in ~/RetroPie-Setup/ext/<name>/scriptmodules/emulators/)
#
# Controls (Xbox pad, by label): A/B/X/Y = Wii U A/B/X/Y, LB/RB = L/R, LT/RT = ZL/ZR,
# Menu = +, View = -, Xbox button = swap TV / GamePad screen, View + Menu = quit to EmulationStation.

rp_module_id="cemu-appimage"
rp_module_desc="Wii U emulator Cemu (official AppImage)"
rp_module_help="ROM Extensions: .wua .wud .wux .rpx .iso\n\nCopy your Wii U games to $romdir/wiiu\n\nKeys for encrypted dumps (.wud/.wux) from your own console go in $biosdir/wiiu/keys.txt"
rp_module_licence="MPL2 https://raw.githubusercontent.com/cemu-project/Cemu/main/LICENSE.txt"
rp_module_section="exp"
rp_module_flags="!all x86"

function depends_cemu-appimage() {
    getDepends curl python3 mesa-vulkan-drivers
}

function install_bin_cemu-appimage() {
    local url
    url=$(curl -fsSL https://api.github.com/repos/cemu-project/Cemu/releases/latest | python3 -c '
import json, sys
for a in json.load(sys.stdin)["assets"]:
    if a["name"].startswith("Cemu") and a["name"].endswith("x86_64.AppImage"):
        print(a["browser_download_url"]); break')
    [[ -z "$url" ]] && md_ret_errors+=("Could not find the Cemu AppImage in the latest release") && return 1
    download "$url" "$md_inst/cemu.AppImage" || return 1
    chmod +x "$md_inst/cemu.AppImage"
    # Extract instead of mounting: no FUSE needed
    pushd "$md_inst" >/dev/null
    rm -rf app squashfs-root
    ./cemu.AppImage --appimage-extract >/dev/null && mv squashfs-root app
    rm -f cemu.AppImage
    popd >/dev/null
    basename "$url" > "$md_inst/version.txt"
}

function configure_cemu-appimage() {
    mkRomDir "wiiu"
    mkUserDir "$biosdir/wiiu"

    # Launcher: Cemu fullscreen + a pad watcher that quits on View+Menu (Cemu has no such hotkey)
    cat > "$md_inst/cemu-launch.sh" <<_EOF_
#!/bin/bash
"$md_inst/app/AppRun" -f -g "\$1" &
pid=\$!
python3 "$md_inst/pad-quit.py" \$pid &
watcher=\$!
wait \$pid
kill \$watcher 2>/dev/null
_EOF_
    cat > "$md_inst/pad-quit.py" <<'_EOF_'
#!/usr/bin/env python3
"""Quit the emulator (pid argv[1]) when View + Menu are held on any controller.
Reads /dev/input/js* directly (xpadneo/xpad numbering: View = 6, Menu = 7)."""
import glob, os, select, signal, struct, sys, time
pid, BACK, START = int(sys.argv[1]), 6, 7
pads = {}
while True:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.exit(0)
    for path in glob.glob('/dev/input/js*'):          # controllers can connect mid-game
        if path not in pads:
            try:
                pads[path] = (os.open(path, os.O_RDONLY | os.O_NONBLOCK), set())
            except OSError:
                pass
    ready, _, _ = select.select([fd for fd, _ in pads.values()], [], [], 1.0)
    for path, (fd, held) in list(pads.items()):
        if fd not in ready:
            continue
        try:
            data = os.read(fd, 8 * 64)
        except OSError:                                # controller switched off
            os.close(fd); del pads[path]; continue
        for i in range(0, len(data) - 7, 8):
            _, value, kind, number = struct.unpack('IhBB', data[i:i + 8])
            if kind & 0x01:                            # button (0x80 = initial state)
                (held.add if value else held.discard)(number)
        if BACK in held and START in held:
            os.kill(pid, signal.SIGTERM)
            time.sleep(4)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            sys.exit(0)
_EOF_
    chmod 755 "$md_inst/cemu-launch.sh" "$md_inst/pad-quit.py"

    addEmulator 1 "$md_id" "wiiu" "$md_inst/cemu-launch.sh %ROM%"
    addSystem "wiiu" "Nintendo Wii U" ".wua .wud .wux .rpx .iso"   # RetroPie adds upper case itself

    [[ "$md_mode" == "remove" ]] && return

    local cfg="$home/.config/Cemu" data="$home/.local/share/Cemu"
    mkUserDir "$home/.config"; mkUserDir "$home/.local"; mkUserDir "$home/.local/share"
    mkUserDir "$cfg"; mkUserDir "$cfg/controllerProfiles"; mkUserDir "$data"
    # keys.txt reachable from the bios share
    [[ -e "$data/keys.txt" ]] || touch "$biosdir/wiiu/keys.txt"
    [[ -e "$data/keys.txt" ]] || ln -s "$biosdir/wiiu/keys.txt" "$data/keys.txt"

    # A settings.xml must exist or Cemu opens its first-run wizard (no mouse on the box)
    if [[ ! -f "$cfg/settings.xml" ]]; then
        cat > "$cfg/settings.xml" <<_EOF_
<?xml version="1.0" encoding="UTF-8"?>
<content>
    <check_update>false</check_update>
    <fullscreen>true</fullscreen>
    <vk_warning>true</vk_warning>
    <GamePaths>
        <Entry>$romdir/wiiu</Entry>
    </GamePaths>
    <Graphic>
        <api>1</api>
        <VSync>1</VSync>
        <AsyncCompile>true</AsyncCompile>
    </Graphic>
    <Audio>
        <api>3</api>
        <TVDevice>default</TVDevice>
        <TVVolume>100</TVVolume>
    </Audio>
</content>
_EOF_
    fi

    # Xbox pad as the Wii U GamePad. Numbers from Cemu v2.6 source: mapping = VPADController
    # ButtonId, button = SDL button (0-31) or Buttons2 axis code (38-49; stick up = negative Y).
    # uuid = "<index>_<SDL GUID>" - GUID of the Xbox pad under xpadneo (045e:028e v1130)
    if [[ ! -f "$cfg/controllerProfiles/controller0.xml" ]]; then
        local map=(1:0 2:1 3:2 4:3 5:9 6:10 7:42 8:43 9:6 10:4 11:11 12:12 13:13 14:14 15:7 16:8
                   17:45 18:39 19:44 20:38 21:47 22:41 23:46 24:40 26:5)
        local entries="" m
        for m in "${map[@]}"; do
            entries+="                <entry><mapping>${m%%:*}</mapping><button>${m#*:}</button></entry>"$'\n'
        done
        cat > "$cfg/controllerProfiles/controller0.xml" <<_EOF_
<?xml version="1.0" encoding="UTF-8"?>
<emulated_controller>
    <type>Wii U GamePad</type>
    <controller>
        <api>SDLController</api>
        <uuid>0_050018dc5e0400008e02000030110000</uuid>
        <display_name>Xbox Wireless Controller</display_name>
        <rumble>0.5</rumble>
        <axis><deadzone>0.15</deadzone><range>1</range></axis>
        <rotation><deadzone>0.15</deadzone><range>1</range></rotation>
        <trigger><deadzone>0.25</deadzone><range>1</range></trigger>
        <mappings>
$entries        </mappings>
    </controller>
</emulated_controller>
_EOF_
    fi
    chown -R "$__user":"$__group" "$cfg" "$data" "$biosdir/wiiu"
}
