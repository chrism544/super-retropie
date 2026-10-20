#!/bin/bash
# Copy the given systems old box -> new box, surviving either box being switched off.
# Waits until both boxes answer SSH, then no game running; a system interrupted by a box
# going offline is simply run again. Also restarts the lr-mame build on the new box if a
# power-off killed it.   Usage: run-all.sh snes arcade n64 ...
W=/root/retropie-migrate
OLD=10.5.0.101; NEW=10.5.0.111
NEW_MAC=20:88:10:9f:96:4d                  # new box network card
NEW_ID=16733f941b59405584f0723a041dd13f    # new box /etc/machine-id
K=(ssh -i /root/.ssh/retropie_migrate -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
# The new box gets a different DHCP address after a power-off (.111 -> .115, Oct 2026):
# find it by its network card (via the old box ARP table), confirm by machine-id
find_new() {
    "${K[@]}" pi@$NEW "grep -q $NEW_ID /etc/machine-id" 2>/dev/null && return 0
    local ip
    for ip in $("${K[@]}" pi@$OLD "for i in \$(seq 1 254); do ping -c1 -W1 10.5.0.\$i >/dev/null 2>&1 & done; wait; ip neigh | grep -i $NEW_MAC | grep -v FAILED | cut -d\" \" -f1" 2>/dev/null); do
        if "${K[@]}" pi@$ip "grep -q $NEW_ID /etc/machine-id" 2>/dev/null; then
            NEW=$ip; export NEW; echo "[$(date +%T)] new box is now at $NEW"; return 0
        fi
    done
    return 1
}
online() { "${K[@]}" pi@$OLD true 2>/dev/null && find_new; }
export NEW
wait_online() {
    online && return
    echo "[$(date +%T)] waiting for both boxes to be online"
    until online; do sleep 60; done
    echo "[$(date +%T)] both boxes online"; sleep 60   # let the new box finish booting
}
resume_build() {  # lr-mame build is a transient unit - gone after a reboot
    "${K[@]}" pi@$NEW 'test -d /opt/retropie/libretrocores/lr-mame || systemctl is-active -q retropie-add-emulators || { sudo -n systemd-run --unit=retropie-add-emulators --description="Build lr-mame" /usr/local/bin/retropie-add-emulators lr-mame >/dev/null && echo "restarted lr-mame build on the new box"; }'
}
declare -A result
for s in "$@"; do
    tries=0
    while :; do
        wait_online; resume_build
        echo; echo "##### [$(date +%T)] $s #####"
        if "$W/run-when-idle.sh" "$s"; then result[$s]=OK; break; fi
        if ! online; then echo "[$(date +%T)] $s interrupted - a box went offline; will run it again"; continue; fi
        tries=$((tries + 1))
        (( tries >= 2 )) && { result[$s]=FAILED; break; }
        echo "[$(date +%T)] $s failed with both boxes online - one more try"
    done
done
echo; echo "##### Summary [$(date +%T)] #####"
for s in "$@"; do echo "$s: ${result[$s]}"; done
