"""Return from Kodi to the games, even if the transition screen is unavailable."""
import os
import subprocess
import xbmc
import xbmcgui

window = xbmcgui.Window(10000)
if window.getProperty('SuperRetroPie.Returning') != 'true':
    window.setProperty('SuperRetroPie.Returning', 'true')
    try:
        xbmcgui.Dialog().notification('Super RetroPie', 'Returning to your games…', '/usr/local/share/super-retropie/kodi-super-retropie.png', 3000, False)
        try:
            subprocess.Popen(['/usr/local/bin/retropie-kodi-leaving'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, DISPLAY=os.environ.get('DISPLAY', ':0')))
        except OSError as error:
            xbmc.log('Super RetroPie transition: ' + str(error), xbmc.LOGWARNING)
        xbmc.sleep(250)
        xbmc.executebuiltin('Quit')
    finally:
        xbmc.sleep(5000)
        window.clearProperty('SuperRetroPie.Returning')
