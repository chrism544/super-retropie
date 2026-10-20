import pathlib,subprocess,hashlib,json,re,sys
expected=sys.argv[1]
stage=pathlib.Path('/home/pi/RetroPie/.wiiu-upload');archive=stage/'wind-waker-hd.7z'
actual=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
assert actual==expected,'Archive transfer checksum mismatch'
listing=subprocess.check_output(['7z','l','-slt','--',str(archive)],text=True)
members=[l[7:] for l in listing.splitlines() if l.startswith('Path = ') and l.lower().endswith('.wux')]
assert len(members)==1,members
name=members[0]; assert '/' not in name and '\\' not in name
subprocess.run(['7z','e','-y','-spd','-o'+str(stage),'--',str(archive),name],check=True,stdout=subprocess.DEVNULL)
game=stage/name;assert game.stat().st_size==2901278720
dest=pathlib.Path('/home/pi/RetroPie/roms/wiiu')/name
dest.parent.mkdir(parents=True,exist_ok=True)
digest=hashlib.file_digest(game.open('rb'),'sha256').hexdigest()
if dest.exists():assert hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()==digest,'Existing game differs'
else:game.replace(dest)
receipt={'destination':str(dest),'size':dest.stat().st_size,'archive_sha256':actual,'game_sha256':digest,'source_archive_kept':True}
(stage/'receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt),flush=True)
key=pathlib.Path('/home/pi/.local/share/Cemu/keys.txt')
print('Cemu key file exists:',key.exists())
if key.exists():print('Wind Waker mentioned in key file:',bool(re.search('wind.?waker',key.read_text(errors='replace'),re.I)))
