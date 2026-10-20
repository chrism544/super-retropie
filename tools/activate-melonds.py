import ctypes,pathlib,re,shutil,subprocess
core=pathlib.Path('/opt/retropie/libretrocores/lr-melondsds/melondsds_libretro.so')
class Info(ctypes.Structure):
 _fields_=[('library_name',ctypes.c_char_p),('library_version',ctypes.c_char_p),('valid_extensions',ctypes.c_char_p),('need_fullpath',ctypes.c_bool),('block_extract',ctypes.c_bool)]
lib=ctypes.CDLL(str(core))
lib.retro_get_system_info.argtypes=[ctypes.POINTER(Info)]
lib.retro_get_system_info.restype=None
info=Info(); lib.retro_get_system_info(ctypes.byref(info))
assert info.library_name and b'melon' in info.library_name.lower()
assert b'nds' in info.valid_extensions
print('Core loaded: '+info.library_name.decode()+' '+info.library_version.decode())
metadata=pathlib.Path('/home/pi/RetroPie-Setup/tmp/build/melondsds/build/melondsds_libretro.info')
subprocess.run(['sudo','-n','install','-m','644',str(metadata),str(core.with_suffix('.info'))],check=True)
config=pathlib.Path('/opt/retropie/configs/nds/emulators.cfg')
backup=config.with_name('emulators.cfg.before-melonds')
if not backup.exists(): shutil.copy2(config,backup)
text=config.read_text()
assert 'lr-melondsds = ' in text
text,count=re.subn(r'^default\s*=.*$', 'default = "lr-melondsds"',text,flags=re.M)
assert count==1
tmp=pathlib.Path('/home/pi/emulators-nds-melonds.cfg')
tmp.write_text(text)
subprocess.run(['sudo','-n','install','-o','pi','-g','pi','-m','644',str(tmp),str(config)],check=True)
assert 'default = "lr-melondsds"' in config.read_text()
print('DS default: lr-melondsds; DeSmuME retained as an alternative')
print('Backup: '+str(backup))
