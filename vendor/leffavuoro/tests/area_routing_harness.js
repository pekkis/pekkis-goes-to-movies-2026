// Runs index.html's own startupArea(), areaParamAfterSelect(), startupLang() and
// langParamAfterSelect() against tables of deep-link, favourite, stored-area and
// stored-language combinations. Driven by tests/test_area_routing.py; prints one JSON
// line.
//
// Sliced verbatim out of index.html between its marker comments and evaluated on its own,
// the way healthState, venueRows and priceLabel are. Both functions are pure -- the
// routing one takes the deep-link string, the prefs object and a validity predicate; the
// URL one takes a query string and an id -- so neither needs a DOM, and the real code
// runs rather than a copy of it.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const START = '// --- area routing: pure, extracted verbatim by tests/area_routing_harness.js ---';
const END = '// --- end area routing ---';

const a = HTML.indexOf(START);
const b = HTML.indexOf(END);
if (a === -1 || b === -1 || b < a) {
  console.error('area routing markers not found in index.html');
  process.exit(2);
}
const source = HTML.slice(a, b);
for (const fn of ['startupArea', 'areaParamAfterSelect', 'startupLang', 'langParamAfterSelect', 'homeCityHref',
                  'homeCityPage']) {
  if (!new RegExp('function ' + fn + '\\s*\\(').test(source)) {
    console.error('marker block does not contain ' + fn);
    process.exit(2);
  }
}

const sandbox = { URLSearchParams };
vm.createContext(sandbox);
vm.runInContext(source + '\n;globalThis.__s = startupArea; globalThis.__p = areaParamAfterSelect;'
                + 'globalThis.__l = startupLang; globalThis.__q = langParamAfterSelect;'
                + 'globalThis.__h = homeCityHref; globalThis.__g = homeCityPage;',
                sandbox, { filename: 'areaRouting' });
const startupArea = sandbox.__s;
const areaParamAfterSelect = sandbox.__p;
const startupLang = sandbox.__l;
const langParamAfterSelect = sandbox.__q;
const homeCityHref = sandbox.__h;
const homeCityPage = sandbox.__g;

// The venues this fixture knows about. `known` is the same shape the app builds: a venue
// id, or a `city:` id for a city with more than one venue.
const VENUES = ['fi-cine-atlas', 'sk-tapio', 'sk-maxim', 'br-redi'];
const MULTI_CITIES = ['Helsinki'];
const known = id => !!id && (VENUES.includes(id) ||
  (id.startsWith('city:') && MULTI_CITIES.includes(id.slice(5))));

// [name, deep, prefs]
const CASES = [
  // -- the reported defect ------------------------------------------------------------
  ['fav_only_no_deep',        '',              { fav: 'fi-cine-atlas', area: 'sk-maxim' }],
  ['fav_and_deep',            'sk-tapio',      { fav: 'fi-cine-atlas', area: 'sk-maxim' }],
  // the second load of the same tab: the param is still there, so it decides again
  ['reload_with_deep',        'sk-tapio',      { fav: 'fi-cine-atlas', area: 'sk-tapio' }],
  // -- the ordinary restore -------------------------------------------------------------
  ['stored_only',             '',              { fav: '', area: 'sk-maxim' }],
  ['nothing_at_all',          '',              { fav: '', area: '' }],
  ['fav_beats_stored',        '',              { fav: 'br-redi', area: 'sk-maxim' }],
  // -- cities ----------------------------------------------------------------------------
  ['city_deep',               'city:Helsinki', { fav: 'fi-cine-atlas', area: '' }],
  ['city_fav_no_deep',        '',              { fav: 'city:Helsinki', area: 'sk-maxim' }],
  ['city_deep_single_venue',  'city:Tapiola',  { fav: 'fi-cine-atlas', area: '' }],
  // -- links that name nothing -----------------------------------------------------------
  ['unknown_deep',            'sk-gone',       { fav: 'fi-cine-atlas', area: 'sk-maxim' }],
  ['unknown_deep_no_fav',     'sk-gone',       { fav: '', area: 'sk-maxim' }],
  ['unknown_deep_nothing',    'sk-gone',       { fav: '', area: '' }],
  ['empty_deep',              '',              { fav: 'fi-cine-atlas', area: '' }],
  ['stale_stored',            '',              { fav: '', area: 'sk-gone' }],
];

