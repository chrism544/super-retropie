#!/bin/bash
# Copy RetroPie settings + one system's games/saves/artwork from the old box to the new box.
# Runs on proxmox-home so it doesn't depend on a laptop staying awake.
#
#   ./migrate-from-proxmox.sh <system> [--plan]
#   e.g. ./migrate-from-proxmox.sh snes --plan   (counts only, copies nothing)
#
# Settings are copied once (marker file). Left out on purpose: Bluetooth pairings,
# es_input.cfg and RetroArch joypad files - the new box has its own fresh pairing and
# xpadneo button mapping (Oct 2026).
set -euo pipefail
OLD=10.5.0.101
NEW=${NEW:-10.5.0.111}   # run-all.sh passes the current address
SYS=${1:?system, e.g. snes}
PLAN=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd)
W=/root/retropie-migrate
mkdir -p "$W/logs"
LOG="$W/logs/$SYS-$(date +%F-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
SSH=(ssh -i /root/.ssh/retropie_migrate -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=4)
# Data goes old -> new directly (6 ms, same switch). Proxmox only orchestrates: via
# Proxmox every byte crossed the slow 65 ms link twice (5.6 MB/s vs 8.5+ direct).
TONEW="ssh -i ~/.ssh/retropie_to_new -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=4 pi@$NEW"
old() { "${SSH[@]}" pi@$OLD "$@"; }
new() { "${SSH[@]}" pi@$NEW "$@"; }
step() { echo; echo "=== [$(date +%T)] $* ==="; }

step "Pre-flight"
for h in $OLD $NEW; do
    "${SSH[@]}" pi@$h 'echo "$(hostname) $(hostname -I | cut -d" " -f1)"; sudo -n true'
done
step "Build $SYS list on the old box (hidden games skipped)"
# curate-gamelists.py only understands GoodTools sets; other systems (multi-disc .cue/.bin,
# .m3u, DS/PSP isos) use the gamelist's own hidden flags. Not arcade either: its keep list
# drops BIOS/parent sets (neogeo.zip...) that the kept games need to run.
case $SYS in
    snes|megadrive) old "python3 - $SYS >/dev/null" < "$HERE/curate-gamelists.py" ;;
    *) old "rm -f /tmp/$SYS-keep.txt" ;;
esac
old "python3 - $SYS" < "$HERE/build-copy-list.py" | tee "$W/$SYS-plan.txt"
eval "$(grep -o 'TOTAL_FILES=[0-9]* TOTAL_BYTES=[0-9]*' "$W/$SYS-plan.txt")"
echo "Free on new box: $(new 'df -h --output=avail / | tail -1')"
[ "$PLAN" = --plan ] && { echo "Plan only - nothing copied"; exit 0; }
# A running game holds unsaved progress and writes saves on exit
for h in OLD NEW; do
    # By path, not name: PCSX2 runs as "AppRun" and slipped past a name list (Oct 2026)
    if ${h,,} 'pgrep -af "[r]uncommand\.sh|[o]pt/retropie/(emulators|libretrocores)/"'; then
        echo "A game is running on the $h box - quit it first"; exit 1
    fi
done

SETTINGS_LIST='cd / && {
  find opt/retropie/configs home/pi/RetroPie/BIOS home/pi/RetroPie/splashscreens etc/emulationstation/themes \
       \( -type f -o -type l \) ! -name "es_log.txt*" ! -name es_input.cfg ! -path "*/retroarch-joypads/*" -print0 2>/dev/null
  find home/pi/curate-gamelists.py home/pi/curate-lists -print0 2>/dev/null
}'
if [ ! -f "$W/settings.done" ]; then
    step "Back up the new box's configs"
    # Never overwrite: a restarted run would replace the clean backup with half-copied settings
    new 'B=/home/pi/configs-before-migrate.tgz; [ -f $B ] || sudo -n tar -C / -czf $B opt/retropie/configs; ls -lh $B'
    step "Copy settings, BIOS, themes, splash screens"
    old "set -o pipefail; sudo -n bash -c '$SETTINGS_LIST | tar --hard-dereference --null -T - -cpf -' | $TONEW 'sudo -n tar -C / -xpf -'"
    touch "$W/settings.done"
else
    echo "Settings already copied ($(date -r "$W/settings.done")) - skipping"
fi

step "Copy $SYS games, saves and artwork ($TOTAL_FILES files, $((TOTAL_BYTES / 1000000)) MB)"
t=$(date +%s)
old "set -o pipefail; sudo -n tar -C / --hard-dereference --null -T /tmp/$SYS-files.lst -cpf - | $TONEW 'sudo -n tar -C / -xpf -'"
old "cat /tmp/$SYS-gamelist.xml" | new "mkdir -p ~/RetroPie/roms/$SYS && cat > ~/RetroPie/roms/$SYS/gamelist.xml"
echo "Copied in $(( $(date +%s) - t ))s"

step "Verify on the new box"
old "cat /tmp/$SYS-files.lst" | new "sudo -n chown -R pi:pi ~/RetroPie /opt/retropie/configs
    n=0; b=0; miss=0
    while IFS= read -r -d '' f; do
        if [ -f \"/\$f\" ]; then n=\$((n+1)); b=\$((b+\$(stat -c%s \"/\$f\"))); else miss=\$((miss+1)); echo \"MISSING /\$f\"; fi
    done
    echo \"new box: \$n files, \$b bytes, \$miss missing\"
    [ \$n -eq $TOTAL_FILES ] && [ \$b -eq $TOTAL_BYTES ] && echo VERIFY-OK || { echo VERIFY-FAILED; exit 1; }"

step "Reload EmulationStation (kill -9 so it can't overwrite the copied lists on exit)"
new 'pkill -9 -x emulationstatio || true; [ -L ~/RetroPie/roms/genesis ] && unlink ~/RetroPie/roms/genesis || true'
echo "Done. Log: $LOG"
