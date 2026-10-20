"""Save editor for the Save Manager: change values straight in a game's save file.

Each supported game has an editor: where its values live in the save file, and how to fix the
checksum afterwards. Before writing, the Save Manager takes a snapshot, and the resume point
(.state.auto) is set aside - otherwise the game would resume from memory and ignore the edit.

  find_editor(system, rom) -> editor or None
  edit_screen(system, rom, name, snapshot_fn)   on-screen editor (needs retropie_ui initialised)

Adding a game: an Editor with match(), slots() and fields; see ALTTP below.
"""
import os, re, struct, time

class Field:
    def __init__(self, label, off, kind='byte', choices=None, desc='', write=None, read=None):
        self.label, self.off, self.kind, self.choices, self.desc = label, off, kind, choices, desc
        self._write, self._read = write, read
    def get(self, b):
        if self._read: return self._read(b)
        return struct.unpack_from('<H', b, self.off)[0] if self.kind == 'word' else b[self.off]
    def set(self, b, v):
        if self._write: return self._write(b, v)
        if self.kind == 'word': struct.pack_into('<H', b, self.off, v)
        else: b[self.off] = v

def steps(lo, hi, *extra):
    return sorted(set([lo, hi, *extra]))

# ------------------------------------------------------------------ Zelda: A Link to the Past (SNES)
# SRAM: 3 save slots of 0x500 bytes at 0x000/0x500/0xA00, mirrored at +0xF00. Slot checksum:
# the 16-bit words of the slot add up to 0x5A5A. Offsets = WRAM $7EF000 + offset.
def _alttp_rupees(b, v):
    struct.pack_into('<H', b, 0x360, v); struct.pack_into('<H', b, 0x362, v)
def _bits(off, bit):
    return (lambda b: 1 if b[off] & bit else 0,
            lambda b, v: b.__setitem__(off, (b[off] | bit) if v else (b[off] & ~bit & 0xFF)))
_pend = {n: _bits(0x374, bit) for n, bit in (('green', 0x04), ('blue', 0x02), ('red', 0x01))}
_crys = {n: _bits(0x37A, bit) for n, bit in (('1', 0x02), ('2', 0x10), ('3', 0x40), ('4', 0x20), ('5', 0x04), ('6', 0x01), ('7', 0x08))}
YN = [(0, 'No'), (1, 'Yes')]
BOTTLE = [(0, 'None'), (2, 'Empty bottle'), (3, 'Red potion'), (4, 'Green potion'), (5, 'Blue potion'), (6, 'Fairy'), (7, 'Bee'), (8, 'Good bee')]
ALTTP_FIELDS = [
    Field('Rupees', 0x362, 'word', [(v, str(v)) for v in steps(0, 999, 50, 100, 200, 300, 500, 750)], 'Money (max 999).',
          write=_alttp_rupees),
    Field('Hearts (max)', 0x36C, choices=[(v * 8, f'{v} hearts') for v in range(3, 21)], desc='Heart containers. Health is refilled to match.',
          write=lambda b, v: (b.__setitem__(0x36C, v), b.__setitem__(0x36D, v))),
    Field('Bombs', 0x343, choices=[(v, str(v)) for v in range(0, 51, 5)], desc='Bombs carried (bag size below).'),
    Field('Bomb bag upgrades', 0x370, choices=[(v, f'+{v}') for v in (0, 5, 10, 15, 20, 25, 30, 35, 40)], desc='Extra bomb capacity (10 + this).'),
    Field('Arrows', 0x377, choices=[(v, str(v)) for v in range(0, 71, 10)], desc='Arrows carried (quiver size below).'),
    Field('Quiver upgrades', 0x371, choices=[(v, f'+{v}') for v in (0, 5, 10, 15, 20, 25, 30, 35, 40)], desc='Extra arrow capacity (30 + this).'),
    Field('Magic', 0x36E, choices=[(v, f'{v * 100 // 128}%') for v in (0, 32, 64, 96, 128)], desc='Magic meter.'),
    Field('Half magic', 0x37B, choices=[(0, 'No'), (1, 'Yes - spells cost half')], desc='The upgrade from the Magic Bat.'),
    Field('Sword', 0x359, choices=[(1, 'Fighter'), (2, 'Master'), (3, 'Tempered'), (4, 'Golden')], desc=''),
    Field('Shield', 0x35A, choices=[(1, 'Fighter'), (2, 'Red (fire)'), (3, 'Mirror')], desc=''),
    Field('Tunic', 0x35B, choices=[(0, 'Green'), (1, 'Blue mail'), (2, 'Red mail')], desc='Blue halves damage, red quarters it.'),
    Field('Bow', 0x340, choices=[(0, 'None'), (2, 'Bow'), (4, 'Silver arrows')], desc='Silver arrows are needed for Ganon.'),
    Field('Boomerang', 0x341, choices=[(0, 'None'), (1, 'Blue'), (2, 'Red')], desc=''),
    Field('Gloves', 0x354, choices=[(0, 'None'), (1, 'Power Glove'), (2, "Titan's Mitt")], desc=''),
    *[Field(n, off, choices=YN) for n, off in (('Hookshot', 0x342), ('Fire Rod', 0x345), ('Ice Rod', 0x346), ('Bombos', 0x347),
        ('Ether', 0x348), ('Quake', 0x349), ('Lamp', 0x34A), ('Magic Hammer', 0x34B), ('Bug net', 0x34D), ('Book of Mudora', 0x34E),
        ('Cane of Somaria', 0x350), ('Cane of Byrna', 0x351), ('Magic Cape', 0x352), ('Pegasus Boots', 0x355),
        ('Flippers', 0x356), ('Moon Pearl', 0x357))],
    Field('Flute', 0x34C, choices=[(0, 'None'), (2, 'Flute'), (3, 'Flute (bird works)')], desc=''),
    Field('Magic Mirror', 0x353, choices=[(0, 'None'), (2, 'Yes')], desc=''),
    *[Field(f'Bottle {i + 1}', 0x35C + i, choices=BOTTLE) for i in range(4)],
    *[Field(f'Pendant - {n}', 0, choices=YN, read=r, write=w) for n, (r, w) in _pend.items()],
    *[Field(f'Crystal {n}', 0, choices=YN, read=r, write=w) for n, (r, w) in _crys.items()],
]

