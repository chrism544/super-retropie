#!/bin/bash
# Builds the Super RetroPie rebuild kit: every customisation (no games, BIOS, saves or keys).
set -u
K=/tmp/super-retropie-kit; rm -rf $K; mkdir -p $K
L=$K/filelist
H=/home/pi
{
  ls -d /usr/local/bin/* /usr/local/lib/retropie /usr/local/share/retropie-splash /usr/local/share/super-retropie
  ls -d /etc/systemd/system/retropie-*.service /etc/systemd/system/retropie-*.timer | grep -v firstboot
  ls -d /etc/udev/rules.d/61-xpadneo-rebind.rules /etc/udev/rules.d/95-retropie-display.rules /etc/modules-load.d/uinput.conf
  echo /etc/emulationstation/es_systems.cfg
  find /etc/emulationstation/themes/bluray -type f -newermt 2026-10-09
  echo /usr/share/plymouth/themes/super-retropie
  echo /etc/default/grub; echo /etc/samba/smb.conf; echo /etc/netplan/50-cloud-init.yaml
  echo /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
  find /opt/retropie/configs -type f ! -path "*/skyscraper/*" ! -path "*/retroarch/overlay/*" ! -path "*/downloaded_*" \
       ! -name "es_log*" ! -name "*.bak" ! -name "*.log" ! -name "*.srm" ! -name "*.state*"
  find /opt/retropie/emulators -maxdepth 2 -type f \( -name "*.sh" -o -name "*.py" \)
  ls -d $H/.config/openbox $H/.config/Cemu/controllerProfiles $H/.config/Cemu/gameProfiles $H/.config/mpv \
        $H/.config/retropie-*.json $H/.config/sunshine/sunshine.conf $H/.config/sunshine/apps.json \
        $H/.config/PCSX2/inis $H/.Xresources $H/.local/share/xemu/xemu/xemu.toml 2>/dev/null
  ls -d $H/*.py $H/*.sh 2>/dev/null
  ls -d $H/RetroPie/retropiemenu $H/RetroPie/retropiemenu-replaced $H/RetroPie/searchgames $H/RetroPie/music \
        $H/RetroPie/splashscreens $H/RetroPie-Setup/ext 2>/dev/null
} | sed 's|^/||' | sort -u > $L
sudo tar -C / -czf $K/files.tar.gz --numeric-owner -T $L 2>$K/tar-errors.txt
# what to reinstall
{ ls /opt/retropie/libretrocores; ls /opt/retropie/emulators; ls /opt/retropie/supplementary; } | sort -u > $K/packages.txt
dpkg-query -W -f='${Package} ${Version}\n' sunshine 2>/dev/null > $K/versions.txt
ls /opt/retropie/emulators/xemu-appimage/ >> $K/versions.txt
wc -l < $L; du -sh $K/files.tar.gz; cat $K/tar-errors.txt | head
