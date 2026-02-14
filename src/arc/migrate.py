"""Migration from beads to arc."""
import json
import sys
from pathlib import Path

import yaml

from arc.storage import error, get_creator, now_iso


def migrate_to_draft(beads_path: str, promote_orphans: bool = False, orphan_parent: str | None = None):
    """Generate manifest YAML from beads export.

    Output structure:
    - outcomes (from epics) with nested children
    - _beads context preserved for Claude reference
    - empty brief placeholders to fill

    Orphan handling (standalone tasks with no parent epic):
    - Default: excluded, listed in orphans_excluded
    - --promote-orphans: convert to outcomes (empty children)
    - --orphan-parent ID: assign to specified parent
    """
    if promote_orphans and orphan_parent:
        error("Cannot use both --promote-orphans and --orphan-parent")

    path = Path(beads_path)
    if not path.exists():
        error(f"File not found: {beads_path}")

    # Parse beads export
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: skipping invalid JSON: {e}", file=sys.stderr)

    # Separate epics and non-epics
    epics = [i for i in items if i.get("issue_type") == "epic"]
    non_epics = [i for i in items if i.get("issue_type") != "epic"]

    # Build parent lookup from dependencies
    parent_map = {}  # child_id -> parent_id
    for item in items:
        for dep in item.get("dependencies", []):
            if dep.get("type") == "parent-child":
                parent_map[item["id"]] = dep.get("depends_on_id")

    # Find orphans (non-epics with no parent)
    orphans = [i for i in non_epics if i["id"] not in parent_map]
    parented = [i for i in non_epics if i["id"] in parent_map]

    # Group children by parent
    children_by_parent = {}
    for item in parented:
        parent_id = parent_map[item["id"]]
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        children_by_parent[parent_id].append(item)

    # Build manifest
    manifest = {"outcomes": [], "orphans_excluded": []}

    for epic in epics:
        outcome = {
            "id": epic["id"],
            "title": epic.get("title", "Untitled"),
            "type": "outcome",
            "status": "done" if epic.get("status") == "closed" else "open",
            "_beads": {
                "description": epic.get("description") or "",
                "design": epic.get("design") or "",
                "acceptance_criteria": epic.get("acceptance_criteria") or "",
                "notes": epic.get("notes") or "",
            },
            "brief": {
                "why": "",   # Claude fills
                "what": "",  # Claude fills
                "done": "",  # Claude fills
            },
            "children": [],
        }

        # Add children
        for child in children_by_parent.get(epic["id"], []):
            action = {
                "id": child["id"],
                "title": child.get("title", "Untitled"),
                "type": "action",
                "status": "done" if child.get("status") == "closed" else "open",
                "_beads": {
                    "description": child.get("description") or "",
                    "design": child.get("design") or "",
                    "acceptance_criteria": child.get("acceptance_criteria") or "",
                    "notes": child.get("notes") or "",
                },
                "brief": {
                    "why": "",
                    "what": "",
                    "done": "",
                },
            }
            outcome["children"].append(action)

        manifest["outcomes"].append(outcome)

    # Handle orphans based on flags
    if promote_orphans:
        # Convert orphans to outcomes (with no children)
        for orphan in orphans:
            outcome = {
                "id": orphan["id"],
                "title": orphan.get("title", "Untitled"),
                "type": "outcome",
                "status": "done" if orphan.get("status") == "closed" else "open",
                "_beads": {
                    "description": orphan.get("description") or "",
                    "design": orphan.get("design") or "",
                    "acceptance_criteria": orphan.get("acceptance_criteria") or "",
                    "notes": orphan.get("notes") or "",
                },
                "brief": {
                    "why": "",
                    "what": "",
                    "done": "",
                },
                "children": [],
                "_promoted_from_orphan": True,
            }
            manifest["outcomes"].append(outcome)
    elif orphan_parent:
        # Validate parent exists in epics
        parent_epic = next((e for e in epics if e["id"] == orphan_parent), None)
        if not parent_epic:
            error(f"Orphan parent '{orphan_parent}' not found in epics")

        # Find the outcome in manifest and add orphans as children
        for outcome in manifest["outcomes"]:
            if outcome["id"] == orphan_parent:
                for orphan in orphans:
                    action = {
                        "id": orphan["id"],
                        "title": orphan.get("title", "Untitled"),
                        "type": "action",
                        "status": "done" if orphan.get("status") == "closed" else "open",
                        "_beads": {
                            "description": orphan.get("description") or "",
                            "design": orphan.get("design") or "",
                            "acceptance_criteria": orphan.get("acceptance_criteria") or "",
                            "notes": orphan.get("notes") or "",
                        },
                        "brief": {
                            "why": "",
                            "what": "",
                            "done": "",
                        },
                        "_adopted_orphan": True,
                    }
                    outcome["children"].append(action)
                break
    else:
        # Default: record orphans as excluded
        for orphan in orphans:
            desc = orphan.get("description") or ""
            context = desc[:80] + "..." if len(desc) > 80 else desc
            manifest["orphans_excluded"].append({
                "id": orphan["id"],
                "title": orphan.get("title", "Untitled"),
                "context": context if context else "(no description)",
                "reason": "standalone action (no parent outcome)",
            })

    # Output YAML
    print(yaml.dump(manifest, default_flow_style=False, allow_unicode=True, sort_keys=False))

    # Summary to stderr
    print("\n# Summary:", file=sys.stderr)
    print(f"#   {len(manifest['outcomes'])} outcomes", file=sys.stderr)
    print(f"#   {sum(len(o['children']) for o in manifest['outcomes'])} actions", file=sys.stderr)
    if orphans:
        if promote_orphans:
            print(f"#   {len(orphans)} orphans PROMOTED to outcomes", file=sys.stderr)
        elif orphan_parent:
            print(f"#   {len(orphans)} orphans ADOPTED by {orphan_parent}", file=sys.stderr)
        else:
            print(f"#   {len(orphans)} orphans EXCLUDED (use --promote-orphans or --orphan-parent)", file=sys.stderr)


