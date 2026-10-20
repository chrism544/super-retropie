#!/usr/bin/env python3
# Settings menu tidy (run with ES stopped): fill the "unknown" Genre/Developer/Players lines shown
# beside every settings item, and shorten "Run Command Configuration" (cut off on screen).
import os, shutil, time, xml.etree.ElementTree as ET
for gl in sorted({os.path.realpath(p) for p in (os.path.expanduser("~/.emulationstation/gamelists/retropie/gamelist.xml"),
                  "/opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml") if os.path.exists(p)}):
    shutil.copy2(gl, gl + ".before-menu-tidy-" + time.strftime("%Y%m%d-%H%M"))
    t = ET.parse(gl); r = t.getroot()
    for g in r.iter("game"):
        if (g.findtext("path") or "").endswith("runcommand.rp"):
            (g.find("name") if g.find("name") is not None else ET.SubElement(g, "name")).text = "Launch Options"
        if (g.findtext("path") or "").endswith("showip.sh"):
            (g.find("name") if g.find("name") is not None else ET.SubElement(g, "name")).text = "Network"
            d = g.find("desc") if g.find("desc") is not None else ET.SubElement(g, "desc")
            d.text = "Address and connection status, live download/upload speed, internet speed test, and automatic (DHCP) or fixed IP settings."
        for tag, val in (("genre", "Settings"), ("developer", "Super RetroPie"), ("players", "")):
            e = g.find(tag)
            if e is None: e = ET.SubElement(g, tag)
            if not (e.text or "").strip() or tag == "players": e.text = val
    ET.indent(t); t.write(gl, encoding="utf-8", xml_declaration=True); print("tidied", gl)
