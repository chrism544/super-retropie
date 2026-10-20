import pathlib,urllib.request,hashlib
p=pathlib.Path('/home/pi/RetroPie/BIOS/dc/dc_flash.bin')
if not p.exists():
 data=urllib.request.urlopen('https://raw.githubusercontent.com/archtaurus/RetroPieBIOS/master/BIOS/dc/dc_flash.bin',timeout=30).read()
 digest=hashlib.md5(data).hexdigest()
 assert len(data)==131072 and digest in ['23df18aa53c8b30784cd9a84e061d008','0a93f7940c455905bea6e392dfde92a4','69c036adfca4ebea0b0c6fa4acfc8538'],digest
 p.write_bytes(data)
print(p,hashlib.md5(p.read_bytes()).hexdigest())
