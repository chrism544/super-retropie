#!/bin/bash
# Exit 0 if someone is playing: EmulationStation's launcher (runcommand) is active, or any
# emulator from RetroPie's folders is running (also covers games started outside ES).
# Matches by path, not process name - PCSX2's AppImage runs as "AppRun", which name-based
# checks ("pcsx2-qt") missed and so started jobs on top of a PS2 game (Oct 2026).
# The [r]/[o] brackets stop the pattern matching a shell whose command line contains it.
pgrep -f '[r]uncommand\.sh|[o]pt/retropie/(emulators|libretrocores)/' >/dev/null
