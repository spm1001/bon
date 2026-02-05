"""Arc CLI - main entry point."""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from arc.display import format_hierarchical, format_json, format_jsonl, format_tactical
from arc.ids import DEFAULT_ORDER, generate_unique_id, next_order
from arc.storage import (
    ValidationError,
    apply_reorder,
    apply_reparent,
    check_initialized,
    error,
    find_active_tactical,
    find_by_id,
    get_creator,
    load_items,
    load_prefix,
    now_iso,
    save_items,
    validate_item,
    validate_tactical,
)


def filter_items_for_output(items: list[dict], filter_mode: str) -> list[dict]:
    """Filter items based on mode for output.

    Used by --json and --jsonl to respect filter flags.
    """
    if filter_mode == "ready":
        # Open outcomes + ready actions only
        outcomes = [i for i in items if i["type"] == "outcome" and i["status"] == "open"]
        actions = [i for i in items if i["type"] == "action" and i["status"] == "open" and not i.get("waiting_for")]
        return outcomes + actions
    elif filter_mode == "waiting":
        # Open outcomes + waiting actions only
        outcomes = [i for i in items if i["type"] == "outcome" and i["status"] == "open"]
        actions = [i for i in items if i["type"] == "action" and i.get("waiting_for")]
        return outcomes + actions
    elif filter_mode == "all":
        return items
    else:
        # Default: open outcomes and all their actions
        outcomes = [i for i in items if i["type"] == "outcome" and i["status"] == "open"]
        outcome_ids = {o["id"] for o in outcomes}
        actions = [i for i in items if i["type"] == "action" and
                   (i.get("parent") in outcome_ids or (not i.get("parent") and i["status"] == "open"))]
        return outcomes + actions


def cmd_init(args):
    """Initialize .arc/ directory."""
    prefix = args.prefix

    # Validate prefix: alphanumeric only, no spaces or hyphens
    if not prefix.isalnum():
        error(f"Prefix must be alphanumeric (no spaces or hyphens), got '{prefix}'")

    arc_dir = Path(".arc")
    if arc_dir.exists():
        error(".arc/ already exists. Use --force to reinitialize.")

    arc_dir.mkdir()
    (arc_dir / "items.jsonl").touch()
    (arc_dir / "prefix").write_text(prefix)  # No trailing newline
    print(f"Initialized .arc/ with prefix '{prefix}'")


def prompt_brief() -> dict:
    """Prompt user for brief fields interactively.

    Guides human through the same structure Claude should use.
    All fields required — empty answers rejected.
    """
    print("Brief (all fields required):")
    print()

    why = input("  Why are we doing this? ").strip()
    if not why:
        error("'Why' cannot be empty")

    what = input("  What will we produce? ").strip()
    if not what:
        error("'What' cannot be empty")

    done = input("  How do we know it's done? ").strip()
    if not done:
        error("'Done' cannot be empty")

    return {"why": why, "what": what, "done": done}


def require_brief_flags(why: str | None, what: str | None, done: str | None) -> dict:
    """Validate brief flags for non-interactive creation.

    All three flags required when not in interactive mode.
    """
    missing = []
    if not why:
        missing.append("--why")
    if not what:
        missing.append("--what")
    if not done:
        missing.append("--done")

    if missing:
        error(f"Brief required. Missing: {', '.join(missing)}")

    return {"why": why, "what": what, "done": done}


def cmd_new(args):
    """Create a new outcome or action."""
    check_initialized()

    # Normalize title: single line, trimmed
    title = " ".join(args.title.split())
    if not title:
        error("Title cannot be empty")

    items = load_items()
    prefix = load_prefix()
    existing_ids = {i["id"] for i in items}
    parent = args.parent

    # Get brief: interactive prompts or flags
    if sys.stdin.isatty() and not (args.why and args.what and args.done):
        brief = prompt_brief()
    else:
        brief = require_brief_flags(args.why, args.what, args.done)

    if parent:
        # Validate parent exists and is an outcome
        parent_item = find_by_id(items, parent, prefix)
        if not parent_item:
            error(f"Parent '{parent}' not found")
        if parent_item["type"] != "outcome":
            error(f"Parent must be an outcome, got {parent_item['type']}")

        # Use the actual parent ID (in case prefix-tolerant matching was used)
        actual_parent = parent_item["id"]

        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "action",
            "title": title,
            "brief": brief,
            "status": "open",
            "parent": actual_parent,
            "order": next_order(items, "action", actual_parent),
            "created_at": now_iso(),
            "created_by": get_creator(),
            "waiting_for": None,
        }
    else:
        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "outcome",
            "title": title,
            "brief": brief,
            "status": "open",
            "order": next_order(items, "outcome", None),
            "created_at": now_iso(),
            "created_by": get_creator(),
        }

    items.append(item)
    save_items(items)
    if args.quiet:
        print(item["id"])
    else:
        print(f"Created: {item['id']}")


