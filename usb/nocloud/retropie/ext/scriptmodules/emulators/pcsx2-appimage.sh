#!/usr/bin/env bash
# RetroPie add-on module: PCSX2 from the official AppImage (latest stable release).
# RetroPie's own "pcsx2" module relies on the old pcsx2-team PPA, which has nothing for
# current Ubuntu. Install with:  sudo ~/RetroPie-Setup/retropie_packages.sh pcsx2-appimage
# (this file lives in ~/RetroPie-Setup/ext/<name>/scriptmodules/emulators/)

rp_module_id="pcsx2-appimage"
rp_module_desc="PS2 emulator PCSX2 (official AppImage, latest stable)"
rp_module_help="ROM Extensions: .iso .chd .cso .bin .cue .gz\n\nCopy your PS2 games to $romdir/ps2\n\nCopy the PS2 BIOS dumped from your console to $biosdir/ps2"
rp_module_licence="GPL3 https://raw.githubusercontent.com/PCSX2/pcsx2/master/COPYING.GPLv3"
rp_module_section="exp"
rp_module_flags="!all x86"

function depends_pcsx2-appimage() {
    getDepends curl python3 mesa-vulkan-drivers
}

function install_bin_pcsx2-appimage() {
    local url
    url=$(curl -fsSL https://api.github.com/repos/PCSX2/pcsx2/releases/latest | python3 -c '
import json, sys
for a in json.load(sys.stdin)["assets"]:
    if a["name"].endswith("linux-appimage-x64-Qt.AppImage"):
        print(a["browser_download_url"]); break')
    [[ -z "$url" ]] && md_ret_errors+=("Could not find the PCSX2 AppImage in the latest release") && return 1
    download "$url" "$md_inst/pcsx2.AppImage" || return 1
    chmod +x "$md_inst/pcsx2.AppImage"
    # Extract instead of mounting: no FUSE needed, starts faster
    pushd "$md_inst" >/dev/null
    rm -rf app squashfs-root
    ./pcsx2.AppImage --appimage-extract >/dev/null && mv squashfs-root app
    rm -f pcsx2.AppImage
    popd >/dev/null
    basename "$url" > "$md_inst/version.txt"
}

function configure_pcsx2-appimage() {
    mkRomDir "ps2"
    mkUserDir "$biosdir/ps2"
    # -batch: close PCSX2 when the game is shut down (View+Menu), back to EmulationStation
    addEmulator 1 "$md_id" "ps2" "$md_inst/app/AppRun -fullscreen -nogui -batch -- %ROM%"
    addSystem "ps2"

    [[ "$md_mode" == "remove" ]] && return

    local ini="$home/.config/PCSX2/inis/PCSX2.ini"
    [[ -f "$ini" ]] && return   # keep any settings already made in PCSX2
    mkUserDir "$home/.config/PCSX2"
    mkUserDir "$home/.config/PCSX2/inis"
    # Xbox pad as a DualShock 2; hotkeys match the RetroArch systems:
    #   View+Menu quit, View+X pause menu, View+RB save state, View+LB load state
    cat > "$ini" <<_EOF_
[UI]
SettingsVersion = 1
SetupWizardIncomplete = false
StartFullscreen = true
ConfirmShutdown = false
HideMouseCursor = true

[Folders]
Bios = $biosdir/ps2

[EmuCore]
EnableFastBoot = true

[EmuCore/Speedhacks]
vuThread = true

[EmuCore/GS]
Renderer = 14
upscale_multiplier = 1

[InputSources]
SDL = true

[Pad1]
Type = DualShock2
Up = SDL-0/DPadUp
Right = SDL-0/DPadRight
Down = SDL-0/DPadDown
Left = SDL-0/DPadLeft
Triangle = SDL-0/FaceNorth
Circle = SDL-0/FaceEast
Cross = SDL-0/FaceSouth
Square = SDL-0/FaceWest
Select = SDL-0/Back
Start = SDL-0/Start
L1 = SDL-0/LeftShoulder
L2 = SDL-0/+LeftTrigger
R1 = SDL-0/RightShoulder
R2 = SDL-0/+RightTrigger
L3 = SDL-0/LeftStick
R3 = SDL-0/RightStick
LUp = SDL-0/-LeftY
LRight = SDL-0/+LeftX
LDown = SDL-0/+LeftY
LLeft = SDL-0/-LeftX
RUp = SDL-0/-RightY
RRight = SDL-0/+RightX
RDown = SDL-0/+RightY
RLeft = SDL-0/-RightX
SmallMotor = SDL-0/SmallMotor
LargeMotor = SDL-0/LargeMotor

[Hotkeys]
ShutdownVM = SDL-0/Back & SDL-0/Start
OpenPauseMenu = SDL-0/Back & SDL-0/FaceWest
SaveStateToSlot = SDL-0/Back & SDL-0/RightShoulder
LoadStateFromSlot = SDL-0/Back & SDL-0/LeftShoulder
_EOF_
    chown -R "$__user":"$__group" "$home/.config/PCSX2"
}
