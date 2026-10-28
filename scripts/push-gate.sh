#!/bin/sh
# Forced command for the home server's push key (pgtm-push@pekkis-himaserver), set with
# `restrict` in ~/.ssh/authorized_keys. The key may run only the three steps of
# `pnpm data:push` (scripts/push-data.ts): make the folder, rsync into it, ingest.
# Every attempt is logged: journalctl -t pgtm-push-gate
set -eu
cmd="${SSH_ORIGINAL_COMMAND:-}"
logger -t pgtm-push-gate -- "$cmd"
case "$cmd" in
  "mkdir -p '/srv/pgtm/data/normalized'")
    exec mkdir -p /srv/pgtm/data/normalized
    ;;
  "cd '/srv/pgtm' && docker compose --profile ingest run --rm ingest")
    cd /srv/pgtm
    exec docker compose --profile ingest run --rm ingest
    ;;
esac
# The receiving side of `rsync -az --delete data/normalized/ host:/srv/pgtm/data/normalized/`.
# Its flag letters vary with the rsync version, but never --sender (reading) or another path.
if printf '%s' "$cmd" | grep -Eqx 'rsync --server -[A-Za-z.]+ --delete \. /srv/pgtm/data/normalized/'; then
  set -f
  # Validated above: split into words on purpose, with globbing off.
  exec $cmd
fi
logger -t pgtm-push-gate -- "refused"
echo "pgtm-push-gate: not allowed" >&2
exit 1
