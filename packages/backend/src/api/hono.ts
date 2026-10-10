import { OpenAPIHono } from "@hono/zod-openapi";

/** Every router uses this: validation failures become `400 { error, issues }`. */
export const router = () =>
  new OpenAPIHono({
    defaultHook: (result, c) => {
      if (!result.success) {
        return c.json({ error: "invalid request", issues: result.error.issues }, 400);
      }
      return undefined;
    },
  });
