import pathlib,shutil
p=pathlib.Path('/usr/local/bin/retropie-drop-import')
old=' bin raw img cue gdi iso zip 7z '
new=' bin raw cue gdi iso zip 7z '
s=p.read_text()
if old in s:
 backup=p.with_name(p.name+'.before-download-schedule')
 if not backup.exists(): shutil.copy2(p,backup)
 p.write_text(s.replace(old,new))
print('IMG publication supported')
