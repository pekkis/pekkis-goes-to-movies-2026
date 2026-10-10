// Drives status/index.html's own status model: what the published provider metadata
// turns into on the page, with no DOM and no network.
//
// Three blocks are sliced verbatim out of status/index.html between their marker
// comments, the way healthState, venueRows and the background refresh already are: the
// time helpers, healthState itself and statusModel. STALE_H, TZ and LOCALE are the
// page's own constants, read out of the file rather than retyped, so a change to the
// threshold cannot pass here while failing in the browser.
//
// Every scenario is a fixture in the shape `normalise()` produces: counts in `stale`,
// `unverified` and `pending` (healthState's contract) and the ids beside them. The
// sandbox has no fetch on purpose; this file tests the decision, not the reading.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'status', 'index.html'), 'utf8');

function slice(start, end, mustHave) {
  const a = HTML.indexOf(start);
  const b = HTML.indexOf(end);
  if (a === -1 || b === -1 || b < a) {
    console.error(`markers not found in status/index.html: ${start}`);
    process.exit(2);
  }
  const src = HTML.slice(a, b);
  for (const fn of mustHave) {
    if (!new RegExp('function ' + fn + '\\s*\\(').test(src)) {
      console.error('marker block does not contain ' + fn);
      process.exit(2);
    }
  }
  return src;
}

function constant(name) {
  const m = HTML.match(new RegExp('const ' + name + "\\s*=\\s*([^;]+);"));
  if (!m) { console.error('constant not found: ' + name); process.exit(2); }
  return m[1];
}

const TIME = slice('// --- status time: pure, extracted verbatim by tests/status_harness.js ---',
                   '// --- end status time ---', ['dtFmt', 'whenText', 'ageHours', 'agoText']);
const HEALTH = slice('// --- healthState: pure, extracted verbatim by tests/health_state_harness.js ---',
                     '// --- end healthState ---', ['healthState']);
const MODEL = slice('// --- status model: pure, extracted verbatim by tests/status_harness.js ---',
                    '// --- end status model ---', ['statusModel']);

const sandbox = { Intl, Date };
vm.createContext(sandbox);
vm.runInContext(
  `const STALE_H = ${constant('STALE_H')};\n` +
  `const TZ = ${constant('TZ')};\n` +
  `const LOCALE = ${constant('LOCALE')};\n` +
  TIME + '\n' + HEALTH + '\n' + MODEL +
  '\n;globalThis.__model = statusModel; globalThis.__health = healthState;' +
  ' globalThis.__stale = STALE_H;',
  sandbox, { filename: 'statusModel' });

const statusModel = sandbox.__model;
const STALE_H = sandbox.__stale;

// The Finnish strings, read out of the page so a copy change cannot leave this file
// asserting words the page no longer uses. `lang` is what whenText formats with.
function strings(lang) {
  const start = HTML.indexOf(`    ${lang}: {`);
  if (start === -1) { console.error('no copy block for ' + lang); process.exit(2); }
  const end = HTML.indexOf('\n    },', start);
  const body = HTML.slice(start + `    ${lang}: {`.length, end);
  const out = { lang };
  // key:'value' pairs, single-quoted, one language block at a time.
  const re = /(\w+):\s*'((?:[^'\\]|\\.)*)'/g;
  let m;
  while ((m = re.exec(body))) out[m[1]] = m[2].replace(/\\'/g, "'").replace(/\\\\/g, '\\');
  return out;
}

const collate = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const NOW = Date.parse('2026-09-07T09:00:00+03:00');
const iso = hoursAgo => new Date(NOW - hoursAgo * 36e5).toISOString();

// A provider entry as data/providers.json carries it.
const P = (id, label, host) => ({ id, label, host: host || `${id}.fi` });

// A metadata entry in the shape normalise() produces.
function M(opts) {
  const venues = opts.venues || 1;
  return {
    generated: opts.generated || opts.oldest, oldest: opts.oldest,
    status: opts.status || 'ok',
    stale: (opts.staleIds || []).length,
    unverified: (opts.unverifiedIds || []).length,
    pending: (opts.pendingIds || []).length,
    staleIds: opts.staleIds || [], unverifiedIds: opts.unverifiedIds || [],
    pendingIds: opts.pendingIds || [],
    names: opts.names || {}, venues,
    city: venues === 1 ? (opts.city || 'Helsinki') : '',
  };
}

const T = strings('fi');
const run = (providers, meta) => statusModel(providers, meta, NOW, T, collate);
const shape = m => ({
  level: m.level, title: m.title, detail: m.detail, icon: m.icon, count: m.count,
  rows: m.rows.map(r => ({ id: r.id, state: r.state, label: r.label, meta: r.meta,
                           detail: r.detail, host: r.host })),
});

const out = {};

