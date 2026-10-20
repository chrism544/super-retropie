#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Builds a UEFI-bootable USB stick that installs Ubuntu Server 24.04 + RetroPie
  unattended on a Datto Alto (x86).

.DESCRIPTION
  - Downloads the latest Ubuntu 24.04 live-server ISO and checks its SHA256
  - Wipes the chosen USB disk, creates an 8 GB FAT32 partition, copies the ISO onto it
  - Adds an "autoinstall" GRUB entry + cloud-init seed (user-data) with:
      your SSH public key (key-only SSH login), user/password, optional WiFi
  - Guards against the Oct 2026 failed install: no installer refresh, waits for internet
    and aborts rather than installing offline, ISO kernel only, checks initramfs
  - First boot of the Alto installs RetroPie, WiFi/BT firmware, Xbox drivers
    (xpad / xpadneo / xone) and boots straight into EmulationStation.

.EXAMPLE
  .\Prepare-RetroPieUsb.ps1 -DiskNumber 2 -WifiSsid "Home" -WifiPassword "secret"
#>
[CmdletBinding()]
param(
    [int]$DiskNumber = -1,
    [string]$Hostname = 'retropie',
    [string]$Username = 'pi',
    [string]$SshPublicKeyPath = "$env:USERPROFILE\.ssh\id_ed25519.pub",
    [string]$WifiSsid,
    [string]$WifiPassword,
    [string]$IsoCache = "$env:USERPROFILE\Downloads"
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# ---------- 1. Pick the USB disk (USB bus only, explicit confirmation) ----------
$usb = Get-Disk | Where-Object BusType -eq 'USB'
if (-not $usb) { throw 'No USB disks found. Plug the stick in and re-run.' }
$usb | Format-Table Number, FriendlyName, @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, PartitionStyle -AutoSize
if ($DiskNumber -lt 0) { $DiskNumber = [int](Read-Host 'Disk number of the USB stick to WIPE') }
$disk = $usb | Where-Object Number -eq $DiskNumber
if (-not $disk) { throw "Disk $DiskNumber is not a USB disk. Refusing." }
if ($disk.Size -lt 8GB) { throw 'USB stick must be at least 8 GB.' }
$confirm = Read-Host "ALL DATA on disk $DiskNumber ($($disk.FriendlyName)) will be erased. Type ERASE to continue"
if ($confirm -cne 'ERASE') { throw 'Aborted.' }

# ---------- 2. Credentials ----------
if (-not (Test-Path $SshPublicKeyPath)) { throw "SSH public key not found: $SshPublicKeyPath" }
$sshKey = (Get-Content $SshPublicKeyPath -Raw).Trim()
$pw = Read-Host "Password for user '$Username' (console + sudo; SSH is key-only)" -AsSecureString
$pwPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw))
$openssl = @('C:\Program Files\Git\usr\bin\openssl.exe', (Get-Command openssl -ErrorAction SilentlyContinue).Source) |
           Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $openssl) { throw 'openssl not found (install Git for Windows).' }
# Don't pipe: Windows PowerShell 5.1 adds a BOM + CR to native stdin, corrupting the password.
# Write it to a temp file with no BOM and no newline instead.
$pwFile = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllText($pwFile, $pwPlain, (New-Object Text.UTF8Encoding $false))
    $pwHash = (& $openssl passwd -6 -in $pwFile).Trim()
} finally { Remove-Item -LiteralPath $pwFile -Force; $pwPlain = $null }
if (-not $pwHash.StartsWith('$6$')) { throw 'Password hashing failed.' }

# ---------- 3. Download + verify ISO ----------
$base = 'https://releases.ubuntu.com/24.04/'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$sums = (Invoke-WebRequest "$base/SHA256SUMS" -UseBasicParsing).Content
# Windows PowerShell 5.1 returns this file as byte[] (served as octet-stream)
if ($sums -is [byte[]]) { $sums = [Text.Encoding]::ASCII.GetString($sums) }
$line = ($sums -split "`n" | Where-Object { $_ -match 'live-server-amd64\.iso' } | Select-Object -First 1)
if (-not $line) { throw "Could not find the live-server ISO in $base/SHA256SUMS" }
$expected, $isoName = $line -split '\s+\*?'
$iso = Join-Path $IsoCache $isoName
if (-not (Test-Path $iso) -or (Get-FileHash $iso -Algorithm SHA256).Hash -ne $expected.ToUpper()) {
    Write-Host "Downloading $isoName ..."
    # curl.exe, not BITS: BITS fails in "Run as different user" admin sessions (0x800704DD)
    & curl.exe -L --fail -o $iso "$base$isoName"
    if ($LASTEXITCODE -ne 0) { throw "ISO download failed (curl exit $LASTEXITCODE)" }
    if ((Get-FileHash $iso -Algorithm SHA256).Hash -ne $expected.ToUpper()) { throw 'ISO checksum mismatch.' }
}
Write-Host "ISO OK: $iso"

