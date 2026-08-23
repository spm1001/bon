#!/bin/bash
# resena experiment 2: ONE writer, one concurrent reader — do reads fracture?
set -u
T=$(mktemp -d /tmp/resena2-XXXXXX)
cd "$T" && mkdir dolt-data && cd dolt-data
dolt init > /dev/null
dolt sql -q "CREATE DATABASE IF NOT EXISTS repro" > /dev/null
nohup dolt sql-server --port 3308 --host 127.0.0.1 > "$T/server.log" 2>&1 &
SERVER_PID=$!
sleep 3
export BON_DOLT_HOST=127.0.0.1 BON_DOLT_PORT=3308 BON_DOLT_USER=root BON_DOLT_PASSWORD= BON_DOLT_DATABASE=repro

mkdir -p "$T/lane"
cd "$T/lane" && bon init --prefix rep --backend dolt > /dev/null 2>&1
[ -d .bon ] || { echo "INIT FAILED"; kill $SERVER_PID; exit 1; }
for i in $(seq 1 60); do bon new "Seed $i" --why w --what x --done d -q > /dev/null 2>&1; done
echo "seeded 60"
ID=$(bon list --all --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted([o['id'] for o in d.get('outcomes',[])])[0])")

# Reader: raw SQL COUNT in a tight loop while the single writer edits.
python3 - "$T" <<'PY' &
import pymysql, sys, time
T = sys.argv[1]
conn = pymysql.connect(host="127.0.0.1", port=3308, user="root", password="", database="repro", autocommit=True)
cur = conn.cursor()
counts = {}
t0 = time.time()
while time.time() - t0 < 25:
    try:
        cur.execute("SELECT COUNT(*) FROM items WHERE id LIKE 'rep-%'")
        n = cur.fetchone()[0]
        counts[n] = counts.get(n, 0) + 1
    except Exception as e:
        counts[f"ERR:{type(e).__name__}"] = counts.get(f"ERR:{type(e).__name__}", 0) + 1
with open(f"{T}/reader-counts.txt", "w") as f:
    for k, v in sorted(counts.items(), key=str):
        f.write(f"count={k}: seen {v} times\n")
PY
READER=$!

# Single writer, 40 edits
for i in $(seq 1 40); do bon edit "$ID" --title "tick $i" > /dev/null 2>&1; done
wait $READER
echo "--- reader's observed row counts (60 = clean, anything lower = fractured read) ---"
cat "$T/reader-counts.txt"
FINAL=$(bon list --all --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('outcomes',[]))+len(d.get('standalone',[])))")
echo "final board count with ONE writer: $FINAL (loss requires a concurrent WRITER only if reads are clean)"
kill $SERVER_PID 2>/dev/null
echo "workdir: $T"
