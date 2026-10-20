"""View+Menu exits xemu; reconnect controllers while a game is running."""
import glob,os,select,signal,struct,sys,time
pid=int(sys.argv[1]); pads={}
while True:
    try: os.kill(pid,0)
    except ProcessLookupError: break
    for path in glob.glob('/dev/input/js*'):
        if path not in pads:
            try: pads[path]=(os.open(path,os.O_RDONLY|os.O_NONBLOCK),set())
            except OSError: pass
    ready,_,_=select.select([fd for fd,held in pads.values()],[],[],.1)
    for path,(fd,held) in list(pads.items()):
        if fd not in ready: continue
        try:
            raw=os.read(fd,8)
            if len(raw)!=8: raise OSError()
            _,value,typ,num=struct.unpack('IhBB',raw)
            if typ&1:
                held.add(num) if value else held.discard(num)
                if {6,7}<=held:
                    os.kill(pid,signal.SIGTERM); sys.exit(0)
        except OSError:
            os.close(fd); pads.pop(path,None)
