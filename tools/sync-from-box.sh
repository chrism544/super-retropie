#!/bin/bash
# Refresh box/ from the live Super RetroPie box, keeping out everything private.
# Run from the repo root (Git Bash on Windows or Linux):
#   tools/sync-from-box.sh [pi@10.5.0.19] [--push]
# Without --push it stops after staging, so you can look at `git status` / `git diff --cached` first.
#
# Kept out of the public repo (rules below):
#   RetroArch downloads (cheats-db, assets, shaders, cores), per-game bezel configs (install-bezels.py
#   makes them), backups (*.bak, *.before-*, ...), play history, game lists other than the RetroPie
#   menu, network settings, the phone companion PIN, console startup recordings (retropie-get-boot-sounds fetches them),
#   and any script that mentions torrents, the download folder or BIOS download sites.
set -eu
BOX=pi@10.5.0.19; PUSH=0
for a in "$@"; do case $a in --push) PUSH=1 ;; *@*) BOX=$a ;; esac; done
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
SSH=(ssh -o BatchMode=yes "$BOX")

echo "== snapshot on $BOX"
"${SSH[@]}" 'bash -s' < tools/build-super-retropie-kit.sh | tail -2

echo "== public file list"
"${SSH[@]}" 'bash -s' <<'EOF'
cd /; RC=opt/retropie/configs/all/retroarch/config
sudo bash -c "for f in $RC/*/*; do head -1 \"\$f\" | grep -q '^# bezel (The Bezel Project)' && echo \"\$f\"; done" > /tmp/srp-bezel.txt
grep -vxF -f /tmp/srp-bezel.txt /tmp/super-retropie-kit/filelist \
 | grep -vE 'retroarch/(cheats-db|assets|shaders|cores)/' \
 | grep -vE '\.(bak|orig|rp-dist|es-scraper-bak)$|\.bak-|\.before-|\.pre-' \
 | grep -vE 'es_temporaryinput\.cfg|content_.*history\.lpl|search-state\.json|^etc/netplan/|^etc/cloud/' \
 | grep -vE 'emulationstation/gamelists/|^usr/local/bin/Skyscraper$' \
 | grep -vE '\.config/retropie-companion\.json|emulationstation/tmp/' > /tmp/srp-public.txt   # phone PIN; ES temp files
echo opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml >> /tmp/srp-public.txt
# scripts about downloading games or BIOS stay private
PRIV='torrent|qbittorrent|\.download-incoming|retropie-downloads|retroarch_system|RetroPieBIOS'
grep -E '^(home/pi/[^/]+\.(py|sh)|usr/local/bin/)' /tmp/srp-public.txt | while read -r f; do
    [ -f "/$f" ] && sudo grep -qiIE "$PRIV" "/$f" && echo "$f"
done > /tmp/srp-private.txt
grep -vxF -f /tmp/srp-private.txt /tmp/srp-public.txt | sort -u > /tmp/srp-final.txt
echo "  $(wc -l < /tmp/srp-final.txt) entries, $(wc -l < /tmp/srp-private.txt) private scripts left out"
sudo tar -C / -czf /tmp/srp-public.tar.gz --numeric-owner \
    --exclude='usr/local/share/retropie-splash/sounds/*.wav' --exclude='usr/local/share/retropie-splash/sounds/*.mp3' \
    --exclude='*.bak' --exclude='*.bak-*' --exclude='*.before-*' --exclude='*.pre-*' --exclude='*.orig' \
    -T /tmp/srp-final.txt
EOF
scp -q -o BatchMode=yes "$BOX:/tmp/srp-public.tar.gz" "$TMP/public.tar.gz"
"${SSH[@]}" 'sudo rm -f /tmp/srp-*.txt /tmp/srp-public.tar.gz'

echo "== secret check"
mkdir "$TMP/box" && tar -C "$TMP/box" -xzf "$TMP/public.tar.gz" --no-same-owner
if grep -rIlE 'BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|psk *[:=]|(password|token|api_?key) *[:=] *["'"'"'][^"'"'"'_$]{4,}' "$TMP/box"; then
    echo "!! possible secret in the files above - nothing changed"; exit 1
fi

echo "== update box/"
git rm -rq --cached box >/dev/null 2>&1 || true
mkdir -p box && find box -mindepth 1 -maxdepth 1 -exec rm -rf {} +    # contents only - on Windows the folder
cp -a "$TMP/box/." box/                                                  # itself can be held open by a shell
git add box
tar -tvzf "$TMP/public.tar.gz" | grep '^-..x' | sed -E 's/^([^ ]+ +){5}//; s|^|box/|' | git update-index --chmod=+x --stdin
git status --short box | awk '{print $1}' | sort | uniq -c
if [ $PUSH = 1 ]; then
    git commit -q -m "Sync box/ from Super RetroPie ($(date +%Y-%m-%d))" && git push -q && echo "pushed"
else
    echo "staged - review with: git diff --cached --stat   then: git commit && git push"
fi
