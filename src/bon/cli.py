"""Bon CLI - main entry point."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bon.display import format_hierarchical, format_json, format_jsonl, format_tactical
from bon.ids import DEFAULT_ORDER, generate_unique_id, next_order
from bon.storage import (
    BonError,
    ValidationError,
    append_archive,
    apply_reorder,
    apply_reparent,
    check_initialized,
    error,
    find_active_tactical,
    find_any_active_tactical,
    find_by_id,
    get_creator,
    load_archive,
    load_items,
    load_prefix,
    now_iso,
    remove_from_archive,
    save_items,
    validate_item,
    validate_tactical,
    warn,
)


def filter_items_for_output(items: list[dict], filter_mode: str) -> list[dict]:
    """Filter items based on mode for output.

    Used by --json and --jsonl to respect filter flags.
    """
    if filter_mode == "ready":
        # Open outcomes + ready and done actions (done shown for context)
        outcomes = [i for i in items if i["type"] == "outcome" and i["status"] == "open"]
        actions = [i for i in items if i["type"] == "action" and
                   (i["status"] == "done" or (i["status"] == "open" and not i.get("waiting_for")))]
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
    """Initialize .bon/ directory."""
    prefix = args.prefix

    # Validate prefix: alphanumeric only, no spaces or hyphens
    if not prefix.isalnum():
        error(f"Prefix must be alphanumeric (no spaces or hyphens), got '{prefix}'")

    bon_dir = Path(".bon")
    if bon_dir.exists():
        error(".bon/ already exists.")

    bon_dir.mkdir()
    (bon_dir / "items.jsonl").touch()
    (bon_dir / "prefix").write_text(prefix)  # No trailing newline
    print(f"Initialized .bon/ with prefix '{prefix}'")


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


# Activity verbs that suggest an outcome title describes work, not achievement.
# Kept deliberately small — the bon skill provides richer coaching.
ACTIVITY_VERBS = [
    "add", "build", "configure", "create", "decide", "deploy",
    "document", "fix", "implement", "improve", "investigate",
    "migrate", "refactor", "remove", "replace", "set up",
    "update", "upgrade", "write",
]


def check_outcome_language(title: str) -> None:
    """Warn if an outcome title uses activity language instead of achievement language.

    Outcomes should describe a desired result, not work to be done.
    E.g. "Users can authenticate with GitHub" not "Implement OAuth".
    """
    lower = title.lower()
    for verb in ACTIVITY_VERBS:
        # Match verb at start of title, followed by word boundary
        if re.match(rf"^{re.escape(verb)}\b", lower):
            warn(
                f"Outcome title starts with \"{verb}\" — that describes activity, not achievement.\n"
                f"  Try: what will be true when this is done?\n"
                f"  E.g. instead of \"Implement OAuth\" → \"Users can authenticate with GitHub\""
            )
            return


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
    # Include archived IDs to prevent collisions with archived items
    existing_ids.update(i["id"] for i in load_archive())
    parent = args.parent

    # Get brief: interactive prompts or flags
    if sys.stdin.isatty() and not (args.why and args.what and args.done):
        brief = prompt_brief()
    else:
        brief = require_brief_flags(args.why, args.what, args.done)

    # Lint outcome titles for activity language
    if not parent:
        check_outcome_language(title)

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
        session = os.path.realpath(os.getcwd())
        active = find_active_tactical(items, session=session)
        if not active:
            return  # Silent exit 0, no output
        print(f"Working: {active['title']} ({active['id']})")
        print(format_tactical(active["tactical"]))
        return

    if not args.id:
        error("Usage: bon show <id> or bon show --current")

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

    # Clear tactical steps (action is done, steps are moot)
    item.pop("tactical", None)

    # CRITICAL: Unblock waiters - clear waiting_for on items waiting for this one
    unblocked = []
    for other in items:
        if other.get("waiting_for") == item["id"]:
            other["waiting_for"] = None
            unblocked.append(other["id"])

    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
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

    # Warn if reason looks like a bon ID but can't be found
    reason = args.reason
    if re.match(r'^[a-z]+-[a-z]+$', reason) and not find_by_id(items, reason, prefix):
        warn(f"'{reason}' not found in active items — waiting_for may never resolve automatically")

    item["waiting_for"] = reason
    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
        print(f"{item['id']} now waiting for: {reason}")


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
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
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

    print(f"Bon status (prefix: {prefix})")
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
        error("At least one edit flag required: --title, --outcome, --why, --what, --done, --order")

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    # Outcomes can't have parents
    if args.parent is not None and item["type"] == "outcome":
        error("Cannot set --outcome on an outcome (only actions belong to outcomes)")

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
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
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
        # Outcome → Action: requires --outcome
        if not args.parent:
            error("Converting outcome to action requires --outcome")

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
            error("Converting action to outcome: don't specify --outcome")

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


def cmd_archive(args):
    """Archive done items to archive.jsonl."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()

    if args.all:
        # Archive all done items
        to_archive = [i for i in items if i["status"] == "done"]
        if not to_archive:
            print("Nothing to archive (no done items)")
            return
    elif args.ids:
        to_archive = []
        for item_id in args.ids:
            item = find_by_id(items, item_id, prefix)
            if not item:
                error(f"Item '{item_id}' not found")
            if item["status"] != "done":
                error(f"Cannot archive '{item_id}' — status is {item['status']}, not done")
            to_archive.append(item)

        # Cascade: if archiving a done outcome, include its done actions
        cascade_ids = set()
        for item in list(to_archive):
            if item["type"] == "outcome":
                children = [i for i in items if i.get("parent") == item["id"]]
                open_children = [c for c in children if c["status"] != "done"]
                if open_children:
                    names = ", ".join(f"{c['id']}" for c in open_children)
                    error(f"Cannot archive outcome '{item['id']}' — has open actions: {names}")
                done_children = [c for c in children if c["status"] == "done"]
                for child in done_children:
                    cascade_ids.add(child["id"])

        # Add cascaded children not already in the list
        existing_ids = {i["id"] for i in to_archive}
        for item in items:
            if item["id"] in cascade_ids and item["id"] not in existing_ids:
                to_archive.append(item)
    else:
        error("Specify item IDs or --all")

    # Stamp and move
    archive_ids = set()
    for item in to_archive:
        item["archived_at"] = now_iso()
        archive_ids.add(item["id"])

    # Append to archive, remove from items
    append_archive(to_archive)
    remaining = [i for i in items if i["id"] not in archive_ids]
    save_items(remaining)

    print(f"Archived {len(to_archive)} item(s)")
    for item in to_archive:
        print(f"  {item['id']} — {item['title']}")


