# Vendored libraries

- `maplibre-gl.js` / `maplibre-gl.css` — MapLibre GL JS **v5.24.0** (BSD-3-Clause,
  see `maplibre-gl-LICENSE.txt`). The site has no build step, so the dist files are
  committed as-is.

Re-vendor (version bump or security fix):

    curl -sO https://unpkg.com/maplibre-gl@<version>/dist/maplibre-gl.js
    curl -sO https://unpkg.com/maplibre-gl@<version>/dist/maplibre-gl.css
    curl -s  https://unpkg.com/maplibre-gl@<version>/LICENSE.txt -o maplibre-gl-LICENSE.txt

then update the version above and re-test /map. These files are served with a
long max-age (vercel.json), so a version bump should also bump the `?v=` query
on the script/link tags in site/map.html to bust caches.
