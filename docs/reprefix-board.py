#!/usr/bin/env python3
"""Re-prefix a JSONL bon board: OLD-XXX -> NEW-XXX, gated on the board's own id set.

Usage: reprefix-board.py BOARD_REPO_PATH NEW_PREFIX [--apply]

The old prefix is read from the board's .bon/prefix. Dry-run by default.

Proven twice: cornichon 2026-08-08 (279 ids, bon- -> crn-, done by hand to this
recipe) and bon-kafono 2026-08-16 (piano- and mas-, this script). The durable
fix is the alias layer (bon-poboso); until then this is the interim tool the
survey's duplicate_prefixes warning points at. JSONL boards only — a Dolt board
needs the same mapping applied server-side inside one transaction.

The doctrine it encodes (see understanding.md, "Renaming anything cited across
a corpus"): replacement is gated on membership of the board's known id set,
never on the bare pattern; POINTERS (items, understanding.md) are corrected;
RECORDS (handoffs, git history) are left untouched and bridged by a lookup doc.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

repo = Path(sys.argv[1])
new_prefix = sys.argv[2]
apply = "--apply" in sys.argv

items_path = repo / ".bon" / "items.jsonl"
prefix_path = repo / ".bon" / "prefix"
understanding_path = repo / ".bon" / "understanding.md"
lookup_path = repo / ".bon" / f"id-migration-{date.today().isoformat()}.md"

old_prefix = prefix_path.read_text().strip()
assert old_prefix and old_prefix != new_prefix, (
    f"old prefix {old_prefix!r} vs new {new_prefix!r}"
)

lines = [l for l in items_path.read_text().splitlines() if l.strip()]
items = [json.loads(l) for l in lines]

# Format sanity: our dump of an unmodified item must equal its source line
# byte-for-byte, or the rewrite would churn lines it doesn't mean to touch.
for orig_line, item in zip(lines, items):
    assert json.dumps(item, ensure_ascii=False) == orig_line, (
        "round-trip format mismatch on " + item["id"]
    )
print(f"format check: {len(items)} lines round-trip byte-identical")

# The known-id map — replacement is gated on membership, never on the pattern.
id_map = {}
for item in items:
    old = item["id"]
    assert old.startswith(old_prefix + "-"), old
    id_map[old] = new_prefix + old[len(old_prefix):]

pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in id_map) + r")\b")


def sub(text):
    return pattern.sub(lambda m: id_map[m.group(1)], text)


def transform(value):
    if isinstance(value, str):
        return sub(value)
    if isinstance(value, list):
        return [transform(v) for v in value]
    if isinstance(value, dict):
        return {k: transform(v) for k, v in value.items()}
    return value


new_items = [transform(i) for i in items]

# Validate structurally before any write.
assert len(new_items) == len(items)
new_ids = [i["id"] for i in new_items]
assert all(i.startswith(new_prefix + "-") for i in new_ids), new_ids
assert len(set(new_ids)) == len(new_ids)
for old_item, new_item in zip(items, new_items):
    assert new_item["id"] == id_map[old_item["id"]]
    if old_item.get("parent"):
        assert new_item["parent"] == id_map[old_item["parent"]], old_item["id"]
serialized = "\n".join(
    json.dumps(i, ensure_ascii=False) for i in sorted(new_items, key=lambda i: i["id"])
) + "\n"
# The leftover check is set-gated like the replacement itself: a bare
# old-prefix pattern would trip on id-shaped prose (live case: "piano-tunnel"
# in a brief — same family as the doctrine's "bon-shaped" example).
survivor = pattern.search(serialized)
assert not survivor, f"old id survived in output: {survivor.group(0)}"
print(
    f"transform check: {len(new_items)} items, all ids {new_prefix}-*, "
    f"parents mapped, no old ids remain"
)

# understanding.md: live pointer doc — gated replacement there too.
und_new = None
if understanding_path.exists():
    und_old = understanding_path.read_text()
    und_new = sub(und_old)
    print(f"understanding.md: {len(pattern.findall(und_old))} id citations to update")

lookup = [f"# id migration {date.today().isoformat()} — prefix {old_prefix} -> {new_prefix}", "",
          f"This board's items were re-minted with the same syllables under the",
          f"`{new_prefix}` prefix (duplicate-prefix repair — see bon-kafono for the",
          "original incident). Handoffs and git commit messages keep the old ids as",
          "records of what was true then — bridge them here.", "",
          "| old | new |", "|---|---|"]
for old, new in sorted(id_map.items()):
    lookup.append(f"| {old} | {new} |")
lookup_text = "\n".join(lookup) + "\n"

if not apply:
    print("DRY RUN — no writes. Mapping:")
    for old, new in sorted(id_map.items()):
        print(f"  {old} -> {new}")
    sys.exit(0)

tmp = items_path.with_suffix(".jsonl.tmp")
tmp.write_text(serialized)
tmp.rename(items_path)
prefix_path.write_text(new_prefix)  # no trailing newline — matches bon init's format
if und_new is not None:
    understanding_path.write_text(und_new)
lookup_path.write_text(lookup_text)

# Post-write assertion on the world, not the script's account of it.
reread = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
assert [i["id"] for i in reread] == sorted(new_ids)
assert prefix_path.read_text().strip() == new_prefix
print(f"APPLIED: {items_path} rewritten, prefix={new_prefix}, lookup at {lookup_path}")
