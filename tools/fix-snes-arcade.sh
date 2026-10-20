#!/bin/bash
# One-off (Oct 2026): after the DS copy, redo SNES + arcade - their gamelists never arrived
# because of the Skyscraper-cache artwork bug - then restore the Mario/Zelda favourites and
# hide arcade clutter on the new box, with EmulationStation held.
W=/root/retropie-migrate
ID=16733f941b59405584f0723a041dd13f
while systemctl is-active -q retropie-migrate; do sleep 120; done
"$W/run-all.sh" snes arcade || true
for ip in 10.5.0.115 10.5.0.111; do
    ssh -i /root/.ssh/retropie_migrate -o BatchMode=yes -o ConnectTimeout=10 pi@$ip "grep -q $ID /etc/machine-id" || continue
    ssh -i /root/.ssh/retropie_migrate -o BatchMode=yes pi@$ip \
        'retropie-es-edit bash -c "python3 ~/add-mario-zelda-favorites.py | tail -1; python3 ~/curate-gamelists.py arcade --apply"'
    break
done
