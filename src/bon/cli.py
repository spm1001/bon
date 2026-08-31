"""Bon CLI - main entry point."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bon import _invlog
from bon.display import _normalize_brief, format_grouped_by_area, format_hierarchical, format_json, format_jsonl, format_tactical
from bon.queries import open_child_parent_ids, someday_ids
from bon.ids import DEFAULT_ORDER, generate_unique_id, next_order
from bon.storage import (
    BOARD_README,
    KNOWN_VERBS,
    BonError,
    ValidationError,
    _data_dir,
    _get_backend,
    _tactical_is_active,
    append_archive,
    apply_reorder,
    apply_reparent,
    archive_ids_at,
    check_initialized,
    error,
    find_active_tactical,
    find_any_active_tactical,
    find_by_id,
    find_no_complete_tactical,
    find_orphaned_tactical,
    find_released_tactical,
    get_creator,
    get_session_identity,
    items_path,
    load_archive,
    load_items,
    load_items_at,
    load_prefix,
    now_iso,
    refresh_bottle,
    remove_from_archive,
    save_items,
    save_items_at,
    target_board,
    validate_item,
    validate_tactical,
    warn,
)


def filter_items_for_output(items: list[dict], filter_mode: str) -> list[dict]:
    """Filter items based on mode for output.

    Used by --json and --jsonl to respect filter flags.
    Done outcomes with open children count as board-visible (bon-kegewe).
    Parked (someday) subtrees are excluded from every mode except "all" and
    the dedicated "someday" view — mirroring format_hierarchical.
    """
    parked_ids = someday_ids(items)
    if filter_mode == "someday":
        return [i for i in items if i["id"] in parked_ids]
    if filter_mode != "all":
        items = [i for i in items if i["id"] not in parked_ids]

    open_parents = open_child_parent_ids(items)

    def board_visible(outcome):
        return outcome["status"] == "open" or outcome["id"] in open_parents

    if filter_mode == "ready":
        # Visible outcomes + ready and done actions (done shown for context)
        outcomes = [i for i in items if i["type"] == "outcome" and board_visible(i)]
        actions = [i for i in items if i["type"] == "action" and
                   (i["status"] == "done" or (i["status"] == "open" and not i.get("waiting_for")))]
        return outcomes + actions
    elif filter_mode == "waiting":
        # Visible outcomes + waiting actions only
        outcomes = [i for i in items if i["type"] == "outcome" and board_visible(i)]
        actions = [i for i in items if i["type"] == "action" and i.get("waiting_for")]
        return outcomes + actions
    elif filter_mode == "all":
        return items
    else:
        # Default: visible outcomes and all their actions
        outcomes = [i for i in items if i["type"] == "outcome" and board_visible(i)]
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


DISCOVERY_STANZA = """\
To help agents discover this board, add two lines to the repo's CLAUDE.md
and/or AGENTS.md:

  Work is tracked on a bon board in `.bon/` — read `.bon/README.md`
  before reading or changing anything there."""


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
    completing = False
    if bon_dir.exists():
        if (bon_dir / "prefix").is_file():
            error(".bon/ already exists.")
        # A .bon without a prefix is a fresh clone whose local markers were
        # gitignored — complete it rather than refuse (the reconnect path
        # check_initialized recommends). Existing files are untouched.
        completing = True
    else:
        bon_dir.mkdir()

    (bon_dir / "prefix").write_text(prefix)  # No trailing newline
    # Unconditional: a reconnect refreshes a clone's bottle to current wording.
    refresh_bottle(bon_dir)

    verb = "Reconnected" if completing else "Initialized"
    if backend == "dolt":
        (bon_dir / "backend").write_text("dolt")
        print(f"{verb} .bon/ with prefix '{prefix}' (backend: dolt)")
        # Register in the shared repos mapping table. Soft-fail: an offline
        # init stays valid — the board self-registers on its first write.
        try:
            from bon.dolt import dolt_register_repo
            dolt_register_repo(prefix)
            print(f"Registered '{prefix}' in the Dolt repos table.")
        except BonError as e:
            print(
                f"Warning: could not register '{prefix}' in the Dolt repos "
                f"table ({e}). The board self-registers on first write, "
                f"or run `bon register` later.",
                file=sys.stderr,
            )
    else:
        if not (bon_dir / "items.jsonl").exists():
            (bon_dir / "items.jsonl").touch()
        # Board-local merge attributes: concurrent clones' different-item
        # edits union cleanly under the CLI-owned sync (bon-guritu).
        if not (bon_dir / ".gitattributes").exists():
            from bon.gitsync import GITATTRIBUTES_CONTENT
            (bon_dir / ".gitattributes").write_text(GITATTRIBUTES_CONTENT)
        print(f"{verb} .bon/ with prefix '{prefix}'")

    print()
    print(DISCOVERY_STANZA)


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


def require_brief_flags(
    why: str | None,
    what: str | None,
    done: str | None,
    how: str | None = None,
    badly: str | None = None,
) -> dict:
    """Validate brief flags for non-interactive creation.

    --why, --what, --done are required. --how and --badly are optional.
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
    if badly:
        brief["badly"] = badly
    return brief


def check_falsifier_placement(item_type: str, badly: str | None) -> None:
    """Nudge, don't refuse, when a falsifier lands on an action.

    GTD's Natural Planning Model puts purpose AND PRINCIPLES in phase 1, and
    bon's brief kept the purpose half (--why) while dropping principles. The
    falsifier restores it — but principles are a property of a *direction*,
    which is what an outcome is. "Fix the racing temp path" needs no
    pre-registered falsifier; "Concurrent sessions can't corrupt each other's
    bookkeeping" very much does.

    Coaching rather than validation deliberately: the data layer has no
    business refusing a field someone had a reason to write, and a hard error
    here would be the tracker second-guessing the delegator.
    """
    if badly and item_type == "action":
        warn(
            "--badly on an action. A falsifier is usually an outcome-level object —\n"
            "  it says what would show the whole direction was wrong, and that is what\n"
            "  a reviewer checks it against. Keeping it, but consider whether it belongs\n"
            "  on the parent outcome instead."
        )


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


def item_not_found(item_id: str, prefix: str, noun: str = "Item"):
    """Lookup-miss error that names the board searched and where it resolved.

    A wrong-cwd read returns a clean null that reads exactly like a real
    absence — the session that filed this had reported a done item as
    missing because an earlier cd had quietly moved the board under it
    (bon-vomuzi). Naming the board makes the null self-diagnosing; when the
    id's own prefix isn't this board's, say the likelier truth outright.
    """
    if not prefix:
        # A caller without board context (validate_edit's default) still errors
        # cleanly rather than naming a board 'None'.
        error(f"{noun} '{item_id}' not found")
    board = f"board '{prefix}' (cwd: {os.getcwd()})"
    id_prefix = item_id.rsplit("-", 1)[0] if "-" in item_id else None
    if id_prefix and id_prefix != prefix:
        error(
            f"{noun} '{item_id}' not found on {board} — id prefix "
            f"'{id_prefix}' doesn't match this board: wrong directory?"
        )
    error(f"{noun} '{item_id}' not found on {board}")



# Top-level keys the JSON creation path honours. Anything else is a hard
# error (bon-gezela): a silently-dropped key looks exactly like success —
# the contract bon edit already holds (bon-cefisu). Brief subfields
# (EDIT_BRIEF_KEYS) are accepted nested under "brief" or flat.
NEW_TOP_KEYS = ("title", "type", "parent", "outcome", "brief", "waiting_for", "area")


