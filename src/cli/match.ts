import { parseArgs } from "node:util";
import { loadEnv } from "../lib/env.ts";
import { runMatching } from "../matching/run.ts";

const { values } = parseArgs({
  options: { out: { type: "string", default: "data" } },
});

await runMatching(values.out, loadEnv());
