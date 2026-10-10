// Drives index.html's venueFilesFrom(), sliced verbatim between its markers, over the
// shapes the two combined venue files can arrive in. Run by tests/test_venuelists_client.py;
// prints one JSON line.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '  // --- venue lists: pure, extracted verbatim by tests/venuelists_harness.js ---';
const END = '  // --- end venue lists ---';
const a = HTML.indexOf(START), b = HTML.indexOf(END);
if (a < 0 || b < a) { console.error('venue lists markers not found'); process.exit(2); }
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(HTML.slice(a, b) + '\nglobalThis.venueFilesFrom = venueFilesFrom;', sandbox);
const f = sandbox.venueFilesFrom;

const file = (gen, n = 1) => ({ generated: gen, venues: Array.from({ length: n }, (_, i) => ({ id: 'v' + i, name: 'V' })) });
const ids = ['regina', 'engel', 'biorex', 'kinola'];
const local = { half: 'local', providers: { regina: file('2026-09-26T06:00'), engel: file('2026-09-26T06:00') } };
const cloud = { half: 'cloud', providers: { biorex: file('2026-09-26T07:00'), kinola: file('2026-09-26T07:00') } };
const run = (bundles) => { const r = f(ids, bundles); return { files: Object.keys(r.files).sort(), missing: r.missing }; };

const out = {
  both: run([local, cloud]),
  local_missing: run([null, cloud]),
  cloud_missing: run([local, null]),
  both_missing: run([null, null]),
  not_an_object: run(['nope', 42]),
  providers_an_array: run([{ half: 'local', providers: [] }, cloud]),
  entry_without_venues: run([{ providers: { regina: { generated: 'x' }, engel: file('g') } }, cloud]),
  entry_venues_not_array: run([{ providers: { regina: { venues: {} } } }, cloud]),
  new_provider_in_neither: run([{ providers: { regina: file('g') } }, { providers: { biorex: file('g') } }]),
  order: f(['engel', 'kinola', 'regina', 'biorex'], [null, cloud]).missing,
  moved_half_newest_wins: f(['regina'], [
    { providers: { regina: file('2026-09-26T06:00', 1) } },
    { providers: { regina: file('2026-09-26T09:00', 2) } }]).files.regina.venues.length,
  moved_half_newest_wins_either_order: f(['regina'], [
    { providers: { regina: file('2026-09-26T09:00', 2) } },
    { providers: { regina: file('2026-09-26T06:00', 1) } }]).files.regina.venues.length,
  verbatim: f(['regina'], [local]).files.regina === local.providers.regina,
};
process.stdout.write(JSON.stringify(out));
