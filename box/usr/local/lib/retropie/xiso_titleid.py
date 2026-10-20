# Print the Xbox title ID (and xemu xdb cover path) of each XISO, read from default.xbe.
import struct, sys
SECTOR = 2048
def title_id(path):
    f = open(path, 'rb')
    for base in (0x10000, 0x18300000 + 0x10000, 0xFD90000 + 0x10000):     # plain xiso, redump video partition offsets
        f.seek(base); h = f.read(0x1C)
        if h[:20] == b'MICROSOFT*XBOX*MEDIA':
            break
    else:
        return None
    start = base - 0x10000
    root_sec, root_size = struct.unpack_from('<II', h, 20)
    f.seek(start + root_sec * SECTOR); d = f.read(root_size)
    i = 0
    while i + 14 <= len(d):
        if d[i:i+2] == b'\xff\xff':
            i = (i // SECTOR + 1) * SECTOR; continue
        sec, size, attr, nl = struct.unpack_from('<IIBB', d, i + 4)
        name = d[i+14:i+14+nl].decode('latin-1')
        if name.lower() == 'default.xbe':
            f.seek(start + sec * SECTOR); x = f.read(0x1000)
            base_addr, = struct.unpack_from('<I', x, 0x104)
            cert_addr, = struct.unpack_from('<I', x, 0x118)
            f.seek(start + sec * SECTOR + cert_addr - base_addr); c = f.read(0x100)
            return struct.unpack_from('<I', c, 8)[0]
        i += (14 + nl + 3) & ~3
    return None
for p in sys.argv[1:]:
    t = title_id(p)
    print(f'{t:08X}|titles/{chr(t >> 24)}{chr((t >> 16) & 0xff)}/{t & 0xffff:03d}|{p}' if t else f'NONE||{p}')
