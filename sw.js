const CACHE = 'sonar-katta-v3';
const STATIC = ['./', './index.html', './manifest.json', './icon-512.png', './crystal-frame.webp', './logo-card.webp', './gold-bars.webp', './silver-bars.webp'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))), self.clients.claim()]));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put('./index.html', copy)); }
      return response;
    }).catch(() => caches.match('./index.html')));
  } else if (new URL(event.request.url).origin === self.location.origin) {
    event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
  }
});