def cmd_reopen(args):
    """Reopen a completed item."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    # Check archive if not found in active items
    if not item:
        archive_item = remove_from_archive(args.id, prefix)
        if archive_item:
            # Move back from archive to items
            archive_item["status"] = "open"
            archive_item.pop("done_at", None)
            archive_item.pop("archived_at", None)
            items.append(archive_item)
            save_items(items)
            print(f"Reopened: {archive_item['id']} (restored from archive)")
            return
        error(f"Item '{args.id}' not found")

    if item["status"] != "done":
        error(f"Item '{args.id}' is already open")

    item["status"] = "open"
    item.pop("done_at", None)
    # Preserve tactical steps if any (per brief)

    save_items(items)
    print(f"Reopened: {item['id']}")


def cmd_log(args):
    """Show recent activity feed."""
    check_initialized()

    items = load_items()
    archived = load_archive()
    all_items = items + archived
    limit = args.limit

    # Build events from timestamps
    events = []
    for item in all_items:
        if item.get("created_at"):
            events.append({
                "time": item["created_at"],
                "verb": "created",
                "item": item,
            })
        if item.get("done_at"):
            events.append({
                "time": item["done_at"],
                "verb": "completed",
                "item": item,
            })
        if item.get("archived_at"):
            events.append({
                "time": item["archived_at"],
                "verb": "archived",
                "item": item,
            })

    # Sort newest first
    events.sort(key=lambda e: e["time"], reverse=True)

    if limit:
        events = events[:limit]

    if not events:
        print("No activity yet.")
        return

    if args.json:
        log_entries = []
        for e in events:
            log_entries.append({
                "time": e["time"],
                "verb": e["verb"],
                "id": e["item"]["id"],
                "title": e["item"]["title"],
                "type": e["item"]["type"],
            })
        print(json.dumps(log_entries, indent=2, ensure_ascii=False))
        return

    for e in events:
        # Compact timestamp: strip seconds and Z for readability
        t = e["time"][:16].replace("T", " ")
        icon = {"created": "+", "completed": "✓", "archived": "⌂"}[e["verb"]]
        print(f"  {icon} {t}  {e['verb']} {e['item']['title']} ({e['item']['id']})")


def cmd_migrate(args):
    """Migrate from beads to bon.

    Two modes:
    - --draft: Generate manifest YAML from beads export (for Claude to complete)
    - --from-draft: Import completed manifest into .bon/
    """
    from bon.migrate import migrate_from_draft, migrate_to_draft

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
    Normalizes newlines to spaces first to prevent garbled steps
    from multiline --what values.
    Returns None if no numbered list found.
    """
    # Normalize: collapse newlines and extra whitespace to single spaces
    normalized = ' '.join(what.split())
    # Step number must be at start or after whitespace (prevents matching "v2.0")
    # Delimiter (. or )) must be followed by whitespace
    # Lookahead requires whitespace before next step number AND after delimiter
    pattern = r'(?:^|(?<=\s))(\d+)[.)]\s+(.+?)(?=\s+\d+[.)]\s|$)'
    matches = re.findall(pattern, normalized)
    if not matches:
        return None
    steps = [m[1].strip() for m in matches if m[1].strip()]
    return steps if steps else None


