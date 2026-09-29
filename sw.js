const CACHE = 'sonar-katta-pages-20260929-12';
const STATIC = ['./', './index.html', './1-card-template.png', './2-brand-original.png', './3-icon-original-512.png', './manifest.json', './icon-512.png', './4-crystal-clean-v2.webp', './logo-card.webp', './1-logo-approved.png', './gold-bars.webp', './silver-bars.webp', './1-footer-glow.webp', './2-arrow-ornament.png', './3-bill-ornament.png', './4-gst-star.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))), self.clients.claim()]));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  // Live bullion rates are never served from the offline/static cache.
  if (new URL(event.request.url).pathname.endsWith('/1-rates.json')) {
    event.respondWith(fetch(event.request, {cache: 'no-store'}));
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok) { const copy = response.clone(); caches.open(CACHE).then(cache => cache.put('./index.html', copy)); }
      return response;
    }).catch(() => caches.match('./index.html')));
  } else if (new URL(event.request.url).origin === self.location.origin) {
    event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
  }
});
