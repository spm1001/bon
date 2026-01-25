#!/usr/bin/env python3
"""Migrate beads export to arc format.

Usage:
    bd export --format jsonl | python scripts/migrate.py > .arc/items.jsonl

Or with a file:
    python scripts/migrate.py < beads-export.jsonl > .arc/items.jsonl
"""
import json
import sys
from typing import TextIO


def extract_parent(item: dict) -> str | None:
    """Extract parent ID from beads dependencies.

    Beads stores parent-child as:
    {"dependencies": [{"issue_id": "x.1", "depends_on_id": "x", "type": "parent-child"}]}
    """
    deps = item.get("dependencies", [])
    for dep in deps:
        if dep.get("type") == "parent-child":
            return dep.get("depends_on_id")
    return None


def migrate_item(item: dict) -> dict:
    """Migrate a single beads item to arc schema."""
    result = {}

    # Preserve core fields
    result["id"] = item["id"]
    result["title"] = item.get("title", "Untitled")

    # Type mapping: epic → outcome, anything else → action
    issue_type = item.get("issue_type", "task")
    if issue_type == "epic":
        result["type"] = "outcome"
    else:
        result["type"] = "action"

    # Status mapping: closed → done
    status = item.get("status", "open")
    if status == "closed":
        result["status"] = "done"
        if item.get("closed_at"):
            result["done_at"] = item["closed_at"]
    else:
        result["status"] = "open"

    # Brief from description/design/acceptance_criteria
    # Preserve full content, not just first line
    desc = item.get("description") or ""
    design = item.get("design") or ""
    acceptance = item.get("acceptance_criteria") or ""

    result["brief"] = {
        "why": desc if desc else "Migrated from beads",
        "what": design if design else "See title",
        "done": acceptance if acceptance else "When complete",
    }

    # Timestamps
    result["created_at"] = item.get("created_at", "")
    result["created_by"] = item.get("created_by", "unknown")

    # Order — derive from ID suffix if possible (x.1 → order 1)
    # Otherwise use sequence
    item_id = item["id"]
    if "." in item_id:
        try:
            result["order"] = int(item_id.split(".")[-1])
        except ValueError:
            result["order"] = 1
    else:
        result["order"] = 1

    # Parent relationship (for actions)
    if result["type"] == "action":
        parent = extract_parent(item)
        if parent:
            result["parent"] = parent
        result["waiting_for"] = None

    return result


def migrate_stream(input_stream: TextIO, output_stream: TextIO) -> tuple[int, int]:
    """Migrate all items from input to output.

    Returns (outcomes_count, actions_count).
    """
    outcomes = 0
    actions = 0

    for line in input_stream:
        line = line.strip()
        if not line:
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Warning: skipping invalid JSON: {e}", file=sys.stderr)
            continue

        migrated = migrate_item(item)
        output_stream.write(json.dumps(migrated, ensure_ascii=False) + "\n")

        if migrated["type"] == "outcome":
            outcomes += 1
        else:
            actions += 1

    return outcomes, actions


def main():
    outcomes, actions = migrate_stream(sys.stdin, sys.stdout)
    print(f"Migrated: {outcomes} outcomes, {actions} actions", file=sys.stderr)


if __name__ == "__main__":
    main()
