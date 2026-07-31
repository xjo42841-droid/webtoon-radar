#!/usr/bin/env python3
"""每日抓取 LINE WEBTOON 台灣站:完結名單 / 即將轉代幣 / 今日新完結。

刻意只用 Python 標準庫,不裝任何第三方套件 —— GitHub Actions 上零安裝、
也不會哪天因為套件升版而壞掉。

⚠ HEADERS 不可省略 Accept-Language:實測少了它,完結頁只會回 396 部
   (完整是 1161 部),而且照樣回 HTTP 200、內容看起來完全正常。
   這是本專案最危險的靜默失敗,健康檢查就是為它而存在。
"""
import gzip, html, io, json, os, re, sys, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
HIST = os.path.join(DATA, "history")
THUMBS = os.path.join(ROOT, "docs", "thumbs")

BASE = "https://www.webtoons.com/zh-hant"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",   # ← 少了這行會靜默少拿 2/3 資料
    "Accept-Encoding": "gzip",
}

# 一張作品卡。結構取自 2026-07-31 實際頁面,已逐欄位驗證。
CARD_RE = re.compile(
    r'<a\s+href="(?P<href>[^"]+)"\s+class="link _originals_title_a"\s+'
    r'data-title-no="(?P<no>\d+)"(?P<rest>.*?)</a>', re.S)
GENRE_RE = re.compile(r'<div class="genre">([^<]*)</div>')
TITLE_RE = re.compile(r'<strong class="title">([^<]*)</strong>')
LIKES_RE = re.compile(r'<div class="view_count[^"]*">([^<]*)</div>')
THUMB_RE = re.compile(r'<img[^>]+src="([^"]+)"')

NOTICE_ROW_RE = re.compile(
    r'<a href="[^"]*noticeNo=(\d+)[^"]*" class="subj">([^<]*)</a>\s*</td>\s*'
    r'<td class="date">(.*?)</td>', re.S)
NOTICE_DATE_RE = re.compile(r'(\d{4})\.(\d{1,2})\.(\d{1,2})')
DATE_RE = re.compile(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日')
LIST_ITEM_RE = re.compile(r'^\s*(\d{1,2})\s*[.、,]\s*(\S.{0,40})$')

warnings = []


def warn(msg):
    warnings.append(msg)
    print(f"[警告] {msg}", file=sys.stderr)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


def parse_cards(page_html, status, weekday=None):
    out = []
    for m in CARD_RE.finditer(page_html):
        rest = m.group("rest")
        t = TITLE_RE.search(rest)
        if not t:
            continue
        g = GENRE_RE.search(rest)
        l = LIKES_RE.search(rest)
        th = THUMB_RE.search(rest)
        out.append({
            "no": m.group("no"),
            "title": html.unescape(t.group(1)).strip(),
            "genre": html.unescape(g.group(1)).strip() if g else "",
            "likes": html.unescape(l.group(1)).strip() if l else "",
            "href": html.unescape(m.group("href")),
            "thumb_src": th.group(1) if th else "",
            "status": status,
            "weekday": weekday,
        })
    return out


def html_to_text(h):
    h = re.sub(r'(?is)<(script|style).*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>', '\n', h)
    h = re.sub(r'(?i)</(p|div|li|tr|h\d)>', '\n', h)
    h = re.sub(r'<[^>]+>', '', h)
    h = html.unescape(h)
    h = h.replace(' ', ' ')
    h = re.sub(r'[ \t]+', ' ', h)
    return '\n'.join(x.strip() for x in h.split('\n'))


def fetch_completed():
    """完結全庫。一頁到底,沒有分頁。"""
    page = get(f"{BASE}/originals/complete?sortOrder=MANA")
    cards = parse_cards(page, "completed")
    if not cards:
        warn("完結頁一部作品都沒解析到 —— 版面可能改了,解析規則要更新")
    return cards


def fetch_ongoing():
    """連載中(週一~週日七頁)。"""
    out = []
    for d in WEEKDAYS:
        try:
            page = get(f"{BASE}/originals/{d}?sortOrder=MANA")
        except Exception as e:
            warn(f"連載頁 {d} 抓取失敗:{e}")
            continue
        got = parse_cards(page, "ongoing", d)
        if not got:
            warn(f"連載頁 {d} 解析到 0 部")
        out.extend(got)
    # 同一部可能掛多天,以 title_no 去重
    seen, uniq = set(), []
    for c in out:
        if c["no"] not in seen:
            seen.add(c["no"])
            uniq.append(c)
    return uniq


def fetch_latest_notice():
    """找最新一則「完結名單」公告,解析出生效日與作品名。"""
    try:
        listing = get(f"{BASE}/notice/list")
    except Exception as e:
        warn(f"公告列表抓取失敗:{e}")
        return None

    rows = NOTICE_ROW_RE.findall(listing)
    if not rows:
        warn("公告列表解析到 0 則 —— 版面可能改了")
        return None

    target = next(((no, html.unescape(t), d) for no, t, d in rows if "完結名單" in t), None)
    if not target:
        warn("公告列表裡找不到「完結名單」;可能這個月還沒發,或標題用語改了")
        return None

    no, title, date_cell = target
    dm0 = NOTICE_DATE_RE.search(date_cell)
    posted = f"{dm0.group(1)}-{int(dm0.group(2)):02d}-{int(dm0.group(3)):02d}" if dm0 else ""
    try:
        detail = get(f"{BASE}/notice/detail?noticeNo={no}")
    except Exception as e:
        warn(f"公告內文 {no} 抓取失敗:{e}")
        return None

    text = html_to_text(detail)

    dm = DATE_RE.search(text)
    if not dm:
        warn(f"公告 {no} 內文找不到生效日期")
        return None
    switch = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), tzinfo=TPE)

    # 只取「轉為完結解鎖模式」那段之後、說明文字之前的編號清單
    start = text.find("轉為完結解鎖模式")
    seg = text[start:] if start >= 0 else text
    for stop in ("詳細使用說明", "保有營運策略", "完結作品最新攻略"):
        i = seg.find(stop)
        if i > 0:
            seg = seg[:i]
            break

    names, expect = [], 1
    for line in seg.split("\n"):
        m = LIST_ITEM_RE.match(line)
        if m and int(m.group(1)) == expect:
            names.append(m.group(2).strip())
            expect += 1
    if not names:
        warn(f"公告 {no} 解析不到作品清單")
        return None

    return {"notice_no": int(no), "notice_title": title, "posted_date": posted,
            "switch_date": switch.strftime("%Y-%m-%d"), "titles": names}


