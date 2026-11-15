// Emerrr Emergency Sentinel Service Worker
// Provides 24/7 background system notifications, lock-screen alarms, and vibration for Android Chrome & Desktop

const CACHE_NAME = 'emerrr-sw-v2';

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

// Primary function: Display high-priority emergency notification with sound & vibration
function displayEmergencyNotification(title, options) {
  var opts = Object.assign({
    body: 'Urgent emergency alert received. Tap to view emergency details.',
    icon: '/assets/icon-192.png',
    badge: '/assets/badge-72.png',
    tag: 'emerrr-fire-alarm',
    renotify: true,
    requireInteraction: true,
    silent: false,
    vibrate: [1000, 300, 1000, 300, 1000, 300, 1000],
    data: { url: '/mobile.html', time: Date.now() },
    actions: [
      { action: 'open', title: '🚨 VIEW EMERGENCY' }
    ]
  }, options || {});

  return self.registration.showNotification(title || '🚨 EMERGENCY ALARM ACTIVE', opts);
}

// Listen for message events from mobile.html or index.html
self.addEventListener('message', function(event) {
  if (!event.data) return;
  if (event.data.type === 'SHOW_NOTIFICATION') {
    var title = event.data.title || '🚨 EMERGENCY ALARM ACTIVE';
    var options = event.data.options || {};
    event.waitUntil(displayEmergencyNotification(title, options));
  } else if (event.data.type === 'PING') {
    if (event.ports && event.ports[0]) {
      event.ports[0].postMessage({ status: 'PONG', time: Date.now() });
    }
  }
});

// Handle push notification events (Web Push / Cloud Relay)
self.addEventListener('push', function(event) {
  var data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch(e) {
      data = { title: '🚨 EMERGENCY ALERT', body: event.data.text() };
    }
  }
  var title = data.title || '🚨 EMERGENCY ALARM ACTIVE';
  var options = {
    body: data.body || 'Fire emergency erupted! 500m evacuation active.',
    icon: '/assets/icon-192.png',
    badge: '/assets/badge-72.png',
    tag: data.tag || 'emerrr-fire-alarm',
    renotify: true,
    requireInteraction: true,
    vibrate: [1000, 300, 1000, 300, 1000, 300, 1000],
    data: { url: data.url || '/mobile.html', time: Date.now() }
  };
  event.waitUntil(displayEmergencyNotification(title, options));
});

// When user taps on the system notification: focus existing window or open portal
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/mobile.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url && client.url.indexOf(targetUrl) !== -1 && 'focus' in client) {
          return client.focus();
        }
      }
      for (var j = 0; j < clientList.length; j++) {
        var c = clientList[j];
        if ('focus' in c) {
          return c.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
