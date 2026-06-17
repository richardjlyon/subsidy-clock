#!/usr/bin/env node
/* Deploy-time secret injection (run by Vercel `buildCommand`).
 * Writes site/mapbox-token.js from the MAPBOX_TOKEN env var so the public
 * (domain-restricted) Mapbox token reaches the browser WITHOUT being committed
 * to git. The generated file is git-ignored. Never fails the build: if the env
 * var is missing it writes an empty token and warns (the map page degrades to
 * markers without a basemap rather than breaking the deploy). */
const fs = require('fs');
const path = require('path');

const token = process.env.MAPBOX_TOKEN || '';
const out = path.join(__dirname, '..', 'site', 'mapbox-token.js');
fs.writeFileSync(out, 'window.MAPBOX_TOKEN=' + JSON.stringify(token) + ';\n');
console.log('[inject-mapbox-token] wrote ' + out +
  (token ? ' (token present)' : ' (EMPTY — set MAPBOX_TOKEN in Vercel env)'));
