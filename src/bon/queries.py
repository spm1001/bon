"""Query functions for filtering items."""


def filter_ready(items: list[dict]) -> list[dict]:
    """Return items that can be worked on now."""
    return [
        i for i in items
        if i["status"] == "open" and not i.get("waiting_for")
    ]


def filter_waiting(items: list[dict]) -> list[dict]:
    """Return items that are waiting."""
    return [i for i in items if i.get("waiting_for")]


def open_child_parent_ids(items: list[dict]) -> set[str]:
    """IDs of parents that have at least one open child action.

    A done outcome with open children must stay board-visible —
    otherwise open work silently vanishes from bon list (bon-kegewe).
    """
    return {
        i["parent"] for i in items
        if i["type"] == "action" and i["status"] == "open" and i.get("parent")
    }
