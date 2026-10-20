# RetroPie import repairs and emulator checks — 13 October 2026

Target: 10.5.0.115.

## Imports
14 broken PSX cue sheets repaired using exact matching track files. Old Windows absolute paths and case mismatches were corrected in new cue copies. All 14 imported successfully; the importer converts and verifies each CHD before placing it in the library. Original failed cue sheets were retained.

Repaired: Arc the Lad 1, 2, and both discs of 3; Final Fantasy VII discs 1–3; Tekken 1 and 2; Gran Turismo 2 Arcade and Simulation; Threads of Fate; X-Men vs. Street Fighter; kal-dw7a.

The remaining 10 missing-track reports have complete copies already in the library. Their cue or playlist references were checked. This establishes file completeness, not a full gameplay compatibility test. Other failed entries are duplicate imports (54 PSX, 1 PSP, 13 Dreamcast, 466 N64).

## BIOS
Dreamcast dc_boot.bin is verified against MD5 e10c53c2f8b90bab96ead2d368858623.
dc_flash.bin was copied from this machine's existing 128KB dc_nvmem.bin flash settings. It is generated console settings, not a checksum-verified retail flash dump. Existing nvmem and VMU saves were preserved. The installed lr-flycast-dev requires dc_boot.bin and maintains nvmem itself.
Saturn Europe/USA mpr-17933.bin is verified against MD5 3240872c70984b6cbfda1586cab68dbe.

## Emulator checks
Intel UHD 770 acceleration works; OpenGL 4.6 and Vulkan are available. CPU governor is performance. Tests used isolated saves and configurations.

- Dreamcast: Metropolis Street Racer CDI loaded and completed 1,800 frames with the Intel OpenGL renderer. Wall time including startup/shutdown: 35.31 seconds. This is a short boot/frame test, not a sustained gameplay FPS measurement.
- PS2: Tekken 5 loaded its game ELF and ran for 28 seconds with the European BIOS and Intel Vulkan renderer at native resolution. Shutdown completed successfully. No sustained gameplay FPS measurement was made.
- Nintendo DS: Super Mario 64 DS initially timed out during shutdown. A repeat with networking disabled completed 600 frames and exited successfully in 2.22 seconds with audio/sync disabled. This is an unthrottled test and does not measure normal gameplay or audio quality.
- DS fix applied: melonds_network_mode = "disabled" in global core options, with a .before-network-fix backup. DS online features are disabled.
- GameCube: no imported games available; game performance could not be tested.

Tests deliberately disabled RetroArch audio, so audio initialization errors in those test logs do not diagnose the normal player configuration. Background image conversions were also running, limiting performance comparisons.

Detailed reports are on the device:
 /home/pi/import-repair-report.json
 /home/pi/import-library-validation.json
 /home/pi/import-repair-completion.json
 /home/pi/emulator-performance-check/
