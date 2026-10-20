import pathlib,subprocess,os,time,json
work=pathlib.Path('/home/pi/emulator-performance-check'); env=os.environ.copy(); env.update(DISPLAY=':0',QT_QPA_PLATFORM='xcb')
log=work/'PCSX2.log'; pcs=work/'PCSX2'
with log.open('w') as f:
 p=subprocess.Popen(['/opt/retropie/emulators/pcsx2-appimage/app/AppRun','-datapath',str(pcs),'-nogui','-nofullscreen','-earlyconsolelog','--','/home/pi/RetroPie/roms/ps2/Tekken 5.chd'],stdout=f,stderr=subprocess.STDOUT,env=env)
 try: p.wait(timeout=35)
 except subprocess.TimeoutExpired:
  p.terminate()
  try: p.wait(timeout=10)
  except subprocess.TimeoutExpired: p.kill(); p.wait()
print('exit',p.returncode); print(log.read_text(errors='replace')[-7000:])
source=pathlib.Path('/home/pi/RetroPie-Setup/tmp/build/melondsds')
for p in (source/'src').rglob('*'):
 if p.suffix in ['.cpp','.h','.hpp']:
  txt=p.read_text(errors='replace')
  if 'network_mode' in txt or 'networking' in p.name.lower():
   print('NETWORK SOURCE',p)
   for l in txt.splitlines():
    if 'network' in l.lower() or 'disabled' in l.lower(): print(l[:180])
