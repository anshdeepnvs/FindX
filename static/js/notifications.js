/**
 * notifications.js — Browser Web Push & Desktop/Mobile Notifications for FindX
 * Supports Android Chrome, Desktop Chrome, Edge, Safari, Firefox.
 */

(function () {
  'use strict';

  var swRegistration = null;
  var pollInterval = null;
  var lastSeenId = parseInt(localStorage.getItem('findx_last_notif_id') || '0', 10);

  // Initialize Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').then(function (reg) {
      swRegistration = reg;
    }).catch(function (err) {
      console.log('SW registration note:', err);
    });
  }

  // Check if browser notifications are supported
  function isSupported() {
    return 'Notification' in window;
  }

  // Get current permission status: 'granted', 'denied', or 'default'
  function getPermission() {
    if (!isSupported()) return 'unsupported';
    return Notification.permission;
  }

  // Request notification permission from user
  window.requestFindXNotificationPermission = function (callback) {
    if (!isSupported()) {
      alert('Browser notifications are not supported by your current browser.');
      if (callback) callback('unsupported');
      return;
    }

    Notification.requestPermission().then(function (permission) {
      updateUIStatus(permission);

      if (permission === 'granted') {
        // Show welcome confirmation notification
        showSystemNotification({
          title: '🔔 FindX Notifications Enabled!',
          body: 'You will receive real-time official alerts on this device when matches or claims update.',
          link: '/notifications/'
        });

        // Hide prompt banner if present
        var banner = document.getElementById('notifPermissionBanner');
        if (banner) banner.style.display = 'none';

        // Start polling immediately
        startPolling();
      }

      if (callback) callback(permission);
    });
  };

  // Show a native browser notification (Mobile & PC)
  function showSystemNotification(data) {
    if (!isSupported() || Notification.permission !== 'granted') return;

    var title = data.title || 'FindX Notification';
    var options = {
      body: data.body || '',
      icon: '/static/img/favicon.png',
      badge: '/static/img/favicon.png',
      tag: 'findx-notif-' + (data.id || Date.now()),
      data: { url: data.link || '/notifications/' },
      vibrate: [200, 100, 200]
    };

    if (swRegistration && swRegistration.showNotification) {
      swRegistration.showNotification(title, options);
    } else {
      try {
        var n = new Notification(title, options);
        n.onclick = function () {
          window.focus();
          if (data.link) window.location.href = data.link;
          n.close();
        };
      } catch (e) {
        console.log('Desktop notification error:', e);
      }
    }
  }

  // Update DOM elements that display notification status
  function updateUIStatus(permission) {
    var statusBadges = document.querySelectorAll('.notif-permission-badge');
    statusBadges.forEach(function (el) {
      if (permission === 'granted') {
        el.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span> Active on this device';
        el.className = 'notif-permission-badge inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300';
      } else if (permission === 'denied') {
        el.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 inline-block"></span> Blocked in browser settings';
        el.className = 'notif-permission-badge inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300';
      } else {
        el.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-500 inline-block"></span> Not enabled on this device';
        el.className = 'notif-permission-badge inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300';
      }
    });

    var enableBtns = document.querySelectorAll('.notif-enable-btn');
    enableBtns.forEach(function (btn) {
      if (permission === 'granted') {
        btn.textContent = '✓ Notifications Enabled';
        btn.disabled = true;
        btn.classList.add('opacity-60', 'cursor-default');
      } else if (permission === 'denied') {
        btn.textContent = '⚠️ Blocked (Check Browser Settings)';
        btn.disabled = true;
        btn.classList.add('opacity-60', 'cursor-not-allowed');
      } else {
        btn.textContent = '🔔 Enable Mobile & PC Notifications';
        btn.disabled = false;
        btn.classList.remove('opacity-60');
      }
    });
  }

  // Update the Navbar Bell Badge
  function updateBellBadge(unreadCount) {
    var bell = document.getElementById('notifBellBadge');
    if (!bell) {
      var bellLink = document.querySelector('a[href*="/notifications/"]');
      if (bellLink && unreadCount > 0) {
        bell = document.createElement('span');
        bell.id = 'notifBellBadge';
        bell.className = 'absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow';
        bellLink.appendChild(bell);
      }
    }

    if (bell) {
      if (unreadCount > 0) {
        bell.textContent = unreadCount;
        bell.style.display = 'flex';
      } else {
        bell.style.display = 'none';
      }
    }
  }

  // Poll for new official notifications (MATCH, CLAIM, RETURN, SYSTEM)
  function pollNotifications() {
    var url = '/notifications/unread-latest/?since_id=' + (lastSeenId || 0);

    fetch(url, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) return null;
        return res.json();
      })
      .then(function (data) {
        if (!data) return;

        // Update badge
        if (typeof data.unread_count !== 'undefined') {
          updateBellBadge(data.unread_count);
        }

        // Fire system notification for each newly arrived official notification
        if (data.official_notifications && data.official_notifications.length > 0) {
          data.official_notifications.forEach(function (item) {
            if (item.id > lastSeenId) {
              lastSeenId = item.id;
              localStorage.setItem('findx_last_notif_id', String(lastSeenId));

              // Deliver native browser notification
              showSystemNotification({
                id: item.id,
                title: item.title,
                body: item.body,
                link: item.link
              });
            }
          });
        }
      })
      .catch(function (err) {
        // Silently ignore network hiccup during background poll
      });
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    // Poll initially after 2 seconds, then every 25 seconds
    setTimeout(pollNotifications, 2000);
    pollInterval = setInterval(pollNotifications, 25000);
  }

  // On page load
  document.addEventListener('DOMContentLoaded', function () {
    var perm = getPermission();
    updateUIStatus(perm);

    // If user is authenticated (indicated by presence of notification bell)
    var bellLink = document.querySelector('a[href*="/notifications/"]');
    if (bellLink) {
      startPolling();

      // If permission is default and user hasn't dismissed prompt, show banner
      var dismissed = localStorage.getItem('findx_notif_prompt_dismissed');
      var banner = document.getElementById('notifPermissionBanner');
      if (banner && perm === 'default' && !dismissed) {
        banner.style.display = 'block';
      }
    }

    // Bind dismiss button if banner exists
    var dismissBtn = document.getElementById('dismissNotifBannerBtn');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', function () {
        var banner = document.getElementById('notifPermissionBanner');
        if (banner) banner.style.display = 'none';
        localStorage.setItem('findx_notif_prompt_dismissed', '1');
      });
    }
  });

})();
