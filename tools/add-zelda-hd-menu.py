import pathlib,xml.etree.ElementTree as ET,shutil
root=pathlib.Path('/home/pi/RetroPie/roms/wiiu');p=root/'gamelist.xml'
tree=ET.parse(p) if p.exists() else ET.ElementTree(ET.Element('gameList'))
if p.exists() and not p.with_name('gamelist.xml.before-zelda-upload').exists():shutil.copy2(p,p.with_name('gamelist.xml.before-zelda-upload'))
for game in root.glob('*.wux'):
 if 'Wind Waker HD' in game.name:title='The Legend of Zelda: The Wind Waker HD'
 elif 'Twilight Princess HD' in game.name:title='The Legend of Zelda: Twilight Princess HD'
 else:continue
 path='./'+game.name
 node=next((n for n in tree.getroot().findall('game') if n.findtext('path')==path),None)
 if node is None:node=ET.SubElement(tree.getroot(),'game')
 for tag,value in [('path',path),('name',title),('favorite','true')]:
  element=node.find(tag)
  if element is None:element=ET.SubElement(node,tag)
  element.text=value
tmp=p.with_suffix('.xml.tmp');ET.indent(tree,space='  ');tree.write(tmp,encoding='utf-8',xml_declaration=True);tmp.replace(p)
print('Zelda HD games added to Wii U menu and favourites.')
