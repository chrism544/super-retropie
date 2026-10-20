import pathlib,json,re,shutil
b=pathlib.Path('/home/pi/RetroPie'); report=json.loads(pathlib.Path('/home/pi/import-repair-report.json').read_text()); logs=pathlib.Path('/var/log/retropie-drop.log').read_text(errors='replace')
done=[]; pending=[]
for r in report:
 if r['status']!='repaired cue and requeued':continue
 name=pathlib.Path(r['game']).stem+'.chd'
 if 'imported psx/'+name in logs: done.append(name)
 else: pending.append(name)
print('Completed',len(done),done,'Pending',pending)
for p in [pathlib.Path('/opt/retropie/configs/all/retroarch-core-options.cfg'),pathlib.Path('/home/pi/.config/retroarch/config/melonDS DS/melonDS DS.opt')]:
 if not p.exists():continue
 text=p.read_text()
 backup=p.with_name(p.name+'.before-network-fix')
 if not backup.exists():shutil.copy2(p,backup)
 line='melonds_network_mode = "disabled"'
 if re.search(r'^melonds_network_mode\s*=',text,re.M):text=re.sub(r'^melonds_network_mode\s*=.*',line,text,flags=re.M)
 else:text+='\n'+line+'\n'
 p.write_text(text);print('DS networking disabled for reliable shutdown:',p)
pathlib.Path('/home/pi/import-repair-completion.json').write_text(json.dumps({'completed':done,'pending':pending},indent=2))