# ---------- 4. Wipe + partition USB (FAT32 caps at 32 GB in Windows -> 8 GB partition) ----------
Clear-Disk -Number $DiskNumber -RemoveData -RemoveOEM -Confirm:$false -ErrorAction SilentlyContinue
if ((Get-Disk $DiskNumber).PartitionStyle -eq 'RAW') { Initialize-Disk -Number $DiskNumber -PartitionStyle GPT }
else { Set-Disk -Number $DiskNumber -PartitionStyle GPT }
$part = New-Partition -DiskNumber $DiskNumber -Size 8GB -AssignDriveLetter -GptType '{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}'
Format-Volume -Partition $part -FileSystem FAT32 -NewFileSystemLabel 'RPINSTALL' -Confirm:$false | Out-Null
$usbRoot = "$((Get-Partition -DiskNumber $DiskNumber -PartitionNumber $part.PartitionNumber).DriveLetter):\"

# ---------- 5. Copy ISO contents ----------
$mount = Mount-DiskImage -ImagePath $iso -PassThru
try {
    $isoRoot = "$(($mount | Get-Volume).DriveLetter):\"
    robocopy $isoRoot $usbRoot /E /NFL /NDL /NJH /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
} finally { Dismount-DiskImage -ImagePath $iso | Out-Null }
Get-ChildItem $usbRoot -Recurse -File | ForEach-Object { $_.IsReadOnly = $false }

# ---------- 6. Seed autoinstall config ----------
$lf = { param($p, $text) [IO.File]::WriteAllText($p, ($text -replace "`r`n", "`n"), (New-Object Text.UTF8Encoding $false)) }
$seed = Join-Path $usbRoot 'nocloud'
New-Item -ItemType Directory -Force -Path "$seed\retropie" | Out-Null

$wifiBlock = ''
if ($WifiSsid) {
    $q = { param($s) "'" + ($s -replace "'", "''") + "'" }
    $wifiBlock = @"
    wifis:
      wireless:
        match:
          name: "wl*"
        dhcp4: true
        optional: true
        access-points:
          $(& $q $WifiSsid):
            password: $(& $q $WifiPassword)
"@
}
# Literal .Replace() - the SHA-512 hash is full of '$'
$userData = (Get-Content "$here\usb\nocloud\user-data.template" -Raw).
    Replace('__HOSTNAME__', $Hostname).Replace('__USERNAME__', $Username).
    Replace('__PASSWORD_HASH__', $pwHash).Replace('__SSH_PUBKEY__', $sshKey).
    Replace('__WIFI_BLOCK__', $wifiBlock)
& $lf "$seed\user-data" $userData
& $lf "$seed\meta-data" "instance-id: retropie-$Hostname`n"
# Copy the first-boot files, including sub-folders (seed\ holds the Xbox controller mappings)
$src = "$here\usb\nocloud\retropie"
foreach ($f in Get-ChildItem $src -File -Recurse) {
    $dest = Join-Path "$seed\retropie" $f.FullName.Substring($src.Length + 1)
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    # Binary files (the Super RetroPie kit's files.tar.gz) are copied as-is - Get-Content would corrupt them
    if ($f.Extension -in '.gz', '.png', '.jpg', '.ttf', '.wav') { Copy-Item -LiteralPath $f.FullName $dest -Force }
    else { & $lf $dest (Get-Content $f.FullName -Raw) }
}

# ---------- 7. GRUB: auto-select unattended install ----------
$grub = Join-Path $usbRoot 'boot\grub\grub.cfg'
$cfg = Get-Content $grub -Raw
$entry = @'
set timeout=10
set default=0
menuentry "AUTO-INSTALL RetroPie (WIPES INTERNAL DISK)" {
	set gfxpayload=keep
	linux	/casper/vmlinuz autoinstall "ds=nocloud;s=/cdrom/nocloud/" ---
	initrd	/casper/initrd
}
'@
$cfg = $cfg -replace '(?m)^set timeout=.*$', ''
& $lf $grub ($entry + "`n" + $cfg)

Write-Host "`nUSB ready on $usbRoot" -ForegroundColor Green
Write-Host "Boot the Alto from it (UEFI, Secure Boot OFF, storage AHCI/VMD off, ethernet plugged in)."
Write-Host "No internet within 3 min = install aborts on purpose instead of going offline. Fix the cable and reboot the stick."
Write-Host "Then: ssh $Username@$Hostname  and  tail -f /var/log/retropie-install.log"
