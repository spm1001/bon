"""Display formatting for bon output."""
import json

from bon.ids import DEFAULT_ORDER
from bon.queries import filter_ready, filter_waiting


def format_tactical(tactical: dict) -> str:
    """Format tactical steps for display.

    Uses markers:
    - ✓ for completed steps (index < current)
    - ⊘ for skipped steps (index in skipped dict)
    - → for active step (index == current) with [current] suffix
    - (space) for pending steps (index > current)
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

    return "\n".join(lines)


def format_json(items: list[dict]) -> str:
    """Format as nested JSON structure."""
    outcomes = []
    for outcome in sorted(
        [i for i in items if i["type"] == "outcome"],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    ):
        actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", DEFAULT_ORDER)
        )
        outcome_copy = dict(outcome)
        outcome_copy["actions"] = actions
        outcomes.append(outcome_copy)

    standalone = sorted(
        [i for i in items if i["type"] == "action" and not i.get("parent")],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    )

    return json.dumps({"outcomes": outcomes, "standalone": standalone}, indent=2, ensure_ascii=False)


def format_jsonl(items: list[dict]) -> str:
    """Format as flat JSONL, one item per line."""
    lines = []
    for item in items:
        lines.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(lines)


def format_hierarchical(items: list[dict], filter_mode: str = "default") -> str:
    """Format items as hierarchical text output.

    Args:
        items: All items to consider
        filter_mode: One of:
            - "default": Open outcomes, all their actions (shows progress)
            - "ready": Open outcomes, only ready actions (or waiting count)
            - "waiting": Open outcomes, only waiting actions
            - "all": All outcomes including done, all their actions

    Returns:
        Formatted string output
    """
    lines = []
    include_done_outcomes = filter_mode == "all"

    # Get outcomes sorted by order
    outcomes = sorted(
        [i for i in items if i["type"] == "outcome" and (include_done_outcomes or i["status"] == "open")],
        key=lambda x: x.get("order", DEFAULT_ORDER)
    )

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
                waiting_suffix = f" ⏳ {action['waiting_for']}"
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

    if standalone:
        if lines:
            lines.append("")
        lines.append("Standalone:")
        for action in sorted(standalone, key=lambda x: x.get("order", DEFAULT_ORDER)):
            status_icon = "✓" if action["status"] == "done" else "○"
            waiting_suffix = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
            lines.append(f"  {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

    # Handle empty case
    if not lines:
        return "No outcomes."

    return "\n".join(lines)
