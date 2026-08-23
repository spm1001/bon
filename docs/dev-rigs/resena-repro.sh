#!/bin/bash
# bon-resena reproduction: two concurrent bon writers on one prefix, scratch Dolt server.
set -u
T=$(mktemp -d /tmp/resena-XXXXXX)
cd "$T" && mkdir dolt-data && cd dolt-data
dolt init
dolt sql -q "CREATE DATABASE IF NOT EXISTS repro"
nohup dolt sql-server --port 3307 --host 127.0.0.1 > "$T/server.log" 2>&1 &
SERVER_PID=$!
sleep 3
export BON_DOLT_HOST=127.0.0.1 BON_DOLT_PORT=3307 BON_DOLT_USER=root BON_DOLT_PASSWORD= BON_DOLT_DATABASE=repro

# Two board dirs sharing the prefix "rep" — mimics two lanes cd'd differently
mkdir -p "$T/laneA" "$T/laneB"
cd "$T/laneA" && bon init --prefix rep --backend dolt 2>&1 | tail -1
[ -d "$T/laneA/.bon" ] || { echo "INIT FAILED"; kill $SERVER_PID; exit 1; }
cp -r "$T/laneA/.bon" "$T/laneB/.bon"

# Seed 60 items from lane A
cd "$T/laneA"
for i in $(seq 1 60); do
  bon new "Seed item $i" --why w --what x --done d -q > /dev/null 2>&1
done
BEFORE=$(bon list --all --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('outcomes',[]))+len(d.get('standalone',[])))")
echo "seeded: $BEFORE items"

# Capture the id set before the race
bon list --all --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
ids=[o['id'] for o in d.get('outcomes',[])]+[s['id'] for s in d.get('standalone',[])]
print('\n'.join(sorted(ids)))" > "$T/ids-before.txt"

# The race: lane A edits item 1 in a tight loop; lane B edits item 2. Every edit
# is a whole-prefix truncate-and-reinsert. 40 rounds each, concurrent.
IDA=$(head -1 "$T/ids-before.txt"); IDB=$(sed -n '2p' "$T/ids-before.txt")
(cd "$T/laneA" && for i in $(seq 1 40); do bon edit "$IDA" --title "A tick $i" >/dev/null 2>&1; done) &
PA=$!
(cd "$T/laneB" && for i in $(seq 1 40); do bon edit "$IDB" --title "B tick $i" >/dev/null 2>&1; done) &
PB=$!
wait $PA $PB

cd "$T/laneA"
bon list --all --json | python3 -c "
import json,sys
d=json.load(sys.stdin)
ids=[o['id'] for o in d.get('outcomes',[])]+[s['id'] for s in d.get('standalone',[])]
print('\n'.join(sorted(ids)))" > "$T/ids-after.txt"
AFTER=$(wc -l < "$T/ids-after.txt")
LOST=$(comm -23 "$T/ids-before.txt" "$T/ids-after.txt" | tr '\n' ' ')
echo "after race: $AFTER items (was $BEFORE)"
echo "LOST: ${LOST:-none}"
kill $SERVER_PID 2>/dev/null
echo "workdir kept: $T"
