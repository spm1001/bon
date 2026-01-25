"""Display formatting for arc output."""


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
        key=lambda x: x.get("order", 999)
    )

    for outcome in outcomes:
        # Outcome line
        status_icon = "✓" if outcome["status"] == "done" else "○"
        lines.append(f"{status_icon} {outcome['title']} ({outcome['id']})")

        # Get actions for this outcome
        all_actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", 999)
        )

        # Filter actions based on mode
        if filter_mode == "ready":
            visible_actions = [a for a in all_actions if a["status"] == "open" and not a.get("waiting_for")]
            waiting_count = len([a for a in all_actions if a["status"] == "open" and a.get("waiting_for")])
        elif filter_mode == "waiting":
            visible_actions = [a for a in all_actions if a.get("waiting_for")]
            waiting_count = 0
        else:
            # default and all: show all actions
            visible_actions = all_actions
            waiting_count = 0

        # Render visible actions
        for idx, action in enumerate(visible_actions, 1):
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
    if filter_mode == "ready":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i["status"] == "open" and not i.get("waiting_for")]
    elif filter_mode == "waiting":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i.get("waiting_for")]
    elif filter_mode == "all":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")]
    else:
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i["status"] == "open"]

    if standalone:
        if lines:
            lines.append("")
        lines.append("Standalone:")
        for action in sorted(standalone, key=lambda x: x.get("order", 999)):
            status_icon = "✓" if action["status"] == "done" else "○"
            waiting_suffix = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
            lines.append(f"  {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

    # Handle empty case
    if not lines:
        return "No outcomes."

    return "\n".join(lines)
