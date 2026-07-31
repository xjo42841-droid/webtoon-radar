#!/usr/bin/env python3
"""把設計稿用到的 12 張 WEBTOON 封面抓到本機 thumbs/。
WEBTOON 圖床擋 referer:不帶 Referer 會回 403,所以這裡補上。
"""
import os, urllib.parse, urllib.request

THUMBS = {
    "450":  "https://webtoon-phinf.pstatic.net/20250204_75/1738644235673VKghf_JPEG/450.jpg?type=q90",
    "7094": "https://webtoon-phinf.pstatic.net/20250205_253/1738719838492hI88J_PNG/7094.png?type=q90",
    "5301": "https://webtoon-phinf.pstatic.net/20260415_100/1776242603498kXjeK_PNG/14__Thumb_Poster.png?type=q90",
    "4283": "https://webtoon-phinf.pstatic.net/20250205_70/1738719249581vL6jm_JPEG/4283.jpg?type=q90",
    "5234": "https://webtoon-phinf.pstatic.net/20250205_125/1738719545575CTfI9_JPEG/5234.jpg?type=q90",
    "7897": "https://webtoon-phinf.pstatic.net/20250512_112/1747037815188r8zKi_JPEG/Thumb_Poster_7897.jpg?type=q90",
    "5150": "https://webtoon-phinf.pstatic.net/20250602_101/1748840104317IcUFW_PNG/20250528-健身地下城_480x623-2(+標準字).png?type=q90",
    "3090": "https://webtoon-phinf.pstatic.net/20250205_194/1738718694116HdiLb_PNG/3090.png?type=q90",
    "7389": "https://webtoon-phinf.pstatic.net/20250220_82/1740037999897lMxVd_JPEG/Thumb_Poster.jpg?type=q90",
    "7902": "https://webtoon-phinf.pstatic.net/20251215_195/1765771705054qUoBY_PNG/垂直略縮圖480x623_Logo.png?type=q90",
    "7388": "https://webtoon-phinf.pstatic.net/20250213_190/1739412038957QGQRN_JPEG/Thumb_Poster.jpg?type=q90",
    "8524": "https://webtoon-phinf.pstatic.net/20250926_248/1758870484832rEec9_JPEG/Thumb_Poster.jpg?type=q90",
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbs")
os.makedirs(out, exist_ok=True)

for no, url in THUMBS.items():
    safe = urllib.parse.quote(url, safe=":/?=&%")
    req = urllib.request.Request(safe, headers={
        "Referer": "https://www.webtoons.com/",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        data = urllib.request.urlopen(req, timeout=20).read()
        ext = ".png" if ".png" in url.lower().split("?")[0] else ".jpg"
        path = os.path.join(out, no + ext)
        with open(path, "wb") as f:
            f.write(data)
        print(f"OK   {no}{ext}  {len(data):>7,} bytes")
    except Exception as e:
        print(f"FAIL {no}  {e}")
