import hashlib,pathlib,zipfile
base=pathlib.Path('/home/pi/RetroPie')
expected={'bios_CD_E.bin':'e66fa1dc5820d254611fdcdba0662372','bios_CD_U.bin':'854b9150240a198070150e4566ae1290','bios_CD_J.bin':'278a9397d192149e84e820ac621a8edd'}
matches={}
for archive in (base/'roms/megadrive').rglob('*.zip'):
 if 'bios' not in archive.name.lower() or not any(x in archive.name.lower() for x in ['megacd','segacd']): continue
 with zipfile.ZipFile(archive) as z:
  for member in z.infolist():
   if member.file_size<131072 or member.file_size>131584: continue
   original=z.read(member)
   for data in [original,original[512:] if len(original)==131584 else original]:
    variants=[data]
    if len(data)%2==0:
     swapped=bytearray(data); swapped[::2]=data[1::2]; swapped[1::2]=data[::2]; variants.append(bytes(swapped))
    if len(data)%16384==0:
     out=bytearray(len(data))
     for offset in range(0,len(data),16384):
      out[offset:offset+16384:2]=data[offset+8192:offset+16384]
      out[offset+1:offset+16384:2]=data[offset:offset+8192]
     variants.append(bytes(out))
    for variant in variants:
     md5=hashlib.md5(variant).hexdigest()
     for name,digest in expected.items():
      if md5==digest: matches[name]=(variant,str(archive),member.filename)
for name,(data,archive,member) in matches.items():
 dest=base/'BIOS'/name
 if dest.exists() and dest.read_bytes()!=data: raise RuntimeError('Existing BIOS differs: '+name)
 if not dest.exists(): dest.write_bytes(data)
 assert hashlib.md5(dest.read_bytes()).hexdigest()==expected[name]
 print('Installed '+name+' from '+archive+'; checksum verified')
for name in expected.keys()-matches.keys(): print('Still missing '+name)
