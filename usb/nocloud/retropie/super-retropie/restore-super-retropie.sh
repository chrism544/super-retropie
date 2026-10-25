#!/bin/bash
# Turns a fresh RetroPie box (built by install-retropie.sh) into Super RetroPie.
# Run as root:  sudo bash restore-super-retropie.sh [--keep-network] [--no-bezels]
#   --keep-network   do not apply the kit's static address / hostname (e.g. a second box).
#                    Automatic when the kit has no network settings (the public git repo).
#   --no-bezels      skip The Bezel Project download (several GB; run ~/install-bezels.py later)
# Log: /var/log/super-retropie-restore.log
#
# What it does
#   1. extra Ubuntu packages (music, menus, boot screen, streaming, file sharing)
#   2. every emulator the Super RetroPie box has (packages.txt), xemu and Sunshine
#   3. the bluray theme, then all Super RetroPie files (files.tar.gz) on top
#   4. downloads: RetroArch cheat database, console startup sounds, game bezels
#   5. switches on the timers/services, boot screen, hostname
# Not in the kit (private or too big): games, BIOS, saves, Wii U keys, Sunshine pairing.
# Saves/BIOS/artwork come back from the nightly Proxmox backup - see README.md.
set -u
KIT=$(cd "$(dirname "$0")" && pwd)
U=pi; H=/home/$U
KEEP_NET=0; BEZELS=1
for a in "$@"; do case $a in --keep-network) KEEP_NET=1 ;; --no-bezels) BEZELS=0 ;; esac; done
exec > >(tee -a /var/log/super-retropie-restore.log) 2>&1
step() { echo; echo "=== $(date '+%T') $*"; }
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

# From a git checkout there is no files.tar.gz - pack the repo's box/ folder (fresh every run)
FILES=$KIT/files.tar.gz
BOX=$(cd "$KIT/../../../.." 2>/dev/null && pwd)/box
if [ ! -f "$FILES" ] && [ -d "$BOX" ]; then
    FILES=$KIT/.box-files.tar.gz
    step "packing $BOX"
    # files and links only: folder entries would stamp the checkout's owner/mode onto /home/pi, /etc,
    # /usr ... (Oct 2026 test: /home/pi became root-owned and group-writable, and SSH refused keys)
    (cd "$BOX" && find . \( -type f -o -type l \) -printf '%P\n' |
        tar -czf "$FILES" --owner=0 --group=0 --mode=go-w --no-recursion -T -) || { echo "!! packing failed"; exit 1; }
fi
[ -f "$FILES" ] || { echo "no files.tar.gz and no box/ folder"; exit 1; }
tar -tzf "$FILES" etc/netplan/50-cloud-init.yaml >/dev/null 2>&1 || KEEP_NET=1

step "Ubuntu packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq mpv xdotool feh x11-apps python3-pygame python3-pil ffmpeg p7zip-full unzip rsync python3-qrcode \
    samba avahi-daemon plymouth plymouth-themes intel-media-va-driver-non-free vainfo git curl || echo "!! some packages failed"

step "RetroPie packages ($(wc -l < "$KIT/packages.txt"))"
# the Super RetroPie scriptmodules (Cemu, PCSX2) first, so retropie_packages.sh knows them
tar -C / -xzf "$FILES" home/pi/RetroPie-Setup/ext 2>/dev/null
chown -R $U:$U $H/RetroPie-Setup/ext
while read -r p; do
    case $p in xemu-appimage|xenia-appimage) continue ;; esac     # not RetroPie packages - installed below
    if [ -d /opt/retropie/emulators/$p ] || [ -d /opt/retropie/libretrocores/$p ] || [ -d /opt/retropie/supplementary/$p ]; then
        echo "  $p already installed"; continue
    fi
    echo "  installing $p"
    $H/RetroPie-Setup/retropie_packages.sh "$p" >/dev/null 2>&1 || echo "!! $p failed - install it later from RetroPie Setup"
done < "$KIT/packages.txt"

step "xemu (Xbox)"
XEMU=0.8.137
if [ ! -x /opt/retropie/emulators/xemu-appimage/app/AppRun ]; then
    mkdir -p /opt/retropie/emulators/xemu-appimage && cd /opt/retropie/emulators/xemu-appimage &&
    curl -fsSL -o xemu.AppImage "https://github.com/xemu-project/xemu/releases/download/v$XEMU/xemu-$XEMU-x86_64.AppImage" &&
    chmod +x xemu.AppImage && ./xemu.AppImage --appimage-extract >/dev/null && rm -rf app && mv squashfs-root app && rm xemu.AppImage ||
    echo "!! xemu download failed"
    cd "$KIT"
fi

step "xenia (Xbox 360)"
XENIA=c28af11; XENIA_SHA=d6b362cdb5d41c58c1dd5f7331949eae0ffb7966e5e9a6146996fdc6d2222115
XD=$H/.local/share/retropie-xenia/$XENIA          # where xenia-launch.sh runs it from
if [ ! -x "$XD/squashfs-root/AppRun" ]; then
    sudo -u $U mkdir -p "$XD" && cd "$XD" &&
    sudo -u $U curl -fsSL -o xenia_canary_linux.AppImage \
        "https://github.com/xenia-canary/xenia-canary/releases/download/$XENIA/xenia_canary_linux.AppImage" &&
    echo "$XENIA_SHA  xenia_canary_linux.AppImage" | sha256sum -c --quiet &&
    chmod +x xenia_canary_linux.AppImage && sudo -u $U ./xenia_canary_linux.AppImage --appimage-extract >/dev/null ||
    echo "!! xenia download failed"
    cd "$KIT"
fi

