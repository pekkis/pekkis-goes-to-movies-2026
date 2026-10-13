/// <reference types="astro/client" />

declare namespace App {
  interface Locals {
    /** Our API client; set per request by the middleware, by tests directly. */
    api: import("./lib/api.ts").Api;
    /** The request's time: which shows have started, start soon or later. Tests fix it. */
    now: Date;
  }
}

// `astro check` normally types .astro imports, but it does not support TypeScript 7 yet;
// tests import pages for the Container API, so declare them for plain `tsc`.
declare module "*.astro" {
  const component: import("astro/runtime/server/index.js").AstroComponentFactory;
  export default component;
}
