#!/bin/bash
# Run a command that edits game lists while EmulationStation is held stopped, so ES cannot
# save its old in-memory lists over the edits. Waits for anyone playing to finish first.
#   retropie-es-edit python3 ~/curate-gamelists.py arcade --apply

while retropie-game-running; do sleep 30; done
touch /tmp/es-hold                     # openbox autostart waits while this exists
pkill -TERM -x emulationstatio && for i in $(seq 1 20); do pgrep -x emulationstatio >/dev/null || break; sleep 1; done
"$@"; rc=$?
# An autostart loop that predates es-hold restarts ES straight away with the old lists -
# kill -9 that one so it cannot save them
pgrep -x emulationstatio >/dev/null && stale=1 || stale=0
rm -f /tmp/es-hold
(( stale )) && pkill -9 -x emulationstatio
exit $rc
