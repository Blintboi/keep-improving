"""Draw the editable controller/timer mark; export antialiased PNG and Windows ICO.

Standard library only. Coordinates are in a 64-unit vector space. PNG-compressed
32-bit icon frames cover small tray icons through 256px Explorer/desktop views.
"""
from math import hypot
from pathlib import Path
import struct
import zlib


def bezier(start, control1, control2, end):
    return [tuple((1-t)**3*start[i] + 3*(1-t)**2*t*control1[i]
                  + 3*(1-t)*t*t*control2[i] + t**3*end[i] for i in (0, 1))
            for t in (j/10 for j in range(1, 11))]


def outline():
    points = [(24, 22)]
    for a, b, end in [((17, 18), (12, 23), (10, 31)),
                      ((8, 37), (6, 44), (8, 48)),
                      ((11, 55), (17, 51), (23, 43)),
                      ((28, 42), (33, 42), (38, 43)),
                      ((44, 51), (50, 55), (53, 48)),
                      ((55, 44), (53, 37), (51, 31)),
                      ((49, 23), (44, 18), (37, 22)),
                      ((33, 24), (28, 24), (24, 22))]:
        points.extend(bezier(points[-1], a, b, end))
    return points


OUTLINE = outline()


def crossings(y):
    result = []
    for first, second in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            result.append(x1 + (x2-x1)*(y-y1)/(y2-y1))
    return sorted(result)


def inside(x, edges):
    return sum(edge > x for edge in edges) % 2 == 1


def rounded(x, y, left, top, right, bottom, radius):
    dx = max(left + radius - x, 0, x - right + radius)
    dy = max(top + radius - y, 0, y - bottom + radius)
    return dx*dx + dy*dy <= radius*radius


def mix(first, second, t):
    t = max(0, min(1, t))
    return tuple(round(a*(1-t) + b*t) for a, b in zip(first, second))


def line(x, y, ax, ay, bx, by, thickness):
    dx, dy = bx-ax, by-ay
    t = max(0, min(1, ((x-ax)*dx + (y-ay)*dy)/(dx*dx+dy*dy)))
    return (x-ax-t*dx)**2 + (y-ay-t*dy)**2 <= (thickness/2)**2


def color(x, y, edges):
    if not rounded(x, y, 3, 3, 61, 61, 15):
        return 0, 0, 0, 0
    # Quiet indigo glass, with a cool upper-left highlight and an inset rim.
    rgb = mix((48, 67, 103), (18, 26, 47), (x+y)/120)
    if rounded(x, y, 4, 4, 60, 60, 14):
        rgb = mix((29, 47, 77), (11, 17, 33), (x+y-10)/100)
    # A clear controller silhouette and dark controls remain legible at 16px.
    if inside(x, edges):
        rgb = mix((234, 245, 255), (150, 188, 234), (y-22)/31)
        if (rounded(x, y, 16, 30, 28, 34, 1) or rounded(x, y, 20, 26, 24, 38, 1)):
            rgb = (28, 53, 85)
        if (x-40)**2+(y-28.5)**2 <= 2.2**2 or (x-45)**2+(y-33.5)**2 <= 2.2**2:
            rgb = (33, 66, 99)
        if rounded(x, y, 29, 28, 33, 30, 1):
            rgb = (77, 119, 165)
    # Mint clock badge: strong separation, a luminous ring, no tiny decoration.
    distance = hypot(x-47, y-46)
    if distance <= 14:
        rgb = (10, 19, 35)
    if distance <= 12:
        rgb = mix((139, 255, 226), (36, 196, 203), (y-34)/24)
    if distance <= 9:
        rgb = mix((28, 62, 77), (15, 37, 55), (y-37)/18)
        if line(x, y, 47, 46, 47, 40, 2.9) or line(x, y, 47, 46, 52, 46, 2.9):
            rgb = (222, 255, 245)
    return *rgb, 255


def render(size):
    scale = 4
    samples = [[[] for _ in range(size)] for _ in range(size)]
    # Cache vector intersections per subpixel row rather than repeating polygon
    # traversal for every pixel; this keeps the generator small and fast.
    for y in range(size):
        for sy in range(scale):
            yy = (y+(sy+.5)/scale)*64/size
            edges = crossings(yy)
            for x in range(size):
                for sx in range(scale):
                    samples[y][x].append(color((x+(sx+.5)/scale)*64/size, yy, edges))
    pixels = []
    for row in samples:
        for group in row:
            alpha = sum(p[3] for p in group)
            pixels.append(tuple(round(sum(p[i]*p[3] for p in group)/alpha) if alpha else 0 for i in range(3))
                          + (round(alpha/len(group)),))
    return pixels


def png(size, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    scan = b''.join(b'\0' + bytes(c for p in pixels[y*size:(y+1)*size] for c in p) for y in range(size))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scan, 9)) + chunk(b'IEND', b''))


def main():
    base = Path(__file__).resolve().parent.parent
    images = [(size, png(size, render(size))) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    offset = 6 + 16*len(images)
    entries = []
    for size, data in images:
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (base/'gametime/app.ico').write_bytes(struct.pack('<HHH', 0, 1, len(images)) + b''.join(entries)
                                        + b''.join(data for _, data in images))
    (base/'gametime/app.png').write_bytes(images[-1][1])


if __name__ == '__main__':
    main()
