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
  # Kodi picks the pad up again after it sleeps (Oct 2026)
  ls -d /etc/udev/rules.d/90-kodi-pad-rescan.rules /etc/systemd/system/kodi-pad-rescan.service 2>/dev/null
  # lr-mupen64plus on x86 is "Mupen64Plus OpenGL" - a link to the per-game N64 settings (Oct 2026)
  echo "/opt/retropie/configs/all/retroarch/config/Mupen64Plus OpenGL"
  echo /etc/emulationstation/es_systems.cfg
  find /etc/emulationstation/themes/bluray -type f -newermt 2026-10-09
  echo /usr/share/plymouth/themes/super-retropie
  echo /etc/default/grub; echo /etc/samba/smb.conf; echo /etc/smartd.conf; echo /etc/netplan/50-cloud-init.yaml
  echo /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
  # cheats-db: 250 MB, restore-super-retropie.sh downloads it again
  find /opt/retropie/configs -type f ! -path "*/skyscraper/*" ! -path "*/retroarch/overlay/*" ! -path "*/downloaded_*" \
       ! -path "*/retroarch/cheats-db/*" \
       ! -name "es_log*" ! -name "*.bak" ! -name "*.log" ! -name "*.srm" ! -name "*.state*"
  find /opt/retropie/emulators -maxdepth 2 -type f \( -name "*.sh" -o -name "*.py" \)
  ls -d $H/.config/openbox $H/.config/Cemu/controllerProfiles $H/.config/Cemu/gameProfiles $H/.config/mpv \
        $H/.config/retropie-*.json $H/.config/sunshine/sunshine.conf $H/.config/sunshine/apps.json \
        $H/.config/PCSX2/inis $H/.Xresources $H/.local/share/xemu/xemu/xemu.toml \
        $H/.local/bin/retropie-preserve-xbox.py $H/.local/bin/retropie-finalize-snes-art.py 2>/dev/null
  ls -d $H/*.py $H/*.sh 2>/dev/null
  # Kodi: Xbox pad map, triggers left/right in Live TV/Radio, the radio picture (Oct 2026)
  ls -d $H/.kodi/userdata/addon_data/peripheral.joystick/resources/buttonmaps/xml/linux/Xbox_Wireless_Controller_11b_9a.xml \
        $H/.kodi/userdata/keymaps/pvr-triggers.xml $H/.kodi/media/radio-station.png 2>/dev/null
  # Ship of Harkinian (Ports): the app, launcher and settings - not oot*.o2r (built from the N64 copies
  # on first start, see /opt/retropie/ports/soh/soh.sh) or its saves (Oct 2026)
  # (the app itself is downloaded again by restore-super-retropie.sh)
  find /opt/retropie/ports/soh -type f ! -name "*.o2r" ! -path "*/soh/app/*" ! -path "*/home/Save/*" ! -path "*/home/logs/*" \
       ! -path "*/__pycache__/*" 2>/dev/null
  ls -d $H/RetroPie/roms/ports/*.sh $H/RetroPie/roms/ports/gamelist.xml 2>/dev/null
  ls -d $H/RetroPie/retropiemenu $H/RetroPie/retropiemenu-replaced $H/RetroPie/searchgames $H/RetroPie/music \
        $H/RetroPie/splashscreens $H/RetroPie-Setup/ext 2>/dev/null
} | sed 's|^/||' | sort -u > $L
sudo tar -C / -czf $K/files.tar.gz --numeric-owner -T $L 2>$K/tar-errors.txt
# what to reinstall
{ ls /opt/retropie/libretrocores; ls /opt/retropie/emulators; ls /opt/retropie/supplementary; } | sort -u > $K/packages.txt
dpkg-query -W -f='${Package} ${Version}\n' sunshine 2>/dev/null > $K/versions.txt
ls /opt/retropie/emulators/xemu-appimage/ >> $K/versions.txt
wc -l < $L; du -sh $K/files.tar.gz; cat $K/tar-errors.txt | head