def cmd_list(args):
    """List items hierarchically."""
    check_initialized()

    items = load_items()

    # Determine filter mode
    if args.ready:
        filter_mode = "ready"
    elif args.waiting:
        filter_mode = "waiting"
    elif args.all:
        filter_mode = "all"
    else:
        filter_mode = "default"

    # Handle output format
    if args.json:
        filtered = filter_items_for_output(items, filter_mode)
        print(format_json(filtered))
    elif args.jsonl:
        filtered = filter_items_for_output(items, filter_mode)
        print(format_jsonl(filtered))
    else:
        output = format_hierarchical(items, filter_mode)
        print(output)


def cmd_show(args):
    """Show details for a single item."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()

    # --current: show active tactical action (for hook injection)
    if args.current:
        active = find_active_tactical(items)
        if not active:
            return  # Silent exit 0, no output
        print(f"Working: {active['title']} ({active['id']})")
        print(format_tactical(active["tactical"]))
        return

    if not args.id:
        error("Usage: arc show <id> or arc show --current")

    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    if args.json:
        # For outcomes, include actions
        if item["type"] == "outcome":
            item_copy = dict(item)
            item_copy["actions"] = sorted(
                [i for i in items if i.get("parent") == item["id"]],
                key=lambda x: x.get("order", DEFAULT_ORDER)
            )
            print(json.dumps(item_copy, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(item, indent=2, ensure_ascii=False))
        return

    # Header
    status_icon = "✓" if item["status"] == "done" else "○"
    print(f"{status_icon} {item['title']} ({item['id']})")
    print(f"   Type: {item['type']}")
    print(f"   Status: {item['status']}")
    print(f"   Created: {item['created_at']} by {item['created_by']}")

    if item.get("waiting_for"):
        print(f"   Waiting for: {item['waiting_for']}")

    # Brief
    brief = item.get("brief", {})
    if brief:
        print(f"\n   --why: {brief.get('why', 'N/A')}")
        print(f"   --what: {brief.get('what', 'N/A')}")
        print(f"   --done: {brief.get('done', 'N/A')}")

    # Tactical steps (actions only)
    if item.get("tactical"):
        tactical = item["tactical"]
        total = len(tactical["steps"])
        current = tactical["current"]
        if current < total:
            print(f"\n   Steps ({current}/{total}):")
            for line in format_tactical(tactical).split("\n"):
                print(f"   {line}")

    # For outcomes, show actions
    if item["type"] == "outcome":
        actions = sorted(
            [i for i in items if i.get("parent") == item["id"]],
            key=lambda x: x.get("order", DEFAULT_ORDER)
        )
        if actions:
            print("\n   Actions:")
            for idx, action in enumerate(actions, 1):
                a_icon = "✓" if action["status"] == "done" else "○"
                waiting = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
                print(f"   {idx}. {a_icon} {action['title']} ({action['id']}){waiting}")


def cmd_done(args):
    """Mark item as done."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    if item["status"] == "done":
        print(f"Already done: {item['id']}")
        return

    # Mark as done
    item["status"] = "done"
    item["done_at"] = now_iso()

    # CRITICAL: Unblock waiters - clear waiting_for on items waiting for this one
    unblocked = []
    for other in items:
        if other.get("waiting_for") == item["id"]:
            other["waiting_for"] = None
            unblocked.append(other["id"])

    save_items(items)
    print(f"Done: {item['id']}")
    if unblocked:
        print(f"Unblocked: {', '.join(unblocked)}")


