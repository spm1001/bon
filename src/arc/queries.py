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
