"""Arc CLI - main entry point."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from arc.storage import (
    load_items,
    save_items,
    load_prefix,
    find_by_id,
    get_creator,
    now_iso,
    error,
    check_initialized,
    ValidationError,
    validate_item,
    apply_reorder,
)
from arc.ids import generate_unique_id, next_order
from arc.display import format_hierarchical, format_json, format_jsonl


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

    arc_dir = Path(".arc")
    if arc_dir.exists():
        print(f".arc/ already exists")
        return

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
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    if args.json:
        # For outcomes, include actions
        if item["type"] == "outcome":
            item_copy = dict(item)
            item_copy["actions"] = sorted(
                [i for i in items if i.get("parent") == item["id"]],
                key=lambda x: x.get("order", 999)
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
        print(f"\n   Why: {brief.get('why', 'N/A')}")
        print(f"   What: {brief.get('what', 'N/A')}")
        print(f"   Done: {brief.get('done', 'N/A')}")

    # For outcomes, show actions
    if item["type"] == "outcome":
        actions = sorted(
            [i for i in items if i.get("parent") == item["id"]],
            key=lambda x: x.get("order", 999)
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


def validate_edit(original: dict, edited: dict, all_items: list[dict]):
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

    # Parent must exist if specified
    if edited.get("parent"):
        parent = find_by_id(all_items, edited["parent"])
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
    """Edit item in $EDITOR."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        error(f"Item '{args.id}' not found")

    old_order = item.get("order")

    # Write to temp file as formatted JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(item, f, indent=2, ensure_ascii=False)
        f.write('\n')
        temp_path = f.name

    try:
        # Open in editor
        editor = os.environ.get("EDITOR", "vim")
        result = subprocess.run([editor, temp_path])
        if result.returncode != 0:
            error(f"Editor exited with code {result.returncode}")

        # Read back
        with open(temp_path) as f:
            try:
                edited = json.load(f)
            except json.JSONDecodeError as e:
                error(f"Invalid JSON: {e}")

        # Validate
        validate_edit(item, edited, items)

        # Handle reorder if order changed
        new_order = edited.get("order")
        if old_order != new_order:
            apply_reorder(items, edited, old_order, new_order)

        # Update in list
        for i, existing in enumerate(items):
            if existing["id"] == item["id"]:
                items[i] = edited
                break

        save_items(items)
        print(f"Updated: {item['id']}")
    finally:
        os.unlink(temp_path)


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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="arc",
        description="Work tracker for Claude-human collaboration"
    )
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
    show_parser.add_argument("id", help="Item ID to show")
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
    edit_parser = subparsers.add_parser("edit", help="Edit item in $EDITOR")
    edit_parser.add_argument("id", help="Item ID to edit")
    edit_parser.set_defaults(func=cmd_edit)

    # status
    status_parser = subparsers.add_parser("status", help="Show status overview")
    status_parser.set_defaults(func=cmd_status)

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
