#!/bin/bash
# Turns a fresh RetroPie box (built by install-retropie.sh) into Super RetroPie.
# Run as root:  sudo bash restore-super-retropie.sh [--keep-network]
#   --keep-network   do not apply the static 10.5.0.19 address / hostname (e.g. a second box)
# Log: /var/log/super-retropie-restore.log
#
# What it does
#   1. extra Ubuntu packages (music, menus, boot screen, streaming, file sharing)
#   2. every emulator the Super RetroPie box has (packages.txt), xemu and Sunshine
#   3. the bluray theme, then all Super RetroPie files (files.tar.gz) on top
#   4. switches on the timers/services, boot screen, hostname
# Not in the kit (private or too big): games, BIOS, saves, Wii U keys, Sunshine pairing.
# Saves/BIOS/artwork come back from the nightly Proxmox backup - see README.md.
set -u
KIT=$(cd "$(dirname "$0")" && pwd)
U=pi; H=/home/$U
KEEP_NET=0; [ "${1:-}" = --keep-network ] && KEEP_NET=1
exec > >(tee -a /var/log/super-retropie-restore.log) 2>&1
step() { echo; echo "=== $(date '+%T') $*"; }
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }

# From a git checkout there is no files.tar.gz - pack it from the repo's box/ folder
BOX=$(cd "$KIT/../../../.." 2>/dev/null && pwd)/box
if [ ! -f "$KIT/files.tar.gz" ] && [ -d "$BOX" ]; then
    step "packing files.tar.gz from $BOX"
    (cd "$BOX" && tar -czf "$KIT/files.tar.gz" --owner=0 --group=0 *) || { echo "!! packing failed"; exit 1; }
fi
[ -f "$KIT/files.tar.gz" ] || { echo "no files.tar.gz and no box/ folder"; exit 1; }

step "Ubuntu packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq mpv xdotool feh x11-apps python3-pygame python3-pil ffmpeg p7zip-full rsync \
    samba avahi-daemon plymouth plymouth-themes intel-media-va-driver-non-free vainfo git curl || echo "!! some packages failed"

step "RetroPie packages ($(wc -l < "$KIT/packages.txt"))"
# the Super RetroPie scriptmodules (Cemu, PCSX2) first, so retropie_packages.sh knows them
tar -C / -xzf "$KIT/files.tar.gz" home/pi/RetroPie-Setup/ext 2>/dev/null
chown -R $U:$U $H/RetroPie-Setup/ext
while read -r p; do
    case $p in xemu-appimage) continue ;; esac
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

step "Sunshine (streaming to Moonlight)"
if ! dpkg -s sunshine >/dev/null 2>&1; then
    V=$(awk '/^sunshine /{sub(/-1\+ubuntu.*/,"",$2); print $2}' "$KIT/versions.txt")
    curl -fsSL -o /tmp/sunshine.deb "https://github.com/LizardByte/Sunshine/releases/download/v$V/sunshine-ubuntu-24.04-amd64.deb" &&
        apt-get install -y -qq /tmp/sunshine.deb || echo "!! Sunshine install failed"
fi

step "bluray theme"
[ -d /etc/emulationstation/themes/bluray ] ||
    git clone -q --depth 1 https://github.com/RetroHursty69/es-theme-bluray.git /etc/emulationstation/themes/bluray

step "Super RetroPie files"
NET_FILES=(etc/netplan/50-cloud-init.yaml etc/cloud/cloud.cfg.d/99-disable-network-config.cfg)
if [ $KEEP_NET = 1 ]; then
    tar -C / -xzpf "$KIT/files.tar.gz" --same-owner "${NET_FILES[@]/#/--exclude=}"
else
    tar -C / -xzpf "$KIT/files.tar.gz" --same-owner
fi
chown -R $U:$U $H/.config $H/.local $H/RetroPie $H/RetroPie-Setup/ext /opt/retropie/configs 2>/dev/null
chown $U:$U $H/*.py $H/*.sh 2>/dev/null
chmod 755 /usr/local/bin/*
[ -e /usr/local/bin/Skyscraper ] || [ ! -x /opt/retropie/supplementary/skyscraper/Skyscraper ] ||
    ln -s /opt/retropie/supplementary/skyscraper/Skyscraper /usr/local/bin/Skyscraper

step "services and timers"
systemctl daemon-reload
for u in /etc/systemd/system/retropie-*.timer; do systemctl enable "$(basename "$u")"; done
for s in retropie-soundbar retropie-build-resume retropie-display-hotplug retropie-battery retropie-power-limit; do
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
