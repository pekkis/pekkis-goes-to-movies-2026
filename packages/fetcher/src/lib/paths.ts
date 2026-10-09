import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** Repository root; this file lives in packages/fetcher/src/lib. */
export const REPO_ROOT = fileURLToPath(new URL("../../../../", import.meta.url));

/** Fetched data is shared by all packages and lives at the repo root (gitignored). */
export const DATA_DIR = join(REPO_ROOT, "data");
