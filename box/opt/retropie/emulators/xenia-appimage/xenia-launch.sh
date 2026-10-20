#!/bin/bash
set -u
D="$HOME/.local/share/xenia"
mkdir -p "$D"
cd "$D" || exit 1
"$HOME/.local/share/retropie-xenia/c28af11/squashfs-root/AppRun" --storage_root="$D" --config="$D/xenia.config.toml" --gpu=vulkan --fullscreen=true "$1" &
pid=$!
python3 /opt/retropie/emulators/xenia-appimage/quit-helper.py "$pid" &
helper=$!
trap 'kill "$helper" 2>/dev/null || true' EXIT
wait "$pid"
