// Drives the real sw.js fetch handler with stubbed Cache/fetch and reports what it
// stored. Run by tests/test_sw_cache.py; prints one JSON line.
//
// The service worker cannot be exercised in a browser here (the harness browser blocks
// registration), and the behaviour under test is a decision this file makes -- "was
// r.ok true before put" -- not something the Cache API does on its own. So a stub is the
// right instrument: it records the calls the code chose to make.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SW = path.join(__dirname, '..', 'sw.js');
const ORIGIN = 'https://leffavuoro.fi';

function response(status, body) {
  const r = {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: () => null },
    clone() { return Object.assign({}, r); },
    body: body || '',
  };
  return r;
}

function run(cases) {
  const listeners = {};
  const stored = [];           // every url the code chose to cache
  const extended = [];         // every promise the code passed to e.waitUntil
  const posted = [];           // every message the code sent to a window client
  let cached = new Map();      // what caches.match will answer with

  // put() settles on a macrotask, not inline: a real Cache write is asynchronous work
  // that outlives the response, and an inline stub would let a fire-and-forget write
  // "finish" before the harness could model the worker being terminated.
  // `putRejects` models a full storage quota: the write is refused, as a real
  // Cache.put rejects with QuotaExceededError.
  const failPut = cases.some(c => c.putRejects);
  const cacheObj = {
    put: (req, res) => new Promise((resolve, reject) => setImmediate(() => {
      if (failPut) return reject(new Error('QuotaExceededError'));
      stored.push(String(req.url || req));
      resolve();
    })),
  };
  const sandbox = {
    self: {
      addEventListener: (name, fn) => { listeners[name] = fn; },
      skipWaiting: () => {},
      clients: { matchAll: async () => [{ postMessage: m => posted.push(m) }], claim: async () => {} },
    },
    caches: {
      open: async () => cacheObj,
      keys: async () => [],
      delete: async () => true,
      match: async (req) => cached.get(String(req.url || req)),
    },
    clients: { claim: async () => {} },
    location: { origin: ORIGIN },
    URL,
    Request: function (input, init) {
      const url = typeof input === 'string' ? input : input.url;
      return { url, method: (init && init.method) || (input && input.method) || 'GET' };
    },
    fetch: null,               // set per case
    console,
  };
  sandbox.self.location = sandbox.location;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(SW, 'utf8'), sandbox, { filename: 'sw.js' });

  const out = [];
  for (const c of cases) {
    stored.length = 0;
    extended.length = 0;
    posted.length = 0;
    cached = new Map(c.cached || []);
    // 'offline' is a fetch that rejects, which is what a dropped connection gives.
    sandbox.fetch = async () => {
      if (c.status === 'offline') throw new TypeError('Failed to fetch');
      return response(c.status);
    };

    let responded = null;
    // The spec's activity rule, not MDN's summary of it: waitUntil() throws
    // InvalidStateError only when the event is not active, and the event is active
    // while its dispatch flag is set OR its pending promises count is above zero --
    // respondWith(r) adds r to those promises "as if event.waitUntil(r) is called".
    // So a waitUntil inside a .then of the respondWith promise is legal, and one
    // fired after every extension has settled is the bug this models.
    const event = {
      request: { url: c.url, method: c.method || 'GET' },
      _dispatching: true,
      _pending: 0,
      _extend(p) {
        event._pending++;
        Promise.resolve(p).catch(() => {}).finally(() => { event._pending--; });
      },
      respondWith(p) { responded = p; event._extend(p); },
      waitUntil(p) {
        if (!event._dispatching && event._pending === 0) {
          throw new DOMException(
            `waitUntil() on an inactive event (${c.name}): no extend-lifetime ` +
            'promise is pending and dispatch has finished', 'InvalidStateError');
        }
        extended.push(p);
        event._extend(p);
      },
    };
    listeners.fetch(event);
    event._dispatching = false;
    out.push({ name: c.name, responded: responded !== null, promise: responded });
  }
  return { out, stored, extended, posted, cacheObj };
}

(async () => {
  const results = [];
  const cases = [
    { name: 'poster_404', url: `${ORIGIN}/data/posters/missing.jpg`, status: 404 },
    { name: 'poster_500', url: `${ORIGIN}/data/posters/broken.jpg`, status: 500 },
    { name: 'poster_200', url: `${ORIGIN}/data/posters/good.jpg`, status: 200 },
    { name: 'page_500', url: `${ORIGIN}/index.html`, status: 500 },
    { name: 'page_200', url: `${ORIGIN}/index.html`, status: 200 },
    { name: 'data_404', url: `${ORIGIN}/data/areas.json`, status: 404 },
    { name: 'data_200', url: `${ORIGIN}/data/areas.json`, status: 200 },
    { name: 'cross_origin', url: 'https://example.test/x.js', status: 200 },
    { name: 'not_get', url: `${ORIGIN}/index.html`, status: 200, method: 'POST' },
    // The background check behind a cached schedule file, and a first fetch with none.
    { name: 'check_cached_200', url: `${ORIGIN}/data/area-x.json`, status: 200,
      cached: [[`${ORIGIN}/data/area-x.json`, response(200, 'old')]] },
    { name: 'check_cached_500', url: `${ORIGIN}/data/area-x.json`, status: 500,
      cached: [[`${ORIGIN}/data/area-x.json`, response(200, 'old')]] },
    { name: 'check_cached_offline', url: `${ORIGIN}/data/area-x.json`, status: 'offline',
      cached: [[`${ORIGIN}/data/area-x.json`, response(200, 'old')]] },
    { name: 'check_first_200', url: `${ORIGIN}/data/area-x.json`, status: 200 },
    { name: 'check_first_offline', url: `${ORIGIN}/data/area-x.json`, status: 'offline' },
    // A write the storage refuses: the answer still stands.
    { name: 'put_fails_first', url: `${ORIGIN}/data/area-x.json`, status: 200, putRejects: true },
    { name: 'put_fails_cached', url: `${ORIGIN}/data/area-x.json`, status: 200, putRejects: true,
      cached: [[`${ORIGIN}/data/area-x.json`, response(200, 'old')]] },
  ];

  for (const c of cases) {
    const { out, stored, extended, posted } = run([c]);
    const r = out[0];
    let body = null, rejected = false;
    if (r.promise) {
      try { const res = await r.promise; body = res && res.body; }
      catch (e) { rejected = true; /* the caller still sees it */ }
    }
    // The worker-termination model: once the response has settled, the browser keeps
    // the worker alive only for promises passed to e.waitUntil. Whatever `stored`
    // holds after these settle is what a real worker is guaranteed to have written;
    // a put() the code fired and forgot is still pending here and is counted lost.
    await Promise.allSettled(extended);
    results.push({ name: c.name, intercepted: r.responded, stored: stored.slice(),
                   posted: posted.slice(), body, rejected });
  }
  process.stdout.write(JSON.stringify(results));
})();
