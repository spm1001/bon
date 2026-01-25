"""Arc CLI - main entry point."""
import argparse
import sys
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
)
from arc.ids import generate_unique_id, next_order
from arc.display import format_hierarchical


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
    new_parser.set_defaults(func=cmd_new)

    # list
    list_parser = subparsers.add_parser("list", help="List items")
    list_parser.add_argument("--ready", action="store_true", help="Show only ready items")
    list_parser.add_argument("--waiting", action="store_true", help="Show only waiting items")
    list_parser.add_argument("--all", action="store_true", help="Include done items")
    list_parser.set_defaults(func=cmd_list)

    # show
    show_parser = subparsers.add_parser("show", help="View item details")
    show_parser.add_argument("id", help="Item ID to show")
    show_parser.set_defaults(func=cmd_show)

    # done
    done_parser = subparsers.add_parser("done", help="Complete item")
    done_parser.add_argument("id", help="Item ID to mark done")
    done_parser.set_defaults(func=cmd_done)

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
