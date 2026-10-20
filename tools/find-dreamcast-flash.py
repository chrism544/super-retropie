import pathlib,urllib.request,json
req=urllib.request.Request('https://api.github.com/repos/Abdess/retroarch_system/git/trees/libretro?recursive=1',headers={'User-Agent':'RetroPie-audit'})
data=json.load(urllib.request.urlopen(req,timeout=30))
print('\n'.join(x['path'] for x in data.get('tree',[]) if 'dc_flash' in x['path'].lower()))
