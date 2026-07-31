/* 完結雷達 Service Worker
   資料走「先連網、失敗才用快取」——寧可慢一點也要拿到當天最新的;
   沒網路時至少還能看到上次抓到的內容,不會開啟就一片空白。
   外框和圖片走「先用快取」——它們幾乎不變,秒開比較重要。 */
const VERSION = "v1";
const SHELL = `shell-${VERSION}`;
const DATA  = `data-${VERSION}`;
const MEDIA = `media-${VERSION}`;

const SHELL_FILES = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon-180.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(SHELL)
      // 單一檔案失敗不該讓整個安裝掛掉
      .then(c => Promise.allSettled(SHELL_FILES.map(f => c.add(f))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => ![SHELL, DATA, MEDIA].includes(k)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // 資料:先連網,拿到就順手更新快取;連不到才退回上次的
  if (url.pathname.includes("/data/")) {
    e.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(DATA).then(c => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // 封面:先用快取,沒有再連網
  if (url.pathname.includes("/thumbs/")) {
    e.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        const copy = res.clone();
        caches.open(MEDIA).then(c => c.put(req, copy));
        return res;
      }))
    );
    return;
  }

  // 外框:先用快取,同時背景更新
  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req).then(res => {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(req, copy));
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
