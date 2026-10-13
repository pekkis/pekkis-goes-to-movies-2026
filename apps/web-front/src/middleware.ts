import { API_URL, INDEXING } from "astro:env/server";
import { defineMiddleware } from "astro:middleware";
import { createApi } from "./lib/api.ts";
import { pageHeaders } from "./lib/headers.ts";

export const onRequest = defineMiddleware(async (context, next) => {
  context.locals.api = createApi(API_URL);
  context.locals.now = new Date();
  const response = await next();
  // A copy: some responses (redirects) have immutable headers.
  const out = new Response(response.body, response);
  pageHeaders(out.headers, { indexing: INDEXING === "on" });
  return out;
});
