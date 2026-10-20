import pathlib,xml.etree.ElementTree as ET,datetime,shutil,json,hashlib,os,subprocess,time,sys,re
HOME=pathlib.Path.home(); OUT=HOME/'.local/share/retropie-library-improvements'
def settext(g,tag,value):
 e=g.find(tag)
 if e is None: e=ET.SubElement(g,tag)
 e.text=value

def run():
 r=HOME/'RetroPie/roms/snes'; p=r/'gamelist.xml'; tree=ET.parse(p); root=tree.getroot(); games=root.findall('game')
 before={g.findtext('path'):tuple(g.findtext(t) for t in ['favorite','playcount','lastplayed','hidden']) for g in games}
 base=next(g for g in games if re.match(r'Super Mario World \(U\)',pathlib.Path(g.findtext('path','')).stem) and g.findtext('image') and (r/g.findtext('image')).is_file())
 donor=next(g for g in games if g.findtext('path','').endswith('Europe/Legend of Zelda, The - A Link to the Past (E) [!].smc'))
 fallbacks=[]; corrected=[]
 for g in games:
  rom=r/g.findtext('path',''); image=g.findtext('image','')
  if rom.is_file() and (not image or not (r/image).is_file()) and '(SMW1 Hack)' in rom.stem:
   settext(g,'image',base.findtext('image'))
   if base.findtext('marquee'): settext(g,'marquee',base.findtext('marquee'))
   settext(g,'name',rom.stem); fallbacks.append({'game':str(rom),'artwork_source':'Super Mario World base game','image':base.findtext('image')})
  if str(rom).endswith('USA/Legend of Zelda, The - A Link to the Past (U) [!].smc'):
   data=rom.read_bytes(); data=data[512:] if len(data)%32768==512 else data
   assert hashlib.md5(data).hexdigest()=='608c22b8ff930c62dc2de54bcd6eba72'
   if g.findtext('name')!='The Legend of Zelda: A Link to the Past (USA)': corrected.append(str(rom))
   settext(g,'name','The Legend of Zelda: A Link to the Past (USA)')
   for tag in ['image','marquee','desc','genre','developer','publisher','players','rating']:
    if donor.findtext(tag): settext(g,tag,donor.findtext(tag))
 assert before=={g.findtext('path'):tuple(g.findtext(t) for t in ['favorite','playcount','lastplayed','hidden']) for g in games}
 if fallbacks or corrected:
  backup=OUT/'backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); backup.mkdir(parents=True,exist_ok=True); shutil.copy2(p,backup/'snes-before-final-artwork.xml')
  ET.indent(tree,space='  '); tmp=p.with_name(p.name+'.final-art-new'); tree.write(tmp,encoding='utf-8',xml_declaration=True); ET.parse(tmp); os.replace(tmp,p)
 report=json.loads((OUT/'report.json').read_text())
 if fallbacks: report['base_game_artwork_fallbacks']=fallbacks
 for g in report['best_games']:
  if g['path'].endswith('USA/Legend of Zelda, The - A Link to the Past (U) [!].smc'): g['name']='The Legend of Zelda: A Link to the Past (USA)'
 actual=[g for g in games if (r/g.findtext('path','')).is_file()]; valid=sum(bool(g.findtext('image')) and (r/g.findtext('image')).is_file() for g in actual)
 report['snes_total_artwork']={'listed_existing_games':len(actual),'valid_images':valid,'base_game_fallbacks':len(report.get('base_game_artwork_fallbacks',[])),'zelda_original_checksum_verified':True}
 (OUT/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report['snes_total_artwork']),flush=True)

if __name__=='__main__':
 if '--already-held' in sys.argv:
  run()
 else:
  hold=pathlib.Path('/tmp/es-hold')
  def others_editing():
   for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
    try:
     cmd=p.read_bytes().replace(b'\0',b' ')
     if b'/usr/local/bin/retropie-es-edit ' in cmd and int(p.parent.name)!=os.getpid(): return True
    except (FileNotFoundError,PermissionError,ProcessLookupError): pass
   return False
  while hold.exists() or others_editing() or subprocess.run(['/usr/local/bin/retropie-game-running']).returncode==0: time.sleep(10)
  try: fd=os.open(hold,os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.close(fd)
  except FileExistsError: raise SystemExit('Another menu edit started; rerun this service')
  try:
   subprocess.run(['pkill','-TERM','-x','emulationstatio'])
   for _ in range(30):
    if subprocess.run(['pgrep','-x','emulationstatio'],stdout=subprocess.DEVNULL).returncode: break
    time.sleep(1)
   else: raise RuntimeError('Menu did not stop; no library edits applied')
   run()
  finally: hold.unlink(missing_ok=True)
