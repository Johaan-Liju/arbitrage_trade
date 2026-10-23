import http from 'node:http';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { snapshot, validatePrice } from './domain.js';

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const specs = JSON.parse(read('../data/synthetic/contracts.v1.json'));
const prices = JSON.parse(read('../data/synthetic/prices.json'));
prices.forEach(r => validatePrice(r, specs));
const files = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/style.css': ['style.css', 'text/css'] };
export function createServer() {
  return http.createServer((req, res) => {
    const send = (status, body, type = 'application/json') => {
      res.writeHead(status, { 'Content-Type': `${type}; charset=utf-8`, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'self'; frame-ancestors 'none'; base-uri 'none'" });
      res.end(type === 'application/json' ? JSON.stringify(body) : body);
    };
    if (req.method !== 'GET') return send(405, { error: 'Read-only service' });
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/api/health') return send(200, { status: 'ok', app: 'GoldLens', version: '0.1.0', mode: 'local', datasets: { synthetic: 'ready', real: 'not configured' } });
    if (url.pathname === '/api/snapshot') {
      if ((url.searchParams.get('dataset') ?? 'synthetic') !== 'synthetic') return send(404, { error: 'Real data is not configured; no synthetic fallback' });
      try { return send(200, snapshot(prices, specs, specs[0], url.searchParams.get('asOf') ?? '2026-10-22T16:01:00Z')); }
      catch (error) { return send(400, { error: error.message }); }
    }
    if (Object.hasOwn(files, url.pathname)) { const [file, type] = files[url.pathname]; return send(200, read(`../dist/${file}`), type); }
    send(404, { error: 'Not found' });
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createServer();
  server.listen(Number(process.env.PORT ?? 4310), '127.0.0.1', () => console.log(`GoldLens: http://127.0.0.1:${server.address().port}`));
}
