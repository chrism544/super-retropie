#!/usr/bin/env python3
# Adds the "Problems" report to retropie-playtime: games that closed within a minute are logged
# with the end of the launch log, and listed on a new Play Stats page with the overnight check results.
import re, sys
p = sys.argv[1]
src = open(p).read()
assert 'QUICK' not in src, 'already patched'

src = src.replace(
    "Sessions under 20 seconds (a game that would not start, a quick look) are not counted.\n",
    "Sessions under 20 seconds (a game that would not start, a quick look) are not counted.\n"
    "Games that close within a minute are also logged to ~/.local/share/retropie-quick-exits.jsonl with the\n"
    "end of the launch log - the Problems page lists them (last 7 days) with the overnight game check results.\n")

src = src.replace(
    "CUR = '/tmp/retropie-playtime-current.json'\n",
    "CUR = '/tmp/retropie-playtime-current.json'\n"
    "QUICK = os.path.expanduser('~/.local/share/retropie-quick-exits.jsonl')\n"
    "CHECK = os.path.expanduser('~/night-check/results.json')\n")

old = """    s['end'] = time.time()
    if s['end'] - s['start'] >= 20:"""
new = """    s['end'] = time.time()
    if s['end'] - s['start'] < 60:
        try:
            log = open('/dev/shm/runcommand.log', errors='replace').read().splitlines()[-12:]
        except OSError:
            log = []
        q = dict(s, name=game_name(s['system'], s['rom']), log=log)
        os.makedirs(os.path.dirname(QUICK), exist_ok=True)
        open(QUICK, 'a').write(json.dumps(q) + '\\n')
    if s['end'] - s['start'] >= 20:"""
assert old in src; src = src.replace(old, new)

old = "PAGES = ['Overview', 'Top games', 'Consoles', 'Recent']"
new = """PAGES = ['Overview', 'Top games', 'Consoles', 'Recent', 'Problems']
quick = collections.OrderedDict()
try:
    for l in open(QUICK):
        q = json.loads(l)
        if q['start'] > time.time() - 7 * 86400:
            k = (q['system'], q['rom'])
            n, last = quick.get(k, (0, None))
            quick[k] = (n + 1, q)
except (OSError, ValueError):
    pass
# a game played properly since its quick exits is fine again
quick = [(k, n, q) for k, (n, q) in quick.items()
         if not any(s['system'] == k[0] and s['rom'] == k[1] and s['start'] > q['end'] and s['end'] - s['start'] >= 60
                    for s in sessions)]
quick.sort(key=lambda x: -x[2]['start'])
try:
    check = json.load(open(CHECK))
except (OSError, ValueError):
    check = None"""
assert old in src; src = src.replace(old, new)

old = """    else:
        for s in sorted(sessions, key=lambda s: -s['start'])[:11]:"""
new = """    elif page == 4:
        ui.text('Games that closed within a minute (last 7 days)', 28, ui.ACCENT_LT, (ui.px(80), y)); y += ui.px(54)
        if not quick:
            ui.text('None - every game you started kept running.', 30, ui.DIM, (ui.px(80), y)); y += ui.px(60)
        for k, n, q in quick[:5]:
            ui.text(q.get('name') or os.path.basename(k[1]), 30, ui.TEXT, (ui.px(80), y), maxw=ui.px(900))
            ui.text(NAMES.get(k[0], k[0]), 26, ui.DIM, (ui.px(1020), y + ui.px(4)))
            ui.text(f'{n}x, last {time.strftime("%a %H:%M", time.localtime(q["start"]))}', 26, ui.BAD, (ui.W - ui.px(80), y + ui.px(4)), 'topright')
            y += ui.px(58)
        y += ui.px(30)
        if check:
            ui.text('Overnight game check  -  ' + check.get('when', ''), 28, ui.ACCENT_LT, (ui.px(80), y)); y += ui.px(54)
            for r in check.get('games', [])[:12 - min(len(quick), 5)]:
                ok = r.get('ok')
                ui.text(r['name'], 28, ui.TEXT, (ui.px(80), y), maxw=ui.px(1000))
                ui.text(r.get('note', 'OK' if ok else 'problem'), 26, ui.GOOD if ok else ui.BAD, (ui.W - ui.px(80), y + ui.px(2)), 'topright', maxw=ui.px(700))
                y += ui.px(50)
    else:
        for s in sorted(sessions, key=lambda s: -s['start'])[:11]:"""
assert old in src; src = src.replace(old, new)
open(p, 'w').write(src)
print('patched')
