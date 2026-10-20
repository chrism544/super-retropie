import pathlib,json,re,os,fcntl,time,shutil
base=pathlib.Path('/home/pi/RetroPie'); report=[]
with open('/run/retropie-drop-import.lock','r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for r in json.loads(pathlib.Path('/home/pi/import-repair-plan.json').read_text()):
  cue=pathlib.Path(r['cue'])
  if r['errors']: report.append({'game':cue.name,'status':'needs review','errors':r['errors']}); continue
  folder=base/'drop/psx'/('repaired-'+cue.stem)
  folder.mkdir(exist_ok=True)
  text=cue.read_text()
  for t in r['tracks']:
   p=pathlib.Path(t['path']); dest=folder/p.name
   if not dest.exists(): os.link(p,dest)
   text=text.replace('"'+t['ref']+'"','"'+p.name+'"')
  out=folder/cue.name
  if out.exists() and out.read_text()!=text: raise RuntimeError('Conflict '+str(out))
  out.write_text(text); os.utime(out,(time.time()-180,time.time()-180))
  report.append({'game':cue.name,'status':'repaired cue and requeued','folder':str(folder)})
pathlib.Path('/home/pi/import-repair-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
