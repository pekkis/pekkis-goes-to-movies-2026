// Drives the real sw.js `activate` handler with a stubbed Cache Storage and reports what
// the new cache holds and which caches survived. Run by tests/test_sw_cache.py; prints
// one JSON line.
//
// A new worker activates with an empty cache of its own, because the navigation that
// discovered the update was served by the old worker and network-first. What activate
// does with the previous version's entries before deleting it is therefore the whole of
// whether the next offline launch works, and it is this file's decision rather than
// anything the Cache API does, so a recording stub is the right instrument.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SW = path.join(__dirname, '..', 'sw.js');
// A watchdog, not politeness: a harness that hangs or throws inside the sandbox exits
// non-zero with no JSON, and a mutation that breaks activate would then look like a
// broken harness rather than a red test.
const WATCHDOG = setTimeout(() => {
  process.stdout.write(JSON.stringify({ error: 'activate did not settle' }));
  process.exit(0);
}, 20000);

// Tagged with the cache it came from, so "kept what this version already has" is an
// assertion about which copy survived and not only about the url being present.
function response(url, tag) {
  return { url, tag, ok: true, status: 200, clone() { return this; } };
}

/** A Cache Storage holding {cacheName: [url, ...]}. -> what activate left behind. */
async function run(initial, currentName) {
  const store = new Map();                 // name -> Map(url -> response)
  for (const [name, urls] of Object.entries(initial)) {
    store.set(name, new Map(urls.map(u => [u, response(u, name)])));
  }
  const deleted = [];
  const cacheFor = name => ({
    async keys() { return [...(store.get(name) || new Map()).keys()].map(u => ({ url: u })); },
    async match(req) { return (store.get(name) || new Map()).get(String(req.url || req)) || undefined; },
    async put(req, res) { store.get(name).set(String(req.url || req), res); },
  });

  const listeners = {};
  const sandbox = {
    self: {
      addEventListener: (n, fn) => { listeners[n] = fn; },
      skipWaiting: () => {},
      clients: { claim: async () => {}, matchAll: async () => [] },
    },
    caches: {
      async keys() { return [...store.keys()]; },
      async open(name) { if (!store.has(name)) store.set(name, new Map()); return cacheFor(name); },
      async delete(name) { deleted.push(name); return store.delete(name); },
      async match(req) {
        for (const name of store.keys()) {
          const hit = store.get(name).get(String(req.url || req));
          if (hit) return hit;
        }
        return undefined;
      },
    },
    clients: { claim: async () => {}, matchAll: async () => [] },
    fetch: async () => { throw new Error('offline'); },
    location: { origin: 'https://leffavuoro.fi' },
    URL, Request, Promise, setTimeout, console,
  };
  sandbox.self.caches = sandbox.caches;
  vm.createContext(sandbox);
  let src = fs.readFileSync(SW, 'utf8');
  // The one edit: the harness decides which version is activating, so the same fixture
  // can model a one-version and a two-version jump.
  src = src.replace(/^const CACHE = '[^']+';$/m, `const CACHE = '${currentName}';`);
  vm.runInContext(src, sandbox);

  let waited = null;
  await listeners.activate({ waitUntil: p => { waited = p; } });
  await waited;
  return {
    surviving: [...store.keys()].sort(),
    deleted: deleted.sort(),
    current: [...(store.get(currentName) || new Map()).keys()].sort(),
    from: Object.fromEntries([...(store.get(currentName) || new Map()).entries()]
      .map(([u, r]) => [u, r.tag])),
  };
}

(async () => {
  const P = 'https://leffavuoro.fi';
  const shell = `${P}/`;
  const data = `${P}/data/area-1111.json`;
  const poster = `${P}/data/posters/a.jpg`;
  const results = {};

  results.migrates_the_previous_version = await run(
    { 'leffavuoro-v188': [shell, data, poster] }, 'leffavuoro-v189');

  results.keeps_what_this_version_already_has = await run(
    { 'leffavuoro-v188': [shell, data], 'leffavuoro-v189': [shell] }, 'leffavuoro-v189');

  results.leaves_a_foreign_cache_alone = await run(
    { 'leffavuoro-v188': [data], 'some-other-app': [`${P}/other.json`] }, 'leffavuoro-v189');

  results.two_version_jump_prefers_the_newer = await run(
    { 'leffavuoro-v187': [`${P}/old.json`], 'leffavuoro-v188': [data] }, 'leffavuoro-v189');

  results.nothing_to_migrate = await run({}, 'leffavuoro-v189');

  clearTimeout(WATCHDOG);
  process.stdout.write(JSON.stringify(results));
})().catch(e => {
  clearTimeout(WATCHDOG);
  process.stdout.write(JSON.stringify({ error: String(e && e.message || e) }));
});