def waiting_for_from_json(value):
    """Normalise a JSON waiting_for value to a list of blockers, or None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(
        isinstance(w, str) and w.strip() for w in value
    ):
        error("'waiting_for' must be a string or a list of non-empty strings")
    return value or None


def _jsonl_staleness_warning() -> str | None:
    """One-line warning when the JSONL board is behind the last-fetched origin (bon-wevodu).

    Deliberately no fetch here: a fetch per CLI call is network I/O at ~20
    calls a session, so the /open rite owns the once-per-session fetch and
    this compares against its result. That makes the check one-sided — it can
    prove staleness, never freshness. An unfetched clone reads clean, which is
    the passe-partout incident's exact blindness; the rite's fetch is what
    keeps this honest for the rest of the session.
    """
    if _get_backend() == "dolt":
        return None
    try:
        board_file = items_path()
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{upstream}", "--", str(board_file)],
            cwd=board_file.parent, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None  # no git, no upstream, detached — nothing to compare against
        behind = int(result.stdout.strip() or 0)
        if behind > 0:
            return (
                f"items.jsonl is {behind} commit(s) behind the last-fetched origin — "
                "the board view may be stale, and this item may duplicate one filed "
                "on another clone (bon-wevodu). Pull before trusting the board."
            )
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def cmd_new(args):
    """Create a new outcome or action."""
    check_initialized()

    # JSON is the default input when stdin is piped and no title given.
    # Flags are the shorthand for quick stubs with a title on the command line.
    use_json = getattr(args, 'json_input', False) or (not args.title and not sys.stdin.isatty())

    waiting_for = None
    if use_json:
        # JSON from stdin — structured input, no shell escaping needed
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            error(f"Invalid JSON on stdin: {e}")
        if not isinstance(data, dict):
            error('JSON on stdin must be an object, e.g. {"title": "...", "brief": {...}}')

        brief_data = data.get("brief", {})
        if not isinstance(brief_data, dict):
            error("'brief' must be an object")

        unknown = (set(data) | set(brief_data)) - set(NEW_TOP_KEYS) - set(EDIT_BRIEF_KEYS)
        if unknown:
            error(
                f"Unknown field(s): {', '.join(sorted(unknown))}\n"
                "Valid: title, type, parent (or outcome), waiting_for, area, "
                "brief{why, how, what, done, badly} — brief fields may also be given flat."
            )

        for key in EDIT_BRIEF_KEYS:
            if key in data and key in brief_data:
                error(f"'{key}' given both flat and inside 'brief' — pick one")
            if key in data:
                brief_data[key] = data[key]
            if key in brief_data and not isinstance(brief_data[key], str):
                error(f"'{key}' must be a string, got {type(brief_data[key]).__name__}")

        title = data.get("title", "")
        if not isinstance(title, str) or not title:
            error("JSON must include 'title' (a string)")

        if "parent" in data or "outcome" in data:
            parent = data.get("parent", data.get("outcome"))
            if parent is not None and not isinstance(parent, str):
                error("'parent' must be a string")
        else:
            parent = args.parent

        explicit_type = data.get("type")
        if explicit_type not in (None, "action", "outcome"):
            error(f"'type' must be 'action' or 'outcome', got {explicit_type!r}")

        waiting_for = waiting_for_from_json(data.get("waiting_for"))

        area = data.get("area")
        if area is not None and not isinstance(area, str):
            error("'area' must be a string")
        area = (area or "").strip() or None

        brief = require_brief_flags(
            brief_data.get("why"),
            brief_data.get("what"),
            brief_data.get("done"),
            brief_data.get("how"),
            brief_data.get("badly"),
        )
    else:
        if not args.title:
            error("Title is required (or pipe JSON to stdin)")

        title = args.title
        parent = args.parent
        explicit_type = None
        area = (getattr(args, "area", None) or "").strip() or None

        # Get brief: interactive prompts or flags
        if sys.stdin.isatty() and not (args.why and args.what and args.done):
            brief = prompt_brief()
        else:
            brief = require_brief_flags(
                args.why, args.what, args.done,
                getattr(args, 'how', None), getattr(args, 'badly', None),
            )

    # Normalize title: single line, trimmed
    title = " ".join(title.split())
    if not title:
        error("Title cannot be empty")

    items = load_items()
    prefix = load_prefix()
    existing_ids = {i["id"] for i in items}
    # Include archived IDs to prevent collisions with archived items
    existing_ids.update(i["id"] for i in load_archive())

    # Same nudge as cmd_wait: an id-shaped blocker that doesn't resolve
    # will never be cleared by the unblock-on-done cascade.
    for blocker in waiting_for or []:
        if re.match(r"^[a-z]+-[a-z]+$", blocker) and not find_by_id(items, blocker, prefix):
            warn(f"'{blocker}' not found in active items — waiting_for may never resolve automatically")

    # Determine item type: explicit type from JSON, or inferred from parent
    is_action = bool(parent) or explicit_type == "action"

    # Lint outcome titles for activity language (skip for actions)
    if not is_action:
        check_outcome_language(title)

    check_falsifier_placement("action" if is_action else "outcome", brief.get("badly"))

    if parent:
        # Validate parent exists and is an outcome
        parent_item = find_by_id(items, parent, prefix)
        if not parent_item:
            item_not_found(parent, prefix, noun="Parent")
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
            "waiting_for": waiting_for,
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
            "waiting_for": waiting_for,
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
        if waiting_for:
            item["waiting_for"] = waiting_for

    if area:
        item["area"] = area
        # Grouped views key on top-level entities — a parented action travels
        # with its outcome's area, so its own tag is inert until it goes
        # standalone. Coaching, not validation (the falsifier-placement pattern).
        if item["type"] == "action" and item.get("parent"):
            warn("area on a parented action is inert in grouped views — it inherits "
                 "its outcome's area. Set the area on the outcome instead.")

    items.append(item)
    save_items(items)
    staleness = _jsonl_staleness_warning()
    if staleness:
        warn(staleness)
    if args.quiet:
        print(item["id"])
    elif waiting_for:
        # The species leads: a bare `bon new TITLE` mints an OUTCOME, and a
        # caller who meant an action gets no error — the announcement is the
        # only signal that converts that silent absorption into a watchable
        # outcome (bon-siciri; the mistake class is invisible to transcript
        # mining precisely because nothing fails).
        print(f"Created {item['type']}: {item['id']} (waiting for: {', '.join(waiting_for)})")
    else:
        print(f"Created {item['type']}: {item['id']}")


def cmd_list(args):
    """List items hierarchically."""
    check_initialized()

    items = load_items()

    # Area filter (bon-razonu): keeps top-level entities in the named area —
    # outcomes with their whole subtree, and standalone actions — mirroring
    # the grouped view's semantics (an action's own area counts only when
    # standalone). Applies to every output format.
    area_filter = getattr(args, "area", None)
    if area_filter:
        keep_outcomes = {
            i["id"] for i in items
            if i["type"] == "outcome" and i.get("area") == area_filter
        }
        items = [
            i for i in items
            if i["id"] in keep_outcomes
            or i.get("parent") in keep_outcomes
            or (i["type"] == "action" and not i.get("parent")
                and i.get("area") == area_filter)
        ]

    # Determine filter mode
    if args.ready:
        filter_mode = "ready"
    elif args.waiting:
        filter_mode = "waiting"
    elif getattr(args, "someday", False):
        filter_mode = "someday"
    elif args.all:
        filter_mode = "all"
    else:
        filter_mode = "default"

    group_by = getattr(args, "group_by", None)
    if group_by:
        # A silently-ignored flag looks exactly like success — refuse the
        # combinations the grouped render doesn't serve rather than no-op.
        if args.json or args.jsonl:
            error("--group-by shapes the text view; with --json/--jsonl read the 'area' field on each item")
        if args.limit is not None:
            error("--limit doesn't combine with --group-by")

    # Handle output format
    if args.json:
        filtered = filter_items_for_output(items, filter_mode)
        filtered = limit_items(filtered, args.limit)
        print(format_json(filtered))
    elif args.jsonl:
        filtered = filter_items_for_output(items, filter_mode)
        filtered = limit_items(filtered, args.limit)
        print(format_jsonl(filtered))
    elif group_by == "area":
        print(format_grouped_by_area(items, filter_mode))
    else:
        output = format_hierarchical(items, filter_mode, limit=args.limit)
        print(output)


def _stamp_with_local(stamp: str) -> str:
    """Render a stored UTC stamp with the local wall-clock time beside it.

    Stored stamps are UTC ('…Z'); a session's sense of time is local. Two
    phantom cross-lane race reports (bon-lomede, bon-dalepu) were manufactured
    by comparing the two directly — an hour of timezone skew inverted a
    causality. Showing both closes the gap at the surface actually read.
    """
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
        return f"{stamp} ({dt.strftime('%Y-%m-%d %H:%M')} local)"
    except (ValueError, TypeError):
        return stamp


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
        item_not_found(args.id, prefix)

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
    if item.get("area"):
        print(f"   Area: {item['area']}")
    print(f"   Created: {_stamp_with_local(item['created_at'])} by {item['created_by']}")
    if item.get("updated_at"):
        updated_by = item.get("updated_by", "updated")
        print(f"   Updated: {_stamp_with_local(item['updated_at'])} ({updated_by})")
    if item.get("done_note"):
        print(f"   Note: {item['done_note']}")

    if item.get("waiting_for"):
        blockers = item["waiting_for"]
        wf_str = ", ".join(blockers) if isinstance(blockers, list) else str(blockers)
        wf_line = f"   Waiting for: {wf_str}"
        if item.get("wait_note"):
            wf_line += f" ({item['wait_note']})"
        print(wf_line)
    elif item.get("released_note"):
        # Why the last block lifted — met, abandoned, decided against
        # (bon-wevapu). Cleared by any fresh `bon wait`.
        print(f"   Released: {item['released_note']}")

    if item.get("someday"):
        print(f"   Someday 🅿️ — revisit: {item['someday']}")

    # Brief
    brief = item.get("brief", {})
    if brief:
        print(f"\n   --why: {brief.get('why', 'N/A')}")
        if brief.get("how"):
            print(f"   --how: {brief['how']}")
        print(f"   --what: {brief.get('what', 'N/A')}")
        print(f"   --done: {brief.get('done', 'N/A')}")
        # Beside --done deliberately: complete, then wrong-way-round. The pair
        # is the point — --done is satisfiable by construction, --badly is not.
        if brief.get("badly"):
            print(f"   --badly: {brief['badly']}")

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
        item_not_found(args.id, prefix)

    if item["status"] == "done":
        # Don't silently discard a note — when another session (or an
        # earlier command in this chain) already closed the item, the
        # note is usually the valuable part (bon-civelu oddity 2)
        note = getattr(args, "note", None)
        if note and not item.get("done_note"):
            item["done_note"] = note
            save_items(items)
            print(f"Already done: {item['id']} (note attached)")
        elif note:
            # A note the caller passed and we will not store must say so
            # audibly (bon-pufezi) — a silent drop reads as recorded.
            print(f"Already done: {item['id']}")
            warn(
                f"note NOT stored — {item['id']} already carries one. "
                f"To replace it: bon edit {item['id']} --note '...'"
            )
        else:
            print(f"Already done: {item['id']}")
        return

    # Mark as done
    item["status"] = "done"
    item["done_at"] = now_iso()
    note = getattr(args, "note", None)
    if note:
        item["done_note"] = note
    else:
        # Re-closing a reopened item with no fresh note: drop the previous
        # close's note rather than let it pose as this close's reasoning
        # (bon-pufezi — an item DROPPED in July read as the August close's
        # verdict). The note deliberately survives `bon reopen` so the old
        # reasoning stays readable while deciding; it clears only here, at
        # the moment it would start lying. History lives in git/dolt.
        item.pop("done_note", None)

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

    # Closing an outcome over open children is allowed but never silent —
    # they stay visible on the board awaiting explicit triage (bon-kegewe)
    if item["type"] == "outcome":
        open_children = [i for i in items
                         if i.get("parent") == item["id"] and i["status"] == "open"]
        if open_children:
            ids = ", ".join(c["id"] for c in open_children)
            warn(f"{len(open_children)} open action(s) remain under this outcome "
                 f"and stay visible on the board: {ids}")

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
        item_not_found(args.id, prefix)

    # Clear tactical if present (long blocks warrant re-planning)
    if item.get("tactical"):
        item.pop("tactical")

    # Warn if reason looks like a bon ID but can't be found
    reason = args.reason
    if re.match(r'^[a-z]+-[a-z]+$', reason) and not find_by_id(items, reason, prefix):
        warn(f"'{reason}' not found in active items — waiting_for may never resolve automatically")

    # Append to blockers list (idempotent); --replace overwrites the whole set
    blockers = item.get("waiting_for") or []
    if getattr(args, "replace", False):
        blockers = [reason]
    elif reason not in blockers:
        blockers.append(reason)
    item["waiting_for"] = blockers
    # A new waiting cycle begins: the previous release's rationale is now
    # another cycle's story (bon-wevapu — same clear-at-the-lie moment as
    # done_note on re-close, bon-pufezi).
    item.pop("released_note", None)
    note = getattr(args, "note", None)
    if note:
        item["wait_note"] = note
    item["updated_at"] = now_iso()
    item["updated_by"] = "waited"
    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    else:
        # Print the resulting state, not the argument: on a list this appends,
        # and reporting only the new reason reads as a replacement (bon-vapebu).
        print(f"{item['id']} now waiting for: {', '.join(blockers)}")


def cmd_unwait(args):
    """Clear waiting status (all blockers, or a specific one)."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        item_not_found(args.id, prefix)

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

    # Why the block lifted — met, abandoned, decided against — is exactly
    # what evaporates at release time (bon-wevapu: 'Sameer decided, and there
    # was nowhere to record the decision'). Overwrites any earlier release's
    # note; a fresh `bon wait` clears it (a new cycle makes it stale).
    note = getattr(args, "note", None)
    if note:
        item["released_note"] = note

    item["updated_at"] = now_iso()
    item["updated_by"] = "unwaited"
    save_items(items)
    if getattr(args, 'quiet', False):
        print(item['id'])
    elif item.get("waiting_for"):
        remaining = ", ".join(item["waiting_for"])
        suffix = " (release note recorded)" if note else ""
        print(f"{item['id']} removed {blocker}, still waiting for: {remaining}{suffix}")
    else:
        suffix = " (release note recorded)" if note else ""
        print(f"{item['id']} no longer waiting{suffix}")


