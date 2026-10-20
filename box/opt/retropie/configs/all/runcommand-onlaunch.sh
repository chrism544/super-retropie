#!/bin/bash
# Super RetroPie: the game is about to start - close the launch screen, show the manual if asked for
export DISPLAY=${DISPLAY:-:0}
if [ -s /tmp/retropie-manual-request ]; then
    m=$(cat /tmp/retropie-manual-request); rm -f /tmp/retropie-manual-request
    /usr/local/bin/retropie-launchscreen-hide
    python3 /usr/local/bin/retropie-manual "$m" >/dev/null 2>&1
fi
# X on the launch screen = start fresh: set the resume point aside (one backup kept)
if [ -s /tmp/retropie-fresh-request ]; then
    f=$(cat /tmp/retropie-fresh-request); rm -f /tmp/retropie-fresh-request
    [ -f "$f" ] && mv -f "$f" "$f.before-fresh"
fi
# keep the launch screen up until the game window shows (no black terminal in between)
setsid /usr/local/bin/retropie-launchscreen-handoff </dev/null >/dev/null 2>&1 &
exit 0
