import { z } from "zod";

/**
 * Environment variables, validated. `.env` at the repo root is loaded by Node itself
 * (`--env-file-if-exists=../../.env` in the package scripts).
 */
const Env = z.object({
  DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/, error: "must be a postgres:// URL" }),
  /** Integration tests only; a separate database so tests never touch development data. */
  TEST_DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/ }).optional(),
  /** URL or email for the User-Agent of outgoing requests (geocoding). Optional. */
  CONTACT: z.string().min(1).optional(),
  /** API server. HOST is 0.0.0.0 inside the container, localhost otherwise. */
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  HOST: z.string().default("127.0.0.1"),
  /**
   * Turns on the MCP endpoint at `/mcp/{MCP_TOKEN}` for chatbots. A long random string:
   * it keeps the endpoint unlisted while it is for internal testing. Unset: no MCP.
   */
  MCP_TOKEN: z
    .string()
    .regex(/^[A-Za-z0-9_-]{24,}$/, "24+ characters of A-Z, a-z, 0-9, _ or -")
    .optional(),
  /** "*" or comma-separated origins allowed to call the API from browsers. */
  CORS_ORIGINS: z
    .string()
    .default("*")
    .transform((v) =>
      v.trim() === "*"
        ? "*"
        : v
            .split(",")
            .map((o) => o.trim())
            .filter(Boolean),
    ),
});
export type Env = z.infer<typeof Env>;

export const loadEnv = (source: NodeJS.ProcessEnv = process.env): Env => {
  // An empty value is unset: Compose passes `MCP_TOKEN: ${MCP_TOKEN:-}` as "" when the
  // deployment has no token, which must mean "no MCP", not an invalid token.
  const set = Object.fromEntries(Object.entries(source).filter(([, v]) => v !== ""));
  const result = Env.safeParse(set);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `  ${i.path.join(".")}: ${i.message}`);
    throw new Error(`Invalid environment (check .env):\n${problems.join("\n")}`);
  }
  return result.data;
};