def cmd_someday(args):
    """Park an item Someday/Maybe with a revisit condition (bon-majoca)."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        item_not_found(args.id, prefix)
    if item["status"] == "done":
        error(f"{item['id']} is done — Someday is for open items still wanted, not now")
    # bon wait silently discards tactical progress (a documented landmine);
    # someday refuses instead and names the way out.
    if item.get("tactical"):
        error(
            f"{item['id']} has tactical steps in progress — parking would orphan them.\n"
            f"Finish the work, or clear first: bon work --clear"
        )

    condition = args.condition.strip()
    if not condition:
        error("A revisit condition is required — /review re-checks it each pass")

    item["someday"] = condition
    item["updated_at"] = now_iso()
    item["updated_by"] = "parked"
    save_items(items)

    if getattr(args, "quiet", False):
        print(item["id"])
    else:
        line = f"{item['id']} parked Someday — revisit: {condition}"
        open_children = [
            i for i in items
            if i.get("parent") == item["id"] and i["status"] == "open"
        ]
        if open_children:
            line += f" ({len(open_children)} open child(ren) park with it)"
        print(line)


def cmd_unsomeday(args):
    """Unpark a Someday item — it returns to the live board."""
    check_initialized()

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        item_not_found(args.id, prefix)
    if not item.get("someday"):
        print(f"{item['id']} is not parked — nothing to do.")
        return

    was = item.pop("someday")
    item["updated_at"] = now_iso()
    item["updated_by"] = "unparked"
    save_items(items)

    if getattr(args, "quiet", False):
        print(item["id"])
    else:
        print(f"{item['id']} unparked (was: revisit {was})")


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
            item_not_found(edited['parent'], prefix, noun="Parent")
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


# Fields `bon edit` accepts as JSON on stdin.
#
# Brief subfields are accepted BOTH nested under "brief" and flat at the top
# level. Claude's training prior is flat — understanding.md keeps a
# field-name mapping table because of it — and a flat key silently ignored
# would apply nothing while printing "Updated": a no-op edit wearing a
# success message, which is the exact failure class this path exists to
# remove. Unknown keys are a hard error for the same reason; a typo that
# quietly drops a field is worse than one that stops.
EDIT_BRIEF_KEYS = ("why", "how", "what", "done", "badly")
EDIT_TOP_KEYS = ("title", "parent", "outcome", "order", "note", "brief", "area", "append_how")


def edit_args_from_stdin(args, *, explicit: bool = False):
    """Overlay a JSON object from stdin onto `args`.

    Mutates `args` so the flag-driven apply logic in cmd_edit runs unchanged:
    one code path applies the edit however it arrived.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        # An empty pipe is not malformed JSON — it is no input at all, which
        # is the same situation as passing no flags. Fall through so the
        # caller gets the "which flags exist" message rather than a JSON
        # complaint about a format they may not have been reaching for.
        if explicit:
            error("--json given but stdin was empty. Pipe a JSON object.")
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON on stdin: {e}")
    if not isinstance(data, dict):
        error('JSON on stdin must be an object, e.g. {"how": "..."}')

    brief = data.get("brief", {})
    if not isinstance(brief, dict):
        error("'brief' must be an object")

    unknown = (set(data) | set(brief)) - set(EDIT_TOP_KEYS) - set(EDIT_BRIEF_KEYS)
    if unknown:
        error(
            f"Unknown field(s): {', '.join(sorted(unknown))}\n"
            "Valid: title, outcome (or parent), order, note, area, append_how, "
            "brief{why, how, what, done} — brief fields may also be given flat."
        )

    for key in EDIT_BRIEF_KEYS:
        if key in data and key in brief:
            error(f"'{key}' given both flat and inside 'brief' — pick one")

    for key in EDIT_BRIEF_KEYS:
        if key in brief or key in data:
            value = brief[key] if key in brief else data[key]
            if not isinstance(value, str):
                error(f"'{key}' must be a string, got {type(value).__name__}")
            setattr(args, key, value)

    if "title" in data:
        if not isinstance(data["title"], str):
            error("'title' must be a string")
        args.title = data["title"]
    if "parent" in data or "outcome" in data:
        value = data.get("parent", data.get("outcome"))
        if value is None:
            value = "none"
        if not isinstance(value, str):
            error("'parent' must be a string (or 'none' to make standalone)")
        args.parent = value
    if "order" in data:
        if not isinstance(data["order"], int) or isinstance(data["order"], bool):
            error("'order' must be an integer")
        args.order = data["order"]
    if "note" in data:
        if not isinstance(data["note"], str):
            error("'note' must be a string")
        args.note = data["note"]
    if "area" in data:
        # null clears, same as "" — a JSON author's natural spelling of "unset"
        value = data["area"]
        if value is None:
            value = ""
        if not isinstance(value, str):
            error("'area' must be a string (or null/'' to clear)")
        args.area = value
    if "append_how" in data:
        if not isinstance(data["append_how"], str):
            error("'append_how' must be a string")
        args.append_how = data["append_how"]


def edit_flags_given(args) -> bool:
    """True when the caller asked for at least one field change."""
    return any([
        args.title,
        args.parent is not None,
        args.why,
        args.how is not None,
        args.what,
        args.done,
        getattr(args, "badly", None) is not None,
        getattr(args, "note", None) is not None,
        getattr(args, "area", None) is not None,
        getattr(args, "append_how", None) is not None,
        args.order is not None,
    ])


