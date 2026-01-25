"""ID generation and ordering for arc items."""
import random

CONSONANTS = "bcdfghjklmnprstvwz"  # No ambiguous: q, x, y
VOWELS = "aeiou"

# Default order for items without explicit order (sorts last)
DEFAULT_ORDER = 999


def generate_id(prefix: str = "arc") -> str:
    """Generate pronounceable ID like 'arc-gaBdur'."""
    syllables = []
    for _ in range(3):
        c = random.choice(CONSONANTS)
        v = random.choice(VOWELS)
        # 30% chance to capitalize consonant
        if random.random() < 0.3:
            c = c.upper()
        syllables.append(c + v)
    return f"{prefix}-{''.join(syllables)}"


def generate_unique_id(prefix: str, existing_ids: set[str]) -> str:
    """Generate ID that doesn't collide with existing."""
    for _ in range(100):  # Safety limit
        new_id = generate_id(prefix)
        if new_id not in existing_ids:
            return new_id
    raise RuntimeError("Failed to generate unique ID after 100 attempts")


def next_order(items: list[dict], item_type: str, parent: str | None = None) -> int:
    """Get next order value (append position) for new item."""
    siblings = get_siblings(items, item_type, parent)
    if not siblings:
        return 1
    return max(i.get("order", 0) for i in siblings) + 1


def get_siblings(items: list[dict], item_type: str, parent: str | None = None) -> list[dict]:
    """Get sibling items for ordering context."""
    if parent:
        # Action under an outcome: siblings are other actions under same parent
        return [i for i in items if i.get("parent") == parent]
    elif item_type == "outcome":
        # Outcome: siblings are other outcomes
        return [i for i in items if i["type"] == "outcome"]
    else:
        # Standalone action: siblings are other standalone actions
        return [i for i in items if i["type"] == "action" and not i.get("parent")]
