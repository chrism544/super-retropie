#!/bin/bash
set -u
D=/opt/retropie/emulators/xemu-appimage
CFG="$HOME/.local/share/xemu/xemu/xemu.toml"
# Per-game settings (/opt/retropie/configs/xbox/per-game-scale.cfg, "<part of file name> = <scale> [opengl|vulkan]"):
# run that game on a copy of the settings, so the main settings stay as they are.
read -r scale rend < <(awk -F' *= *' -v g="$(basename "$1")" '!/^#/ && NF==2 && index(tolower(g), tolower($1)) {print $2; exit}' \
        /opt/retropie/configs/xbox/per-game-scale.cfg 2>/dev/null)
tmp=
if [ -n "${scale:-}" ]; then
    tmp=$(mktemp /tmp/xemu-XXXXXX.toml)
    xemu-set-scale "$CFG" "$tmp" "$scale" "${rend:-}"
    CFG=$tmp
fi
"$D/app/AppRun" -config_path "$CFG" -full-screen -dvd_path "$1" &
pid=$!
python3 "$D/quit-helper.py" "$pid" &
helper=$!
trap 'kill "$helper" 2>/dev/null || true; [ -n "$tmp" ] && rm -f "$tmp"' EXIT
wait "$pid"
