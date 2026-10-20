#!/usr/bin/env python3
"""Fake Wii U GamePad tilt from the Xbox pad's right stick, for Cemu.

The Xbox controller has no gyro, so games that aim up/down by tilting the GamePad
(Splatoon...) can't look up or down. This runs a tiny DSU ("cemuhook") motion server on
127.0.0.1:26760: right stick up/down tilts a virtual GamePad up/down. Cemu reads it through
a DSUController entry with <motion>true</motion> in the GamePad controller profile.

  stick-gyro.py <cemu pid>        (exits when Cemu does)
Tuning (environment): GYRO_RATE deg/s at full stick (default 90), GYRO_SIGN / YAW_SIGN (+1/-1),
ACC_SIGN (+1/-1). Testing: a number in /tmp/stick-gyro-fake overrides the stick (-1..1).
"""
import glob, math, os, select, socket, struct, sys, time, zlib

pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
RATE = float(os.environ.get('GYRO_RATE', 90))
GSIGN = float(os.environ.get('GYRO_SIGN', 1))
YSIGN = float(os.environ.get('YAW_SIGN', 1))
ASIGN = float(os.environ.get('ACC_SIGN', 1))
RX, RY = 3, 4                              # xpadneo right stick (js axes)
SERVER_ID = 0x5E0B13
MAC = b'\x00\x00\x00\x00\x00\x01'

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('127.0.0.1', 26760))
sock.setblocking(False)

def packet(msg_type, payload):
    body = struct.pack('<I', msg_type) + payload
    head = b'DSUS' + struct.pack('<HHII', 1001, len(body), 0, SERVER_ID)
    crc = zlib.crc32(head + body) & 0xffffffff
    return b'DSUS' + struct.pack('<HHII', 1001, len(body), crc, SERVER_ID) + body

def shared(slot):
    # slot, state (2 = connected), model (2 = full gyro), connection (2 = bluetooth), mac, battery (5 = full)
    return struct.pack('<BBBB', slot, 2 if slot == 0 else 0, 2 if slot == 0 else 0, 2 if slot == 0 else 0) \
        + (MAC if slot == 0 else b'\0' * 6) + struct.pack('<B', 5 if slot == 0 else 0)

clients = {}          # addr -> last data request time
seen = {}
LOG = open("/tmp/stick-gyro.log", "a") if os.environ.get("GYRO_LOG", "1") == "1" else None
pads, axes = {}, {}
pitch, count, last = 0.0, 0, time.time()

def stick(axis=RY, fake='/tmp/stick-gyro-fake'):
    try:
        return max(-1.0, min(1.0, float(open(fake).read())))
    except (OSError, ValueError):
        pass
    v = axes.get(axis, 0) / 32767
    if abs(v) < 0.15:
        return 0.0
    return math.copysign(((abs(v) - 0.15) / 0.85) ** 1.6, v)   # fine control near the centre

while True:
    if pid:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            sys.exit(0)
    for path in glob.glob('/dev/input/js*'):
        if path not in pads:
            try:
                pads[path] = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                pass
    ready, _, _ = select.select([sock] + list(pads.values()), [], [], 0.005)
    for fd in ready:
        if fd is sock:
            try:
                data, addr = sock.recvfrom(1024)
            except BlockingIOError:
                continue
            if len(data) < 20 or data[:4] != b'DSUC':
                continue
            mtype = struct.unpack_from("<I", data, 16)[0]
            if LOG and seen.get(mtype, 0) < 3:
                seen[mtype] = seen.get(mtype, 0) + 1
                LOG.write(f"{time.strftime('%T')} {addr} type {mtype:#x} len {len(data)} {data[20:32].hex()}\n")
                LOG.flush()
            if mtype == 0x100000:                                  # version
                sock.sendto(packet(0x100000, struct.pack('<H', 1001)), addr)
            elif mtype == 0x100001:                                # port info
                n = struct.unpack_from('<i', data, 20)[0]
                for i in range(max(0, min(n, 4))):
                    slot = data[24 + i]
                    sock.sendto(packet(0x100001, shared(slot) + b'\0'), addr)
            elif mtype == 0x100002:                                # pad data request
                clients[addr] = time.time()
        else:
            path = next(p for p, f in pads.items() if f == fd)
            try:
                buf = os.read(fd, 8 * 64)
            except OSError:
                os.close(fd); del pads[path]; continue
            for i in range(0, len(buf) - 7, 8):
                _, value, kind, number = struct.unpack('IhBB', buf[i:i + 8])
                if kind & 0x02:
                    axes[number] = value
    now = time.time()
    if now - last >= 0.004:                                        # ~250 samples a second
        dt, last = now - last, now
        rate = -stick() * RATE * GSIGN                             # stick up (negative) = tilt up
        yaw = -stick(RX, '/tmp/stick-gyro-fake-x') * RATE * YSIGN  # stick left/right = turn
        pitch = max(-1.4, min(1.4, pitch + math.radians(rate) * dt))
        # gravity seen by the tilted pad (held upright facing the screen at pitch 0)
        ay, az = -math.cos(pitch) * ASIGN, math.sin(pitch) * ASIGN
        count += 1
        for addr, t in list(clients.items()):
            if now - t > 5:
                del clients[addr]; continue
            payload = (shared(0) + struct.pack('<BI', 1, count)
                       + bytes(4)                                  # buttons, home, touch
                       + bytes([128, 128, 128, 128])               # sticks centred (motion only)
                       + bytes(12) + bytes(12)                     # analog buttons, 2 touches
                       + struct.pack('<Q', int(now * 1e6))
                       + struct.pack('<fff', 0.0, ay, az)
                       + struct.pack('<fff', rate, yaw, 0.0))
            try:
                sock.sendto(packet(0x100002, payload), addr)
            except OSError:
                pass