def cmd_edit(args):
    """Edit item fields via flags or piped JSON (no interactive editor)."""
    check_initialized()

    # JSON on stdin is the default when no edit flag was given and stdin is
    # piped — the same convention as `bon new`, adopted for the same reason:
    # flag quoting mangles briefs carrying quotes, backticks or $, silently,
    # and a mangled field looks exactly like an edited one (bon-cefisu).
    explicit_json = getattr(args, "json_input", False)
    if explicit_json or (not edit_flags_given(args) and not sys.stdin.isatty()):
        edit_args_from_stdin(args, explicit=explicit_json)

    if not edit_flags_given(args):
        error(
            "At least one edit flag required: --title, --outcome, --why, --how, "
            "--append-how, --what, --done, --note, --order, --area — or pipe JSON to stdin"
        )

    items = load_items()
    prefix = load_prefix()
    item = find_by_id(items, args.id, prefix)

    if not item:
        item_not_found(args.id, prefix)

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
        if args.parent.lower() == "none":
            edited["parent"] = None
        else:
            parent_item = find_by_id(items, args.parent, prefix)
            if not parent_item:
                item_not_found(args.parent, prefix, noun="Parent")
            if parent_item["type"] != "outcome":
                error(f"Parent must be an outcome, got {parent_item['type']}")
            edited["parent"] = parent_item["id"]
    if args.why:
        edited["brief"]["why"] = args.why
    if args.how is not None:
        if args.how:
            edited["brief"]["how"] = args.how
        else:
            edited["brief"].pop("how", None)
    if getattr(args, "append_how", None) is not None:
        # Annotating an item used to mean a hand-rolled read-modify-write on
        # --how, whose failure mode is silently replacing the field (the
        # carte-vudusu destruction shape). This does the append atomically.
        if args.how is not None:
            error("--how and --append-how together are ambiguous — pick one")
        if not args.append_how.strip():
            error("--append-how needs text (to clear the field, use --how '')")
        existing = edited["brief"].get("how")
        edited["brief"]["how"] = (
            f"{existing}\n\n{args.append_how}" if existing else args.append_how
        )
    if args.what:
        edited["brief"]["what"] = args.what
    if args.done:
        edited["brief"]["done"] = args.done
    if getattr(args, "badly", None) is not None:
        if args.badly:
            edited["brief"]["badly"] = args.badly
        else:
            edited["brief"].pop("badly", None)
        check_falsifier_placement(item["type"], args.badly)
    if args.order is not None:
        edited["order"] = args.order
    if getattr(args, "area", None) is not None:
        if args.area.strip():
            edited["area"] = args.area.strip()
            if edited["type"] == "action" and edited.get("parent"):
                warn("area on a parented action is inert in grouped views — it inherits "
                     "its outcome's area. Set the area on the outcome instead.")
        else:
            edited.pop("area", None)
    if getattr(args, "note", None) is not None:
        # The repair path for a mangled closing note. `bon done --note` refuses
        # to overwrite an existing one, so before this flag a note damaged by
        # shell quoting was permanent on the item (bon-cefisu, second witness).
        if item["status"] != "done":
            error(
                f"--note sets the closing note, and {item['id']} is still open.\n"
                f"Close it with one instead: bon done {item['id']} --note \"...\""
            )
        if args.note:
            edited["done_note"] = args.note
        else:
            edited.pop("done_note", None)

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
        item_not_found(args.id, prefix)

    if item["type"] == "outcome":
        # Validate parent if given. "none" means standalone, matching
        # `bon edit --parent none` — bon taught that spelling, so rejecting
        # it here was our own grammar contradicting itself (bon-siciri: the
        # rejection sent a session on a needless three-verb dance).
        old_parent = None
        if args.parent and args.parent.lower() == "none":
            args.parent = None
        if args.parent:
            parent = find_by_id(items, args.parent, prefix)
            if not parent:
                item_not_found(args.parent, prefix, noun="Parent")
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
    if getattr(args, "quiet", False):
        print(item["id"])
    else:
        print(f"Converted {item['id']} to {item['type']}")


def _resolve_target_repo(to: str) -> Path:
    """Resolve `--to`: a path (absolute, relative, or ~) or a bare repo name.

    Bare names resolve under ~/repos/*/NAME (the owner-bucket layout);
    anything containing a slash, or starting with ~ or ., is taken as a path.
    """
    if "/" in to or to.startswith(("~", ".")):
        p = Path(to).expanduser().resolve()
        if not p.is_dir():
            error(f"Target path does not exist: {p}")
        return p
    matches = sorted(d for d in Path.home().glob(f"repos/*/{to}") if d.is_dir())
    if not matches:
        error(f"No repo named '{to}' under ~/repos/*/ — pass a path instead")
    if len(matches) > 1:
        listing = "\n  ".join(str(m) for m in matches)
        error(f"Ambiguous repo name '{to}':\n  {listing}\nPass the full path.")
    return matches[0]


