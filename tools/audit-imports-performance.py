import pathlib,re,json,collections,subprocess
base=pathlib.Path('/home/pi/RetroPie'); failed=base/'drop/_failed'
counts=collections.Counter(); records=[]
for w in failed.rglob('*.why.txt'):
 reason=w.read_text().strip(); counts[reason]+=1
 if 'missing' not in reason: continue
 src=pathlib.Path(str(w)[:-8])
 refs=re.findall(r'^\s*FILE\s+"([^"]+)"',src.read_text(errors='replace'),re.M|re.I) if src.exists() else []
 records.append({'cue':str(src),'refs':refs,'nearby':[p.name for p in src.parent.iterdir() if p.suffix.lower() in ['.bin','.img','.cue']]})
out={'counts':dict(counts),'missing':records}
pathlib.Path('/home/pi/import-audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'counts':dict(counts),'missing':[{'cue':r['cue'],'refs':r['refs']} for r in records]},indent=2))
print('TOOLS',subprocess.getoutput('command -v Xvfb; command -v nrg2iso; command -v vulkaninfo'))
print('ROMS')
for s in ['ps2','gc','dreamcast','nds']:
 files=[str(p) for p in (base/'roms'/s).rglob('*') if p.suffix.lower() in ['.chd','.iso','.nds','.cdi','.gdi','.rvz']]
 print(s,len(files),files[:4])