def cmd_wait(args):
    """Mark item as waiting."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    # Clear tactical if present (long blocks warrant re-planning)
    if item.get("tactical"):
        item.pop("tactical")

    item["waiting_for"] = args.reason
    save_items(items)
    print(f"{item['id']} now waiting for: {args.reason}")


def cmd_unwait(args):
    """Clear waiting status."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    item["waiting_for"] = None
    save_items(items)
    print(f"{item['id']} no longer waiting")


def validate_edit(original: dict, edited: dict, all_items: list[dict], prefix: str | None = None):
    """Validate edited item. Raises error on invalid changes."""
    # ID cannot change
    if edited.get("id") != original["id"]:
        error("Cannot change item ID")

    # Type cannot change
    if edited.get("type") != original["type"]:
        error("Cannot change item type")

    # Full validation including brief subfields
    try:
        validate_item(edited, strict=True)
    except ValidationError as e:
        error(str(e))

    # Additional required fields for edit
    for field in ["order", "created_at", "created_by"]:
        if field not in edited:
            error(f"Missing required field: {field}")

    # Order must be positive
    if edited.get("order", 1) < 1:
        error(f"Order must be positive, got {edited.get('order')}")

    # Parent must exist if specified
    if edited.get("parent"):
        parent = find_by_id(all_items, edited["parent"], prefix)
        if not parent:
            error(f"Parent '{edited['parent']}' not found")
        if parent["type"] != "outcome":
            error(f"Parent must be an outcome, got {parent['type']}")


def cmd_help(args, parser):
    """Show help."""
    if args.command_name:
        # Find the subparser for this command
        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        if subparsers_actions:
            subparsers = subparsers_actions[0]
            if args.command_name in subparsers.choices:
                subparsers.choices[args.command_name].print_help()
            else:
                print(f"Unknown command: {args.command_name}", file=sys.stderr)
                sys.exit(1)
    else:
        parser.print_help()


def cmd_status(args):
    """Show status overview."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()

    outcomes = [i for i in items if i["type"] == "outcome"]
    actions = [i for i in items if i["type"] == "action"]

    open_outcomes = [i for i in outcomes if i["status"] == "open"]
    done_outcomes = [i for i in outcomes if i["status"] == "done"]

    open_actions = [i for i in actions if i["status"] == "open"]
    done_actions = [i for i in actions if i["status"] == "done"]
    waiting_actions = [i for i in open_actions if i.get("waiting_for")]
    ready_actions = [i for i in open_actions if not i.get("waiting_for")]

    standalone = [i for i in actions if not i.get("parent")]

    print(f"Arc status (prefix: {prefix})")
    print()
    print(f"Outcomes:   {len(open_outcomes)} open, {len(done_outcomes)} done")
    print(f"Actions:    {len(open_actions)} open ({len(ready_actions)} ready, {len(waiting_actions)} waiting), {len(done_actions)} done")
    if standalone:
        open_standalone = [s for s in standalone if s["status"] == "open"]
        print(f"Standalone: {len(open_standalone)} open")


def cmd_edit(args):
    """Edit item fields via flags (no interactive editor)."""
    check_initialized()

    # Require at least one edit flag
    has_edit = any([
        args.title,
        args.parent is not None,
        args.why,
        args.what,
        args.done,
        args.order is not None,
    ])
    if not has_edit:
        error("At least one edit flag required: --title, --parent, --why, --what, --done, --order")

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    # Outcomes can't have parents
    if args.parent is not None and item["type"] == "outcome":
        error("Cannot set parent on outcome (only actions can have parents)")

    # Make a copy to edit
    edited = dict(item)
    edited["brief"] = dict(item.get("brief", {}))

    old_order = item.get("order")
    old_parent = item.get("parent")

    # Apply edits
    if args.title:
        edited["title"] = args.title
    if args.parent is not None:
        # Special value "none" clears parent (makes standalone)
        edited["parent"] = None if args.parent.lower() == "none" else args.parent
    if args.why:
        edited["brief"]["why"] = args.why
    if args.what:
        edited["brief"]["what"] = args.what
    if args.done:
        edited["brief"]["done"] = args.done
    if args.order is not None:
        edited["order"] = args.order

    # Validate
    validate_edit(item, edited, items, prefix)

    new_parent = edited.get("parent")
    new_order = edited.get("order")

    # Handle reparenting (closes gap in old parent, appends to new parent)
    if old_parent != new_parent:
        apply_reparent(items, edited, old_parent, new_parent)
    # Handle reorder within same parent
    elif old_order != new_order:
        apply_reorder(items, edited, old_order, new_order)

    # Update in list
    for i, existing in enumerate(items):
        if existing["id"] == item["id"]:
            items[i] = edited
            break

    save_items(items)
    print(f"Updated: {item['id']}")


def cmd_convert(args):
    """Convert outcome↔action while preserving ID and metadata."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    if item["type"] == "outcome":
        # Outcome → Action: requires --parent
        if not args.parent:
            error("Converting outcome to action requires --parent")

        parent = find_by_id(items, args.parent, prefix)
        if not parent:
            error(f"Parent '{args.parent}' not found")
        if parent["type"] != "outcome":
            error(f"Parent must be an outcome, got {parent['type']}")

        # Check for children
        children = [i for i in items if i.get("parent") == item["id"]]
        if children and not args.force:
            error(f"Outcome has {len(children)} children. Use --force to make them standalone.")

        # Orphan children (make standalone actions)
        for child in children:
            apply_reparent(items, child, item["id"], None)
            child["parent"] = None

        # Convert outcome → action
        old_parent = None
        new_parent = parent["id"]
        item["type"] = "action"
        item["parent"] = new_parent
        item["waiting_for"] = None
        apply_reparent(items, item, old_parent, new_parent)

    else:  # action → outcome
        if args.parent:
            error("Converting action to outcome: don't specify --parent")

        old_parent = item.get("parent")
        item["type"] = "outcome"
        item["parent"] = None
        item.pop("waiting_for", None)
        apply_reparent(items, item, old_parent, None)

        # Assign order among outcomes (append at end)
        outcomes = [i for i in items if i["type"] == "outcome" and i["id"] != item["id"]]
        if outcomes:
            max_order = max(o.get("order", 0) for o in outcomes)
            item["order"] = max_order + 1
        else:
            item["order"] = 1

    save_items(items)
    print(f"Converted {item['id']} to {item['type']}")