def cmd_move(args):
    """Move an item to another repo's board: new ID there, source closed with a cross-reference."""
    check_initialized()
    items = load_items()
    prefix = load_prefix()

    item = find_by_id(items, args.id, prefix)
    if not item:
        item_not_found(args.id, prefix)
    if item["status"] == "done":
        error(f"{item['id']} is already done — nothing to move")

    # Only OPEN children block the move: the source closes as a done tombstone,
    # so closed children's parent link stays valid after the move (bon-rofatu —
    # counting done children made the error's own remedy unsatisfiable).
    children = [i for i in items if i.get("parent") == item["id"]]
    open_children = [i for i in children if i["status"] == "open"]
    if open_children:
        error(
            f"{item['id']} has {len(open_children)} open child item(s) — moving it would strand them here.\n"
            "Move or close the children first (or `bon convert` them to standalone)."
        )

    target_root = _resolve_target_repo(args.to)
    board = target_board(target_root)
    source_dir = _data_dir()
    if board["dir"] == Path(source_dir):
        error("Target is this repo — nothing to move")

    t_items = load_items_at(board)
    existing = {i["id"] for i in t_items} | archive_ids_at(board)
    new_id = generate_unique_id(board["prefix"], existing)

    # Provenance rides in the brief (visible wherever the item is read);
    # the source's done_note carries the forward link.
    source_name = Path(source_dir).parent.name
    provenance = [f"Moved from {item['id']} ({source_name})"]
    if item.get("parent"):
        parent_item = find_by_id(items, item["parent"], prefix)
        parent_desc = f" '{parent_item['title']}'" if parent_item else ""
        provenance.append(f"was under {item['parent']}{parent_desc}")
        warn(f"Parent {item['parent']} stays here — {new_id} files as standalone in the target")
    blockers = item.get("waiting_for") or []
    if blockers:
        provenance.append(f"was waiting for {', '.join(blockers)}")
        warn(f"Blocker link(s) {', '.join(blockers)} dropped — waits don't cross repos")
    if _tactical_is_active(item):
        warn("Tactical progress is not carried over")
    done_children = [i for i in children if i["status"] != "open"]
    if done_children:
        warn(
            f"{len(done_children)} closed child record(s) stay here — "
            f"{item['id']} remains as a done tombstone their parent link resolves to"
        )

    brief = dict(item.get("brief") or {})
    brief["why"] = ((brief.get("why") or "").rstrip() + f"\n[{'; '.join(provenance)}]").strip()

    new_item = {
        "id": new_id,
        "type": item["type"],
        "title": item["title"],
        "brief": brief,
        "status": "open",
        "order": next_order(t_items, item["type"], None),
        "created_at": now_iso(),
        "created_by": get_creator(),
    }
    if item["type"] == "action":
        new_item["parent"] = None
        new_item["waiting_for"] = None

    # Target first: if the source close then fails, the item exists in both
    # places with the source still open — recoverable, nothing lost.
    t_items.append(new_item)
    save_items_at(board, t_items)
    if board["backend"] != "dolt":
        warn(
            f"Target board is JSONL — commit {board['dir'] / 'items.jsonl'} "
            "in the target repo, or the move only exists on this machine"
        )

    item["status"] = "done"
    item["done_at"] = now_iso()
    item["done_note"] = f"Moved to {new_id} ({board['root']})"
    item["updated_at"] = now_iso()
    item["updated_by"] = "moved"
    item.pop("tactical", None)

    # Unblock waiters (same cascade as cmd_done) — but the work moved rather
    # than finished, so name each one for a manual re-link decision.
    unblocked = []
    for other in items:
        other_blockers = other.get("waiting_for") or []
        if item["id"] in other_blockers:
            other_blockers = [b for b in other_blockers if b != item["id"]]
            other["waiting_for"] = other_blockers if other_blockers else None
            if not other["waiting_for"]:
                other.pop("wait_note", None)
                unblocked.append(other["id"])
    save_items(items)

    if getattr(args, "quiet", False):
        print(new_id)
        return
    print(f"Moved: {item['id']} → {new_id}")
    print(f"Target: {board['root']} (prefix '{board['prefix']}')")
    print(f"Source closed: {item['done_note']}")
    if unblocked:
        print(f"Unblocked here: {', '.join(unblocked)} — re-link manually if they still depend on the moved work")


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
                item_not_found(item_id, prefix)
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
        item_not_found(args.id, prefix)

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
    Markers must count 1, 2, 3… in order: a "N." or "N)" that isn't the
    next expected number is inline content (e.g. a cross-reference like
    "(step 3)"), not a step boundary. "step N)" never splits, even when
    N is the next expected number — but "step N." does, since a step can
    legitimately end with the word "step".
    Returns None if no numbered list found.
    """
    # Normalize: collapse newlines and extra whitespace to single spaces
    normalized = ' '.join(what.split())
    # Step number must be at start or after whitespace (prevents matching "v2.0")
    # Delimiter (. or )) must be followed by whitespace
    marker = re.compile(r'(?:^|(?<=\s))(\d+)([.)])\s+')
    boundaries = []
    expected = 1
    for m in marker.finditer(normalized):
        if int(m.group(1)) != expected:
            continue
        if m.group(2) == ")" and re.search(r'[Ss]tep\s$', normalized[:m.start()]):
            continue
        boundaries.append((m.start(), m.end()))
        expected += 1
    if not boundaries:
        return None
    steps = []
    for i, (_, end) in enumerate(boundaries):
        text_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(normalized)
        text = normalized[end:text_end].strip()
        if text:
            steps.append(text)
    return steps if steps else None


def _baton_dirs(root, cwd) -> list:
    """The handoffs dirs the baton may read — the resolver's semantics.

    NEVER a bounded walk of the whole tree: the first cut's 6000-dir budget
    tripped on the live ~/.claude board before reaching its own handoffs/,
    while the only dirs it DID reach were vendored plugin-cache copies of
    other repos' handoffs (essayeur refutation, 2026-08-30). Instead:
    upward from cwd to the board root (lib-handoff.sh's read set — the
    guaranteed floor), then room handoffs downward at depth ≤ 4 (the
    scan_down_candidates bound), skipping any dir that sits behind a
    foreign .git/.bon boundary — another repo's or board's territory,
    which is exactly what a vendored clone is.
    """
    from pathlib import Path
    root = Path(root)
    cwd = Path(cwd)
    dirs: list = []
    try:
        inside = cwd.is_relative_to(root)
    except (AttributeError, ValueError):
        inside = False
    walk = cwd if inside else root
    while True:
        d = walk / "handoffs"
        if d.is_dir():
            dirs.append(d)
        if walk == root or walk.parent == walk:
            break
        walk = walk.parent
    for pattern in ("*/handoffs", "*/*/handoffs", "*/*/*/handoffs",
                    "*/*/*/*/handoffs"):
        for d in root.glob(pattern):  # glob's * never matches dot-dirs
            if not d.is_dir():
                continue
            anc = d.parent
            foreign = False
            while anc != root:
                if ((anc / ".git").exists() or (anc / ".bon").exists()
                        or anc.name in ("node_modules", "__pycache__")):
                    foreign = True
                    break
                anc = anc.parent
            if not foreign:
                dirs.append(d)
    seen = set()
    unique = []
    for d in dirs:
        r = os.path.realpath(d)
        if r not in seen:
            seen.add(r)
            unique.append(d)
    return unique


def _baton_items_field(head: str) -> str | None:
    """The items: value, including wrapped continuation lines.

    Only INDENTED lines continue the field: a flush-left prose line right
    after items: ("Also reviewed bon-x in passing…") once minted a false
    citation — a confident wrong baton, worse than none (essayeur N1).
    """
    lines = head.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("items:"):
            value = [line[len("items:"):]]
            for cont in lines[i + 1:]:
                if not cont.strip() or not cont[0].isspace():
                    break
                value.append(cont)
            return " ".join(value)
    return None


def _baton_write_stamp(path: str, head: str, name: str):
    """(day, hhmm, tiebreak) for ranking — provenance-first, never fabricated.

    Header date and v4 filename HHMM when present; else the file's GIT
    commit date — mtime is not provenance on a git-shared board, where a
    pull flattens every mtime to checkout time on the receiving clones and
    a five-day-stale nonconforming file can beat the true latest with a
    fabricated date (essayeur N2). mtime is the last resort (untracked or
    no git), which is exactly the author's-machine case where it is honest.
    """
    from datetime import datetime
    dm = re.search(r"^# Handoff — (\d{4}-\d{2}-\d{2})", head, re.MULTILINE)
    hm = re.match(r"^\d{4}-\d{2}-\d{2}-(\d{4})-", name)
    day = dm.group(1) if dm else None
    hhmm = hm.group(1) if hm else None
    if day is None or hhmm is None:
        git_iso = None
        try:
            result = subprocess.run(
                ["git", "-C", os.path.dirname(path), "log", "-1",
                 "--format=%cI", "--", path],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                git_iso = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        if git_iso:
            if day is None:
                day = git_iso[:10]
            if hhmm is None:
                hhmm = git_iso[11:13] + git_iso[14:16]
        else:
            mt = datetime.fromtimestamp(os.path.getmtime(path))
            if day is None:
                day = mt.strftime("%Y-%m-%d")
            if hhmm is None:
                hhmm = mt.strftime("%H%M")
    return day, hhmm, int(os.path.getmtime(path))


def find_baton_handoff(item_id: str) -> tuple[str, str, str] | None:
    """Newest handoff citing item_id in its `items:` frontmatter (bon-jeweke).

    The baton follows the ticket: the directional briefing — "here is where
    this thread was left" — goes to whoever draws the item down, not whoever
    opens next. Closes stamp `items: <ids worked>` in the handoff metadata;
    this reads the resolver-legitimate handoffs dirs for the newest file
    citing the id. Ranking mirrors open-context.sh's find_latest_in: header
    date (mtime-derived when the header is nonconforming — a sentinel would
    make format drift surface a STALE handoff under a confident label),
    then filename HHMM (mtime-derived fallback), then raw mtime. Returns
    (path, date, purpose) or None. Best-effort by construction: a prose
    scan must never break a board verb.
    """
    try:
        from bon.storage import _data_dir
        root = _data_dir().parent
        cite = re.compile(r"(?<![A-Za-z0-9-])" + re.escape(item_id) + r"(?![A-Za-z0-9-])")
        best_key = ""
        best = None
        for hdir in _baton_dirs(root, os.getcwd()):
            for name in sorted(os.listdir(hdir)):
                if not name.endswith(".md") or name in ("LEDGER.md", "README.md"):
                    continue
                path = os.path.join(str(hdir), name)
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        head = f.read(4096)
                except OSError:
                    continue
                field = _baton_items_field(head)
                if not field or not cite.search(field):
                    continue
                day, hhmm, tiebreak = _baton_write_stamp(path, head, name)
                key = f"{day}.{hhmm}.{tiebreak:012d}"
                if key > best_key:
                    pm = re.search(r"^purpose:\s*(.*)$", head, re.MULTILINE)
                    best_key = key
                    best = (path, day, pm.group(1).strip() if pm else "")
        return best
    except Exception:
        return None


def print_baton(item_id: str) -> None:
    """One line surfacing the thread's latest handoff at draw-down time."""
    baton = find_baton_handoff(item_id)
    if not baton:
        return  # a fresh item surfaces nothing — by design
    path, day, purpose = baton
    try:
        rel = os.path.relpath(path)
    except ValueError:
        rel = path
    if len(purpose) > 120:
        purpose = purpose[:117] + "…"
    print()
    print(f"Baton ({day}): {rel}" + (f" — {purpose}" if purpose else ""))
    print("  The last session on this thread. Read it before starting.")


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
    if "--clear" in positional:
        positional = [a for a in positional if a != "--clear"]
        args.clear = True
    if "--release" in positional:
        positional = [a for a in positional if a != "--release"]
        args.release = True
    work_id = positional[0] if positional else None
    work_steps = positional[1:] if len(positional) > 1 else []

    # --status: show current tactical (scoped to CWD)
    if args.status:
        active = find_active_tactical(items, session=session)
        if not active:
            active = find_no_complete_tactical(items, session=session)
        if not active:
            orphan = find_orphaned_tactical(items, session)
            released = find_released_tactical(items, session=session)
            if orphan:
                print(f"Orphaned tactical: {orphan['id']} ({orphan['title']})")
                print(format_tactical(orphan["tactical"], action_status=orphan["status"]))
                print(f"\nOld session no longer exists. Run `bon work {orphan['id']}` to re-claim.")
            elif released:
                print(f"Released tactical: {released['id']} ({released['title']})")
                print(format_tactical(released["tactical"], action_status=released["status"]))
                print(f"\nProgress kept, claim handed back. Resume with `bon work {released['id']}`.")
            else:
                print("No active tactical steps. Run `bon work <id>` to start.")
            return
        print(f"Working on: {active['title']} ({active['id']})")
        print()
        print(format_tactical(active["tactical"], action_status=active["status"]))
        return

    # --release: hand back the claim WITHOUT losing the progress. The pair to
    # --clear: release keeps the steps, clear discards them.
    #
    # Why this verb exists: a tactical can be parked on purpose — bon-jagoha
    # sat at step 4 of 6 waiting for a scheduled review ceremony. The claim is
    # keyed to the directory and serially enforced, so it refused every other
    # `bon work` in that repo, and all three escapes destroyed the progress
    # (done is a lie, `bon wait` silently discards tactical, `--clear` pops
    # it). `bon someday` refuses outright on an active tactical, so the
    # parking verb was the one thing that could not help (bon-kewimu).
    #
    # Deliberately NOT spelled --park: `someday` already owns "parked" in this
    # codebase's vocabulary and means something different (the ITEM is
    # Someday/Maybe and leaves the default view). A released tactical says
    # nothing about the item, which stays exactly as visible as before.
    if getattr(args, "release", False):
        if work_id:
            target = find_by_id(items, work_id, prefix)
            if not target:
                item_not_found(work_id, prefix)
        else:
            target = find_active_tactical(items, session=session)
            if not target:
                target = find_no_complete_tactical(items, session=session)
            if not target:
                error("No tactical claim in this session to release.")
        tactical = target.get("tactical")
        if not tactical:
            error(f"{target['id']} has no tactical steps to release.")
        if tactical.get("released"):
            print(f"Already released: {target['id']}")
            return
        if target["status"] == "done":
            error(f"{target['id']} is done — its tactical record is history, not a claim")
        t_session = tactical.get("session")
        if t_session and t_session != session and not args.force:
            error(
                f"{target['id']}'s tactical belongs to another session ({t_session}).\n"
                f"Use `bon work --release {target['id']} --force` to release it anyway."
            )
        tactical["released"] = True
        tactical["released_at"] = now_iso()
        target["updated_at"] = now_iso()
        target["updated_by"] = "released"
        save_items(items)
        done_count = tactical.get("current", 0)
        total = len(tactical.get("steps", []))
        print(f"Released: {target['id']} at step {done_count + 1} of {total} "
              f"({done_count} complete, progress kept)")
        print(f"Resume with `bon work {target['id']}` — no --force needed.")
        return

    # --clear: release a tactical claim. Bare form takes this session's
    # active tactical, falling back to its finished (--no-complete) one —
    # the same pair --status reads, so the two surfaces agree on what a
    # claim is (a finished tactical was previously unreachable: bon-rucape).
    # `--clear ID` targets a specific item; another session's claim needs --force.
    if args.clear:
        if work_id:
            target = find_by_id(items, work_id, prefix)
            if not target:
                item_not_found(work_id, prefix)
            tactical = target.get("tactical")
            if not tactical:
                return  # Silent success
            if target["status"] == "done":
                error(f"{target['id']} is done — its tactical record is history, not a claim")
            t_session = tactical.get("session")
            if t_session and t_session != session and not args.force:
                error(
                    f"{target['id']}'s tactical belongs to another session ({t_session}).\n"
                    f"Use `bon work --clear {target['id']} --force` to clear it anyway."
                )
        else:
            target = find_active_tactical(items, session=session)
            if not target:
                target = find_no_complete_tactical(items, session=session)
            if not target:
                return  # Silent success
        target.pop("tactical", None)
        target["updated_at"] = now_iso()
        target["updated_by"] = "cleared"
        save_items(items)
        print(f"Cleared tactical steps from {target['id']}")
        return

    # Initialize tactical for specific action
    if not work_id:
        error("Usage: bon work <id> [steps...] or bon work --status/--clear")

    item = find_by_id(items, work_id, prefix)
    if not item:
        item_not_found(work_id, prefix)
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
        error(
            f"{active['id']} has active steps. Complete it, wait it, "
            f"release it with `bon work --release` (keeps its progress), "
            f"or discard it with `bon work --clear`"
        )

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
    if existing and existing.get("released") and not args.force:
        # Resuming a deliberately released tactical: progress is intact and
        # picking it back up is the expected move, so this must NOT need
        # --force (which restarts from step 1 and would throw the progress
        # away — the very thing releasing existed to protect).
        existing.pop("released", None)
        existing.pop("released_at", None)
        existing["session"] = session
        item["updated_at"] = now_iso()
        item["updated_by"] = "reclaimed"
        save_items(items)
        print(f"Resumed: {item['id']} (progress intact)")
        print()
        print(format_tactical(item["tactical"], action_status=item["status"]))
        print_baton(item["id"])
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
    print_baton(item["id"])


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
                f"No steps in progress for this session ({session}).\n"
                f"Last worked: {last['id']} ({last['title']})\n"
                f"Run `bon work {last['id']}` to resume"
            )
        error(f"No steps in progress for this session ({session}). Run `bon work <id>` first")

    tactical = active["tactical"]
    current = tactical["current"]
    steps = tactical["steps"]

    # CAS guard (bon-tedabo): refuse, loudly and without writing, when the
    # board moved under the caller — the lomede race generalised. Equality
    # check only; --expect is the 1-based number every surface displays.
    expect = getattr(args, "expect", None)
    if expect is not None and expect != current + 1:
        error(
            f"Tactical moved: you expected step {expect} but {active['id']} is at "
            f"step {current + 1} of {len(steps)} — another session may have advanced it.\n"
            f"Nothing was written. Re-read before acting: bon work --status"
        )

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

    from bon.storage import _data_dir
    bon_dir = _data_dir()

    if target == "dolt":
        # Verify Dolt is reachable before touching any state
        from bon.dolt import check_prefix_collision, verify_dolt_connection
        verify_dolt_connection()

        # Migrate JSONL → Dolt: load from files, write to Dolt
        items = load_items()  # Still JSONL at this point
        archive = load_archive()

        # Refuse if Dolt already has prefix-rows that aren't ours
        # (would be silently DELETEd by truncate-and-reinsert)
        prefix = load_prefix()
        local_item_ids = {item["id"] for item in items}
        local_archive_ids = {item["id"] for item in archive}
        check_prefix_collision(prefix, local_item_ids, local_archive_ids)

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

        # Ensure the repos mapping row exists even for an empty board —
        # save_items above only ran when there were items to write.
        from bon.dolt import dolt_register_repo
        dolt_register_repo()

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