class AlttpEditor:
    name = 'Zelda - A Link to the Past'
    fields = ALTTP_FIELDS
    @staticmethod
    def match(system, rom):
        return system in ('snes', 'sfc') and 'link to the past' in rom.lower() and not re.search(r'hack|\[t', rom, re.I)
    @staticmethod
    def save_file(rom):
        p = os.path.splitext(rom)[0] + '.srm'
        return p if os.path.exists(p) else None
    @staticmethod
    def slots(data):
        out = []
        for i in range(3):
            b = data[i * 0x500:(i + 1) * 0x500]
            if len(b) == 0x500 and sum(struct.unpack('<640H', b)) & 0xFFFF == 0x5A5A:
                out.append(i)
        return out
    @staticmethod
    def slot_bytes(data, i): return bytearray(data[i * 0x500:(i + 1) * 0x500])
    @staticmethod
    def put_slot(data, i, b):
        s = sum(struct.unpack('<639H', bytes(b[:0x4FE]))) & 0xFFFF
        struct.pack_into('<H', b, 0x4FE, (0x5A5A - s) & 0xFFFF)
        assert sum(struct.unpack('<640H', bytes(b))) & 0xFFFF == 0x5A5A
        for base in (i * 0x500, 0xF00 + i * 0x500):                         # slot and its mirror copy
            data[base:base + 0x500] = b
    @staticmethod
    def slot_label(b, i):
        name = ''.join(chr(0x41 + (c - 0x00)) if False else '' for c in b[0x3D9:0x3E5])
        return f'File {i + 1}  -  {b[0x36C] // 8} hearts, {sum(bin(b[0x37A]).count("1") for _ in [0])} crystals'

EDITORS = [AlttpEditor]

def find_editor(system, rom):
    for e in EDITORS:
        if e.match(system, rom) and e.save_file(rom):
            return e
    return None

def edit_screen(system, rom, name, snapshot_fn):
    import pygame, retropie_ui as ui
    ed = find_editor(system, rom)
    path = ed.save_file(rom)
    data = bytearray(open(path, 'rb').read())
    slots = ed.slots(data)
    if not slots:
        return 'No valid save file to edit - save in the game first.'
    slot = slots[0]
    work = ed.slot_bytes(data, slot)
    rows = []
    if len(slots) > 1:
        rows.append({'label': 'Save file', 'choices': [(s, f'File {s + 1}') for s in slots], 'value': slot,
                     'desc': 'Which of the game\'s save files to edit.', 'gap': True})
    def build():
        del rows[1 if len(slots) > 1 else 0:]
        for f in ed.fields:
            v = f.get(work)
            ch = list(f.choices)
            if v not in [c for c, _ in ch]: ch = sorted(ch + [(v, f'{v} (now)')], key=lambda c: c[0])
            rows.append({'label': f.label, 'choices': ch, 'value': v, 'desc': f.desc or f.label, 'field': f})
        rows.append({'label': 'Save changes', 'action': apply_, 'desc': 'Writes the changes into the save file. A snapshot of '
                     'your saves is taken first (Save Manager can put it back), and the resume point is set aside so the '
                     'game starts from its own save - pick your file on the title screen.'})
    def apply_():
        nonlocal data
        snapshot_fn(rom, 'before edit')
        ed.put_slot(data, rows[0]['value'] if len(slots) > 1 else slot, work)
        open(path, 'wb').write(data)
        auto = os.path.splitext(rom)[0] + '.state.auto'
        if os.path.exists(auto):
            os.replace(auto, auto + '.before-edit-' + time.strftime('%Y%m%d-%H%M%S'))
        return 'Saved! Start the game and load your file.'
    def on_change(i, v):
        nonlocal slot, work
        row = rows[i]
        if 'field' in row:
            row['field'].set(work, v)
        elif row['label'] == 'Save file':
            slot = v; work = ed.slot_bytes(data, slot); build()
        return None
    build()
    # options_screen shows 9-10 rows; page through long lists with up/down (it scrolls by selection)
    ui.options_screen('SAVE EDITOR', name, rows, on_change, sub=f'{ed.name}  -  change values, then Save changes at the bottom')
    return None
