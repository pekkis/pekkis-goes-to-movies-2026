import { execFileSync } from "node:child_process";

/**
 * Ships the day's pull to the server and loads it there:
 *
 *   pnpm pull && pnpm data:push
 *
 * rsyncs data/normalized/ to `{DEPLOY_TARGET}/data/normalized/` over SSH, then runs the
 * stack's one-shot ingest on the server (`docker compose --profile ingest run --rm ingest`).
 * DEPLOY_TARGET is `user@host:/path/to/checkout`, set in .env (never in the repo).
 */
const target = process.env["DEPLOY_TARGET"];
const match = target?.match(/^([^:\s]+):(\/[^'\s]+)$/);
if (!match) {
  console.error("Set DEPLOY_TARGET in .env to user@host:/absolute/path/of/the/server/checkout");
  process.exit(1);
}
const [, host, path] = match as unknown as [string, string, string];

const run = (cmd: string, args: string[]) => {
  console.log(`$ ${cmd} ${args.join(" ")}`);
  execFileSync(cmd, args, { stdio: "inherit" });
};

// rsync creates only the last folder: a fresh checkout has no data/ yet (2026-10-24).
run("ssh", [host, `mkdir -p '${path}/data/normalized'`]);
run("rsync", ["-az", "--delete", "data/normalized/", `${host}:${path}/data/normalized/`]);
run("ssh", [host, `cd '${path}' && docker compose --profile ingest run --rm ingest`]);
