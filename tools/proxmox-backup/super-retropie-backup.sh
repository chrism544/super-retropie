#!/bin/bash
# Nightly backup of Super RetroPie (10.5.0.19) onto this Proxmox host.
#   /var/lib/vz/super-retropie-backups/<date>/   one folder per night; unchanged files are hard links,
#   so each night only costs the space of what changed. Keeps 14 nights + the 1st of each month for 6 months.
#   Status: /var/lib/vz/super-retropie-backups/last-result
# The box only lets this key read files (rrsync -ro), it cannot change anything there.
# The timer also fires hourly through the day: if the box was switched off at 03:30, the backup
# happens the next time it is on (Oct 2026: a night with the box off left no backup that day).
set -u
BOX=pi@10.5.0.19
KEY=/root/.ssh/super-retropie-backup
DEST=/var/lib/vz/super-retropie-backups
TODAY=$DEST/$(date +%F)
mkdir -p "$DEST"
grep -q "^OK $(date +%F) " "$DEST/last-result" 2>/dev/null && exit 0      # already done today
if ! timeout 10 bash -c "</dev/tcp/${BOX#*@}/22" 2>/dev/null; then     # the key only allows rsync, so test the port
    echo "WAITING $(date '+%F %T') box not reachable (switched off?) - tries again next hour" > "$DEST/last-result"
    exit 0
fi
prev=$(ls -d "$DEST"/20*/ 2>/dev/null | grep -v "$(date +%F)" | tail -1)
rsync -a -m --numeric-ids --delete --partial \
    --filter="merge /root/super-retropie-backup/backup.filter" \
    ${prev:+--link-dest="$prev"} \
    -e "ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=20" \
    "$BOX:/" "$TODAY/" > "$DEST/last-log" 2>&1
rc=$?
# 23/24 = some files unreadable / vanished during the copy (e.g. a log being rotated) - still a good backup
if [ $rc -eq 0 ] || [ $rc -eq 23 ] || [ $rc -eq 24 ]; then
    echo "OK $(date '+%F %T') $(du -sh "$TODAY" | cut -f1)" > "$DEST/last-result"
else
    echo "FAILED $(date '+%F %T') rsync exit $rc - see last-log" > "$DEST/last-result"
fi
# prune: keep the newest 14, plus the newest folder of each of the last 6 months
keep=$( (ls -d "$DEST"/20*/ | tail -14; for m in $(seq 0 5); do ls -d "$DEST"/$(date -d "$(date +%Y-%m-15) -$m month" +%Y-%m)-*/ 2>/dev/null | head -1; done) | sort -u)
for d in "$DEST"/20*/; do grep -qxF "$d" <<<"$keep" || rm -rf "$d"; done
exit 0
