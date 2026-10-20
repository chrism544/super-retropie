"""Refresh original Xbox entries without dropping discs unsupported by the artwork renderer.
Run only while EmulationStation is held stopped (retropie-es-edit or retropie-scrape).
"""
from pathlib import Path
import datetime,json,os,re,shutil,xml.etree.ElementTree as ET
HOME=Path.home(); BASE=HOME/'RetroPie/.manual-game-upload'; ROMS=HOME/'RetroPie/roms/xbox'; file=ROMS/'gamelist.xml'
if file.exists():
    tree=ET.parse(file)
    backup=BASE/'xbox-list-backups'; backup.mkdir(exist_ok=True)
    shutil.copy2(file,backup/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.xml'))
else: tree=ET.ElementTree(ET.Element('gameList'))
root=tree.getroot(); known={str((ROMS/g.findtext('path','')).resolve()):g for g in root.findall('game')}
receipts={}
for p in BASE.glob('*-receipt.json'):
    r=json.loads(p.read_text())
    if r.get('system')=='xbox': receipts[r['path']]=r
art={r['id']:r for r in json.loads((BASE/'game-art.json').read_text())} if (BASE/'game-art.json').exists() else {}
art_by_file={Path(r['path']).stem:r['path'] for r in art.values() if 'path' in r}
count=0
for p in sorted(ROMS.iterdir()):
    if not p.is_file() or p.suffix.lower() not in ('.iso','.xiso'): continue
    key=str(p.resolve()); game=known.get(key)
    if game is None:
        game=ET.SubElement(root,'game'); ET.SubElement(game,'path').text=key
        title=receipts.get(key,{}).get('game',re.sub(r'\s*\([^)]*\)','',p.stem.removesuffix('.xiso')))
        ET.SubElement(game,'name').text=title
    path=art_by_file.get(p.name)
    if path and Path(path).is_file():
        image=game.find('image')
        if image is None: image=ET.SubElement(game,'image')
        image.text=path
    count+=1
ET.indent(tree,space='  '); tmp=file.with_suffix('.preserved-new'); tree.write(tmp,encoding='utf-8',xml_declaration=True); ET.parse(tmp); os.replace(tmp,file)
print('Xbox game list preserved:',count,'disc images',flush=True)
