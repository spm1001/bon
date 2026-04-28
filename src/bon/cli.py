"""Bon CLI - main entry point."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bon.display import _normalize_brief, format_hierarchical, format_json, format_jsonl, format_tactical
from bon.ids import DEFAULT_ORDER, generate_unique_id, next_order
from bon.storage import (
    KNOWN_VERBS,
    BonError,
    ValidationError,
    _get_backend,
    append_archive,
    apply_reorder,
    apply_reparent,
    check_initialized,
    error,
    find_active_tactical,
    find_any_active_tactical,
    find_by_id,
    find_no_complete_tactical,
    find_orphaned_tactical,
    get_creator,
    get_session_identity,
    items_path,
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


def limit_items(items: list[dict], limit: int | None) -> list[dict]:
    """Truncate to first N top-level items, keeping their children.

    Top-level = outcomes + standalone actions. Render order is outcomes
    before standalones, each sorted by (order, id). Children of kept
    outcomes come along regardless. limit=None or limit<=0 returns items
    unchanged.
    """
    if not limit or limit <= 0:
        return items

    outcomes = sorted(
        [i for i in items if i["type"] == "outcome"],
        key=lambda x: (x.get("order", DEFAULT_ORDER), x["id"])
    )
    standalones = sorted(
        [i for i in items if i["type"] == "action" and not i.get("parent")],
        key=lambda x: (x.get("order", DEFAULT_ORDER), x["id"])
    )

    kept_top = (outcomes + standalones)[:limit]
    kept_ids = {i["id"] for i in kept_top}
    return [i for i in items if i["id"] in kept_ids or i.get("parent") in kept_ids]


def cmd_init(args):
    """Initialize .bon/ directory."""
    prefix = args.prefix
    backend = getattr(args, "backend", "jsonl")

    # Validate prefix: alphanumeric only, no spaces or hyphens
    if not prefix.isalnum():
        error(f"Prefix must be alphanumeric (no spaces or hyphens), got '{prefix}'")

    if backend not in ("jsonl", "dolt"):
        error(f"Unknown backend '{backend}'. Use 'jsonl' or 'dolt'.")

    bon_dir = Path(".bon")
    if bon_dir.exists():
        error(".bon/ already exists.")

    bon_dir.mkdir()
    (bon_dir / "prefix").write_text(prefix)  # No trailing newline

    if backend == "dolt":
        (bon_dir / "backend").write_text("dolt")
        print(f"Initialized .bon/ with prefix '{prefix}' (backend: dolt)")
    else:
        (bon_dir / "items.jsonl").touch()
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

    how = input("  How will we approach it? (optional, Enter to skip) ").strip()

    what = input("  What will we produce? ").strip()
    if not what:
        error("'What' cannot be empty")

    done = input("  How do we know it's done? ").strip()
    if not done:
        error("'Done' cannot be empty")

    brief = {"why": why, "what": what, "done": done}
    if how:
        brief["how"] = how
    return brief


def require_brief_flags(why: str | None, what: str | None, done: str | None, how: str | None = None) -> dict:
    """Validate brief flags for non-interactive creation.

    --why, --what, --done are required. --how is optional.
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

    brief = {"why": why, "what": what, "done": done}
    if how:
        brief["how"] = how
    return brief


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

    # JSON is the default input when stdin is piped and no title given.
    # Flags are the shorthand for quick stubs with a title on the command line.
    use_json = getattr(args, 'json_input', False) or (not args.title and not sys.stdin.isatty())

    if use_json:
        # JSON from stdin — structured input, no shell escaping needed
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            error(f"Invalid JSON on stdin: {e}")

        title = data.get("title", "")
        if not title:
            error("JSON must include 'title'")

        parent = data.get("parent", args.parent)
        explicit_type = data.get("type")

        brief_data = data.get("brief", {})
        brief = require_brief_flags(
            brief_data.get("why"),
            brief_data.get("what"),
            brief_data.get("done"),
            brief_data.get("how"),
        )
    else:
        if not args.title:
            error("Title is required (or pipe JSON to stdin)")

        title = args.title
        parent = args.parent
        explicit_type = None

        # Get brief: interactive prompts or flags
        if sys.stdin.isatty() and not (args.why and args.what and args.done):
            brief = prompt_brief()
        else:
            brief = require_brief_flags(args.why, args.what, args.done, getattr(args, 'how', None))

    # Normalize title: single line, trimmed
    title = " ".join(title.split())
    if not title:
        error("Title cannot be empty")

    items = load_items()
    prefix = load_prefix()
    existing_ids = {i["id"] for i in items}
    # Include archived IDs to prevent collisions with archived items
    existing_ids.update(i["id"] for i in load_archive())

    # Determine item type: explicit type from JSON, or inferred from parent
    is_action = bool(parent) or explicit_type == "action"

    # Lint outcome titles for activity language (skip for actions)
    if not is_action:
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
    elif is_action:
        # Standalone action (explicit type, no parent)
        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "action",
            "title": title,
            "brief": brief,
            "status": "open",
            "parent": None,
            "order": next_order(items, "action", None),
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
        filtered = limit_items(filtered, args.limit)
        print(format_json(filtered))
    elif args.jsonl:
        filtered = filter_items_for_output(items, filter_mode)
        filtered = limit_items(filtered, args.limit)
        print(format_jsonl(filtered))
    else:
        output = format_hierarchical(items, filter_mode, limit=args.limit)
        print(output)


