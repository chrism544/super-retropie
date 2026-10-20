import pathlib,json,re,subprocess
b=pathlib.Path('/home/pi/RetroPie')
for p in (b/'roms/psx').rglob('*'):
 if p.is_file() and any(k in p.name.casefold() for k in ['jade','dragon warrior','lunar','persona','resident evil 3','kbv','tekken']): print(p)
lines=pathlib.Path('/var/log/retropie-drop.log').read_text(errors='replace').replace('\r','\n').splitlines()
print('IMPORTS',*[l for l in lines if 'imported psx/' in l or 'FAILED' in l][-18:],sep='\n')
for p in pathlib.Path('/home/pi/emulator-performance-check').glob('*.log'):
 text=p.read_text(errors='replace'); print(p.name,text[-2000:])
