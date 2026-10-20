#!/bin/bash
# One-off (Oct 2026): after the current game, check EmulationStation fills the screen width; if it
# was started at a 4:3 size it draws in the left 3/4 only - restart it once in that case.
export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
while retropie-game-running; do sleep 20; done
sleep 25
w() { xwd -root -silent | python3 -c "
import sys, struct; from PIL import Image
d=sys.stdin.buffer.read(); h=struct.unpack(\">25I\",d[:100]); hs,w,ht,bpl,nc=h[0],h[4],h[5],h[12],h[19]; off=hs+nc*12
im=Image.frombuffer(\"RGBX\",(w,ht),d[off:off+bpl*ht],\"raw\",\"BGRX\",bpl,1).convert(\"L\")
band=im.crop((0,int(ht*0.008),w,int(ht*0.025)))
xs=[x for x in range(w) if max(band.crop((x,0,x+1,band.height)).getdata())>60]
print(max(xs) if xs else 0, w)"; }
read r sw < <(w); echo "$(date) top line ends at $r of $sw" >> /home/pi/es-width-check.log
if [ "$r" -gt 0 ] && [ "$r" -lt $((sw * 85 / 100)) ]; then
    echo "narrow - restarting EmulationStation" >> /home/pi/es-width-check.log
    retropie-es-edit true; sleep 30
    read r sw < <(w); echo "$(date) after restart: $r of $sw" >> /home/pi/es-width-check.log
fi
