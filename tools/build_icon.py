"""Build the controller/clock ICO using only the standard library (no runtime step)."""
from pathlib import Path
import struct
import zlib

POLYGON = [(16, 25), (42, 25), (48, 29), (57, 48), (54, 54), (49, 54),
           (40, 45), (24, 45), (15, 54), (10, 54), (7, 48), (12, 30)]


def inside(x, y):
    odd = False
    prior = POLYGON[-1]
    for point in POLYGON:
        x1, y1 = prior
        x2, y2 = point
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            odd = not odd
        prior = point
    return odd


def color(x, y):
    if min(max(9 - x, 0, x - 55), 64) ** 2 + min(max(9 - y, 0, y - 55), 64) ** 2 > 81:
        return 0, 0, 0, 0
    value = (25, 43, 64, 255)
    if inside(x, y):
        value = (134, 185, 255, 255)
    if (17 <= x <= 29 and 34 <= y <= 38) or (21 <= x <= 25 and 30 <= y <= 42):
        value = (25, 43, 64, 255)
    if (x - 43) ** 2 + (y - 33) ** 2 < 6 or (x - 48) ** 2 + (y - 39) ** 2 < 6:
        value = (25, 43, 64, 255)
    d = (x - 46) ** 2 + (y - 18) ** 2
    if d <= 144:
        value = (241, 242, 245, 255) if d >= 81 else (25, 43, 64, 255)
        if (44.5 <= x <= 47.5 and 11 <= y <= 19) or (45 <= x <= 52 and 17 <= y <= 20):
            value = (134, 185, 255, 255)
    return value


def render(size):
    pixels = []
    scale = 4
    for y in range(size):
        for x in range(size):
            samples = [color((x + (sx + .5) / scale) * 64 / size,
                             (y + (sy + .5) / scale) * 64 / size)
                       for sy in range(scale) for sx in range(scale)]
            alpha = sum(p[3] for p in samples)
            pixels.append(tuple(round(sum(p[i] * p[3] for p in samples) / alpha) if alpha else 0 for i in range(3))
                          + (round(alpha / len(samples)),))
    return pixels


def png(size, pixels):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    scan = b"".join(b"\0" + bytes(channel for p in pixels[y * size:(y + 1) * size] for channel in p) for y in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scan)) + chunk(b"IEND", b""))


def main():
    base = Path(__file__).resolve().parent.parent
    images = [(size, png(size, render(size))) for size in (16, 24, 32, 48, 64)]
    offset = 6 + 16 * len(images)
    entries = []
    for size, data in images:
        entries.append(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (base / "gametime/app.ico").write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries)
                                          + b"".join(data for _, data in images))


if __name__ == "__main__":
    main()
