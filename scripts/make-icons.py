#!/usr/bin/env python3
"""產生 PWA 圖示(純標準庫手寫 PNG,不裝 Pillow)。

圖案:深色底 + 綠色同心圓環(雷達)+ 中心亮點。
邊緣做了簡易反鋸齒,縮到桌面小圖也不會有鋸齒。
"""
import math, os, struct, zlib

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "icons")
BG = (0x0A, 0x0C, 0x0E)
GREEN = (0x00, 0xDC, 0x64)

# 圓環:(半徑比例, 線寬比例, 不透明度)
RINGS = [(0.42, 0.030, 0.28), (0.30, 0.034, 0.52), (0.18, 0.038, 0.80)]
DOT_R = 0.065


def blend(base, over, a):
    return tuple(round(b + (o - b) * a) for b, o in zip(base, over))


def make(size):
    cx = cy = (size - 1) / 2
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = (x - cx) / size, (y - cy) / size
            d = math.hypot(dx, dy)
            px, cover = BG, 0.0
            for r, w, alpha in RINGS:
                # 距離環中線多遠(以線寬的一半為單位),1 以內算在環上
                t = abs(d - r) / (w / 2)
                if t < 1.6:
                    a = alpha * max(0.0, min(1.0, 1.6 - t))
                    if a > cover:
                        cover = a
            t = (d - DOT_R) / 0.012
            dot = max(0.0, min(1.0, 1.0 - t))
            cover = max(cover, dot)
            if cover > 0:
                px = blend(BG, GREEN, cover)
            row.append((px[0], px[1], px[2], 255))
        rows.append(row)
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in (180, 192, 512):
        n = write_png(os.path.join(OUT, f"icon-{s}.png"), s, make(s))
        print(f"icon-{s}.png  {n:,} bytes")