// -- every provider fresh -------------------------------------------------------------
out.healthy = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi'), P('biorex', 'BioRex', 'biorex.fi')],
  { orion: M({ oldest: iso(0.5) }), biorex: M({ oldest: iso(1), venues: 12 }) }));

// -- one single-venue provider past the threshold --------------------------------------
out.one_late = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi'), P('biorex', 'BioRex', 'biorex.fi')],
  { orion: M({ oldest: iso(11) }), biorex: M({ oldest: iso(1), venues: 12 }) }));

// -- a chain past the threshold: described by its oldest venue, never as a whole chain --
out.chain_late = shape(run(
  [P('biorex', 'BioRex', 'biorex.fi')],
  { biorex: M({ oldest: iso(11), venues: 12 }) }));

// -- one venue of a chain kept its previous data ---------------------------------------
out.partial = shape(run(
  [P('biorex', 'BioRex', 'biorex.fi'), P('orion', 'Cinema Orion', 'cinemaorion.fi')],
  { biorex: M({ oldest: iso(2), venues: 12, status: 'partial', staleIds: ['br-vaasa'],
                names: { 'br-vaasa': 'Vaasa' } }),
    orion: M({ oldest: iso(0.5) }) }));

// -- a venue the adapter confirmed empty ------------------------------------------------
out.pending = shape(run(
  [P('kinometso', 'Kino Metso', 'kinoaurora.fi'), P('orion', 'Cinema Orion', 'cinemaorion.fi')],
  { kinometso: M({ oldest: iso(1), venues: 4, pendingIds: ['km-muurame', 'km-tikkakoski'],
                   names: { 'km-muurame': 'Muurame', 'km-tikkakoski': 'Tikkakoski' } }),
    orion: M({ oldest: iso(0.5) }) }));

// -- a venue that has never parsed: partial, never pending -------------------------------
out.unverified = shape(run(
  [P('etiketti', 'eTiketti', 'etiketti.fi')],
  { etiketti: M({ oldest: iso(1), venues: 5, unverifiedIds: ['et-uusi'],
                  names: { 'et-uusi': 'Uusi Kino' } }) }));

// -- the file arrived but its timestamp will not parse ------------------------------------
out.bad_stamp = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi')],
  { orion: M({ oldest: 'not-a-date' }) }));

// -- the file never arrived ---------------------------------------------------------------
out.missing = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi'), P('biorex', 'BioRex', 'biorex.fi')],
  { biorex: M({ oldest: iso(1), venues: 12 }) }));

// -- every request failed -----------------------------------------------------------------
out.all_failed = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi'), P('biorex', 'BioRex', 'biorex.fi')], {}));

// -- providers.json itself failed: nothing to list ----------------------------------------
out.no_providers = shape(run([], {}));

// -- late and partial together: the aggregate must not claim a single delayed venue -------
out.mixed = shape(run(
  [P('orion', 'Cinema Orion', 'cinemaorion.fi'), P('biorex', 'BioRex', 'biorex.fi'),
   P('gilda', 'Gilda', 'gilda.fi')],
  { orion: M({ oldest: iso(11) }),
    biorex: M({ oldest: iso(2), venues: 12, status: 'partial', staleIds: ['br-vaasa'],
                names: { 'br-vaasa': 'Vaasa' } }),
    gilda: M({ oldest: iso(1), venues: 2 }) }));

// -- ordering: affected first, then healthy, each group by name ---------------------------
out.order = run(
  [P('zulu', 'Zulu'), P('alfa', 'Alfa'), P('bravo', 'Bravo'), P('delta', 'Delta')],
  { zulu: M({ oldest: iso(1) }), alfa: M({ oldest: iso(1) }),
    bravo: M({ oldest: iso(11) }), delta: M({ oldest: iso(1), venues: 3,
      status: 'partial', staleIds: ['d1'], names: { d1: 'Yksi' } }) }
).rows.map(r => `${r.id}:${r.state}`);

// -- the threshold itself, from both sides -------------------------------------------------
out.threshold = {
  stale_h: STALE_H,
  just_inside: run([P('orion', 'Cinema Orion')], { orion: M({ oldest: iso(STALE_H - 0.1) }) }).rows[0].state,
  just_outside: run([P('orion', 'Cinema Orion')], { orion: M({ oldest: iso(STALE_H + 0.1) }) }).rows[0].state,
};

// -- the same fixture in every language: no key falls through to Finnish -------------------
out.langs = {};
for (const l of ['fi', 'sv', 'en']) {
  const t = strings(l);
  const m = statusModel([P('orion', 'Cinema Orion', 'cinemaorion.fi')],
                        { orion: M({ oldest: iso(11) }) }, NOW, t, collate);
  out.langs[l] = { title: m.title, label: m.rows[0].label, meta: m.rows[0].meta,
                   detail: m.rows[0].detail, count: m.count };
}

process.stdout.write(JSON.stringify(out));