step "Sunshine (streaming to Moonlight)"
if ! dpkg -s sunshine >/dev/null 2>&1; then
    V=$(awk '/^sunshine /{print $2}' "$KIT/versions.txt")          # e.g. 2026.914.233613-1+ubuntu24.04
    curl -fsSL -o /tmp/sunshine.deb "https://github.com/LizardByte/Sunshine/releases/download/v${V%%-*}/sunshine_${V}_amd64.deb" &&
        apt-get install -y -qq /tmp/sunshine.deb || echo "!! Sunshine install failed"
fi

step "bluray theme"
[ -d /etc/emulationstation/themes/bluray ] ||
    git clone -q --depth 1 https://github.com/RetroHursty69/es-theme-bluray.git /etc/emulationstation/themes/bluray

step "Super RetroPie files"
NET_FILES=(etc/netplan/50-cloud-init.yaml etc/cloud/cloud.cfg.d/99-disable-network-config.cfg)
if [ $KEEP_NET = 1 ]; then
    tar -C / -xzpf "$FILES" --same-owner "${NET_FILES[@]/#/--exclude=}"
else
    tar -C / -xzpf "$FILES" --same-owner
fi
chown -R $U:$U $H/.config $H/.local $H/RetroPie $H/RetroPie-Setup/ext /opt/retropie/configs 2>/dev/null
chown $U:$U $H/*.py $H/*.sh $H/.Xresources 2>/dev/null
chmod 755 /usr/local/bin/*
[ -e /usr/local/bin/Skyscraper ] || [ ! -x /opt/retropie/supplementary/skyscraper/Skyscraper ] ||
    ln -s /opt/retropie/supplementary/skyscraper/Skyscraper /usr/local/bin/Skyscraper

step "downloads (cheats, startup sounds, bezels)"
DB=/opt/retropie/configs/all/retroarch/cheats-db
if [ ! -d "$DB/Sony - PlayStation" ]; then
    rm -rf /tmp/cheats && mkdir -p /tmp/cheats &&
    curl -fsSL -o /tmp/cheats.zip https://buildbot.libretro.com/assets/frontend/cheats.zip &&
    unzip -q -o /tmp/cheats.zip -d /tmp/cheats && {
        SRC=/tmp/cheats; [ -d "$SRC/Sony - PlayStation" ] || SRC=$(dirname "$(find /tmp/cheats -maxdepth 3 -type d -name 'Sony - PlayStation' | head -1)")
        rm -rf "$DB" && mv "$SRC" "$DB" && chown -R $U:$U "$DB" && echo "  cheat database: $(find "$DB" -name '*.cht' | wc -l) files"
    } || echo "!! cheat database download failed - the Cheats menu stays empty until it is fetched"
    rm -rf /tmp/cheats /tmp/cheats.zip
fi
/usr/local/bin/retropie-get-boot-sounds || echo "!! startup sounds failed - run: sudo retropie-get-boot-sounds"
if [ $BEZELS = 1 ] && [ -f $H/install-bezels.py ]; then
    sudo -u $U -H python3 $H/install-bezels.py || echo "!! bezels failed - run: python3 ~/install-bezels.py"
fi

step "Ship of Harkinian (Ports)"
# the kit has its launcher and settings; the app is the official 9.3.0 release, checked (Oct 2026)
SOH=/opt/retropie/ports/soh
if [ -f $SOH/soh.sh ] && [ ! -x $SOH/app/AppRun ] &&
   curl -fsSL -o /tmp/soh.appimage https://github.com/HarbourMasters/Shipwright/releases/download/9.3.0/SoH-Dewey-Alpha.appimage &&
   echo "8507bb70413e130e452ebaf5f156bfd78013ee0144364b7968680e8cf064a0fa  /tmp/soh.appimage" | sha256sum -c --quiet; then
    chmod +x /tmp/soh.appimage && (cd /tmp && ./soh.appimage --appimage-extract >/dev/null) &&
        rm -rf $SOH/app && mv /tmp/squashfs-root $SOH/app && chown -R $U:$U $SOH
    rm -f /tmp/soh.appimage
    echo "  game data: see README.md (Ship of Harkinian)"
else
    [ -x $SOH/app/AppRun ] || echo "!! Ship of Harkinian download failed or checksum wrong"
fi

step "services and timers"
systemctl daemon-reload
for u in /etc/systemd/system/retropie-*.timer; do systemctl enable "$(basename "$u")"; done
for s in retropie-soundbar retropie-build-resume retropie-display-hotplug retropie-battery retropie-power-limit retropie-companion; do
    [ -f /etc/systemd/system/$s.service ] && systemctl enable $s.service
done
udevadm control --reload
modprobe uinput

step "boot screen"
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth \
    /usr/share/plymouth/themes/super-retropie/super-retropie.plymouth 200
update-alternatives --set default.plymouth /usr/share/plymouth/themes/super-retropie/super-retropie.plymouth
update-grub && update-initramfs -u

if [ $KEEP_NET = 0 ]; then
    step "name and network (Super RetroPie, 10.5.0.19)"
    hostnamectl set-hostname super-retropie
    hostnamectl set-hostname --pretty "Super RetroPie"
    sed -i 's/^127\.0\.1\.1.*/127.0.1.1 super-retropie/' /etc/hosts
    chmod 600 /etc/netplan/*.yaml
    netplan generate && echo "  static address applies at the next reboot"
    sudo -u $U xauth add super-retropie/unix:0 . "$(sudo -u $U xauth list 2>/dev/null | awk 'NR==1{print $3}')" 2>/dev/null
else
    step "keeping this box's own name and network"
fi
systemctl restart smbd avahi-daemon 2>/dev/null

step "Done. Reboot, then restore saves/BIOS from the Proxmox backup (README.md)."
