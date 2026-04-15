var CACHE_NAME = 'epaper-v1';
var PRECACHE_URLS = [
  '/static/favicon.ico',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

var OFFLINE_HTML = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>epaper-frame — offline</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:monospace;background:#111;color:#eee;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:2rem}h1{font-size:1.4rem;color:#fff;margin-bottom:0.8rem}p{color:#888;font-size:0.9rem}</style></head><body><div><h1>epaper-frame</h1><p>Cannot reach the Pi right now.</p><p style="margin-top:0.5rem">Check that it is powered on and connected.</p></div></body></html>';

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(PRECACHE_URLS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function(event) {
  var url = event.request.url;

  // Don't intercept API calls — always live data
  if (url.includes('/api/')) return;

  // Cache-first for static assets
  if (url.includes('/static/')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        if (cached) return cached;
        return fetch(event.request).then(function(response) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
          return response;
        });
      })
    );
    return;
  }

  // Network-first for HTML pages, offline fallback on error
  var isHTML = event.request.headers.get('accept') &&
               event.request.headers.get('accept').includes('text/html');
  if (isHTML) {
    event.respondWith(
      fetch(event.request).catch(function() {
        return new Response(OFFLINE_HTML, {
          headers: {'Content-Type': 'text/html; charset=utf-8'},
        });
      })
    );
  }
});
