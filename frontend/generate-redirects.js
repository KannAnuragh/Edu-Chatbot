const fs = require('fs');
const path = require('path');

// Fallback to localhost if the env var isn't set
const targetUrl = process.env.BACKEND_API_URL || 'http://localhost:8001';

// Format: /api/* <target>/api/:splat 200!
// The '200!' tells Netlify to act as a proxy rewrite rather than a 301 redirect.
const content = `/api/* ${targetUrl}/api/:splat 200!\n/uploads/* ${targetUrl}/uploads/:splat 200!\n`;

const publicDir = path.join(__dirname, 'public');

if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir, { recursive: true });
}

fs.writeFileSync(path.join(publicDir, '_redirects'), content);
console.log(`Generated Netlify _redirects file proxying /api/* and /uploads/* to ${targetUrl}`);