def cmd_show(args):
    """Show details for a single item."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()

    # --current: show active tactical action (for hook injection)
    if args.current:
        session = get_session_identity()
        active = find_active_tactical(items, session=session)
        if not active:
            active = find_no_complete_tactical(items, session=session)
        if not active:
            orphan = find_orphaned_tactical(items, session)
            if orphan:
                print(f"Orphaned tactical: {orphan['id']} ({orphan['title']})")
                print(f"Old session no longer exists: {orphan['tactical']['session']}")
                print(f"Run `bon work {orphan['id']}` to re-claim")
            return  # Exit 0 either way
        print(f"Working: {active['title']} ({active['id']})")
        print(format_tactical(active["tactical"], action_status=active["status"]))
        return

    if not args.id:
        error("Usage: bon show <id> or bon show --current")

    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    if args.json:
        item_copy = _normalize_brief(item)
        if item["type"] == "outcome":
            item_copy["actions"] = sorted(
                [_normalize_brief(i) for i in items if i.get("parent") == item["id"]],
                key=lambda x: x.get("order", DEFAULT_ORDER)
            )
        print(json.dumps(item_copy, indent=2, ensure_ascii=False))
        return

    # Header
    status_icon = "✓" if item["status"] == "done" else "○"
    print(f"{status_icon} {item['title']} ({item['id']})")
    print(f"   Type: {item['type']}")
    print(f"   Status: {item['status']}")
    print(f"   Created: {item['created_at']} by {item['created_by']}")
    if item.get("updated_at"):
        updated_by = item.get("updated_by", "updated")
        print(f"   Updated: {item['updated_at']} ({updated_by})")
    if item.get("done_note"):
        print(f"   Note: {item['done_note']}")

    if item.get("waiting_for"):
        blockers = item["waiting_for"]
        wf_str = ", ".join(blockers) if isinstance(blockers, list) else str(blockers)
        wf_line = f"   Waiting for: {wf_str}"
        if item.get("wait_note"):
            wf_line += f" ({item['wait_note']})"
        print(wf_line)

    # Brief
    brief = item.get("brief", {})
    if brief:
        print(f"\n   --why: {brief.get('why', 'N/A')}")
        if brief.get("how"):
            print(f"   --how: {brief['how']}")
        print(f"   --what: {brief.get('what', 'N/A')}")
        print(f"   --done: {brief.get('done', 'N/A')}")

    # Tactical steps (actions only)
    if item.get("tactical"):
        tactical = item["tactical"]
        total = len(tactical["steps"])
        current = tactical["current"]
        if current < total or (current >= total and item["status"] == "open"):
            print(f"\n   Steps ({current}/{total}):")
            for line in format_tactical(tactical, action_status=item["status"]).split("\n"):
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
                wf = action.get("waiting_for")
                waiting = f" ⏳ {', '.join(wf)}" if wf else ""
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
    note = getattr(args, "note", None)
    if note:
        item["done_note"] = note

    # Clear tactical steps (action is done, steps are moot)
    item.pop("tactical", None)

    # CRITICAL: Unblock waiters - remove this ID from all waiting_for lists
    unblocked = []
    for other in items:
        blockers = other.get("waiting_for") or []
        if item["id"] in blockers:
            blockers.remove(item["id"])
            other["waiting_for"] = blockers if blockers else None
            if not other["waiting_for"]:
                other.pop("wait_note", None)
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

    # Append to blockers list (idempotent)
    blockers = item.get("waiting_for") or []
    if reason not in blockers:
        blockers.append(reason)
    item["waiting_for"] = blockers
    note = getattr(args, "note", None)
    if note:
        item["wait_note"] = note
    item["updated_at"] = now_iso()
    item["updated_by"] = "waited"
    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
        print(f"{item['id']} now waiting for: {reason}")


def cmd_unwait(args):
    """Clear waiting status (all blockers, or a specific one)."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    blocker = getattr(args, "blocker", None)
    if blocker:
        # Remove specific blocker
        blockers = item.get("waiting_for") or []
        if blocker in blockers:
            blockers.remove(blocker)
        item["waiting_for"] = blockers if blockers else None
        if not item["waiting_for"]:
            item.pop("wait_note", None)
    else:
        # Clear all blockers
        item["waiting_for"] = None
        item.pop("wait_note", None)

    item["updated_at"] = now_iso()
    item["updated_by"] = "unwaited"
    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    elif item.get("waiting_for"):
        remaining = ", ".join(item["waiting_for"])
        print(f"{item['id']} removed {blocker}, still waiting for: {remaining}")
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
        args.how is not None,
        args.what,
        args.done,
        args.order is not None,
    ])
    if not has_edit:
        error("At least one edit flag required: --title, --outcome, --why, --how, --what, --done, --order")

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
    if args.how is not None:
        if args.how:
            edited["brief"]["how"] = args.how
        else:
            edited["brief"].pop("how", None)
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

    edited["updated_at"] = now_iso()
    edited["updated_by"] = "edited"

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
        # Validate parent if given
        old_parent = None
        if args.parent:
            parent = find_by_id(items, args.parent, prefix)
            if not parent:
                error(f"Parent '{args.parent}' not found")
            if parent["type"] != "outcome":
                error(f"Parent must be an outcome, got {parent['type']}")
            new_parent = parent["id"]
        else:
            new_parent = None

        # Check for children
        children = [i for i in items if i.get("parent") == item["id"]]
        if children and not args.force:
            dest = f"action under {args.parent}" if args.parent else "standalone action"
            error(f"Outcome has {len(children)} children. Use --force to convert to {dest} (children become standalone).")

        # Orphan children (make standalone actions)
        for child in children:
            apply_reparent(items, child, item["id"], None)
            child["parent"] = None

        # Convert outcome → action (standalone if no --outcome given)
        item["type"] = "action"
        item["parent"] = new_parent
        item["waiting_for"] = None
        item.pop("wait_note", None)
        if new_parent:
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

    item["updated_at"] = now_iso()
    item["updated_by"] = "converted"
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
        item["updated_at"] = now_iso()
        item["updated_by"] = "archived"
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
            archive_item["updated_at"] = now_iso()
            archive_item["updated_by"] = "reopened"
            items.append(archive_item)
            save_items(items)
            print(f"Reopened: {archive_item['id']} (restored from archive)")
            return
        error(f"Item '{args.id}' not found")

    if item["status"] != "done":
        error(f"Item '{args.id}' is already open")

    item["status"] = "open"
    item.pop("done_at", None)
    item["updated_at"] = now_iso()
    item["updated_by"] = "reopened"
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
        if item.get("updated_at"):
            events.append({
                "time": item["updated_at"],
                "verb": item.get("updated_by", "updated"),
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
            entry = {
                "time": e["time"],
                "verb": e["verb"],
                "id": e["item"]["id"],
                "title": e["item"]["title"],
                "type": e["item"]["type"],
            }
            if e["verb"] == "completed" and e["item"].get("done_note"):
                entry["note"] = e["item"]["done_note"]
            log_entries.append(entry)
        print(json.dumps(log_entries, indent=2, ensure_ascii=False))
        return

    for e in events:
        # Compact timestamp: strip seconds and Z for readability
        t = e["time"][:16].replace("T", " ")
        icon = {"created": "+", "completed": "✓", "archived": "⌂"}.get(e["verb"], "~")
        line = f"  {icon} {t}  {e['verb']} {e['item']['title']} ({e['item']['id']})"
        if e["verb"] == "completed" and e["item"].get("done_note"):
            line += f" — {e['item']['done_note']}"
        print(line)


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
    session = get_session_identity()

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
            active = find_no_complete_tactical(items, session=session)
        if not active:
            orphan = find_orphaned_tactical(items, session)
            if orphan:
                print(f"Orphaned tactical: {orphan['id']} ({orphan['title']})")
                print(format_tactical(orphan["tactical"], action_status=orphan["status"]))
                print(f"\nOld session no longer exists. Run `bon work {orphan['id']}` to re-claim.")
            else:
                print("No active tactical steps. Run `bon work <id>` to start.")
            return
        print(f"Working on: {active['title']} ({active['id']})")
        print()
        print(format_tactical(active["tactical"], action_status=active["status"]))
        return

    # --clear: clear active tactical (scoped to CWD)
    if args.clear:
        active = find_active_tactical(items, session=session)
        if not active:
            return  # Silent success
        active.pop("tactical", None)
        active["updated_at"] = now_iso()
        active["updated_by"] = "cleared"
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
    orphaned_reclaim = False
    for other in all_active:
        if other["id"] == item["id"]:
            other_session = other.get("tactical", {}).get("session")
            if other_session and other_session != session:
                if os.path.isdir(other_session):
                    error(f"{item['id']} has active steps from another worktree ({other_session})")
                else:
                    orphaned_reclaim = True

    # Serial enforcement scoped to THIS session
    active = find_active_tactical(items, session=session)
    if active and active["id"] != item["id"]:
        error(f"{active['id']} has active steps. Complete it, wait it, or run `bon work --clear`")

    # Check for existing progress
    existing = item.get("tactical")
    if orphaned_reclaim and existing and not args.force:
        # Re-claim orphaned tactical: preserve steps and progress, update session
        old_session = existing.get("session", "unknown")
        item["tactical"]["session"] = session
        item["updated_at"] = now_iso()
        item["updated_by"] = "reclaimed"
        save_items(items)
        print(f"Re-claimed from {old_session} (directory no longer exists)")
        print()
        print(format_tactical(item["tactical"]))
        return
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
    item["updated_at"] = now_iso()
    item["updated_by"] = "worked"
    save_items(items)

    how = item.get("brief", {}).get("how")
    if how:
        print(f"Approach: {how}")
        print()
    print(format_tactical(item["tactical"]))


def cmd_step(args):
    """Advance to next tactical step, auto-complete on final."""
    check_initialized()
    items = load_items()
    session = get_session_identity()

    active = find_active_tactical(items, session=session)
    if not active:
        # Check for orphaned tactical before generic suggestions
        orphan = find_orphaned_tactical(items, session)
        if orphan:
            error(
                f"No steps in this session, but {orphan['id']} ({orphan['title']}) has orphaned steps "
                f"from a directory that no longer exists.\n"
                f"Run `bon work {orphan['id']}` to re-claim"
            )
        # Find most recently worked/stepped action as a suggestion
        worked = [
            i for i in items
            if i["type"] == "action" and i["status"] == "open"
            and i.get("updated_by") in ("worked", "stepped")
        ]
        if worked:
            last = max(worked, key=lambda i: i.get("updated_at", ""))
            error(
                f"No steps in progress. Last worked: {last['id']} ({last['title']})\n"
                f"Run `bon work {last['id']}` to resume"
            )
        error("No steps in progress. Run `bon work <id>` first")

    tactical = active["tactical"]
    current = tactical["current"]
    steps = tactical["steps"]

    # Record skip if requested
    skip_reason = getattr(args, "skip", None)
    if skip_reason:
        skipped = tactical.setdefault("skipped", {})
        skipped[str(current)] = skip_reason

    # Advance
    tactical["current"] = current + 1
    active["updated_at"] = now_iso()
    active["updated_by"] = "stepped"

    no_complete = getattr(args, "no_complete", False)

    # Check if complete
    if tactical["current"] >= len(steps):
        if no_complete:
            # All steps done but don't auto-complete the action
            save_items(items)
            print(format_tactical(tactical))
            print(f"\nAll steps done. Action {active['id']} left open (--no-complete).")
        else:
            # Auto-complete the action
            active["status"] = "done"
            active["done_at"] = now_iso()
            # Unblock waiters
            for other in items:
                blockers = other.get("waiting_for") or []
                if active["id"] in blockers:
                    blockers.remove(active["id"])
                    other["waiting_for"] = blockers if blockers else None
                    if not other["waiting_for"]:
                        other.pop("wait_note", None)
            save_items(items)
            print(format_tactical(tactical))
            print(f"\nAction {active['id']} complete.")
    else:
        save_items(items)
        print(format_tactical(tactical))
        print(f"\nNext: {steps[tactical['current']]}")


def cmd_migrate(args):
    """Migrate between storage backends (jsonl ↔ dolt)."""
    check_initialized()
    target = args.to

    if target not in ("jsonl", "dolt"):
        error(f"Unknown backend '{target}'. Use 'jsonl' or 'dolt'.")

    current = _get_backend()
    if current == target:
        print(f"Already using {target} backend.")
        return

    bon_dir = Path(".bon")

    if target == "dolt":
        # Verify Dolt is reachable before touching any state
        from bon.dolt import verify_dolt_connection
        verify_dolt_connection()

        # Migrate JSONL → Dolt: load from files, write to Dolt
        items = load_items()  # Still JSONL at this point
        archive = load_archive()

        # Switch backend
        (bon_dir / "backend").write_text("dolt")
        from bon.storage import _reset_backend
        _reset_backend()

        # Write to Dolt
        if items:
            save_items(items)
        if archive:
            append_archive(archive)

        # Rename stale JSONL so hooks/scripts don't read outdated data
        items_file = bon_dir / "items.jsonl"
        if items_file.exists():
            items_file.rename(bon_dir / "items.jsonl.pre-dolt")
        archive_file = bon_dir / "archive.jsonl"
        if archive_file.exists():
            archive_file.rename(bon_dir / "archive.jsonl.pre-dolt")

        print(f"Migrated {len(items)} items and {len(archive)} archived items to Dolt.")

    elif target == "jsonl":
        # Migrate Dolt → JSONL: load from Dolt, write to files
        items = load_items()  # Still Dolt at this point
        archive = load_archive()

        # Switch backend
        if (bon_dir / "backend").exists():
            (bon_dir / "backend").unlink()
        from bon.storage import _reset_backend
        _reset_backend()

        # Ensure items.jsonl exists
        items_file = bon_dir / "items.jsonl"
        if not items_file.exists():
            items_file.touch()

        # Write to JSONL
        if items:
            save_items(items)
        if archive:
            append_archive(archive)

        print(f"Migrated {len(items)} items and {len(archive)} archived items to JSONL.")


try:
    from importlib.metadata import version as _meta_version
    __version__ = _meta_version("bon")
except Exception:
    __version__ = "0.0.0"


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


def cmd_doctor(args):
    """Check items.jsonl for health issues."""
    check_initialized()

    if _get_backend() == "dolt":
        # In Dolt mode, validate loaded items (no file-level checks)
        items = load_items()
        archived = load_archive()
        issues = []
        all_ids = {i["id"] for i in items}
        for item in items:
            brief = item.get("brief")
            if not brief or not isinstance(brief, dict):
                issues.append(f"{item['id']}: missing brief")
            elif any(k not in brief for k in ("why", "what", "done")):
                issues.append(f"{item['id']}: incomplete brief")
            parent_id = item.get("parent")
            if parent_id and parent_id not in all_ids:
                issues.append(f"{item['id']}: parent '{parent_id}' does not exist")
        if issues:
            for issue in issues:
                print(f"  {issue}")
            print(f"\n{len(issues)} issue(s) found.")
        else:
            print(f"Dolt backend: {len(items)} items, {len(archived)} archived. All clear.")
        return

    path = items_path()
    issues = []

    if not path.exists():
        print("No items.jsonl found — nothing to check.")
        return

    raw_text = path.read_text()
    lines = raw_text.splitlines()

    # --- Phase 1: Raw-file checks ---
    seen_ids: dict[str, list[int]] = {}  # id -> list of line numbers
    parsed_items: list[tuple[int, dict]] = []  # (line_num, item)

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Git conflict markers
        if stripped.startswith(("<<<<<<", "======", ">>>>>>")):
            issues.append(f"line {line_num}: git conflict marker")
            continue

        # Malformed JSON
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as e:
            issues.append(f"line {line_num}: malformed JSON — {e}")
            continue

        parsed_items.append((line_num, item))

        # Track IDs for duplicate detection
        item_id = item.get("id")
        if item_id:
            seen_ids.setdefault(item_id, []).append(line_num)

    # Report duplicates
    for item_id, line_nums in seen_ids.items():
        if len(line_nums) > 1:
            nums = ", ".join(str(n) for n in line_nums)
            issues.append(f"duplicate ID '{item_id}' on lines {nums}")

    # --- Phase 2: Per-item schema checks ---
    valid_items: list[dict] = []
    for line_num, item in parsed_items:
        # Basic structure
        for field in ("id", "type", "title", "status", "created_at", "created_by"):
            if field not in item:
                issues.append(f"line {line_num}: missing required field '{field}'")

        if item.get("type") not in ("outcome", "action"):
            issues.append(f"line {line_num}: invalid type '{item.get('type')}'")
        if item.get("status") not in ("open", "done"):
            issues.append(f"line {line_num}: invalid status '{item.get('status')}'")

        # Brief completeness
        brief = item.get("brief")
        if not brief:
            issues.append(f"line {line_num} ({item.get('id', '?')}): missing brief")
        elif isinstance(brief, dict):
            for subfield in ("why", "what", "done"):
                if subfield not in brief:
                    issues.append(f"line {line_num} ({item.get('id', '?')}): missing brief.{subfield}")

        # updated_by verb validation
        verb = item.get("updated_by")
        if verb and verb not in KNOWN_VERBS:
            issues.append(f"line {line_num} ({item.get('id', '?')}): unknown updated_by verb '{verb}'")

        # Tactical validation
        tactical = item.get("tactical")
        if tactical:
            try:
                validate_tactical(tactical)
            except Exception as e:
                issues.append(f"line {line_num} ({item.get('id', '?')}): bad tactical — {e}")

        # Type-specific field rules
        if item.get("type") == "outcome":
            if item.get("waiting_for"):
                issues.append(f"line {line_num} ({item.get('id', '?')}): outcome has waiting_for")
            if item.get("tactical"):
                issues.append(f"line {line_num} ({item.get('id', '?')}): outcome has tactical")

        valid_items.append(item)

    # --- Phase 3: Cross-item referential integrity ---
    all_ids = {item.get("id") for item in valid_items if item.get("id")}
    prefix = load_prefix()

    for item in valid_items:
        # Parent references
        parent_id = item.get("parent")
        if parent_id and parent_id not in all_ids:
            issues.append(f"{item['id']}: parent '{parent_id}' does not exist")

        # Parent must be an outcome
        if parent_id and parent_id in all_ids:
            parent = next((i for i in valid_items if i.get("id") == parent_id), None)
            if parent and parent.get("type") != "outcome":
                issues.append(f"{item['id']}: parent '{parent_id}' is not an outcome")

        # waiting_for references (only check ID-shaped values)
        wf = item.get("waiting_for")
        if wf:
            blockers = wf if isinstance(wf, list) else [wf]
            for blocker in blockers:
                if "-" in blocker and blocker not in all_ids:
                    issues.append(f"{item['id']}: waiting_for '{blocker}' does not exist")

    # Check order gaps/duplicates among siblings
    from collections import defaultdict
    siblings_by_parent: dict[str | None, list[dict]] = defaultdict(list)
    for item in valid_items:
        if item.get("type") == "action" and item.get("status") == "open":
            siblings_by_parent[item.get("parent")].append(item)

    for parent_id, siblings in siblings_by_parent.items():
        orders = [s.get("order") for s in siblings if s.get("order") is not None]
        if len(orders) != len(set(orders)):
            dupes = [o for o in orders if orders.count(o) > 1]
            label = parent_id or "standalone"
            issues.append(f"under {label}: duplicate order values {sorted(set(dupes))}")

    # --- Output ---
    if issues:
        for issue in issues:
            print(f"  {issue}")
        print(f"\n{len(issues)} issue(s) found.")
    else:
        print("All clear.")


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
    init_parser.add_argument("--backend", default="jsonl", choices=["jsonl", "dolt"],
                             help="Storage backend (default: jsonl)")
    init_parser.set_defaults(func=cmd_init)

    # new
    new_parser = subparsers.add_parser("new", help="Create outcome or action")
    new_parser.add_argument("title", nargs="?", default=None, help="Title for the item")
    new_parser.add_argument("--json", action="store_true", dest="json_input", help="Read item as JSON from stdin")
    new_parser.add_argument("--outcome", "--for", "--parent", dest="parent", help="Parent outcome ID (creates action)")
    new_parser.add_argument("--why", help="Brief: why are we doing this?")
    new_parser.add_argument("--how", help="Brief: how will we approach it? (optional)")
    new_parser.add_argument("--what", help="Brief: what will we produce?")
    new_parser.add_argument("--done", help="Brief: how do we know it's done?")
    add_output_flags(new_parser, quiet=True)
    new_parser.set_defaults(func=cmd_new)

    # list
    list_parser = subparsers.add_parser("list", help="List items")
    list_parser.add_argument("--ready", action="store_true", help="Show only ready items")
    list_parser.add_argument("--waiting", action="store_true", help="Show only waiting items")
    list_parser.add_argument("--all", action="store_true", help="Include done items")
    list_parser.add_argument("--limit", type=int, default=None,
                             help="Truncate to first N top-level items (outcomes + standalones); children of kept outcomes always come along")
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
    done_parser.add_argument("--note", help="Completion context (why/how it was done)")
    add_output_flags(done_parser, quiet=True)
    done_parser.set_defaults(func=cmd_done)

    # wait
    wait_parser = subparsers.add_parser("wait", help="Mark item as waiting")
    wait_parser.add_argument("id", help="Item ID")
    wait_parser.add_argument("reason", help="What it's waiting for (ID or text)")
    wait_parser.add_argument("--note", help="Why it's waiting (context for future sessions)")
    add_output_flags(wait_parser, quiet=True)
    wait_parser.set_defaults(func=cmd_wait)

    # unwait
    unwait_parser = subparsers.add_parser("unwait", help="Clear waiting status")
    unwait_parser.add_argument("id", help="Item ID")
    unwait_parser.add_argument("blocker", nargs="?", help="Specific blocker to remove (omit to clear all)")
    add_output_flags(unwait_parser, quiet=True)
    unwait_parser.set_defaults(func=cmd_unwait)

    # edit
    edit_parser = subparsers.add_parser("edit", help="Edit item fields")
    edit_parser.add_argument("id", help="Item ID to edit")
    edit_parser.add_argument("--title", help="New title")
    edit_parser.add_argument("--outcome", "--parent", dest="parent", help="New parent outcome ID (use 'none' to make standalone)")
    edit_parser.add_argument("--why", help="New brief.why")
    edit_parser.add_argument("--how", help="New brief.how (approach/strategy)")
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
    step_parser.add_argument("--skip", metavar="REASON", help="Skip current step with a reason instead of completing it")
    step_parser.add_argument("--no-complete", action="store_true", help="Don't auto-complete action on final step")
    step_parser.set_defaults(func=cmd_step)

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

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Check items.jsonl for health issues")
    doctor_parser.set_defaults(func=cmd_doctor)

    # migrate
    migrate_parser = subparsers.add_parser("migrate", help="Migrate between backends")
    migrate_parser.add_argument("--to", required=True, choices=["jsonl", "dolt"],
                                help="Target backend")
    migrate_parser.set_defaults(func=cmd_migrate)

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