def cmd_work(args):
    """Initialize or manage tactical steps for an action."""
    check_initialized()
    items = load_items()
    prefix = load_prefix()
    session = os.path.realpath(os.getcwd())

    # Split args.args into id (first) and steps (rest).
    # REMAINDER captures everything after flags, but --force may appear
    # mixed with positionals (e.g. "work ID --force step1 step2"), so
    # we filter it out and set the flag manually.
    positional = args.args or []
    if "--force" in positional:
        positional = [a for a in positional if a != "--force"]
        args.force = True
    work_id = positional[0] if positional else None
    work_steps = positional[1:] if len(positional) > 1 else []

    # --status: show current tactical (scoped to CWD)
    if args.status:
        active = find_active_tactical(items, session=session)
        if not active:
            print("No active tactical steps. Run `bon work <id>` to start.")
            return
        print(f"Working on: {active['title']} ({active['id']})")
        print()
        print(format_tactical(active["tactical"]))
        return

    # --clear: clear active tactical (scoped to CWD)
    if args.clear:
        active = find_active_tactical(items, session=session)
        if not active:
            return  # Silent success
        active.pop("tactical", None)
        save_items(items)
        print(f"Cleared tactical steps from {active['id']}")
        return

    # Initialize tactical for specific action
    if not work_id:
        error("Usage: bon work <id> [steps...] or bon work --status/--clear")

    item = find_by_id(items, work_id, prefix)
    if not item:
        error(f"Item '{work_id}' not found")
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
            msg += f"\n\nNo actions yet. Create one:\n  bon new \"title\" --for {item['id']} --why \"...\" --what \"...\" --done \"...\""
        error(msg)
    if item["status"] == "done":
        error(f"Action '{work_id}' is already complete")

    # Cross-session conflict: same action claimed by a different CWD
    all_active = find_any_active_tactical(items)
    for other in all_active:
        if other["id"] == item["id"]:
            other_session = other.get("tactical", {}).get("session")
            if other_session and other_session != session:
                error(f"{item['id']} has active steps from another worktree ({other_session})")

    # Serial enforcement scoped to THIS session
    active = find_active_tactical(items, session=session)
    if active and active["id"] != item["id"]:
        error(f"{active['id']} has active steps. Complete it, wait it, or run `bon work --clear`")

    # Check for existing progress
    existing = item.get("tactical")
    if existing and existing.get("current", 0) > 0 and not args.force:
        error(f"Steps in progress (step {existing['current'] + 1}). Run `bon work {work_id} --force` to restart")

    # Get steps
    if work_steps:
        steps = work_steps
    else:
        what = item.get("brief", {}).get("what", "")
        steps = parse_steps_from_what(what)
        if not steps:
            error("No numbered steps in --what. Provide explicit steps: bon work <id> 'step 1' 'step 2'")

    # Validate
    try:
        validate_tactical({"steps": steps, "current": 0})
    except ValidationError as e:
        error(str(e))

    # Set tactical with session stamp
    item["tactical"] = {"steps": steps, "current": 0, "session": session}
    save_items(items)

    print(format_tactical(item["tactical"]))