def cmd_migrate(args):
    """Migrate from beads to arc.

    Two modes:
    - --draft: Generate manifest YAML from beads export (for Claude to complete)
    - --from-draft: Import completed manifest into .arc/
    """
    if args.from_draft:
        # Import mode
        migrate_from_draft(args.from_draft)
    elif args.from_beads:
        if not args.draft:
            error("--from-beads requires --draft flag (direct migration not supported)")

        # Handle directory shorthand: if path is directory, look for issues.jsonl
        beads_path = Path(args.from_beads)
        if beads_path.is_dir():
            issues_file = beads_path / "issues.jsonl"
            if not issues_file.exists():
                error(f"Directory '{args.from_beads}' has no issues.jsonl")
            beads_path = issues_file

        migrate_to_draft(
            str(beads_path),
            promote_orphans=args.promote_orphans,
            orphan_parent=args.orphan_parent,
        )
    else:
        error("Specify --from-beads FILE --draft or --from-draft FILE")


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


def add_output_flags(subparser, json=False, jsonl=False, quiet=False):
    """Add output format flags to a subparser.

    Args:
        subparser: The argparse subparser to add flags to
        json: If True, add --json flag
        jsonl: If True, add --jsonl flag
        quiet: If True, add --quiet/-q flag
    """
    if json:
        subparser.add_argument("--json", action="store_true", help="Output as nested JSON")
    if jsonl:
        subparser.add_argument("--jsonl", action="store_true", help="Output as flat JSONL")
    if quiet:
        subparser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")


def parse_steps_from_what(what: str) -> list[str] | None:
    """Extract numbered steps from --what field.

    Looks for patterns like "1. step" or "1) step".
    Returns None if no numbered list found.
    """
    pattern = r'(\d+)[.)]\s*(.+?)(?=\s*\d+[.)]|$)'
    matches = re.findall(pattern, what, re.DOTALL)
    if not matches:
        return None
    steps = [m[1].strip() for m in matches if m[1].strip()]
    return steps if steps else None


