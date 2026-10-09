import { z } from "zod";

/**
 * Environment variables, validated. `.env` is loaded by Node itself
 * (`--env-file-if-exists=.env` in the package scripts); no dotenv needed.
 */
const Env = z.object({
  /** TMDB v4 read access token, used as a Bearer token. */
  TMDB_APIKEY: z.string().startsWith("eyJ", "must be a TMDB v4 read access token (eyJ…)"),
  /** URL or email put into the User-Agent so that cinemas can reach whoever runs the fetcher. */
  CONTACT: z.string().min(1).optional(),
});
export type Env = z.infer<typeof Env>;

/** Validates on call, so modules that never need the environment can be imported freely. */
export const loadEnv = (source: NodeJS.ProcessEnv = process.env): Env => {
  const result = Env.safeParse(source);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `  ${i.path.join(".")}: ${i.message}`);
    throw new Error(`Invalid environment (check .env):\n${problems.join("\n")}`);
  }
  return result.data;
};
