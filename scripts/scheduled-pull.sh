#!/bin/bash
# The home server's scheduled pull (pgtm-pull.timer, docs/deploy.md): update the checkout,
# pull every provider under Xvfb (Finnkino's token step needs a visible Chrome), then push to
# production. The push runs even when some providers failed: ingest logs their venues as
# failed checks (pull-status.jsonl) and leaves their screenings as they were.
#
# Output goes to the journal (journalctl -u pgtm-pull) and to ~/logs/pull-<time>.log, kept
# for 60 days. The last line sums the run up: `result: ok`, `result: degraded …` (some
# providers failed, the rest was pushed) or `result: failed …`; only failed exits non-zero.
set -uo pipefail

export PNPM_HOME="$HOME/.local/share/pnpm"
export PATH="$PNPM_HOME:$PATH"
cd "$(dirname "$0")/.."

logs="$HOME/logs"
mkdir -p "$logs"
log="$logs/pull-$(date -u +%Y-%m-%dT%H%MZ).log"
exec > >(tee "$log") 2>&1
find "$logs" -name 'pull-*.log' -mtime +60 -delete

echo "== update: $(date -u +%FT%TZ)"
# A failed update keeps the code we have: an old pull beats no pull.
git pull --ff-only -q || echo "update failed: pulling with $(git rev-parse --short HEAD)"
git log --oneline -1
pnpm install --frozen-lockfile --reporter=silent || echo "install failed"

echo "== pull: $(date -u +%FT%TZ)"
out=$(mktemp)
xvfb-run -a pnpm pull 2>&1 | tee "$out"
pull=${PIPESTATUS[0]}
pulled=$(grep -oE 'pulled [0-9]+ of [0-9]+ providers' "$out" | tail -1)
rm -f "$out"

echo "== push: $(date -u +%FT%TZ)"
if [[ $pulled =~ ^pulled\ 0\  || -z $pulled ]]; then
  echo "nothing new to push"
  echo "result: failed (pull: ${pulled:-no summary}, exit $pull)"
  exit 1
fi
pnpm data:push
push=$?

echo "== done: $(date -u +%FT%TZ)"
if ((push != 0)); then
  echo "result: failed (push exit $push; $pulled)"
  exit 1
fi
if ((pull != 0)); then
  echo "result: degraded ($pulled; see FAILED above)"
  exit 0
fi
echo "result: ok ($pulled)"
