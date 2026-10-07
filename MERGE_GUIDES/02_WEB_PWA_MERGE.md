# 02 — Browser / PWA merge

## A. Add these two files

- `backend/web/v210.css`
- `backend/web/v210.js`

## B. Edit `backend/web/index.html`

Make sure the `<head>` contains a mobile viewport line. If one already exists, replace it with:

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

Load `v210.css` **after** the existing `styles.css`:

```html
<link rel="stylesheet" href="/web/v210.css?v=2100">
```

Load `v210.js` **after** the existing `app.js`:

```html
<script src="/web/v210.js?v=2100"></script>
```

If your static files are referenced relatively instead of `/web/...`, use:

```html
<link rel="stylesheet" href="v210.css?v=2100">
<script src="v210.js?v=2100"></script>
```

Use the same style as the existing CSS/JS paths in your file.

## C. Update `backend/web/sw.js`

The service worker must not keep serving the V2.9 cached HTML/CSS/JS.

1. Find the current cache name, for example:

```js
const CACHE_NAME = 'lemmiq-v29';
```

Change it to a new value such as:

```js
const CACHE_NAME = 'lemmiq-v210';
```

2. If the service worker has a static asset list, add:

```js
'/web/v210.css?v=2100',
'/web/v210.js?v=2100',
```

Use relative equivalents if your current list uses relative paths.

3. Keep existing old-cache deletion in the `activate` event. If there is none, add:

```js
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});
```

## D. What the additive browser patch does automatically

After `v210.js` loads it will:

- find the current five-tab bottom navigation and append **More** as tab 6
- open a More sheet with the required secondary areas
- hide the old `Profile, Trust, Business & Settings` Q-sheet link
- make the floating Q button glassy/transparent
- apply mobile safe-area padding
- make Q Economy tabs scrollable
- detect/tag Q Predict category rails, market cards and page layout for mobile responsiveness
- intercept `Q · Analyse this market` and call `/v210/q-predict/analyse`
- make likely chat photos tappable and open them full-screen with zoom/pan
- reduce large image-bubble padding where it can safely identify the chat-photo wrapper

## E. More routes
The patch first tries to click your existing V2.9 hidden/menu destinations, which preserves your current routing.

If an item does not route correctly, update the `moreDestinations` object near the top/middle of `v210.js` with the exact hash/route your app already uses.

## F. Browser/PWA test sizes
Test Chrome and installed PWA at:

- 320 px
- 360 px
- 375 px
- 390 px
- 412 px
- 430 px

Specifically check:

- no giant empty right side on Q Predict
- no page-level horizontal scrolling
- Q Predict cards readable at one card per row on phones
- all category chips reachable
- all Q Economy tabs reachable
- bottom nav shows six items
- Q button does not cover the bottom nav
- last page content is not hidden behind nav
