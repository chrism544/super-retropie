import urllib.request,hashlib,pathlib
base=pathlib.Path('/home/pi/RetroPie/BIOS')
items=[('mpr-17933.bin','3240872c70984b6cbfda1586cab68dbe'),('dc/dc_boot.bin','e10c53c2f8b90bab96ead2d368858623')]
for name,expected in items:
 p=base/name
 if p.exists():
  assert hashlib.md5(p.read_bytes()).hexdigest()==expected, 'Existing file differs: '+name
 else:
  data=urllib.request.urlopen('https://raw.githubusercontent.com/archtaurus/RetroPieBIOS/master/BIOS/'+name,timeout=40).read()
  assert hashlib.md5(data).hexdigest()==expected, 'Checksum mismatch: '+name
  p.parent.mkdir(parents=True,exist_ok=True)
  tmp=p.with_suffix('.verified.tmp')
  tmp.write_bytes(data)
  tmp.replace(p)
 print(name,p.stat().st_size,hashlib.md5(p.read_bytes()).hexdigest())
for name in ['bios_CD_E.bin','bios_CD_J.bin','bios_CD_U.bin','scph7502.bin']:
 p=base/name
 print(name,p.stat().st_size,hashlib.md5(p.read_bytes()).hexdigest())
