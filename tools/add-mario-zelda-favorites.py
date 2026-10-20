#!/usr/bin/env python3
import collections,datetime,json,os,pathlib,re,shutil,subprocess,sys,xml.etree.ElementTree as ET
BASE=pathlib.Path('/home/pi/RetroPie/roms')
ES=pathlib.Path('/opt/retropie/configs/all/emulationstation')
systems=ET.parse('/etc/emulationstation/es_systems.cfg').getroot()
selected=collections.defaultdict(dict)
for system in systems.findall('system'):
 name=system.findtext('name'); folder=pathlib.Path(system.findtext('path','')).expanduser()
 if not folder.is_relative_to(BASE) or not folder.exists(): continue
 exts={s.lower() for s in system.findtext('extension','').split()}
 for f in folder.rglob('*'):
  if not f.is_file() or f.suffix.lower() not in exts or 'media' in f.relative_to(folder).parts: continue
  title=f.stem.replace('_',' ')
  if not re.search(r'\b(mario|zelda)\b',title,re.I) and f.stem.lower()!='drmario': continue
  if re.search(r'mario andretti|mario lemieux|\(unl\)',title,re.I): continue
  if re.search(r'hack|\[[hbtfop][0-9a-z]*\]|prototype|\bdemo\b|\bsample\b',title,re.I): continue
  english=bool(re.search(r'\((?:E|EU|Europe|U|US|USA|UE|W|World)\)|english',title,re.I))
  if not english and re.search(r'\((?:J|JP|Japan|K|KS|Korea|F|France|G|Germany|I|Italy|S|Spain|FC)\)',title,re.I): continue
  key=re.sub(r'\([^)]*\)|\[[^]]*\]','',title)
  key=re.sub(r'^\d{4}\s+','',key)
  key=re.sub(r'\s+',' ',key).strip().casefold()
  if name=='n64' and "majora" in key: key="zelda - majora's mask"
  if name=='n64' and key=='mario golf 64': key='mario golf'
  if name=='nds' and key in {'mario hoops 3 on 3','mario slam basketball'}: key='mario basketball'
  score=(30 if re.search(r'\((?:E|EU|Europe)\)',title,re.I) else 20 if english else 0)
  score+=10 if '[!]' in title else 0
  score+=2 if re.search(r'\(v0?1\)|\(V1\.2\)',title,re.I) else 0
  previous=selected[name].get(key)
  if not previous or (score,str(f))>(previous[0],str(previous[1])):
   selected[name][key]=(score,f,title)
report=[]
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
for name,choices in sorted(selected.items()):
 folder=BASE/name
 candidates=[folder/'gamelist.xml',ES/'gamelists'/name/'gamelist.xml']
 gamelist=next((p for p in candidates if p.exists()),candidates[0])
 tree=ET.parse(gamelist) if gamelist.exists() else ET.ElementTree(ET.Element('gameList'))
 root=tree.getroot()
 entries={}
 for game in root.findall('game'):
  p=game.findtext('path','')
  full=(folder/p).resolve() if not pathlib.Path(p).is_absolute() else pathlib.Path(p).resolve()
  entries[full]=game
 for _,f,title in sorted(choices.values(),key=lambda x:x[2]):
  report.append({'system':name,'name':title,'path':str(f)})
  if '--plan' in sys.argv: continue
  game=entries.get(f.resolve())
  if game is None:
   game=ET.SubElement(root,'game')
   ET.SubElement(game,'path').text='./'+str(f.relative_to(folder))
   cleaned=re.sub(r'^\d{4}\s+','',re.sub(r'\([^)]*\)|\[[^]]*\]','',title)).strip()
   ET.SubElement(game,'name').text=cleaned
  for tag,value in [('favorite','true'),('hidden','false')]:
   element=game.find(tag)
   if element is None: element=ET.SubElement(game,tag)
   element.text=value
 if '--plan' not in sys.argv:
  if gamelist.exists(): shutil.copy2(gamelist,gamelist.with_name('gamelist.xml.before-favorites-'+stamp))
  gamelist.parent.mkdir(parents=True,exist_ok=True)
  ET.indent(tree,space='  ')
  tmp=gamelist.with_suffix('.favorites.tmp')
  tree.write(tmp,encoding='utf-8',xml_declaration=True)
  tmp.replace(gamelist)
  verified=ET.parse(gamelist).getroot()
  for _,f,_ in choices.values():
   matches=[g for g in verified.findall('game') if (folder/g.findtext('path','')).resolve()==f.resolve()]
   assert matches and matches[0].findtext('favorite')=='true'
print(json.dumps(report,indent=2))
print('Selected '+str(len(report))+' games',flush=True)
if '--plan' not in sys.argv:
 pathlib.Path('/home/pi/mario-zelda-favorites.json').write_text(json.dumps(report,indent=2))
