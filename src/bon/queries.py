"""Query functions for filtering items."""


def someday_ids(items: list[dict]) -> set[str]:
    """IDs effectively parked Someday/Maybe (bon-majoca).

    The `someday` field holds the revisit condition; truthy means parked.
    Children of a parked parent inherit at read time — parking an outcome
    parks its subtree with no mutation of the children. Inheritance is only
    complete when `items` is the whole board (a child passed without its
    parent can't see the parent's flag).
    """
    flagged = {i["id"] for i in items if i.get("someday")}
    return {
        i["id"] for i in items
        if i.get("someday") or i.get("parent") in flagged
    }


def filter_ready(items: list[dict]) -> list[dict]:
    """Return items that can be worked on now.

    Parked (someday) items are not ready — deliberately dormant is the
    opposite of workable-now, and orientation noise is what the flag exists
    to remove.
    """
    parked = someday_ids(items)
    return [
        i for i in items
        if i["status"] == "open" and not i.get("waiting_for")
        and i["id"] not in parked
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
