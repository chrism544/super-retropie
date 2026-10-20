# Super RetroPie rebuild kit

Everything that makes the box "Super RetroPie" on top of plain RetroPie, taken from the
running box (super-retropie, 10.5.0.19) on 18 Oct 2026.

| File | What it is |
|---|---|
| `files.tar.gz` | All customised files, stored with their full paths (see `files-list.txt`) |
| `restore-super-retropie.sh` | Installs packages, emulators, xemu, Sunshine and the bluray theme, then unpacks the files and enables everything |
| `packages.txt` | RetroPie emulator packages the box has |
| `versions.txt` | Sunshine version (the matching release is downloaded) |

What's in it: themed menus and screens (Search, Show IP, theme manager, settings, Bluetooth,
screensaver, kid mode, boot screen, Save Manager, menu music, Play Stats), launch and boot
screens, the Plymouth theme, the Xbox and Wii U launchers (pad helper, tilt/gyro), controller
mappings, per-game settings and bezel settings, `es_systems.cfg` (with Search last and Xbox),
the changed bluray theme files, timers (saves, scrape, safe update), soundbar reconnect,
Samba, the static network and the hostname.

What's **not** in it (private, copyrighted or too big): games, BIOS files, saves, Wii U keys,
Sunshine passwords/pairing, scraped artwork. Saves, BIOS and artwork are in the nightly
Proxmox backup.

## Rebuilding a box

1. Run `Prepare-RetroPieUsb.ps1` as usual. The kit rides along on the stick, and the
   first-boot install runs `restore-super-retropie.sh` at the end by itself.
   (To get plain RetroPie instead, create an empty file `.plain-retropie` next to
   `install-retropie.sh` on the box before first boot finishes.)
2. Put the saves, BIOS and artwork back from the Proxmox backup. On Proxmox, as root:

   ```
   B=$(ls -d /var/lib/vz/super-retropie-backups/20*/ | tail -1)
   rsync -a $B/home/pi/RetroPie/ pi@10.5.0.19:/home/pi/RetroPie/
   rsync -a $B/opt/retropie/configs/ pi@10.5.0.19:/opt/retropie/configs/
   rsync -a $B/home/pi/.config/ $B/home/pi/.local pi@10.5.0.19:/home/pi/
   ```
   The backup key is read-only on the box, so this needs Proxmox root's normal key on the new
   box first: `ssh-copy-id pi@10.5.0.19` (password login) - remove it again afterwards.
3. Copy the games back (drop folder / Samba share), re-add the Wii U keys, then run
   `python3 ~/install-bezels.py` for the bezel artwork and let the nightly scrape fill in
   anything missing.
4. Sunshine: open https://super-retropie.local:47990, create a login and pair Moonlight again.

On an existing RetroPie box (not from the stick): copy this folder over and run
`sudo bash restore-super-retropie.sh` (add `--keep-network` to leave its name/IP alone).

## Refreshing the kit

The kit is a snapshot. After more changes on the box, rebuild it on the box with the build
script (`tools/build-super-retropie-kit.sh`) and copy `/tmp/super-retropie-kit/*` back here.
