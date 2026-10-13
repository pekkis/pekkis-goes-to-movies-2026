/**
 * Temporal everywhere: native in Node 26 and current Chrome and Firefox; this installs
 * temporal-polyfill (about 20 kB gzipped) only where it's missing (Safari, for now).
 * Import it first in any module that runs Temporal code in the browser.
 */
import "temporal-polyfill/global";
