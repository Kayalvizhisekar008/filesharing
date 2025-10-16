// PDF.js Service Worker
self.addEventListener('install', function(event) {
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', function(event) {
    if (event.request.url.includes('standard_fonts') || event.request.url.includes('cmaps')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    if (!response.ok) {
                        // If font fetch fails, return a fallback font or handle the error
                        if (event.request.url.includes('FoxitSymbol.pfb')) {
                            return fetch('/static/fonts/FoxitSymbol.pfb');
                        }
                    }
                    return response;
                })
                .catch(() => {
                    // Handle network errors or CORS issues
                    if (event.request.url.includes('FoxitSymbol.pfb')) {
                        return fetch('/static/fonts/FoxitSymbol.pfb');
                    }
                    return new Response('Font not available', { status: 404 });
                })
        );
    }
});