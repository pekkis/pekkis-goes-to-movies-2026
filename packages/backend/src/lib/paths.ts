import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** Repository root; this file lives in packages/backend/src/lib. */
export const REPO_ROOT = fileURLToPath(new URL("../../../../", import.meta.url));

/** The fetcher's output, shared at the repo root (gitignored). */
export const NORMALIZED_DIR = join(REPO_ROOT, "data", "normalized");
