/**
 * Daily Route Planner - Service Worker for PWA
 * 
 * Provides offline functionality by caching static assets
 * and intercepting network requests.
 * 
 * Author: Chioma Okoye
 * Year: 2026
 */

// Cache version - update when assets change
const CACHE_VERSION = 'v1';
const CACHE_NAME = `daily-route-planner-${CACHE_VERSION}`;

// Assets to cache immediately on install
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/manifest.json',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

/**
 * Install event - cache static assets
 * WHY: Enable offline access to core app functionality
 * COMPLEXITY: O(n) where n is number of assets to cache
 */
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[SW] Installation complete, skipping waiting');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[SW] Cache installation failed:', error);
            })
    );
});

/**
 * Activate event - clean up old caches
 * WHY: Remove outdated cached data to save storage
 * COMPLEXITY: O(n) where n is number of old cache versions
 */
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Activation complete, claiming clients');
                return self.clients.claim();
            })
    );
});

/**
 * Fetch event - serve from cache, fallback to network
 * WHY: Provide offline support while keeping data fresh
 * COMPLEXITY: O(1) per request - cache lookup
 * 
 * Strategy: Stale-while-revalidate for static assets
 *           Network-first for API calls
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Handle API requests with network-first strategy
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirstStrategy(request));
        return;
    }
    
    // Handle static assets with cache-first strategy
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirstStrategy(request));
        return;
    }
    
    // Handle HTML pages with cache-first, fallback to network
    event.respondWith(cacheFirstStrategy(request));
});

/**
 * Cache-first strategy
 * WHY: Fast response for static assets that rarely change
 * @param {Request} request - The fetch request
 * @returns {Promise<Response>} Cached or network response
 */
async function cacheFirstStrategy(request) {
    try {
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            console.log('[SW] Serving from cache:', request.url);
            return cachedResponse;
        }
        
        // Not in cache, fetch from network
        console.log('[SW] Fetching from network:', request.url);
        const networkResponse = await fetch(request);
        
        // Cache the new response
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        console.error('[SW] Cache-first failed:', error);
        return new Response('Offline - Resource not available', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

/**
 * Network-first strategy
 * WHY: Ensure fresh data for API calls, fallback to cache if offline
 * @param {Request} request - The fetch request
 * @returns {Promise<Response>} Network or cached response
 */
async function networkFirstStrategy(request) {
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            console.log('[SW] Serving from network:', request.url);
            // Don't cache API responses by default
            return networkResponse;
        }
        
    } catch (networkError) {
        console.log('[SW] Network failed, trying cache:', request.url);
        
        // Network failed, try cache
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            console.log('[SW] Serving cached API response:', request.url);
            return cachedResponse;
        }
    }
    
    // Neither network nor cache available
    return new Response(JSON.stringify({
        error: 'Offline',
        message: 'You are currently offline. Some features may not work.'
    }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
    });
}

/**
 * Background sync for offline actions
 * WHY: Queue actions when offline, execute when back online
 */
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync triggered:', event.tag);
    
    if (event.tag === 'sync-route-data') {
        event.waitUntil(syncRouteData());
    }
});

/**
 * Sync route data saved while offline
 * @returns {Promise<void>}
 */
async function syncRouteData() {
    // This would sync any data saved while offline
    console.log('[SW] Syncing route data...');
    // Implementation would depend on IndexedDB storage
}

/**
 * Push notification handler
 * WHY: Send route updates and alerts to users
 */
self.addEventListener('push', (event) => {
    console.log('[SW] Push notification received');
    
    const options = {
        body: event.data ? event.data.text() : 'New route update available',
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'view',
                title: 'View Route'
            },
            {
                action: 'dismiss',
                title: 'Dismiss'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('Daily Route Planner', options)
    );
});

/**
 * Notification click handler
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event.action);
    
    event.notification.close();
    
    if (event.action === 'view') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

console.log('[SW] Service Worker loaded');