def download_thumb(no, src):
    """封面圖有防盜連,不帶 Referer 會 403。已存在就不重抓。"""
    if not src:
        return ""
    ext = ".png" if ".png" in src.lower().split("?")[0] else ".jpg"
    name = f"{no}{ext}"
    path = os.path.join(THUMBS, name)
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return f"thumbs/{name}"
    try:
        import urllib.parse
        safe = urllib.parse.quote(src, safe=":/?=&%")
        req = urllib.request.Request(safe, headers={
            "Referer": "https://www.webtoons.com/", "User-Agent": HEADERS["User-Agent"]})
        data = urllib.request.urlopen(req, timeout=25).read()
        with open(path, "wb") as f:
            f.write(data)
        return f"thumbs/{name}"
    except Exception as e:
        warn(f"封面 {no} 下載失敗:{e}")
        return ""


def load_previous():
    """讀最近一份『成功的』歷史快照,用來算今天的變化。

    ⚠ 必須跳過失敗那幾天的快照。失敗快照沒有 complete_ids,若拿它當基準,
      全庫每一部都會被誤判成「今天剛完結」(實測踩過:一次誤報 1162 部)。
    """
    if not os.path.isdir(HIST):
        return None
    for name in sorted((f for f in os.listdir(HIST) if f.endswith(".json")), reverse=True):
        try:
            with open(os.path.join(HIST, name), encoding="utf-8") as f:
                snap = json.load(f)
        except Exception:
            continue
        if snap.get("failed") or not snap.get("complete_ids"):
            continue
        return snap
    return None


