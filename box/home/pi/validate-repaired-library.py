import pathlib,re,json,shutil,hashlib,collections
base=pathlib.Path('/home/pi/RetroPie'); root=base/'roms/psx'; records=[]
for cue in root.rglob('*.cue'):
 text=cue.read_text(errors='replace'); changed=text; missing=[]
 refs=re.findall(r'^\s*FILE\s+"([^"]+)"',text,re.I|re.M)
 for ref in refs:
  if (cue.parent/ref).is_file(): continue
  name=ref.replace('\\','/').split('/')[-1]
  found=[p for p in cue.parent.iterdir() if p.is_file() and p.name.casefold()==name.casefold()]
  if len(found)==1: changed=changed.replace('"'+ref+'"','"'+found[0].name+'"')
  else: missing.append(ref)
 if missing: records.append({'cue':str(cue),'status':'missing tracks','refs':missing}); continue
 if changed!=text:
  backup=base/'import-repair-backups'/cue.relative_to(root)
  backup.parent.mkdir(parents=True,exist_ok=True)
  if not backup.exists(): shutil.copy2(cue,backup)
  cue.write_text(changed)
  records.append({'cue':str(cue),'status':'repaired library cue'})
plans=json.loads(pathlib.Path('/home/pi/import-repair-plan.json').read_text())
for p in plans:
 if not p['errors']: continue
 name=pathlib.Path(p['cue']).name
 targets={
 'Lunar - Silver Star Story (CD1)(NTSC-U).cue':'Lunar - Silver Star Story(NTSC-U).m3u',
 'Lunar 2 Eternal Blue Disk 1.cue':'Lunar 2 - Eternal Blue Complete (USA).m3u',
 'Lunar 2 Eternal Blue Disk 2.cue':'Lunar 2 - Eternal Blue Complete (USA).m3u',
 'Lunar 2 Eternal Blue Disk 3.cue':'Lunar 2 - Eternal Blue Complete (USA).m3u',
 'Persona 1 - Revelations.cue':'Persona 1 - Revelations.chd',
 'Jade Cocoon - Story of the Tamamayu.cue':'Jade Cocoon - Story of the Tamamayu (USA).cue',
 'Tekken 3.cue':'Tekken 3 (USA).cue',
 'resident evil 3.cue':'Resident Evil 3 - Nemesis (USA).cue',
 'KBV.cue':'KBV.cue',
 'Persona 2 Innocent Sin [NTSC-J].cue':'Persona 2 - Tsumi - Innocent Sin (Japan).cue'}
 target=root/targets[name]; valid=target.exists()
 if valid and target.suffix=='.cue':
  valid=all((target.parent/r).exists() for r in re.findall(r'^\s*FILE\s+"([^"]+)"',target.read_text(),re.M|re.I))
 if valid and target.suffix=='.m3u':
  valid=all((target.parent/r.strip()).exists() for r in target.read_text().splitlines() if r.strip() and not r.startswith('#'))
 records.append({'failed_cue':name,'status':'playable copy present' if valid else 'unresolved','copy':str(target)})
pathlib.Path('/home/pi/import-library-validation.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
