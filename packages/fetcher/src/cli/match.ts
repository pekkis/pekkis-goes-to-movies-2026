import { parseArgs } from "node:util";
import { loadEnv } from "../lib/env.ts";
import { DATA_DIR } from "../lib/paths.ts";
import { runMatching } from "../matching/run.ts";

const { values } = parseArgs({
  options: { out: { type: "string", default: DATA_DIR } },
});

await runMatching(values.out, loadEnv());
