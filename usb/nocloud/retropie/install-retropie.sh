#!/bin/bash
# Runs once on first boot (as root) via retropie-firstboot.service.
# Log: /var/log/retropie-install.log   (watch remotely: ssh <box> tail -f /var/log/retropie-install.log)
#
# Everything here was learned on the first box (Datto Alto, Oct 2026). Each block says why it exists.
set -uo pipefail
exec > >(tee -a /var/log/retropie-install.log) 2>&1

BOOT=/opt/retropie-bootstrap
U="$(cat "$BOOT/user")"
H="/home/$U"
CFG=/opt/retropie/configs
export DEBIAN_FRONTEND=noninteractive

step() { echo; echo "=== [$(date +%T)] $* ==="; }
set_kv() { # file key value  -> key = "value" (RetroArch / core-options style)
    touch "$1"; grep -q "^$2 = " "$1" && sed -i "s|^$2 = .*|$2 = \"$3\"|" "$1" || echo "$2 = \"$3\"" >> "$1"
}

step "Waiting for internet"
for i in $(seq 1 60); do
    curl -fsS --max-time 5 https://github.com >/dev/null && break
    sleep 5
done

step "Install sanity checks (kernel, initramfs, apt sources)"
uname -r
# curtin diverts update-initramfs during install; if it's still diverted, future kernel
# updates would get no initramfs -> "VFS: Unable to mount root fs" (Oct 2026 failure)
if [ "$(dpkg-divert --truename /usr/sbin/update-initramfs)" != /usr/sbin/update-initramfs ]; then
    echo "!! update-initramfs still diverted - restoring"
    rm -f /usr/sbin/update-initramfs
    dpkg-divert --rename --remove /usr/sbin/update-initramfs
    update-initramfs -u -k all
fi
ls -l /boot/vmlinuz-* /boot/initrd.img-*
# An offline install leaves only the ISO as a package source
if grep -rqs 'file:///cdrom' /etc/apt/sources.list /etc/apt/sources.list.d/ \
   || ! grep -rqs 'archive.ubuntu.com' /etc/apt/sources.list /etc/apt/sources.list.d/; then
    echo "!! apt sources point at the install media - replacing with the online archive"
    for f in /etc/apt/sources.list.d/*; do grep -qs 'file:///cdrom' "$f" && mv "$f" "$f.disabled"; done
    [ -f /etc/apt/sources.list ] && : > /etc/apt/sources.list
    cat > /etc/apt/sources.list.d/ubuntu.sources <<'EOF'
Types: deb
URIs: http://gb.archive.ubuntu.com/ubuntu/
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://security.ubuntu.com/ubuntu/
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
fi

step "System update"
apt-get update
apt-get -y full-upgrade

step "HWE kernel + headers (newest WiFi/Bluetooth/GPU drivers; headers for xpadneo/xone DKMS)"
# Installed here, online, rather than by the installer - the ISO pool may not carry it
apt-get -y install linux-generic-hwe-24.04 linux-headers-generic-hwe-24.04 "linux-headers-$(uname -r)" \
    || echo "!! HWE kernel/headers install failed"

step "GPU drivers (Nvidia etc. if present; Intel/AMD use Mesa)"
apt-get -y install ubuntu-drivers-common
ubuntu-drivers install || echo "!! no extra GPU driver needed / install failed"

step "Desktop-less X stack for EmulationStation"
apt-get -y install --no-install-recommends \
    xorg openbox xinit x11-xserver-utils unclutter xterm fonts-dejavu-core \
    pulseaudio alsa-utils mesa-utils libgl1-mesa-dri \
    dialog unzip xmlstarlet curl python3 bc \
    xdotool wmctrl smartmontools cabextract libarchive-tools

step "Groups / power / speed / housekeeping"
usermod -aG input,video,audio,render,bluetooth,plugdev "$U"
cat > /etc/systemd/system/cpu-performance.service <<'EOF'
[Unit]
Description=Set CPU governor to performance (RetroPie)
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $g; done'
[Install]
WantedBy=multi-user.target
EOF
systemctl enable cpu-performance.service
systemctl disable multipathd.service multipathd.socket || true
touch /etc/cloud/cloud-init.disabled
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
# Login adverts: mask properly (chmod -x on the script left a failed unit on the Alto)
systemctl disable --now motd-news.timer 2>/dev/null; systemctl mask motd-news.service
pro config set apt_news=false >/dev/null 2>&1 || true
# Updates at night, never at boot (on the Alto they ran 44 s at every boot and slowed the menu)
for t in apt-daily:04:00 apt-daily-upgrade:04:30; do
    mkdir -p /etc/systemd/system/${t%%:*}.timer.d
    printf '[Timer]\nOnCalendar=\nOnCalendar=*-*-* %s\nRandomizedDelaySec=15m\nPersistent=false\n' "${t#*:}" \
        > /etc/systemd/system/${t%%:*}.timer.d/override.conf
done
# Weekly disk health check
grep -q '^DEVICESCAN' /etc/smartd.conf && sed -i 's/^DEVICESCAN.*/DEVICESCAN -a -o on -S on -s (S\/..\/..\/7\/03) -W 4,50,55 -m root/' /etc/smartd.conf
systemctl enable --now smartmontools 2>/dev/null || systemctl enable --now smartd 2>/dev/null || true

