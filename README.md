# Super RetroPie

Turns a small x86 box (built on a Datto Alto) into a living-room console: unattended
Ubuntu Server 24.04 + RetroPie install from a USB stick, then a set of extras on top -
themed menus, Search, Save Manager with cheats, Play Stats, kid mode, Xbox (xemu) and Wii U
(Cemu) launchers, Sunshine streaming, controller mappings, per-game settings and nightly backups.

No games, BIOS files, keys or saves are included - bring your own.

## Highlights

- **Resume where you left off** - RetroArch games carry on from where you quit. Press **X** on the
  launch screen to start a game fresh instead (the resume point is kept as a backup; saves untouched).
- **CRT look** - subtle scanlines on the 8/16-bit and arcade consoles; change per console in
  RetroPie menu > Configuration Editor > Screen effect.
- **Phone Companion** - open `http://<box address>:8080` in any browser on your home network (or scan
  the QR code in RetroPie menu > Phone Companion) and enter the PIN shown on the TV: what's playing,
  Play Stats, upload games into the drop folder, Kid mode, reload the menu.
- Themed menus, Search, Save Manager with cheats, launch and boot screens, manuals, menu music,
  Xbox / Xbox 360 / Wii U launchers, Sunshine streaming, nightly artwork scraping and backups.

## Layout

| Path | What it is |
|---|---|
| `box/` | Every Super RetroPie file, at its path on the box (`box/usr/local/bin/...` = `/usr/local/bin/...`). This is the source of truth - refreshed with `tools/sync-from-box.sh` |
| `Prepare-RetroPieUsb.ps1` | Builds the bootable autoinstall USB stick (run as admin on Windows) |
| `Migrate-RetroPie.ps1` | Moves an existing box's setup over to a new one |
| `usb/nocloud/` | cloud-init seed and the first-boot RetroPie installer |
| `usb/nocloud/retropie/super-retropie/` | Rebuild kit - see its [README](usb/nocloud/retropie/super-retropie/README.md) |
| `tools/sync-from-box.sh` | Pulls a fresh `box/` from the live box, keeping private files out |
| `tools/build-super-retropie-kit.sh` | Full private snapshot (`files.tar.gz`) for the USB rebuild kit |
| `tools/proxmox-backup/` | Nightly backup of saves, BIOS and artwork to Proxmox |
| `tools/migration-2026-10/` | One-off scripts from the October 2026 move to the new box (kept for reference) |

## Quick start

```powershell
.\Prepare-RetroPieUsb.ps1 -DiskNumber 2 -WifiSsid "Home" -WifiPassword "..."
```

Boot the box from the stick; it installs, reboots and lands in EmulationStation.

## Turning an existing RetroPie (Ubuntu x86) into Super RetroPie

```bash
git clone https://github.com/chrism544/super-retropie.git && cd super-retropie
sudo bash usb/nocloud/retropie/super-retropie/restore-super-retropie.sh [--no-bezels]
```

The script packs `box/`, installs the emulators in `packages.txt`, xemu and Sunshine, lays the
files on top, then downloads the RetroArch cheat database, the console startup sounds and
The Bezel Project art (several GB - `--no-bezels` skips it; run `~/install-bezels.py` later).
The box keeps its own name and network settings. Reboot when it finishes.

Not in `box/`: games, BIOS, saves, keys, console startup recordings (`sudo retropie-get-boot-sounds`
fetches them), your game lists, per-game bezel configs (regenerated), RetroArch's downloadable
cheats/assets/shaders, network settings, and scripts for downloading games or BIOS.

## Keeping this repo up to date

```bash
tools/sync-from-box.sh            # stage the changes, review with: git diff --cached --stat
tools/sync-from-box.sh --push     # or commit and push in one go
```