def cmd_work(args):
    """Initialize or manage tactical steps for an action."""
    check_initialized()
    items = load_items()
    prefix = load_prefix()

    # --status: show current tactical
    if args.status:
        active = find_active_tactical(items)
        if not active:
            print("No active tactical steps. Run `arc work <id>` to start.")
            return
        print(f"Working on: {active['title']} ({active['id']})")
        print()
        print(format_tactical(active["tactical"]))
        return

    # --clear: clear active tactical
    if args.clear:
        active = find_active_tactical(items)
        if not active:
            return  # Silent success
        active.pop("tactical", None)
        save_items(items)
        print(f"Cleared tactical steps from {active['id']}")
        return

    # Initialize tactical for specific action
    if not args.id:
        error("Usage: arc work <id> [steps...] or arc work --status/--clear")

    item = find_by_id(items, args.id, prefix)
    if not item:
        error(f"Item '{args.id}' not found")
    if item["type"] == "outcome":
        # Helpful error: show child actions or suggest creating one
        children = sorted(
            [i for i in items if i.get("parent") == item["id"] and i["status"] == "open"],
            key=lambda x: x.get("order", DEFAULT_ORDER)
        )
        msg = f"{item['id']} is an outcome. Tactical steps are for actions."
        if children:
            msg += "\n\nDid you mean one of its actions?"
            for child in children[:5]:  # Limit to 5
                msg += f"\n  {child['id']} — {child['title']}"
            if len(children) > 5:
                msg += f"\n  (+{len(children) - 5} more)"
        else:
            msg += f"\n\nNo actions yet. Create one:\n  arc new \"title\" --for {item['id']} --why \"...\" --what \"...\" --done \"...\""
        error(msg)
    if item["status"] == "done":
        error(f"Action '{args.id}' is already complete")

    # Check for other active tactical
    active = find_active_tactical(items)
    if active and active["id"] != item["id"]:
        error(f"{active['id']} has active steps. Complete it, wait it, or run `arc work --clear`")

    # Check for existing progress
    existing = item.get("tactical")
    if existing and existing.get("current", 0) > 0 and not args.force:
        error(f"Steps in progress (step {existing['current'] + 1}). Run `arc work {args.id} --force` to restart")

    # Get steps
    if args.steps:
        steps = args.steps
    else:
        what = item.get("brief", {}).get("what", "")
        steps = parse_steps_from_what(what)
        if not steps:
            error("No numbered steps in --what. Provide explicit steps: arc work <id> 'step 1' 'step 2'")

    # Validate
    try:
        validate_tactical({"steps": steps, "current": 0})
    except ValidationError as e:
        error(str(e))

    # Set tactical
    item["tactical"] = {"steps": steps, "current": 0}
    save_items(items)

    print(format_tactical(item["tactical"]))


def cmd_step(args):
    """Advance to next tactical step, auto-complete on final."""
    check_initialized()
    items = load_items()

    active = find_active_tactical(items)
    if not active:
        error("No steps in progress. Run `arc work <id>` first")

    tactical = active["tactical"]
    current = tactical["current"]
    steps = tactical["steps"]

    # Advance
    tactical["current"] = current + 1

    # Check if complete
    if tactical["current"] >= len(steps):
        # Auto-complete the action
        active["status"] = "done"
        active["done_at"] = now_iso()
        # Unblock waiters
        for other in items:
            if other.get("waiting_for") == active["id"]:
                other["waiting_for"] = None
        save_items(items)
        print(format_tactical(tactical))
        print(f"\nAction {active['id']} complete.")
    else:
        save_items(items)
        print(format_tactical(tactical))
        print(f"\nNext: {steps[tactical['current']]}")