step "Bluetooth for Xbox controllers"
sed -i -E \
    -e 's/^#?\s*ControllerMode\s*=.*/ControllerMode = dual/' \
    -e 's/^#?\s*FastConnectable\s*=.*/FastConnectable = true/' \
    -e 's/^#?\s*JustWorksRepairing\s*=.*/JustWorksRepairing = always/' \
    -e 's/^#?\s*Privacy\s*=.*/Privacy = device/' \
    -e 's/^#?\s*AutoEnable\s*=.*/AutoEnable=true/' \
    /etc/bluetooth/main.conf
# Only lengthen the link timeout (6 s) so brief signal fades don't disconnect. 2 s still dropped
# the Xbox pad every few minutes (Oct 2026), worse while the soundbar shares the adapter.
# Do NOT set Min/MaxConnectionInterval - forcing 7-9 caused constant dropouts on the Alto.
grep -q '^\[LE\]' /etc/bluetooth/main.conf || echo '[LE]' >> /etc/bluetooth/main.conf
grep -q '^ConnectionSupervisionTimeout' /etc/bluetooth/main.conf \
    && sed -i 's/^ConnectionSupervisionTimeout.*/ConnectionSupervisionTimeout=600/' /etc/bluetooth/main.conf \
    || sed -i '/^\[LE\]/a ConnectionSupervisionTimeout=600' /etc/bluetooth/main.conf
# USB power-saving on Bluetooth dongles causes dropouts
echo 'options btusb enable_autosuspend=0' > /etc/modprobe.d/btusb-no-autosuspend.conf
rfkill unblock all || true
systemctl enable --now bluetooth

step "RetroPie-Setup"
if [[ ! -d "$H/RetroPie-Setup" ]]; then
    sudo -u "$U" git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git "$H/RetroPie-Setup"
fi
cd "$H/RetroPie-Setup"
export SUDO_USER="$U"   # retropie_packages.sh takes the target user from SUDO_USER
./retropie_packages.sh setup basic_install
# Emulators chosen after testing on the Alto (all RetroArch, so View+Menu / View+X work everywhere)
for p in lr-pcsx-rearmed lr-ppsspp ppsspp lr-desmume skyscraper; do
    ./retropie_packages.sh $p || echo "!! $p install failed"
done
./retropie_packages.sh samba depends && ./retropie_packages.sh samba install_shares || echo "!! samba failed"

step "Xbox controller drivers"
./retropie_packages.sh xpadneo || echo "!! xpadneo install failed"
if ! dkms status | grep -q xone; then
    git clone --depth=1 https://github.com/dlundqvist/xone.git /tmp/xone \
      && (cd /tmp/xone && ./install.sh --release && ./install/firmware.sh --skip-disclaimer) \
      || echo "!! xone install failed (only needed for the Microsoft USB wireless adapter)"
