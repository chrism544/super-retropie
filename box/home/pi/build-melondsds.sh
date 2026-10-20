#!/bin/bash
set -e
D=~/RetroPie-Setup/tmp/build/melondsds; mkdir -p ~/RetroPie-Setup/tmp/build
tag=$(git ls-remote --tags --refs --sort=-v:refname https://github.com/JesseTG/melonds-ds 'v*' | head -1 | sed 's#.*/##')
echo "$(date +%T) building melonDS DS $tag"
[ -f $D/CMakeLists.txt ] || git clone -q --depth 1 --branch "$tag" https://github.com/JesseTG/melonds-ds $D
cd $D
nice -n 19 cmake -B build -DCMAKE_BUILD_TYPE=Release > ~/melondsds-cmake.log 2>&1
nice -n 19 ionice -c3 cmake --build build -j"$(nproc)" > ~/melondsds-make.log 2>&1
so=$(find build -name 'melondsds_libretro.so' | head -1); [ -f "$so" ] || { echo "BUILD FAILED"; exit 1; }
sudo -n mkdir -p /opt/retropie/libretrocores/lr-melondsds
sudo -n cp "$so" /opt/retropie/libretrocores/lr-melondsds/
c=/opt/retropie/configs/nds/emulators.cfg
grep -q '^lr-melondsds' $c || echo 'lr-melondsds = "/opt/retropie/emulators/retroarch/bin/retroarch -L /opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so --config /opt/retropie/configs/nds/retroarch.cfg %ROM%"' >> $c
echo "$(date +%T) INSTALLED $tag: $(ls -la /opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so)"