def cmd_register(args):
    """Register this board in Dolt's repos mapping table."""
    check_initialized()
    if _get_backend() != "dolt":
        error(
            "bon register requires the Dolt backend — this board is JSONL.\n"
            "JSONL boards are discovered by filesystem scan, not the repos table."
        )
    from bon.dolt import dolt_register_repo
    prefix = load_prefix()
    job = getattr(args, "job", None)
    if dolt_register_repo(prefix, job=job):
        if job:
            print(f"Registered '{prefix}' in the Dolt repos table (job: {job}).")
        elif job == "":
            print(f"Registered '{prefix}' in the Dolt repos table (job cleared).")
        else:
            print(f"Registered '{prefix}' in the Dolt repos table.")
    else:
        print(f"'{prefix}' already registered and current.")


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


STALE_CLAIM_DAYS = 7


def _stale_claim_lines(items, days=STALE_CLAIM_DAYS):
    """Advisory lines for active tactical claims untouched for `days`.

    Visibility only, never reclamation (bon-tedabo, adjudicated 2026-08-08):
    long-idle sessions are normal on this estate and an idle-but-alive
    session emits no heartbeat, so TTL auto-reclaim would hand a live
    session's claim to a sibling. Taking over stays a deliberate act.
    """
    from datetime import datetime, timezone

    lines = []
    now = datetime.now(timezone.utc)
    for item in items:
        if not _tactical_is_active(item):
            continue
        stamp = item.get("updated_at") or item.get("created_at") or ""
        try:
            then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        age = (now - then).days
        if age >= days:
            t = item["tactical"]
            steps = t.get("steps", [])
            lines.append(
                f"{item['id']} held by {t.get('session') or 'unscoped'} — untouched {age}d "
                f"at step {min(t.get('current', 0) + 1, len(steps))}/{len(steps)}. "
                f"If that session is gone: `bon work --release` from its cwd keeps the progress, "
                f"or `bon work {item['id']} --force` here takes over."
            )
    return lines


def _order_dup_groups(items):
    """Sibling groups (open actions, keyed by parent) holding duplicate orders.

    Returns {parent_id_or_None: (siblings, sorted_dup_values)}.
    """
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for item in items:
        if item.get("type") == "action" and item.get("status") == "open":
            groups[item.get("parent")].append(item)
    dup_groups = {}
    for parent_id, siblings in groups.items():
        orders = [s.get("order") for s in siblings if s.get("order") is not None]
        dupes = sorted({o for o in orders if orders.count(o) > 1})
        if dupes:
            dup_groups[parent_id] = (siblings, dupes)
    return dup_groups


def _resequence_siblings(siblings):
    """Renumber a sibling group 1..N by (order, created_at); returns changed items.

    The mover (apply_reorder) legitimately assumes unique sibling orders, so a
    repair built from single moves re-mints the dup one rung down — three
    times in a row in the live incident (bon-tagoje). The repair is therefore
    a whole-group renumber where detection lives. None orders sort last and
    gain real rungs, so a repaired group comes out fully 1..N.
    """
    ordered = sorted(siblings, key=lambda s: (
        s.get("order") if s.get("order") is not None else DEFAULT_ORDER,
        s.get("created_at") or "",
        s.get("id") or "",  # created_at is second-resolution — same-second twins need a deterministic tie-break
    ))
    changed = []
    for n, s in enumerate(ordered, 1):
        if s.get("order") != n:
            s["order"] = n
            changed.append(s)
    return changed