fi
# dkms only builds for the running kernel - also build for the HWE kernel we boot into next
# (Oct 2026: drivers existed only for 6.8, so the controller had no driver on 7.0)
for k in /lib/modules/*/build; do
    k=$(basename "$(dirname "$k")")
    dkms autoinstall -k "$k" || echo "!! dkms build failed for $k"
done
dkms status

step "Xbox controller mappings (from the Alto: Bluetooth fw 5.09 + 5.23, and USB cable)"
install -o "$U" -g "$U" -m 644 "$BOOT/seed/es_input.cfg" "$CFG/all/emulationstation/es_input.cfg"
for f in "$BOOT"/seed/*.cfg; do
    [ "$(basename "$f")" = es_input.cfg ] && continue
    install -o "$U" -g "$U" -m 644 "$f" "$CFG/all/retroarch-joypads/"
done

step "Emulator defaults and settings"
setdef() { local f=$CFG/$1/emulators.cfg; [ -f "$f" ] && grep -q "^$2 = " "$f" && set_kv "$f" default "$2"; }
setdef n64 lr-mupen64plus          # standalone mupen64plus has no in-game menu
setdef psx lr-pcsx-rearmed         # beetle-psx too heavy for low-end CPUs
setdef psp lr-ppsspp               # standalone PPSSPP has no RetroArch menu
setdef nds lr-desmume
setdef arcade lr-fbneo
for p in channelf:lr-fbneo-chf coleco:lr-fbneo-cv msx:lr-fbneo-msx sega32x:lr-picodrive; do
    f=$CFG/${p%%:*}/emulators.cfg; [ -f "$f" ] && ! grep -q '^default' "$f" && setdef ${p%%:*} ${p#*:}
done
# Standalone PPSSPP starts in a small window otherwise
sed -i 's#/PPSSPPSDL  %ROM%#/PPSSPPSDL --fullscreen %ROM%#' $CFG/psp/emulators.cfg 2>/dev/null
A=$CFG/all/retroarch.cfg
set_kv $A input_analog_deadzone 0.15
set_kv $A savestate_auto_save true
set_kv $A savestate_auto_load true
O=$CFG/all/retroarch-core-options.cfg
set_kv $O desmume_cpu_mode jit                 # interpreter was far too slow
set_kv $O desmume_jit_block_size 100
set_kv $O desmume_advanced_timing disabled      # with PulseAudio this deadlocked DeSmuME
set_kv $O ppsspp_internal_resolution 960x544
set_kv $O ppsspp_cpu_core JIT
set_kv $O ppsspp_fast_memory enabled
set_kv $O ppsspp_auto_frameskip disabled
set_kv $O ppsspp_frameskip 0
set_kv $O pcsx_rearmed_bios auto
sed -i '/^audio_driver/d' $CFG/nds/retroarch.cfg; sed -i '1i audio_driver = "sdl2"' $CFG/nds/retroarch.cfg
# 1-frame run-ahead on light systems (snappier controls)
for s in nes fds snes megadrive mastersystem gamegear sg-1000 gb gbc pcengine; do
    f=$CFG/$s/retroarch.cfg; [ -f $f ] || continue
    sed -i '/^run_ahead_/d' $f
    sed -i '1i run_ahead_enabled = "true"\nrun_ahead_frames = "1"\nrun_ahead_secondary_instance = "true"\nrun_ahead_hide_warnings = "true"' $f
done
chown -R "$U:$U" $CFG
# Genesis is a link to megadrive -> every game listed twice
[ -L "$H/RetroPie/roms/genesis" ] && unlink "$H/RetroPie/roms/genesis"

step "EmulationStation settings"
ES=$CFG/all/emulationstation/es_settings.cfg
if [ ! -f "$ES" ]; then
    sudo -u "$U" tee "$ES" >/dev/null <<'EOF'
<?xml version="1.0"?>
<bool name="BackgroundIndexing" value="false" />
<bool name="IgnoreLeadingArticles" value="true" />
<bool name="UseFullscreenPaging" value="true" />
<bool name="QuickSystemSelect" value="true" />
<string name="ThemeSet" value="bluray" />
EOF
fi
# BackgroundIndexing=true froze the menu for hours on a hard disk with thousands of images

step "Themes"
while read -r repo theme; do
    ./retropie_packages.sh esthemes install_theme "$theme" "$repo" >/dev/null 2>&1 && echo "  $theme" || echo "!! $theme"
done <<'LIST'
anthonycaccese art-book-next
RetroPie pixel
c64-dev epicnoir
ruckage nes-mini
ehettervik luminous
ehettervik workbench
AmadhiX eudora
lilbud material
lilbud switch
lilbud flat-dark
ruckage snes-mini
ruckage famicom-mini
anthonycaccese crt
anthonycaccese art-book
TMNTturtleguy ComicBook
ChoccyHobNob cygnus
dmmarti steampunk
coinjunkie synthwave
nickearl retrowave
lostless playstation
RetroHursty69 magazinemadness
RetroHursty69 bluray
RetroHursty69 retroboy
RetroHursty69 mariobrosiii
LIST

step "Autologin on tty1 and boot straight into EmulationStation"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $U --noclear %I \$TERM
EOF
# 1080p60 if the TV offers it (lighter for games than 4K), otherwise the TV's preferred mode
cat > /usr/local/bin/retropie-display-mode <<'EOF'
#!/bin/sh
export DISPLAY=${DISPLAY:-:0}
out=$(xrandr | awk '/ connected/{print $1; exit}')
xrandr | grep -q '^ *1920x1080 ' && xrandr --output "$out" --mode 1920x1080 --rate 60 2>/dev/null || xrandr --output "$out" --auto
EOF
chmod 755 /usr/local/bin/retropie-display-mode
sudo -u "$U" tee "$H/.xinitrc" >/dev/null <<'EOF'
#!/bin/sh
# Stop fullscreen SDL apps (EmulationStation/RetroArch) minimising when focus moves -> black screen
export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS=0
/usr/local/bin/retropie-display-mode
xset -dpms; xset s off; xset s noblank
unclutter -idle 1 &
exec openbox-session
EOF
sudo -u "$U" mkdir -p "$H/.config/openbox"
sudo -u "$U" tee "$H/.config/openbox/autostart" >/dev/null <<'EOF'
# EmulationStation runs inside a fullscreen xterm so runcommand / RetroPie menus
# have a real foreground terminal (otherwise they get SIGTTIN-stopped -> black screen).
# Quit ES twice within 5s to drop to Openbox.
while true; do
    start=$(date +%s)
    xterm -fullscreen -bg black -fg white -fa 'DejaVu Sans Mono' -fs 16 \
        -e /usr/bin/emulationstation --no-splash
    [ $(( $(date +%s) - start )) -lt 5 ] && break
done &
EOF
# pi needs passwordless sudo for the RetroPie menu entries (as on the official Pi image)
echo "$U ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/010-retropie-pi
chmod 440 /etc/sudoers.d/010-retropie-pi
if ! grep -q 'startx' "$H/.bash_profile" 2>/dev/null; then
    sudo -u "$U" tee -a "$H/.bash_profile" >/dev/null <<'EOF'
[ -f ~/.profile ] && . ~/.profile
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor >/dev/null 2>&1
fi
EOF
fi

step "Game launch hooks"
# Pause background package builds while a game runs (they made games stutter); restore display mode after.
# The [R] trick stops pkill matching its own sudo process.
sudo -u "$U" tee $CFG/all/runcommand-onstart.sh >/dev/null <<'EOF'
#!/bin/bash
sudo -n pkill -STOP -f '[R]etroPie-Setup/tmp/build' 2>/dev/null
EOF
sudo -u "$U" tee $CFG/all/runcommand-onend.sh >/dev/null <<'EOF'
#!/bin/bash
/usr/local/bin/retropie-display-mode
sudo -n pkill -CONT -f '[R]etroPie-Setup/tmp/build' 2>/dev/null
EOF
chmod +x $CFG/all/runcommand-onstart.sh $CFG/all/runcommand-onend.sh
# Safety net: if a game crashes and onend never runs, resume paused builds anyway
cat > /usr/local/bin/retropie-build-resume-watchdog <<'EOF'
#!/bin/bash
while true; do
  if ! retropie-game-running; then
    ps -eo pid=,stat=,args= | awk '$2 ~ /^T/ && /[R]etroPie-Setup\/tmp\/build/ {print $1}' | xargs -r kill -CONT
  fi
  sleep 15
done
EOF
chmod 755 /usr/local/bin/retropie-build-resume-watchdog
printf '[Unit]\nDescription=Resume paused RetroPie builds when no game is running\n[Service]\nExecStart=/usr/local/bin/retropie-build-resume-watchdog\nRestart=always\nNice=10\n[Install]\nWantedBy=multi-user.target\n' \
    > /etc/systemd/system/retropie-build-resume.service
systemctl enable retropie-build-resume.service

step "Tailscale (remote access - run 'sudo tailscale up --hostname=$(hostname)' once to log in)"
curl -fsSL https://tailscale.com/install.sh | sh || echo "!! tailscale install failed"

step "melonDS DS (better DS emulator, built from source in the background after first boot)"
cp "$BOOT/build-melondsds.sh" "$H/" && chown "$U:$U" "$H/build-melondsds.sh" && chmod +x "$H/build-melondsds.sh"
mkdir -p "$H/RetroPie-Setup/tmp/build/melondsds" && chown "$U:$U" "$H/RetroPie-Setup/tmp/build/melondsds"
cat > /etc/systemd/system/melondsds-build.service <<EOF
[Unit]
Description=Build melonDS DS once (RetroPie)
After=network-online.target
ConditionPathExists=!/opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so
[Service]
Type=oneshot
User=$U
ExecStart=/bin/bash -c '$H/build-melondsds.sh > $H/build-melondsds.log 2>&1'
[Install]
WantedBy=multi-user.target
EOF
systemctl enable melondsds-build.service

step "Super RetroPie (menus, themes, launchers, timers - super-retropie/README.md)"
if [ -f "$BOOT/super-retropie/restore-super-retropie.sh" ] && [ ! -f "$BOOT/.plain-retropie" ]; then
    bash "$BOOT/super-retropie/restore-super-retropie.sh" || echo "!! Super RetroPie restore reported errors"
fi

step "Done - rebooting into EmulationStation"
touch "$BOOT/.done"
systemctl disable retropie-firstboot.service
sleep 5
systemctl reboot
