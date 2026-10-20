"""Console startup recordings shared by the settings preview and startup player."""
import json, os, time
from pathlib import Path

SOUNDS = Path('/usr/local/share/retropie-splash/sounds')
CONSOLES = {'playstation':'PlayStation','gamecube':'GameCube','ps2':'PlayStation 2','ps3':'PlayStation 3','xbox':'Xbox','wii':'Wii','wiiu':'Wii U','xbox360':'Xbox 360'}

def find(sound):
    for ext in ('.wav', '.mp3'):
        path = SOUNDS / (sound+ext)
        if path.is_file(): return path
    return None

def resolve(sound, style):
    if sound == 'console': sound = style
    return find(sound) if sound in CONSOLES else None

# Only offer recordings that are on the box (a fresh build has none until retropie-get-boot-sounds)
HAVE = [(k, v) for k, v in CONSOLES.items() if find(k)]
CHOICES = [('off','Off')] + ([('console','Match console')] + HAVE if HAVE else [])

def main():
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
    try:
        config=json.loads((Path.home()/'.config/retropie-splash.json').read_text())
        path=resolve(config.get('sound','off'),config.get('style','super'))
        if path is None: return
        import fcntl
        runtime=Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))
        with (runtime/'retropie-loading-sound.lock').open('a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return
            marker=runtime/'retropie-loading-sound.once'
            if config.get('sound_when','startup') != 'always' and marker.exists(): return
            import pygame
            try:
                pygame.mixer.init()
                clip=pygame.mixer.Sound(str(path))
                clip.set_volume(max(0,min(100,int(config.get('volume',50))))/100)
                channel=clip.play()
                if channel is None: return
                marker.touch()
                # Let the recording finish while EmulationStation continues loading.
                end=time.monotonic()+min(30,clip.get_length()+1)
                while channel.get_busy() and time.monotonic()<end: time.sleep(.05)
            finally:
                pygame.mixer.quit()
    except Exception:
        # Audio failure must never prevent the menu from starting.
        return

if __name__ == '__main__': main()
