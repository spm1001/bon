"""Display formatting for bon output."""
import json

from bon.ids import DEFAULT_ORDER
from bon.queries import filter_ready, filter_waiting, open_child_parent_ids

# Optional brief fields with their default values for JSON output.
# Required fields (why, what, done) are always present; optional ones
# get normalized to their default when missing from stored data.
OPTIONAL_BRIEF_FIELDS = {"how": None}


def _normalize_brief(item: dict) -> dict:
    """Return a copy of item with optional brief fields guaranteed present.

    Used at the JSON output boundary so consumers get a consistent shape
    without polluting stored data with nulls.
    """
    if "brief" not in item:
        return item
    item = dict(item)
    item["brief"] = dict(item["brief"])
    for field, default in OPTIONAL_BRIEF_FIELDS.items():
        if field not in item["brief"]:
            item["brief"][field] = default
    return item


def format_tactical(tactical: dict, action_status: str | None = None) -> str:
    """Format tactical steps for display.

    Uses markers:
    - ✓ for completed steps (index < current)
    - ⊘ for skipped steps (index in skipped dict)
    - → for active step (index == current) with [current] suffix
    - (space) for pending steps (index > current)

    If action_status is provided and all steps are done but action is still
    open, appends a deliberate-open indicator line.
    """
    lines = []
    steps = tactical.get("steps", [])
    current = tactical.get("current", 0)
    skipped = tactical.get("skipped", {})

    for i, step in enumerate(steps):
        skip_reason = skipped.get(str(i))
        if i < current:
            if skip_reason:
                lines.append(f"⊘ {i + 1}. {step} [skipped: {skip_reason}]")
            else:
                lines.append(f"✓ {i + 1}. {step}")
        elif i == current:
            lines.append(f"→ {i + 1}. {step} [current]")
        else:
            lines.append(f"  {i + 1}. {step}")

    if action_status == "open" and current >= len(steps) and steps:
        lines.append("\nAll steps done — action left open (--no-complete)")

    return "\n".join(lines)


def format_json(items: list[dict]) -> str:
    """Format as nested JSON structure."""
    outcomes = []
    for outcome in sorted(
        [i for i in items if i["type"] == "outcome"],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    ):
        actions = sorted(
            [_normalize_brief(i) for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", DEFAULT_ORDER)
        )
        outcome_copy = _normalize_brief(outcome)
        outcome_copy["actions"] = actions
        outcomes.append(outcome_copy)

    standalone = sorted(
        [_normalize_brief(i) for i in items if i["type"] == "action" and not i.get("parent")],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    )

    return json.dumps({"outcomes": outcomes, "standalone": standalone}, indent=2, ensure_ascii=False)


def format_jsonl(items: list[dict]) -> str:
    """Format as flat JSONL, one item per line."""
    lines = []
    for item in items:
        lines.append(json.dumps(_normalize_brief(item), ensure_ascii=False))
    return "\n".join(lines)


def format_hierarchical(items: list[dict], filter_mode: str = "default", limit: int | None = None) -> str:
    """Format items as hierarchical text output.

    Args:
        items: All items to consider
        filter_mode: One of:
            - "default": Open outcomes, all their actions (shows progress)
            - "ready": Open outcomes, only ready actions (or waiting count)
            - "waiting": Open outcomes, only waiting actions
            - "all": All outcomes including done, all their actions
        limit: If set, keep only the first N top-level items (outcomes
            before standalones, each by render order). Children of kept
            outcomes come along.

    Returns:
        Formatted string output
    """
    lines = []
    include_done_outcomes = filter_mode == "all"

    # Get outcomes sorted by order. Done outcomes with open children stay
    # visible — their stragglers are still board work (bon-kegewe).
    open_parents = open_child_parent_ids(items)
    outcomes = sorted(
        [i for i in items if i["type"] == "outcome" and (
            include_done_outcomes or i["status"] == "open" or i["id"] in open_parents
        )],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    )

    # Apply limit: outcomes first, then standalones share whatever's left
    standalone_budget: int | None
    if limit is not None and limit > 0:
        if len(outcomes) >= limit:
            outcomes = outcomes[:limit]
            standalone_budget = 0
        else:
            standalone_budget = limit - len(outcomes)
    else:
        standalone_budget = None

    for outcome in outcomes:
        # Outcome line
        status_icon = "✓" if outcome["status"] == "done" else "○"
        lines.append(f"{status_icon} {outcome['title']} ({outcome['id']})")

        # Get actions for this outcome
        all_actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", DEFAULT_ORDER)
        )

        # Filter actions based on mode
        if filter_mode == "ready":
            ready_actions = filter_ready(all_actions)
            done_actions = [a for a in all_actions if a["status"] == "done"]
            visible_actions = done_actions + ready_actions
            # Re-sort by order to maintain original numbering
            visible_actions.sort(key=lambda x: x.get("order", DEFAULT_ORDER))
            waiting_count = len(filter_waiting([a for a in all_actions if a["status"] == "open"]))
        elif filter_mode == "waiting":
            visible_actions = filter_waiting(all_actions)
            waiting_count = 0
        else:
            # default and all: show all actions
            visible_actions = all_actions
            waiting_count = 0

        # Render visible actions (use action's own order for numbering)
        for action in visible_actions:
            idx = action.get("order", DEFAULT_ORDER)
            if action["status"] == "done":
                status_icon = "✓"
                waiting_suffix = ""
            elif action.get("waiting_for"):
                status_icon = "○"
                wf = action["waiting_for"]
                wf_str = ", ".join(wf) if isinstance(wf, list) else str(wf)
                waiting_suffix = f" ⏳ {wf_str}"
            else:
                status_icon = "○"
                waiting_suffix = ""

            lines.append(f"  {idx}. {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

        # Show waiting count when filtering to ready and some are hidden
        if filter_mode == "ready" and waiting_count > 0 and not visible_actions:
            lines.append(f"  ({waiting_count} waiting)")
        elif filter_mode == "ready" and waiting_count > 0 and visible_actions:
            lines.append(f"  (+{waiting_count} waiting)")

    # Add blank lines between outcomes (if there were any)
    if outcomes:
        # Join with blank lines between outcomes
        result_lines = []
        current_outcome_lines = []
        for line in lines:
            if line.startswith("○") or line.startswith("✓"):
                if current_outcome_lines:
                    result_lines.extend(current_outcome_lines)
                    result_lines.append("")
                current_outcome_lines = [line]
            else:
                current_outcome_lines.append(line)
        if current_outcome_lines:
            result_lines.extend(current_outcome_lines)
        lines = result_lines

    # Standalone actions (no parent)
    standalone_base = [i for i in items if i["type"] == "action" and not i.get("parent")]
    if filter_mode == "ready":
        standalone = filter_ready(standalone_base)
    elif filter_mode == "waiting":
        standalone = filter_waiting(standalone_base)
    elif filter_mode == "all":
        standalone = standalone_base
    else:
        standalone = [a for a in standalone_base if a["status"] == "open"]

    if standalone_budget is not None:
        standalone = sorted(standalone, key=lambda x: (x.get("order", DEFAULT_ORDER), x["id"]))[:standalone_budget]

    if standalone:
        if lines:
            lines.append("")
        lines.append("Standalone:")
        for action in sorted(standalone, key=lambda x: x.get("order", DEFAULT_ORDER)):
            status_icon = "✓" if action["status"] == "done" else "○"
            wf = action.get("waiting_for")
            waiting_suffix = f" ⏳ {', '.join(wf)}" if wf else ""
            lines.append(f"  {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

    # Handle empty case
    if not lines:
        return "No outcomes."

    return "\n".join(lines)