def migrate_from_draft(manifest_path: str):
    """Import completed manifest into .arc/.

    Validates:
    - All briefs complete (why/what/done non-empty)
    - No orphan actions
    - .arc/ doesn't already exist (unless --force? no, we said no --force)
    """
    path = Path(manifest_path)
    if not path.exists():
        error(f"File not found: {manifest_path}")

    with open(path) as f:
        manifest = yaml.safe_load(f)

    # Check .arc/ exists
    arc_dir = Path(".arc")
    if arc_dir.exists():
        error(".arc/ already exists. Remove it first or migrate to a different directory.")

    # Validate and collect items
    items = []
    errors = []
    order_counter = {"outcome": 0, "action": {}}

    for outcome in manifest.get("outcomes", []):
        # Validate brief
        brief = outcome.get("brief", {})
        if not brief.get("why") or not brief.get("what") or not brief.get("done"):
            errors.append(f"{outcome['id']}: incomplete brief (why/what/done required)")
            continue

        order_counter["outcome"] += 1

        item = {
            "id": outcome["id"],
            "type": "outcome",
            "title": outcome["title"],
            "brief": brief,
            "status": outcome.get("status", "open"),
            "order": order_counter["outcome"],
            "created_at": outcome.get("created_at") or now_iso(),
            "created_by": outcome.get("created_by") or get_creator(),
        }
        if item["status"] == "done":
            item["done_at"] = outcome.get("done_at") or now_iso()
        items.append(item)

        # Process children
        order_counter["action"][outcome["id"]] = 0
        for child in outcome.get("children", []):
            child_brief = child.get("brief", {})
            if not child_brief.get("why") or not child_brief.get("what") or not child_brief.get("done"):
                errors.append(f"{child['id']}: incomplete brief (why/what/done required)")
                continue

            order_counter["action"][outcome["id"]] += 1

            action = {
                "id": child["id"],
                "type": "action",
                "title": child["title"],
                "brief": child_brief,
                "status": child.get("status", "open"),
                "parent": outcome["id"],
                "order": order_counter["action"][outcome["id"]],
                "created_at": child.get("created_at") or now_iso(),
                "created_by": child.get("created_by") or get_creator(),
                "waiting_for": None,
            }
            if action["status"] == "done":
                action["done_at"] = child.get("done_at") or now_iso()
            items.append(action)

    # Report errors
    if errors:
        print("Migration blocked - incomplete briefs:", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        error(f"{len(errors)} items need complete briefs before migration")

    # Derive prefix from first item ID
    if not items:
        error("No valid items to migrate")

    first_id = items[0]["id"]
    if "-" in first_id:
        prefix = first_id.rsplit("-", 1)[0]
    else:
        prefix = "arc"

    # Create .arc/
    arc_dir.mkdir()
    (arc_dir / "prefix").write_text(prefix)

    # Write items
    with open(arc_dir / "items.jsonl", "w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Migrated {len(items)} items to .arc/ (prefix: {prefix})")
