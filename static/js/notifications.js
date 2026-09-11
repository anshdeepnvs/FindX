/**
 * notifications.js — Browser Web Push & Desktop/Mobile Notifications for FindX
 * Supports Android Chrome, Desktop Chrome, Edge, Safari, Firefox.
 */

(function () {
  'use strict';

  var swRegistration = null;
  var pollInterval = null;
  var lastSeenId = parseInt(localStorage.getItem('findx_last_notif_id') || '0', 10);
  var isInitialized = localStorage.getItem('findx_notif_initialized') === '1';

  // Initialize Service Worker for background push / mobile devices
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

  // Subtle web audio chime for notifications (zero external files required)
  function playNotificationChime() {
    try {
      var AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      var ctx = new AudioContext();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.setValueAtTime(880.00, ctx.currentTime + 0.09); // A5

      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      // Audio context might be restricted before user gesture
    }
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
        playNotificationChime();

        // Show welcome confirmation notification
        showSystemNotification({
          title: '🔔 FindX Notifications Enabled!',
          body: 'You will receive real-time alerts on this device when matches, claims, or chat messages arrive.',
          link: '/notifications/'
        });

        // Hide prompt banners
        var banner = document.getElementById('notifPermissionBanner');
        if (banner) banner.style.display = 'none';
        var chatBanner = document.getElementById('chatNotifPromptBar');
        if (chatBanner) chatBanner.style.display = 'none';

        // Start polling immediately
        startPolling();
      }

      if (callback) callback(permission);
    });
  };

  // Show a native browser notification (Mobile & PC)
  window.showFindXNotification = function (data) {
    showSystemNotification(data);
  };

  function showSystemNotification(data) {
    if (!isSupported() || Notification.permission !== 'granted') return;

    playNotificationChime();

    var title = data.title || 'FindX Notification';
    var options = {
      body: data.body || '',
      icon: '/static/img/favicon.png',
      badge: '/static/img/favicon.png',
      tag: 'findx-notif-' + (data.id || Date.now()),
      data: { url: data.link || '/notifications/' },
      vibrate: [200, 100, 200]
    };

    // On Desktop browsers (Chrome, Edge, Firefox), new Notification() triggers native OS toast directly
    try {
      var n = new Notification(title, options);
      n.onclick = function () {
        window.focus();
        if (data.link) window.location.href = data.link;
        n.close();
      };
      return;
    } catch (e) {
      // On mobile / Android, fallback to Service Worker showNotification
      if (swRegistration && swRegistration.showNotification) {
        swRegistration.showNotification(title, options);
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

  // Poll for new notifications (MATCH, CLAIM, RETURN, CHAT, SYSTEM)
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

        var items = data.notifications || data.official_notifications || [];
        if (!items || items.length === 0) return;

        // First run: sync latest ID without firing notifications for old messages
        if (!isInitialized) {
          isInitialized = true;
          localStorage.setItem('findx_notif_initialized', '1');
          var maxId = lastSeenId;
          items.forEach(function (it) {
            if (it.id > maxId) maxId = it.id;
          });
          lastSeenId = maxId;
          localStorage.setItem('findx_last_notif_id', String(lastSeenId));
          return;
        }

        // Fire system notification for each new notification
        items.forEach(function (item) {
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
      })
      .catch(function (err) {
        // Silently ignore network hiccup during background poll
      });
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    // Poll quickly (every 5 seconds) so chat messages appear in real time on PC & mobile
    setTimeout(pollNotifications, 1000);
    pollInterval = setInterval(pollNotifications, 5000);
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