def cmd_step(args):
    """Advance to next tactical step, auto-complete on final."""
    check_initialized()
    items = load_items()
    session = os.path.realpath(os.getcwd())

    active = find_active_tactical(items, session=session)
    if not active:
        error("No steps in progress. Run `bon work <id>` first")

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


try:
    from importlib.metadata import version as _meta_version
    __version__ = _meta_version("bon")
except Exception:
    __version__ = "0.0.0"


def cmd_migrate_repo(args):
    """Migrate a repo from .arc/ to .bon/.

    Renames .arc/ → .bon/, optionally updates the prefix file,
    updates .gitattributes, and commits.
    """
    import shutil

    arc_dir = Path(".arc")
    bon_dir = Path(".bon")
    dry_run = args.dry_run

    # Validate preconditions
    if bon_dir.exists():
        error(".bon/ already exists — already migrated?")
    if not arc_dir.exists():
        error("No .arc/ directory found. Nothing to migrate.")

    # Check if we're in a git repo
    in_git = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True
    ).returncode == 0

    # Determine prefix update
    prefix_path = arc_dir / "prefix"
    update_prefix = False
    if prefix_path.exists() and prefix_path.read_text() == "arc":
        update_prefix = True

    # Check .gitattributes
    gitattributes = Path(".gitattributes")
    update_gitattributes = False
    if gitattributes.exists():
        content = gitattributes.read_text()
        if ".arc/" in content:
            update_gitattributes = True

    # Dry run: report and exit
    if dry_run:
        print("Dry run — would perform:")
        if in_git:
            print("  git mv .arc .bon")
        else:
            print("  rename .arc/ → .bon/")
        if update_prefix:
            print("  update .bon/prefix: 'arc' → 'bon'")
        if update_gitattributes:
            print("  update .gitattributes: .arc/ → .bon/")
        if in_git:
            print("  git commit 'Rename .arc/ → .bon/ (arc→bon migration)'")
        return

    # 1. Rename .arc/ → .bon/
    if in_git:
        result = subprocess.run(
            ["git", "mv", ".arc", ".bon"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            error(f"git mv failed: {result.stderr.strip()}")
    else:
        shutil.move(str(arc_dir), str(bon_dir))

    # 2. Update prefix if it was "arc" (the old default)
    if update_prefix:
        (bon_dir / "prefix").write_text("bon")

    # 3. Update .gitattributes
    if update_gitattributes:
        content = gitattributes.read_text()
        content = content.replace(".arc/", ".bon/")
        gitattributes.write_text(content)

    # 4. Commit
    if in_git:
        # Stage any additional changes (prefix edit, gitattributes)
        to_add = [".bon/"]
        if update_gitattributes:
            to_add.append(".gitattributes")
        subprocess.run(["git", "add", *to_add], capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "Rename .arc/ → .bon/ (arc→bon migration)"],
            capture_output=True, text=True
        )

    # Report
    print("Migrated .arc/ → .bon/")
    if update_prefix:
        print("  prefix: 'arc' → 'bon'")
    if update_gitattributes:
        print("  .gitattributes updated")
    if in_git:
        print("  committed")


def cmd_update(args):
    """Re-install bon from source via uv tool upgrade."""
    print(f"Current: bon {__version__}")
    result = subprocess.run(["uv", "tool", "upgrade", "bon"], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        error(f"Update failed: {stderr}")
    # Show what happened
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    # Report new version by re-checking
    result2 = subprocess.run(["bon", "--version"], capture_output=True, text=True)
    if result2.returncode == 0:
        new_version = result2.stdout.strip()
        print(f"Updated: {new_version}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="bon",
        description="Work tracker for Claude-human collaboration"
    )
    parser.add_argument("--version", action="version", version=f"bon {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize .bon/")
    init_parser.add_argument("--prefix", default="bon", help="ID prefix (default: bon)")
    init_parser.set_defaults(func=cmd_init)

    # new
    new_parser = subparsers.add_parser("new", help="Create outcome or action")
    new_parser.add_argument("title", help="Title for the item")
    new_parser.add_argument("--outcome", "--for", dest="parent", help="Parent outcome ID (creates action)")
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
    add_output_flags(done_parser, quiet=True)
    done_parser.set_defaults(func=cmd_done)

    # wait
    wait_parser = subparsers.add_parser("wait", help="Mark item as waiting")
    wait_parser.add_argument("id", help="Item ID")
    wait_parser.add_argument("reason", help="What it's waiting for (ID or text)")
    add_output_flags(wait_parser, quiet=True)
    wait_parser.set_defaults(func=cmd_wait)

    # unwait
    unwait_parser = subparsers.add_parser("unwait", help="Clear waiting status")
    unwait_parser.add_argument("id", help="Item ID")
    add_output_flags(unwait_parser, quiet=True)
    unwait_parser.set_defaults(func=cmd_unwait)

    # edit
    edit_parser = subparsers.add_parser("edit", help="Edit item fields")
    edit_parser.add_argument("id", help="Item ID to edit")
    edit_parser.add_argument("--title", help="New title")
    edit_parser.add_argument("--outcome", "--parent", dest="parent", help="New parent outcome ID (use 'none' to make standalone)")
    edit_parser.add_argument("--why", help="New brief.why")
    edit_parser.add_argument("--what", help="New brief.what")
    edit_parser.add_argument("--done", help="New brief.done")
    edit_parser.add_argument("--order", type=int, help="New order within parent")
    add_output_flags(edit_parser, quiet=True)
    edit_parser.set_defaults(func=cmd_edit)

    # status
    status_parser = subparsers.add_parser("status", help="Show status overview")
    status_parser.set_defaults(func=cmd_status)

    # work
    work_parser = subparsers.add_parser("work", help="Manage tactical steps for an action")
    work_parser.add_argument("args", nargs=argparse.REMAINDER, help="Action ID followed by optional steps")
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

    # migrate-repo
    migrate_repo_parser = subparsers.add_parser("migrate-repo", help="Migrate .arc/ → .bon/")
    migrate_repo_parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    migrate_repo_parser.set_defaults(func=cmd_migrate_repo)

    # convert
    convert_parser = subparsers.add_parser("convert", help="Convert outcome↔action")
    convert_parser.add_argument("id", help="Item ID to convert")
    convert_parser.add_argument("--outcome", "--parent", "-p", dest="parent", help="Parent outcome (required for outcome→action)")
    convert_parser.add_argument("--force", "-f", action="store_true",
                                help="Allow converting outcome with children (makes them standalone)")
    convert_parser.set_defaults(func=cmd_convert)

    # archive
    archive_parser = subparsers.add_parser("archive", help="Archive done items")
    archive_parser.add_argument("ids", nargs="*", help="Item IDs to archive")
    archive_parser.add_argument("--all", action="store_true", help="Archive all done items")
    archive_parser.set_defaults(func=cmd_archive)

    # log
    log_parser = subparsers.add_parser("log", help="Show recent activity")
    log_parser.add_argument("-n", "--limit", type=int, default=20, help="Number of events (default: 20)")
    add_output_flags(log_parser, json=True)
    log_parser.set_defaults(func=cmd_log)

    # reopen
    reopen_parser = subparsers.add_parser("reopen", help="Reopen a completed item")
    reopen_parser.add_argument("id", help="Item ID to reopen")
    reopen_parser.set_defaults(func=cmd_reopen)

    # update
    update_parser = subparsers.add_parser("update", help="Re-install bon from source")
    update_parser.set_defaults(func=cmd_update)

    # help
    help_parser = subparsers.add_parser("help", help="Show help")
    help_parser.add_argument("command_name", nargs="?", help="Command to get help for")
    help_parser.set_defaults(func=lambda args: cmd_help(args, parser))

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    try:
        if hasattr(args, 'func'):
            args.func(args)
        else:
            print(f"Command '{args.command}' not yet implemented")
            sys.exit(1)
    except BonError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
