# Super RetroPie

Turns a small x86 box (built on a Datto Alto) into a living-room console: unattended
Ubuntu Server 24.04 + RetroPie install from a USB stick, then a set of extras on top -
themed menus, Search, Save Manager, Play Stats, kid mode, Xbox (xemu) and Wii U (Cemu)
launchers, Sunshine streaming, controller mappings, per-game settings and nightly backups.

No games, BIOS files, keys or saves are included - bring your own.

## Layout

| Path | What it is |
|---|---|
| `box/` | Every Super RetroPie file, at its path on the box (`box/usr/local/bin/...` = `/usr/local/bin/...`) - snapshot of 20 Oct 2026 |
| `Prepare-RetroPieUsb.ps1` | Builds the bootable autoinstall USB stick (run as admin on Windows) |
| `Migrate-RetroPie.ps1` | Moves an existing box's setup over to a new one |
| `usb/nocloud/` | cloud-init seed and the first-boot RetroPie installer |
| `usb/nocloud/retropie/super-retropie/` | Rebuild kit - see its [README](usb/nocloud/retropie/super-retropie/README.md) |
| `tools/box-scripts/` | Scripts and services that run on the box |
| `tools/` | Library import, BIOS, gamelist and maintenance helpers |
| `tools/proxmox-backup/` | Nightly backup of saves, BIOS and artwork to Proxmox |

## Quick start

```powershell
.\Prepare-RetroPieUsb.ps1 -DiskNumber 2 -WifiSsid "Home" -WifiPassword "..."
```

Boot the box from the stick; it installs, reboots and lands in EmulationStation.

## Turning an existing RetroPie (Ubuntu x86) into Super RetroPie

```bash
git clone https://github.com/<you>/super-retropie.git && cd super-retropie
sudo bash usb/nocloud/retropie/super-retropie/restore-super-retropie.sh --keep-network
```

`--keep-network` keeps the box's own name and address. The script packs `box/` itself,
installs the emulators in `packages.txt`, xemu and Sunshine, then lays the files on top.
Run `~/install-bezels.py` afterwards to fetch The Bezel Project art and per-game bezels.

Not in `box/`: games, BIOS, saves, keys, console startup sound recordings, your game lists,
per-game bezel configs (regenerated), RetroArch's downloadable cheats/assets/shaders, and
network settings. `tools/build-super-retropie-kit.sh` makes a full private snapshot instead.
