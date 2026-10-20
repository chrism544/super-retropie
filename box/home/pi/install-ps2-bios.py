import configparser,hashlib,pathlib,shutil
src=pathlib.Path('/home/pi/pcsx2-bios-extracted/ps2bios')
dest=pathlib.Path('/home/pi/RetroPie/BIOS/ps2')
chosen='SCPH-70004_BIOS_V12_PAL_200.BIN'
assert (src/chosen).stat().st_size==4194304
assert b'0200EC20040614' in (src/chosen).read_bytes()
dest.mkdir(exist_ok=True)
files=[p for p in src.iterdir() if p.is_file() and p.suffix.lower() in {'.bin','.mec','.nvm','.erom','.rom1','.rom2'}]
for p in files:
 target=dest/p.name
 if target.exists() and target.read_bytes()!=p.read_bytes(): raise RuntimeError('Existing BIOS differs: '+p.name)
 if not target.exists(): shutil.copy2(p,target)
 assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(p.read_bytes()).digest()
config=pathlib.Path('/home/pi/.config/PCSX2/inis/PCSX2.ini')
backup=config.with_name('PCSX2.ini.before-bios')
if not backup.exists(): shutil.copy2(config,backup)
cfg=configparser.ConfigParser(interpolation=None)
cfg.optionxform=str
cfg.read(config)
for section in ['Folders','Filenames']:
 if not cfg.has_section(section): cfg.add_section(section)
cfg.set('Folders','Bios',str(dest))
cfg.set('Filenames','BIOS',chosen)
tmp=config.with_suffix('.bios.tmp')
with tmp.open('w') as out: cfg.write(out)
tmp.replace(config)
check=configparser.ConfigParser(interpolation=None); check.optionxform=str; check.read(config)
assert check.get('Filenames','BIOS')==chosen
print('Installed and checksum-verified '+str(len(files))+' BIOS/support files')
print('Default BIOS: '+chosen+' (Europe v2.00, 2004-06-14)')
print('Configuration backup: '+str(backup))
