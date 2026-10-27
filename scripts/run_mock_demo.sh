#!/bin/sh
set -eu

# Every invocation gets new append-only demo stores. Published records from an
# earlier presentation are neither deleted nor overwritten.
SHH_DEMO_DIR=$(mktemp -d "${TMPDIR:-/tmp}/shh-demo.XXXXXX")
export SHH_EXTRACTOR_MODE=mock
export SHH_RESIDENT_NOTICE_STORE_PATH="$SHH_DEMO_DIR/resident_notices.json"
export SHH_RECOMMENDATION_SNAPSHOT_STORE_PATH="$SHH_DEMO_DIR/recommendation_snapshots.json"

cleanup_demo_processes() {
  kill "$SHH_BACKEND_PID" "$SHH_FRONTEND_PID" 2>/dev/null || true
}
trap cleanup_demo_processes EXIT INT TERM

echo "Mock demo store: $SHH_DEMO_DIR"
echo "No API key is used. Stop with Ctrl-C; the isolated records are retained."

(cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
SHH_BACKEND_PID=$!
npm run dev -- --host 127.0.0.1 &
SHH_FRONTEND_PID=$!
wait
