import pathlib,subprocess,os,time,json,shutil
w=pathlib.Path('/home/pi/emulator-performance-check'); env=os.environ.copy(); env.update(DISPLAY=':0',QT_QPA_PLATFORM='xcb',XDG_CONFIG_HOME=str(w/'xdg'))
log=w/'PCSX2-retest.log'
with log.open('w') as f:
 p=subprocess.Popen(['/opt/retropie/emulators/pcsx2-appimage/app/AppRun','-datapath',str(w),'-nogui','-nofullscreen','-earlyconsolelog','--','/home/pi/RetroPie/roms/ps2/Tekken 5.chd'],stdout=f,stderr=subprocess.STDOUT,env=env)
 try: p.wait(timeout=30)
 except subprocess.TimeoutExpired:
  p.terminate()
  try: p.wait(timeout=10)
  except subprocess.TimeoutExpired:p.kill();p.wait()
print('PS2 exit',p.returncode,log.read_text(errors='replace')[-6000:],flush=True)
opts=w/'ds-retest-options.cfg'; opts.write_text('melonds_network_mode = "disabled"\n')
cfg=w/'ds-retest.cfg'
cfg.write_text((w/'benchmark.cfg').read_text().replace(str(w/'options.cfg'),str(opts))+'\nconfig_directory = "'+str(w/'config')+'"\nmicrophone_enable = "false"\n')
start=time.monotonic(); log=w/'DS-retest.log'
with log.open('w') as f:
 try:
  p=subprocess.run(['/opt/retropie/emulators/retroarch/bin/retroarch','-v','-L','/opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so','-c',str(cfg),'-M','noload-nosave','--max-frames','600',str(w/'Super Mario 64 DS.nds')],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=45); code=p.returncode
 except subprocess.TimeoutExpired:code='timeout'
print('DS exit',code,'seconds',round(time.monotonic()-start,2),log.read_text(errors='replace')[-2500:],flush=True)
