import pathlib,shutil,os,subprocess,time,json,zipfile,re
base=pathlib.Path('/home/pi/RetroPie'); work=pathlib.Path('/home/pi/emulator-performance-check'); work.mkdir(exist_ok=True)
dc=base/'BIOS/dc'
if not (dc/'dc_flash.bin').exists(): shutil.copy2(dc/'dc_nvmem.bin',dc/'dc_flash.bin')
print('Preserved existing Dreamcast flash settings as dc_flash.bin',flush=True)
if subprocess.run(['pgrep','-x','retroarch|pcsx2-qt|dolphin-emu'],stdout=subprocess.DEVNULL).returncode==0: raise SystemExit('Game active; postponing benchmarks')
bios=work/'BIOS'
if not bios.exists(): shutil.copytree(base/'BIOS',bios)
save=work/'saves'; save.mkdir(exist_ok=True)
opts=work/'options.cfg'; shutil.copy2('/opt/retropie/configs/all/retroarch-core-options.cfg',opts)
cfg=work/'benchmark.cfg'
cfg.write_text('system_directory = "'+str(bios)+'"\nsavefile_directory = "'+str(save)+'"\nsavestate_directory = "'+str(save)+'"\ncore_options_path = "'+str(opts)+'"\nvideo_driver = "gl"\nvideo_fullscreen = "false"\nvideo_windowed_fullscreen = "false"\nvideo_window_scale = "1"\nvideo_vsync = "false"\naudio_driver = "null"\naudio_sync = "false"\ninput_driver = "null"\ninput_joypad_driver = "null"\nconfig_save_on_exit = "false"\n')
env=os.environ.copy(); env.update(DISPLAY=':0',QT_QPA_PLATFORM='xcb')
ra='/opt/retropie/emulators/retroarch/bin/retroarch'; results=[]
tests=[('Dreamcast','/opt/retropie/libretrocores/lr-flycast-dev/flycast_libretro.so',next((base/'roms/dreamcast').glob('*Metropolis*.cdi'),None))]
z=next((base/'roms/nds').glob('*Super Mario 64 DS (EU)*.zip'),None)
if z:
 with zipfile.ZipFile(z) as archive:
  n=next(n for n in archive.namelist() if n.lower().endswith('.nds'))
  rom=work/'Super Mario 64 DS.nds'; rom.write_bytes(archive.read(n))
 tests.append(('Nintendo DS','/opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so',rom))
for name,core,rom in tests:
 if not rom: continue
 if subprocess.run(['pgrep','-x','retroarch|pcsx2-qt'],stdout=subprocess.DEVNULL).returncode==0: break
 log=work/(name.replace(' ','-')+'.log'); start=time.monotonic()
 with log.open('w') as f:
  try:
   p=subprocess.run([ra,'-v','-L',core,'-c',str(cfg),'-M','noload-nosave','--max-frames','1800',str(rom)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=90)
   code=p.returncode
  except subprocess.TimeoutExpired: code='timeout'
 elapsed=time.monotonic()-start
 text=log.read_text(errors='replace')
 result={'system':name,'game':str(rom),'exit_code':code,'seconds':round(elapsed,2),'details':[l for l in text.splitlines() if any(k in l.lower() for k in ['average monitor','frames','renderer','error','failed'])][-15:]}
 results.append(result); print(json.dumps(result),flush=True)
pcs=work/'PCSX2'; pcs.mkdir(exist_ok=True)
shutil.copytree('/home/pi/.config/PCSX2/inis',pcs/'inis',dirs_exist_ok=True)
ini=pcs/'inis/PCSX2.ini'; text=ini.read_text(); text=re.sub(r'^StartFullscreen =.*','StartFullscreen = false',text,flags=re.M); ini.write_text(text)
rom=next((base/'roms/ps2').glob('*Tekken 5*.chd'),None)
if rom and subprocess.run(['pgrep','-x','retroarch|pcsx2-qt'],stdout=subprocess.DEVNULL).returncode!=0:
 log=work/'PCSX2.log'
 with log.open('w') as f:
  p=subprocess.Popen(['/opt/retropie/emulators/pcsx2-appimage/app/AppRun','-datapath',str(pcs),'-nogui','-nofullscreen','--',str(rom)],env=env,stdout=f,stderr=subprocess.STDOUT)
  try: p.wait(timeout=35)
  except subprocess.TimeoutExpired:
   p.terminate()
   try: p.wait(timeout=10)
   except subprocess.TimeoutExpired: p.kill(); p.wait()
 results.append({'system':'PS2','game':str(rom),'exit_code':p.returncode,'log':str(log)})
 print('PS2',log.read_text(errors='replace')[-4500:],flush=True)
results.append({'system':'GameCube','status':'No games currently imported; cannot benchmark'})
(work/'results.json').write_text(json.dumps(results,indent=2))
