import { z } from "zod";

/**
 * Environment variables, validated. `.env` at the repo root is loaded by Node itself
 * (`--env-file-if-exists=../../.env` in the package scripts).
 */
const Env = z.object({
  DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/, error: "must be a postgres:// URL" }),
  /** Integration tests only; a separate database so tests never touch development data. */
  TEST_DATABASE_URL: z.url({ protocol: /^postgres(ql)?$/ }).optional(),
  /** API server. HOST is 0.0.0.0 inside the container, localhost otherwise. */
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  HOST: z.string().default("127.0.0.1"),
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
  const result = Env.safeParse(source);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `  ${i.path.join(".")}: ${i.message}`);
    throw new Error(`Invalid environment (check .env):\n${problems.join("\n")}`);
  }
  return result.data;
};