def main():
    now = datetime.now(TPE)
    today = now.strftime("%Y-%m-%d")

    # 任何一段掛掉都不讓整支程式中斷 —— 中斷 = 什麼都不寫 = 錯誤看不見,
    # 而且 repo 那天沒有 commit,會往「60 天沒動靜就被停用」那條路上累積。
    try:
        completed = fetch_completed()
    except Exception as e:
        warn(f"完結頁抓取失敗:{e}")
        completed = []
    try:
        ongoing = fetch_ongoing()
    except Exception as e:
        warn(f"連載頁抓取失敗:{e}")
        ongoing = []
    try:
        notice = fetch_latest_notice()
    except Exception as e:
        warn(f"公告抓取失敗:{e}")
        notice = None

    by_title = {}
    for c in ongoing + completed:          # 連載優先,對得到就是「還在連載=快要完結」
        by_title.setdefault(c["title"], c)

    upcoming = None
    if notice:
        days_left = (datetime.strptime(notice["switch_date"], "%Y-%m-%d").replace(tzinfo=TPE)
                     - now.replace(hour=0, minute=0, second=0, microsecond=0)).days
        items, missed = [], []
        for name in notice["titles"]:
            hit = by_title.get(name)
            if not hit:
                missed.append(name)
                items.append({"title": name, "status": "unknown"})
                continue
            items.append({
                "title": hit["title"], "no": hit["no"], "genre": hit["genre"],
                "likes": hit["likes"], "href": hit["href"], "weekday": hit["weekday"],
                "status": "ongoing" if hit["status"] == "ongoing" else "completed_free",
                "thumb": download_thumb(hit["no"], hit["thumb_src"]),
            })
        if missed:
            warn(f"公告有 {len(missed)} 部作品在站上對不到名稱:{'、'.join(missed)}")
        upcoming = {**notice, "days_left": days_left, "items": items}

    prev = load_previous()
    newly = []
    if prev:
        new_ids = set(c["no"] for c in completed) - set(prev.get("complete_ids", []))
        new_list = [c for c in completed if c["no"] in new_ids]
        # 一天冒出幾十部「新完結」實務上不可能,多半是比對基準出了問題。
        # 這時照樣記錄,但不下載封面 —— 實測踩過:一次誤抓 1,153 張、176 MB 灌進 repo。
        sane = len(new_list) <= 40
        if not sane:
            warn(f"今日新完結 {len(new_list)} 部,數量異常,已略過封面下載,請檢查比對基準")
        newly = [{"title": c["title"], "no": c["no"], "genre": c["genre"],
                  "likes": c["likes"], "href": c["href"],
                  "thumb": download_thumb(c["no"], c["thumb_src"]) if sane else ""}
                 for c in new_list]
        # 數量暴跌 = 最可能是抓取被削,不是真的有一堆作品消失
        for label, now_n, key in (("完結", len(completed), "complete_count"),
                                  ("連載", len(ongoing), "ongoing_count")):
            was = prev.get(key, 0)
            if was and now_n < was * 0.9:
                warn(f"{label}數量從 {was} 掉到 {now_n}(少於九成)—— 抓取很可能被削,不是真的變少")

    health = {
        "ok": not warnings,
        "complete_count": len(completed),
        "ongoing_count": len(ongoing),
        "notice_found": notice is not None,
        "warnings": warnings,
        "checked_at": now.isoformat(timespec="seconds"),
    }

    latest = {
        "generated_at": now.isoformat(timespec="seconds"),
        "today": today,
        "health": health,
        "upcoming": upcoming,
        "newly_completed": newly,
        "completed_total": len(completed),
        "ongoing_total": len(ongoing),
    }

    os.makedirs(HIST, exist_ok=True)
    os.makedirs(THUMBS, exist_ok=True)

    # 這次一部都沒抓到 = 幾乎肯定是抓取端出事,不是全站作品消失。
    # 這時保留上次的內容給畫面用,只把健康狀態換成壞的 —— 使用者會看到
    # 上次的資料配一則紅色警告,而不是莫名其妙的一片空白。
    prev_latest_path = os.path.join(DATA, "latest.json")
    if not completed and os.path.exists(prev_latest_path):
        try:
            with open(prev_latest_path, encoding="utf-8") as f:
                old = json.load(f)
            warn("這次一部都沒抓到,畫面沿用上次的資料(下方時間為上次成功時間)")
            health["warnings"] = warnings
            health["ok"] = False
            health["stale_from"] = old.get("generated_at", "")
            latest = {**old, "health": health, "checked_at": now.isoformat(timespec="seconds")}
            with open(prev_latest_path, "w", encoding="utf-8") as f:
                json.dump(latest, f, ensure_ascii=False, indent=1)
            with open(os.path.join(HIST, f"{today}.json"), "w", encoding="utf-8") as f:
                json.dump({"date": today, "failed": True, "warnings": warnings}, f, ensure_ascii=False)
            print(f"\n抓取失敗,已保留上次資料並標記警告({len(warnings)} 則)。")
            return 1
        except Exception as e:
            warn(f"連沿用上次資料都失敗:{e}")

    with open(prev_latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)
    # 全庫索引(給「全庫」分頁搜尋用)。不含封面網址 —— 全庫不預抓圖,
    # 只有倒數名單那十幾部才存封面,避免上百 MB 的圖庫。
    with open(os.path.join(DATA, "library.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": now.isoformat(timespec="seconds"),
                   "count": len(completed),
                   "items": [{"no": c["no"], "title": c["title"], "genre": c["genre"],
                              "likes": c["likes"], "href": c["href"]} for c in completed]},
                  f, ensure_ascii=False)
    # 每天都寫一份快照 —— 即使毫無變化。這同時讓 repo 天天有 commit,
    # 避開 GitHub「60 天沒動靜就停用排程」的規則。
    with open(os.path.join(HIST, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today,
                   "complete_ids": sorted(c["no"] for c in completed),
                   "ongoing_ids": sorted(c["no"] for c in ongoing),
                   "complete_count": len(completed),
                   "ongoing_count": len(ongoing)}, f, ensure_ascii=False)

    print(f"完結 {len(completed)} 部 · 連載 {len(ongoing)} 部 · "
          f"公告 {'找到' if notice else '沒找到'} · 今日新完結 {len(newly)} 部")
    if upcoming:
        print(f"下次轉代幣:{upcoming['switch_date']}(剩 {upcoming['days_left']} 天)"
              f",{len(upcoming['items'])} 部")
    if warnings:
        print(f"\n有 {len(warnings)} 個警告,資料已照常寫檔,但請去看一下。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
