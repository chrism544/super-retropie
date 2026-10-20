<#
.SYNOPSIS
  Copies your RetroPie setup from the old box (Datto Alto) to the new box.

.DESCRIPTION
  Run from a normal (not Administrator) PowerShell on the PC whose SSH key both boxes trust,
  AFTER the new box has finished its USB install (it boots into EmulationStation).

  Copied:   EmulationStation settings, game lists (incl. hidden entries), controller mappings,
            all emulator configs + core options, RetroArch hotkeys, artwork (media folders),
            Skyscraper cache, themes, BIOS, saves / save states / memory cards,
            the game-list clean-up tool, and Bluetooth pairings (work if you move the same
            USB Bluetooth adapter across).
  NOT copied: the game files themselves (ROMs / ISOs). Put your games into \\<new box>\roms
            using the same folder names and the saves, artwork and lists line up again.

.EXAMPLE
  .\Migrate-RetroPie.ps1 -New 10.5.0.90
  .\Migrate-RetroPie.ps1 -New 10.5.0.90 -WhatIf     # size estimate only
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Old = '10.5.0.82',
    [Parameter(Mandatory)][string]$New,
    [string]$User = 'pi'
)
$ErrorActionPreference = 'Stop'
$ssh = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10')
function Remote($hostIp, $cmd) { $out = & ssh @ssh "$User@$hostIp" $cmd; if ($LASTEXITCODE -ne 0) { throw "ssh $hostIp failed: $cmd" }; $out }

# ---------- 1. Pre-flight ----------
foreach ($h in $Old, $New) {
    $info = Remote $h 'echo "$(hostname)|$(sudo -n true && echo sudo-ok)|$(pgrep -x "retroarch|PPSSPPSDL|mupen64plus" >/dev/null && echo PLAYING)|$(test -f /opt/retropie-bootstrap/.done -o -d /opt/retropie/supplementary/emulationstation && echo ready)"'
    $name, $sudo, $playing, $ready = $info -split '\|'
    Write-Host "$h = $name  ($sudo, $(if ($ready) {'RetroPie installed'} else {'NOT READY'}))"
    if ($sudo -ne 'sudo-ok') { throw "$h : passwordless sudo not available for $User" }
    if ($playing) { throw "$h : a game is running - quit it first" }
    if (-not $ready) { throw "$h : RetroPie isn't installed yet - wait for the USB install to finish" }
}
if ($Old -eq $New) { throw 'Old and New are the same box' }

# ---------- 2. What to copy (built on the old box; game files excluded) ----------
$list = @'
cd / || exit 1
{
  find opt/retropie/configs home/pi/RetroPie/BIOS home/pi/RetroPie/splashscreens etc/emulationstation/themes \
       \( -type f -o -type l \) ! -name 'es_log.txt*' -print0 2>/dev/null
  find home/pi/RetroPie/roms \( -type f -o -type l \) \( -path '*/media/*' -o -name gamelist.xml \
       -o -iname '*.srm' -o -iname '*.state*' -o -iname '*.sav' -o -iname '*.mcd' -o -iname '*.dsv' \
       -o -iname '*.eep' -o -iname '*.fla' -o -iname '*.mpk' -o -iname '*.sra' -o -iname '*.rtc' -o -iname '*.nv' \) -print0
  find home/pi/curate-gamelists.py home/pi/curate-lists -print0 2>/dev/null
  find var/lib/bluetooth -mindepth 1 -print0 2>/dev/null
}
'@ -replace "`r", ''
$size = Remote $Old ("sudo -n bash -c " + "'" + ($list -replace "'", "'\''") + " | du -ch --files0-from=- 2>/dev/null | tail -1'")
Write-Host "To copy from $Old (game files excluded): $size"
if (-not $PSCmdlet.ShouldProcess($New, "copy $size of settings, saves and artwork")) { return }

# ---------- 3. Stream old -> PC -> new (cmd pipe keeps the tar stream binary-safe) ----------
$tarOut = "sudo -n bash -c '" + ($list -replace "'", "'\''") + " | tar --null -T - -cpf -'"
$sshArgs = ($ssh -join ' ')
$t = Get-Date
cmd /c "ssh $sshArgs $User@$Old `"$($tarOut -replace '"','\"')`" | ssh $sshArgs $User@$New `"sudo -n tar -C / -xpf -`""
if ($LASTEXITCODE -ne 0) { throw "copy failed (exit $LASTEXITCODE)" }
Write-Host ("Copied in {0:mm\:ss}" -f ((Get-Date) - $t))

# ---------- 4. Tidy up on the new box ----------
$pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 20 | ForEach-Object { [char]$_ })
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$pw`n$pw`n"))
$post = @'
set -e
sudo -n chown -R pi:pi /opt/retropie/configs /home/pi/RetroPie /home/pi/curate-lists 2>/dev/null || true
[ -L /home/pi/RetroPie/roms/genesis ] && sudo -n unlink /home/pi/RetroPie/roms/genesis || true
sudo -n systemctl restart bluetooth
echo B64 | base64 -d | sudo -n smbpasswd -s -a pi >/dev/null
for s in roms bios configs splashscreens; do sudo -n sed -i -E "/^\[$s\]/,/^\[/{s/^(\s*)guest ok\s*=.*/\1guest ok = no\n\1valid users = pi/}" /etc/samba/smb.conf; done
sudo -n systemctl restart smbd
pkill -9 -x emulationstatio || true   # reload without letting ES overwrite the copied lists
echo "new box ready"
'@ -replace "`r", '' -replace 'B64', $b64
Remote $New $post
cmdkey /add:$New /user:$User /pass:$pw | Out-Null
$pw = $null; $b64 = $null

Write-Host "`nDone. Next on the new box:" -ForegroundColor Green
Write-Host "  1. Copy your games into \\$New\roms (same folder names as the old box); restart EmulationStation."
Write-Host "  2. Moved the TP-Link Bluetooth adapter across? The controller just reconnects. Otherwise pair it again."
Write-Host "  3. ssh $User@$New  then  sudo tailscale up --hostname=<name>   (remote access)"
