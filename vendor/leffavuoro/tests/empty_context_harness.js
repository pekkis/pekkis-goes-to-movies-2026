// Drives index.html's emptyContextParts() against controlled state.
//
// The block is sliced verbatim out of index.html between its marker comments. What it
// pins: the search as typed (trimmed), the labels of the filters that are on in chip
// order, chain restrictions by their display name in sorted id order, and an empty half
// for each that has nothing, so the renderer can drop the line.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function slice(start, end, name) {
  const a = HTML.indexOf(start);
  const b = HTML.indexOf(end);
  if (a === -1 || b === -1 || b < a) {
    console.error(name + ' markers not found in index.html');
    process.exit(2);
  }
  return HTML.slice(a, b);
}
const SRC = slice('  // --- emptyContext: pure, extracted verbatim by tests/empty_context_harness.js ---',
                  '  // --- end emptyContext ---', 'emptyContext');
if (!/function emptyContextParts\s*\(/.test(SRC)) {
  console.error('marker block does not contain emptyContextParts');
  process.exit(2);
}
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(SRC + '\n;globalThis.__p = emptyContextParts;', sandbox, { filename: 'emptyContext' });
const parts = sandbox.__p;

const T = { flang: 'Suom. puhe', fkids: 'Lapsille', fannis: 'Anniskelu' };
const names = { finnkino: 'Finnkino', biorex: 'BioRex', gilda: 'Gilda' };
const name = (c) => names[c] || c;
const out = {};

out.search_and_two_chips = parts('Autofiktio', { fLang: true, fKids: true, fAnnis: false }, null, T, name);
out.search_only = parts('  Dune  ', { fLang: false, fKids: false, fAnnis: false }, null, T, name);
out.chips_only = parts('', { fLang: false, fKids: false, fAnnis: true }, null, T, name);
out.nothing = parts('', { fLang: false, fKids: false, fAnnis: false }, null, T, name);
out.blank_search = parts('   ', {}, null, T, name);
out.chains = parts('', {}, new Set(['gilda', 'biorex']), T, name);
out.chains_and_chip = parts('x', { fKids: true }, new Set(['finnkino']), T, name);
out.unknown_chain = parts('', {}, new Set(['zzz']), T, name);
out.markup_in_query = parts('<img src=x onerror=alert(1)> $&', {}, null, T, name);
out.many = parts('q', { fLang: true, fKids: true, fAnnis: true }, new Set(['biorex', 'finnkino', 'gilda']), T, name);
process.stdout.write(JSON.stringify(out));