const routing = {};
for (const [name, deep, pr] of CASES) routing[name] = startupArea(deep, pr, known);

// [name, search, id]
const URL_CASES = [
  ['deep_then_pick',        '?area=sk-tapio',           'sk-maxim'],
  ['deep_then_pick_city',   '?area=sk-tapio',           'city:Helsinki'],
  ['deep_then_pick_same',   '?area=sk-tapio',           'sk-tapio'],
  ['deep_with_other_params','?area=sk-tapio&lang=en',   'sk-maxim'],
  ['no_param',              '',                          'sk-maxim'],
  ['other_params_only',     '?lang=en',                  'sk-maxim'],
  ['empty_area_param',      '?area=',                    'sk-maxim'],
];
const urls = {};
for (const [name, search, id] of URL_CASES) urls[name] = areaParamAfterSelect(search, id);

// The language half of the deep link. `LANGS` is passed in the way the app passes its own
// constant, so the harness does not have to slice a second block.
const LANGS = ['fi', 'sv', 'en'];
// [name, ?lang= value, stored prefs.lang]
const LANG_CASES = [
  // -- the case the generated English pages need ---------------------------------------
  ['en_link_nothing_stored',  'en', undefined],
  ['en_link_fi_stored',       'en', 'fi'],
  ['fi_link_en_stored',       'fi', 'en'],
  ['sv_link_fi_stored',       'sv', 'fi'],
  ['en_link_bad_stored',      'en', 'de'],
  // -- no parameter: the stored restore as before -------------------------------------
  ['no_param_en_stored',      '',   'en'],
  ['no_param_nothing_stored', '',   undefined],
  ['no_param_bad_stored',     '',   'de'],
  // -- values the app does not have -----------------------------------------------------
  ['bad_param_en_stored',     'xx', 'en'],
  ['bad_param_nothing_stored','xx', undefined],
  ['upper_case_param',        'EN', 'fi'],
];
const lang = {};
for (const [name, param, stored] of LANG_CASES) lang[name] = startupLang(param, stored, LANGS);

// [name, search, language the reader just picked]
const LANG_URL_CASES = [
  ['deep_lang_then_toggle',  '?area=sk-tapio&lang=en', 'fi'],
  ['lang_only_then_toggle',  '?lang=en',               'sv'],
  ['area_only_then_toggle',  '?area=sk-tapio',         'en'],
  ['plain_visit_then_toggle','',                        'en'],
  ['empty_lang_param',       '?lang=',                  'en'],
];
const langUrls = {};
for (const [name, search, l] of LANG_URL_CASES) langUrls[name] = langParamAfterSelect(search, l);

// Where the chooser's city links point: each language's city page until the venue lists
// name the city's cinemas, then the programme. The page list under the chooser keeps the
// pages.
const homeHrefs = {
  fi: homeCityHref('Jyväskylä', 'jyvaskyla', 'fi'),
  en: homeCityHref('Jyväskylä', 'jyvaskyla', 'en'),
  sv: homeCityHref('Jyväskylä', 'jyvaskyla', 'sv', [], ''),
  multi: homeCityHref('Jyväskylä', 'jyvaskyla', 'en', ['kl-fantasia', 'kl-kinolinna'], ''),
  single: homeCityHref('Jyväskylä', 'jyvaskyla', 'sv', ['kl-fantasia'], ''),
  keepsQuery: homeCityHref('Jyväskylä', 'jyvaskyla', 'sv', ['a', 'b'], '?lang=sv'),
  replacesArea: homeCityHref('Jyväskylä', 'jyvaskyla', 'fi', ['a', 'b'], '?area=nope&lang=en'),
};
const homePages = { fi: homeCityPage('jyvaskyla', 'fi'), sv: homeCityPage('jyvaskyla', 'sv'),
                    en: homeCityPage('jyvaskyla', 'en') };

process.stdout.write(JSON.stringify({ routing, urls, lang, langUrls, homeHrefs, homePages }));
