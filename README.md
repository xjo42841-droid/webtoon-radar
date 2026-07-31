# 完結雷達

每天自動追蹤 LINE WEBTOON 台灣站:哪些作品**快要完結**、**剛完結**、以及**即將從免費轉成要代幣**。

做成 PWA,可以加到手機主畫面當 App 用。

---

## 它在追什麼

LINE WEBTOON 的「完結」和「轉代幣」是**兩個階段**,不是同一件事:

1. 作品連載結束 → 進「完結」列表,**但仍然免費全看**
2. 官方公告的某一天 → 轉成「**完結解鎖模式**」,看舊話要代幣或看廣告

官方每個月會發一則「X月最新完結名單」公告,**提前約一個月**預告哪些作品要轉。這支程式就是盯著那則公告 + 每天比對完結列表。

畫面分三塊:

| 區塊 | 意思 |
|---|---|
| 快要完結 | 公告點名了,但站上還在連載 |
| 已完結 · 還免費 | 已完結,現在補完不用錢,到期就要代幣 |
| 今天剛完結 | 跟昨天的清單比對後新增的 |

---

## 部署(三步,全部免費)

### 1. 推上 GitHub

```bash
gh repo create webtoon-radar --public --source=. --push
```

用**公開**專案的話 GitHub Actions 完全免費、無用量上限。
設成私人也可以,免費額度每月 2,000 分鐘,而這個工作一天只花約 2 分鐘。

### 2. 開啟 GitHub Pages

repo 的 **Settings → Pages → Source** 選 `Deploy from a branch`,
branch 選 `main`、資料夾選 **`/docs`**,存檔。

過一兩分鐘就會有網址:`https://<你的帳號>.github.io/webtoon-radar/`

### 3. 手機加到主畫面

用手機瀏覽器打開那個網址 → 分享選單 → **加入主畫面**。
之後它就是一個 App:全螢幕、有圖示、離線也能看上次抓到的資料。

---

## 每天怎麼跑

`.github/workflows/daily.yml` 設定為每天 **台北時間早上 6:00** 跑一次
(GitHub 排程不保證準時,尖峰時可能延後幾十分鐘,屬正常)。

也可以到 Actions 頁面按 **Run workflow** 手動立刻跑。

抓完的資料會 commit 回 repo,所以:

* 每天都有 commit → 自動避開 GitHub「**60 天沒動靜就停用排程**」的規則
* git 歷史等於免費的每日快照,可以回看任何一天的狀態

---

## 壞掉的時候會怎樣

這整套是靠讀網頁做的(WEBTOON 沒有公開 API),所以對方改版就會壞。
**重點是壞的時候不能安靜**,所以做了這些:

* **數量暴跌警告** — 完結或連載數量比上次少一成以上,直接標記警告
* **抓到 0 筆不覆蓋** — 保留上次的資料給畫面用,只把狀態標成壞,App 上會顯示紅色警示配上次的時間,不會變成空白
* **失敗那天不當比較基準** — 否則隔天會把全庫誤判成「今天剛完結」(這個坑實測踩過,一次誤報 1,162 部)
* **Actions 會標紅** — 抓取有警告時這次執行會失敗,你會收到 GitHub 通知

App 裡的**設定**分頁隨時看得到目前的抓取狀態和警告內容。

### 一個特別陰險的坑

抓網頁時 **`Accept-Language: zh-TW` 這個標頭不能少**。

實測:少了它,完結頁只會回 **396 部**(完整是 1,162 部),而且照樣回 HTTP 200、
內容看起來完全正常。這種錯誤不會自己現形,只會讓你每天安靜地漏掉三分之二的資料。
`scripts/fetch.py` 的 `HEADERS` 有註解標記,不要動它。

---

## 封面圖

WEBTOON 圖床擋外連,不帶 `Referer` 一律 403。所以:

* 抓取階段由程式帶著 Referer 下載,存進 `docs/thumbs/`
* 前端**不能**直接把 `<img src>` 指向 WEBTOON,會整片破圖
* 只存倒數名單那 12 部,實測 **2.5 MB**。全庫 1,162 部若全存實測是 **176 MB**,沒必要
* 另有保護:某天「新完結」超過 40 部時不下載封面(那幾乎肯定是比對基準壞了,
  實測踩過一次,誤抓 1,153 張)

---

## 檔案結構

```
docs/                    ← GitHub Pages 發布目錄(整個 PWA)
  index.html               主畫面(從 mockup/style-a-dark.html 衍生)
  manifest.webmanifest     PWA 設定
  sw.js                    離線快取
  icons/                   圖示(scripts/make-icons.py 產生)
  data/latest.json         今天的資料
  data/library.json        完結全庫索引(給搜尋用)
  data/history/*.json      每日快照(比對用)
  thumbs/                  封面
scripts/
  fetch.py                 每日抓取(只用 Python 標準庫,零安裝)
  make-icons.py            產生圖示
mockup/                  ← 設計稿(A/B/C 三版,保留備查)
.github/workflows/daily.yml
```

## 本機測試

```bash
python3 scripts/fetch.py                      # 抓一次資料
python3 -m http.server 8899 -d docs           # 開 http://localhost:8899
```

> 改了 `index.html` 卻沒變化 → 是 Service Worker 快取住了。
> 開發時用無痕視窗,或到瀏覽器開發者工具 Application → Service Workers 按 Unregister。

---

這是非官方工具,一切以 [LINE WEBTOON 官方公告](https://www.webtoons.com/zh-hant/notice/list) 為準。