def _gitignored_durable_advisory() -> list[str]:
    """Advisory lines when a root .gitignore strands durable .bon artefacts (bon-kizeje).

    A wholesale `.bon/` ignore usually arrives as init boilerplate (the
    mit-plongeur case). understanding.md and the bottle then write locally but
    never commit — nothing errors, the next machine just never sees them.
    `git check-ignore` matches paths that don't exist yet, so a fresh board
    reports before its first stranded write. Exceptions can't be added inside
    an ignored directory (git never descends into one); the fix lives in the
    ROOT .gitignore.

    Handoffs are NOT probed any more (bon-sedoze): they live in the visible
    `handoffs/` outside `.bon/`, so a `.bon/` ignore no longer reaches them.
    """
    data_dir = _data_dir()
    candidates = ["README.md", "understanding.md"]
    if _get_backend() != "dolt":
        candidates.append("items.jsonl")
    ignored = []
    try:
        for rel in candidates:
            result = subprocess.run(
                ["git", "check-ignore", "-q", str(data_dir / rel)],
                cwd=data_dir.parent, capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                ignored.append(f".bon/{rel}")
    except (OSError, subprocess.SubprocessError):
        return []
    if not ignored:
        return []
    return [
        f"gitignored durable artefact(s): {', '.join(ignored)} — they write locally but never commit,",
        "so understanding.md and the bottle silently stop travelling to other machines.",
        "Fix the ROOT .gitignore (exceptions inside an ignored dir are inert): replace a wholesale",
        "`.bon/` rule with scoped patterns that keep understanding.md, README.md,",
        "prefix and backend tracked (plus items.jsonl on JSONL boards).",
    ]


# A DATED stamp, not the words. The generated bridge doc now carries an "Open —
# close this out when the migration lands" section telling the reader what to
# append, so a bare word-match would read every fresh doc as already closed —
# a check that could never fire. The date is the part only a human can supply.
CLOSEOUT_STAMP = re.compile(r"closed[ -]out\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def _bridge_doc_advisory() -> list[str]:
    """Advisory lines for an id-migration bridge doc with no close-out stamp (bon-kefoba).

    A bridge doc exists to answer "where did that id go", which makes it the
    FIRST thing a future reader consults and the LAST thing a migration sweep
    thinks to check. It is written in the present tense about an in-flight
    change — "these two pointers want updating", "the correct target is
    genuinely unknown" — and that tense is what goes stale. The sweep cannot
    catch it either: grep the retired id and the bridge doc turns up looking
    like a correct record, because on the day it was written it was one.
    That is how bon-zigupa's migration finished with its own bridge doc still
    telling readers to do work that was already done (2026-08-31, caught by
    an essayeur rather than by the session that did the sweep).

    So the check is presence-of-a-stamp, not correctness-of-content: a bridge
    doc naming no close-out is flagged, and appending one dated section
    silences it forever. Deliberately NOT parsing the migrated ids — the
    estate's own rename doctrine says never to key on an id-shaped pattern,
    and a stamp is a claim the human made rather than one we inferred.
    """
    from datetime import date

    data_dir = _data_dir()
    # `.bon/` is where reprefix-board.py writes them; `docs/` catches the
    # hand-made ones that predate the tool (cornichon's, 2026-08-08). Both
    # recursive: a doc one directory deeper escaped a flat glob entirely.
    candidates = sorted(data_dir.rglob("id-migration-*.md")) + sorted(
        (data_dir.parent / "docs").rglob("id-migration-*.md")
    )
    today = date.today().isoformat()
    found = []
    for path in candidates:
        try:
            body = path.read_text(errors="replace")
        except OSError:
            # An unreadable candidate is not an absent one. Skipping silently
            # would read "cannot see it" as "nothing to see" — the fault this
            # whole advisory exists to prevent, turned on the detector itself.
            found.append(f"{path.name} (unreadable)")
            continue
        # A stamp dated in the FUTURE is a promise, not a close-out — "will be
        # closed out 2026-12-01 once the sweep lands" matched the pattern and
        # silenced the check forever. The regex cannot read tense; it can read
        # a calendar.
        stamps = [m for m in CLOSEOUT_STAMP.findall(body) if m <= today]
        if not stamps:
            found.append(path.name)
    if not found:
        return []
    return [
        f"id-migration bridge doc with no close-out stamp: {', '.join(found)}",
        "A bridge doc is written in the present tense about a migration in flight, so once the",
        "last pointer is corrected it starts telling the next reader to do work already done —",
        "and it is the first artefact they consult. Append one dated 'Closed out YYYY-MM-DD'",
        "section saying what landed; leave the original text as the record of what was true then.",
    ]


def cmd_doctor(args):
    """Check items.jsonl for health issues."""
    check_initialized()

    issues = []

    # The bottle (.bon/README.md) refreshes automatically on every save;
    # doctor is the deliberate route for boards not being written.
    readme = _data_dir() / "README.md"
    bottle_current = readme.exists() and readme.read_text() == BOARD_README
    if not bottle_current and getattr(args, "fix", False):
        refresh_bottle(_data_dir())
        print("Refreshed .bon/README.md to current bottle wording.")
        bottle_current = True
    if not bottle_current:
        state = "differs from current wording" if readme.exists() else "is missing"
        issues.append(
            f".bon/README.md (the bottle) {state} — `bon doctor --fix` refreshes it"
        )

    if _get_backend() == "dolt":
        # In Dolt mode, validate loaded items (no file-level checks)
        items = load_items()
        archived = load_archive()
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
        dup_groups = _order_dup_groups(items)
        if dup_groups and getattr(args, "fix", False):
            for parent_id, (siblings, dupes) in sorted(dup_groups.items(), key=lambda kv: str(kv[0])):
                for it in _resequence_siblings(siblings):
                    it["updated_at"] = now_iso()
                    it["updated_by"] = "repaired"
                label = parent_id or "standalone"
                print(f"Resequenced {len(siblings)} sibling(s) under {label} (duplicate orders were {dupes}).")
            save_items(items)
        elif dup_groups:
            for parent_id, (_siblings, dupes) in sorted(dup_groups.items(), key=lambda kv: str(kv[0])):
                label = parent_id or "standalone"
                issues.append(f"under {label}: duplicate order values {dupes} — `bon doctor --fix` resequences")
        if issues:
            for issue in issues:
                print(f"  {issue}")
            print(f"\n{len(issues)} issue(s) found.")
        else:
            print(f"Dolt backend: {len(items)} items, {len(archived)} archived. All clear.")
        stale = _stale_claim_lines(items)
        if stale:
            print("\nStale claims (advisory — not counted as issues):")
            for line in stale:
                print(f"  {line}")
        bridges = _bridge_doc_advisory()
        if bridges:
            print("\nUnclosed migration bridge (advisory — not counted as issues):")
            for line in bridges:
                print(f"  {line}")
        gitignored = _gitignored_durable_advisory()
        if gitignored:
            print("\nSync hazard (advisory — not counted as issues):")
            for line in gitignored:
                print(f"  {line}")
        return

    path = items_path()

    if not path.exists():
        print("No items.jsonl found — nothing to check.")
        for issue in issues:
            print(f"  {issue}")
        if issues:
            print(f"\n{len(issues)} issue(s) found.")
        # The advisories are about artefacts BESIDE the items file, so an
        # absent board is no reason to skip them — and this is exactly the
        # dormant board doctor exists to serve.
        bridges = _bridge_doc_advisory()
        if bridges:
            print("\nUnclosed migration bridge (advisory — not counted as issues):")
            for line in bridges:
                print(f"  {line}")
        return

    raw_text = path.read_text()
    lines = raw_text.splitlines()

    # --- Phase 1: Raw-file checks ---
    seen_ids: dict[str, list[int]] = {}  # id -> list of line numbers
    parsed_items: list[tuple[int, dict]] = []  # (line_num, item)
    # Any phase-1 hit makes a rewrite unsafe: a repair that saves parsed items
    # would silently drop the very lines doctor couldn't read.
    file_unsafe = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Git conflict markers
        if stripped.startswith(("<<<<<<", "======", ">>>>>>")):
            issues.append(f"line {line_num}: git conflict marker")
            file_unsafe = True
            continue

        # Malformed JSON
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as e:
            issues.append(f"line {line_num}: malformed JSON — {e}")
            file_unsafe = True
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
            file_unsafe = True

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

        # Type-specific field rules. Tactical is genuinely action-only (`bon
        # work` refuses outcomes). waiting_for is NOT flagged: a delegated
        # outcome is GTD's textbook Waiting For, `bon wait` has always
        # accepted outcomes, `bon new` can create one born blocked, and the
        # display renders it (⏳) — doctor was the lone dissenter
        # (adjudicated 2026-08-16, with Sameer, out of bon-gufale).
        if item.get("type") == "outcome":
            if item.get("tactical"):
                issues.append(f"line {line_num} ({item.get('id', '?')}): outcome has tactical")

        valid_items.append(item)

    # --- Phase 3: Cross-item referential integrity ---
    all_ids = {item.get("id") for item in valid_items if item.get("id")}
    prefix = load_prefix()
    # The prefixes this board actually uses — its configured one plus any
    # carried by live items (legacy ids from before a re-prefix migration).
    board_prefixes = {i.rsplit("-", 1)[0] for i in all_ids if "-" in i}
    board_prefixes.add(prefix)

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

        # waiting_for references — existence-check only entries that could BE
        # this board's ids: whitespace-free AND carrying one of the board's
        # own prefixes. `bon wait` documents its reason as "ID or text", so
        # free-text rationales ("waiting on Ellie's sign-off") are legitimate
        # data, and any hyphenated word used to read as a dangling id — five
        # false positives on a clean 55-item board, a noise floor that kept
        # doctor from being run at all (bon-gufale). Foreign-board ids also
        # pass: this doctor cannot know whether crn-abc exists.
        wf = item.get("waiting_for")
        if wf:
            blockers = wf if isinstance(wf, list) else [wf]
            for blocker in blockers:
                b = str(blocker)
                if " " in b or "-" not in b:
                    continue
                if b.rsplit("-", 1)[0] in board_prefixes and b not in all_ids:
                    issues.append(f"{item['id']}: waiting_for '{b}' does not exist")

    # Duplicate orders among siblings (open actions per parent-group). Repair
    # lives here, with detection, because the mover can't do it: bon edit
    # --order assumes unique sibling orders and re-mints the dup one rung
    # down (bon-tagoje).
    dup_groups = _order_dup_groups(valid_items)
    if dup_groups and getattr(args, "fix", False) and not file_unsafe:
        # Repair through the canonical load/save path (atomic, deduped) —
        # safe exactly because phase 1 found nothing it couldn't parse.
        fresh = load_items()
        for parent_id, (siblings, dupes) in sorted(
            _order_dup_groups(fresh).items(), key=lambda kv: str(kv[0])
        ):
            for it in _resequence_siblings(siblings):
                it["updated_at"] = now_iso()
                it["updated_by"] = "repaired"
            label = parent_id or "standalone"
            print(f"Resequenced {len(siblings)} sibling(s) under {label} (duplicate orders were {dupes}).")
        save_items(fresh)
    elif dup_groups:
        if getattr(args, "fix", False) and file_unsafe:
            print("Skipping order resequence: fix the file-level issues above first "
                  "(a rewrite would drop what doctor can't parse).")
        for parent_id, (_siblings, dupes) in sorted(dup_groups.items(), key=lambda kv: str(kv[0])):
            label = parent_id or "standalone"
            issues.append(f"under {label}: duplicate order values {dupes} — `bon doctor --fix` resequences")

    # --- Output ---
    if issues:
        for issue in issues:
            print(f"  {issue}")
        print(f"\n{len(issues)} issue(s) found.")
    else:
        print("All clear.")

    stale = _stale_claim_lines(valid_items)
    if stale:
        print("\nStale claims (advisory — not counted as issues):")
        for line in stale:
            print(f"  {line}")

    bridges = _bridge_doc_advisory()
    if bridges:
        print("\nUnclosed migration bridge (advisory — not counted as issues):")
        for line in bridges:
            print(f"  {line}")
    gitignored = _gitignored_durable_advisory()
    if gitignored:
        print("\nSync hazard (advisory — not counted as issues):")
        for line in gitignored:
            print(f"  {line}")


def main():
    """Main CLI entry point: invocation logging around the real main.

    Every invocation — success and failure alike — appends one caller-stamped
    JSONL line via the vendored shim (src/bon/_invlog.py; canonical copy and
    conformance test live in spm1001/harness-ergonomics). Logging is
    best-effort: a broken log path never breaks the CLI (erg-fatogo).
    """
    with _invlog.capture("bon", __version__) as inv:
        _main(inv)


def _main(inv):
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
    new_parser.add_argument("--badly", help="Brief: what would show this went wrong? (optional, outcomes)")
    new_parser.add_argument("--area", help="Area of Focus grouping (optional; groups bon list --group-by area)")
    add_output_flags(new_parser, quiet=True)
    new_parser.set_defaults(func=cmd_new)

    # list
    list_parser = subparsers.add_parser("list", help="List items")
    list_parser.add_argument("--ready", action="store_true", help="Show only ready items")
    list_parser.add_argument("--waiting", action="store_true", help="Show only waiting items")
    list_parser.add_argument("--someday", action="store_true",
                             help="Show only parked (Someday/Maybe) items with their revisit conditions")
    list_parser.add_argument("--all", action="store_true", help="Include done items")
    list_parser.add_argument("--group-by", dest="group_by", choices=["area"],
                             help="Group the text view (areas sorted, (ungrouped) last)")
    list_parser.add_argument("--area", help="Show only the named area (outcomes with their subtree + standalone actions)")
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
    wait_parser.add_argument("--replace", action="store_true", help="Replace all existing blockers with this reason (default appends)")
    add_output_flags(wait_parser, quiet=True)
    wait_parser.set_defaults(func=cmd_wait)

    # unwait
    unwait_parser = subparsers.add_parser("unwait", help="Clear waiting status")
    unwait_parser.add_argument("id", help="Item ID")
    unwait_parser.add_argument("blocker", nargs="?", help="Specific blocker to remove (omit to clear all)")
    unwait_parser.add_argument("--note", help="Why the block lifted — met, abandoned, or decided against (stored as released_note)")
    add_output_flags(unwait_parser, quiet=True)
    unwait_parser.set_defaults(func=cmd_unwait)

    # someday / unsomeday
    someday_parser = subparsers.add_parser(
        "someday", help="Park an item Someday/Maybe (still wanted, not now)"
    )
    someday_parser.add_argument("id", help="Item ID")
    someday_parser.add_argument(
        "condition",
        help="Revisit condition (required) — e.g. 'when Mary picks it up'; /review re-checks it",
    )
    add_output_flags(someday_parser, quiet=True)
    someday_parser.set_defaults(func=cmd_someday)

    unsomeday_parser = subparsers.add_parser("unsomeday", help="Unpark a Someday item")
    unsomeday_parser.add_argument("id", help="Item ID")
    add_output_flags(unsomeday_parser, quiet=True)
    unsomeday_parser.set_defaults(func=cmd_unsomeday)

    # edit
    edit_parser = subparsers.add_parser("edit", help="Edit item fields")
    edit_parser.add_argument("id", help="Item ID to edit")
    edit_parser.add_argument("--title", help="New title")
    edit_parser.add_argument("--outcome", "--parent", dest="parent", help="New parent outcome ID (use 'none' to make standalone)")
    edit_parser.add_argument("--why", help="New brief.why")
    edit_parser.add_argument("--how", help="New brief.how (approach/strategy)")
    edit_parser.add_argument("--what", help="New brief.what")
    edit_parser.add_argument("--done", help="New brief.done")
    edit_parser.add_argument("--badly", help="New brief.badly — the pre-registered falsifier ('' clears)")
    edit_parser.add_argument("--order", type=int, help="New order within parent")
    edit_parser.add_argument("--note", help="New closing note (done items only; '' clears)")
    edit_parser.add_argument("--area", help="New area ('' clears)")
    edit_parser.add_argument("--append-how", dest="append_how",
                             help="Append a paragraph to brief.how (atomic — no read-modify-write)")
    edit_parser.add_argument("--json", action="store_true", dest="json_input",
                             help="Read fields as JSON from stdin (the default when stdin is piped and no flag is given)")
    add_output_flags(edit_parser, quiet=True)
    edit_parser.set_defaults(func=cmd_edit)

    # status
    status_parser = subparsers.add_parser("status", help="Show status overview")
    status_parser.set_defaults(func=cmd_status)

    # work
    work_parser = subparsers.add_parser("work", help="Manage tactical steps for an action")
    work_parser.add_argument("args", nargs=argparse.REMAINDER, help="Action ID followed by optional steps")
    work_parser.add_argument("--status", action="store_true", help="Show current tactical state")
    work_parser.add_argument("--clear", action="store_true", help="Clear tactical steps (bare: this session's claim, active or finished; with ID: that item's)")
    work_parser.add_argument("--release", action="store_true",
                             help="Hand back the claim but KEEP the progress (pair to --clear, which discards it)")
    work_parser.add_argument("--force", action="store_true", help="Restart steps even if in progress")
    work_parser.set_defaults(func=cmd_work)

    # step
    step_parser = subparsers.add_parser("step", help="Complete current step, advance to next")
    step_parser.add_argument("--skip", metavar="REASON", help="Skip current step with a reason instead of completing it")
    step_parser.add_argument("--no-complete", action="store_true", help="Don't auto-complete action on final step")
    step_parser.add_argument("--expect", type=int, metavar="N", help="1-based step number you believe you're completing; refuses without writing if the board moved")
    step_parser.set_defaults(func=cmd_step)

    # convert
    convert_parser = subparsers.add_parser("convert", help="Convert outcome↔action")
    convert_parser.add_argument("id", help="Item ID to convert")
    convert_parser.add_argument("--outcome", "--parent", "-p", dest="parent", help="Parent outcome (required for outcome→action)")
    add_output_flags(convert_parser, quiet=True)
    convert_parser.add_argument("--force", "-f", action="store_true",
                                help="Allow converting outcome with children (makes them standalone)")
    convert_parser.set_defaults(func=cmd_convert)

    # move
    move_parser = subparsers.add_parser("move", help="Move an item to another repo's board")
    move_parser.add_argument("id", help="Item ID to move")
    move_parser.add_argument("--to", required=True, metavar="REPO",
                             help="Target repo: a path, or a bare repo name resolved under ~/repos/*/")
    move_parser.add_argument("--quiet", "-q", action="store_true", help="Print only the new ID")
    move_parser.set_defaults(func=cmd_move)

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
    doctor_parser.add_argument(
        "--fix",
        action="store_true",
        help="Repair fixable issues (refreshes .bon/README.md to current wording)",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    # migrate
    register_parser = subparsers.add_parser(
        "register", help="Register this board in Dolt's repos mapping table"
    )
    register_parser.add_argument(
        "--job",
        help="Assign this board to a review jobs-group (e.g. 'knowledge work'); "
        "--job '' clears the assignment",
    )
    register_parser.set_defaults(func=cmd_register)

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
    inv.note(subcommand=args.command, parsed=args)

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
