import pathlib,json,hashlib,subprocess
base=pathlib.Path('/home/pi/RetroPie')
found=[]
for root in [base/'BIOS',base/'roms/megadrive',base/'roms/arcade']:
 if not root.exists(): continue
 for p in root.rglob('*'):
  if p.is_file() and any(x in p.name.lower() for x in ['bios','dc_boot','17933','sega_101']):
   found.append({'path':str(p),'size':p.stat().st_size})
print(json.dumps(found,indent=2))