__version__ = "0.1.0"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="arc",
        description="Work tracker for Claude-human collaboration"
    )
    parser.add_argument("--version", action="version", version=f"arc {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize .arc/")
    init_parser.add_argument("--prefix", default="arc", help="ID prefix (default: arc)")
    init_parser.set_defaults(func=cmd_init)

    # new
    new_parser = subparsers.add_parser("new", help="Create outcome or action")
    new_parser.add_argument("title", help="Title for the item")
    new_parser.add_argument("--for", dest="parent", help="Parent outcome ID (creates action)")
    new_parser.add_argument("--why", help="Brief: why are we doing this?")
    new_parser.add_argument("--what", help="Brief: what will we produce?")
    new_parser.add_argument("--done", help="Brief: how do we know it's done?")
    add_output_flags(new_parser, quiet=True)
    new_parser.set_defaults(func=cmd_new)

    # list
    list_parser = subparsers.add_parser("list", help="List items")
    list_parser.add_argument("--ready", action="store_true", help="Show only ready items")
    list_parser.add_argument("--waiting", action="store_true", help="Show only waiting items")
    list_parser.add_argument("--all", action="store_true", help="Include done items")
    add_output_flags(list_parser, json=True, jsonl=True)
    list_parser.set_defaults(func=cmd_list)

    # show
    show_parser = subparsers.add_parser("show", help="View item details")
    show_parser.add_argument("id", nargs="?", help="Item ID to show")
    show_parser.add_argument("--current", action="store_true", help="Show action with active tactical steps")
    add_output_flags(show_parser, json=True)
    show_parser.set_defaults(func=cmd_show)

    # done
    done_parser = subparsers.add_parser("done", help="Complete item")
    done_parser.add_argument("id", help="Item ID to mark done")
    done_parser.set_defaults(func=cmd_done)

    # wait
    wait_parser = subparsers.add_parser("wait", help="Mark item as waiting")
    wait_parser.add_argument("id", help="Item ID")
    wait_parser.add_argument("reason", help="What it's waiting for (ID or text)")
    wait_parser.set_defaults(func=cmd_wait)

    # unwait
    unwait_parser = subparsers.add_parser("unwait", help="Clear waiting status")
    unwait_parser.add_argument("id", help="Item ID")
    unwait_parser.set_defaults(func=cmd_unwait)

    # edit
    edit_parser = subparsers.add_parser("edit", help="Edit item fields")
    edit_parser.add_argument("id", help="Item ID to edit")
    edit_parser.add_argument("--title", help="New title")
    edit_parser.add_argument("--parent", help="New parent ID (use 'none' to make standalone)")
    edit_parser.add_argument("--why", help="New brief.why")
    edit_parser.add_argument("--what", help="New brief.what")
    edit_parser.add_argument("--done", help="New brief.done")
    edit_parser.add_argument("--order", type=int, help="New order within parent")
    edit_parser.set_defaults(func=cmd_edit)

    # status
    status_parser = subparsers.add_parser("status", help="Show status overview")
    status_parser.set_defaults(func=cmd_status)

    # work
    work_parser = subparsers.add_parser("work", help="Manage tactical steps for an action")
    work_parser.add_argument("id", nargs="?", help="Action ID to work on")
    work_parser.add_argument("steps", nargs="*", help="Explicit steps (optional)")
    work_parser.add_argument("--status", action="store_true", help="Show current tactical state")
    work_parser.add_argument("--clear", action="store_true", help="Clear active tactical steps")
    work_parser.add_argument("--force", action="store_true", help="Restart steps even if in progress")
    work_parser.set_defaults(func=cmd_work)

    # step
    step_parser = subparsers.add_parser("step", help="Complete current step, advance to next")
    step_parser.set_defaults(func=cmd_step)

    # migrate
    migrate_parser = subparsers.add_parser("migrate", help="Migrate from beads")
    migrate_parser.add_argument("--from-beads", metavar="PATH", help="Beads JSONL file or .beads/ directory")
    migrate_parser.add_argument("--draft", action="store_true", help="Output manifest YAML for Claude to complete")
    migrate_parser.add_argument("--from-draft", metavar="FILE", help="Import completed manifest YAML")
    migrate_parser.add_argument("--promote-orphans", action="store_true", help="Convert orphan tasks to outcomes")
    migrate_parser.add_argument("--orphan-parent", metavar="ID", help="Assign orphans to this parent outcome")
    migrate_parser.set_defaults(func=cmd_migrate)

    # convert
    convert_parser = subparsers.add_parser("convert", help="Convert outcome↔action")
    convert_parser.add_argument("id", help="Item ID to convert")
    convert_parser.add_argument("--parent", "-p", help="Parent outcome (required for outcome→action)")
    convert_parser.add_argument("--force", "-f", action="store_true",
                                help="Allow converting outcome with children (makes them standalone)")
    convert_parser.set_defaults(func=cmd_convert)

    # help
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.add_argument("command_name", nargs="?", help="Command to get help for")
    help_parser.set_defaults(func=lambda args: cmd_help(args, parser))

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, 'func'):
        args.func(args)
    else:
        print(f"Command '{args.command}' not yet implemented")
        sys.exit(1)


if __name__ == "__main__":
    main()
