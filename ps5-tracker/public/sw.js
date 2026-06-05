self.addEventListener('push', function(e){
  const data = e.data ? e.data.json() : {title:'PS5 Tracker', body:'New update!'};
  e.waitUntil(
    self.registration.showNotification(data.title || 'Binds PS5 Tracker', {
      body: data.body || '',
      tag: 'ps5-tracker',
      renotify: true
    })
  );
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  e.waitUntil(clients.openWindow('/'));
});
self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(clients.claim()); });
