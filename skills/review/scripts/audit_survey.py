# /// script
# requires-python = ">=3.9"
# ///
"""Audit survey — scans all .bon/ directories under ~/Repos and produces
a JSON summary of open items with full briefs and age flags.

Built for the /audit skill. For human-readable overviews, use bon-survey.py.

Usage:
    uv run --script audit_survey.py              # JSON to stdout
    uv run --script audit_survey.py --repos trousse passe  # Filter to specific repos
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_items(bon_path: Path) -> list[dict]:
    """Load items from a .bon/items.jsonl file, deduping by last occurrence."""
    items = {}
    with open(bon_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            items[item["id"]] = item  # last wins (union merge dedup)
    return list(items.values())


def age_flag(created_at: str | None) -> str | None:
    """Return an age flag based on item creation date."""
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days >= 60:
            return "very_old"
        if age_days >= 30:
            return "old"
        return None
    except (ValueError, TypeError):
        return None


def item_record(item: dict) -> dict:
    """Extract the fields the audit skill needs for verification."""
    record = {
        "id": item["id"],
        "title": item["title"],
        "type": item["type"],
        "status": item.get("status", "open"),
    }
    if item.get("parent"):
        record["parent"] = item["parent"]
    if item.get("waiting_for"):
        record["waiting_for"] = item["waiting_for"]
    if item.get("created_at"):
        record["created_at"] = item["created_at"]
        flag = age_flag(item["created_at"])
        if flag:
            record["age_flag"] = flag
    # Full brief fields for verification (nested under "brief" key)
    brief = item.get("brief", {})
    if brief:
        for field in ("why", "what", "done"):
            if brief.get(field):
                record[field] = brief[field]
    return record


def survey(repos_dir: Path, repo_filter: list[str] | None = None) -> list[dict]:
    """Scan repos and return structured audit data."""
    results = []
    for entry in sorted(repos_dir.iterdir()):
        if not entry.is_dir():
            continue
        if repo_filter and entry.name not in repo_filter:
            continue

        items_path = entry / ".bon" / "items.jsonl"
        if not items_path.exists():
            continue

        items = load_items(items_path)
        open_items = [i for i in items if i.get("status") == "open"]

        if not open_items:
            continue

        outcomes = [item_record(i) for i in open_items if i["type"] == "outcome"]
        actions = [item_record(i) for i in open_items if i["type"] == "action"]

        results.append({
            "repo": entry.name,
            "repo_path": str(entry),
            "open_count": len(open_items),
            "outcomes": outcomes,
            "actions": actions,
        })

    results.sort(key=lambda r: r["open_count"], reverse=True)
    return results


def main():
    repos_dir = Path(os.environ.get("REPOS_DIR", Path.home() / "Repos"))

    # Parse --repos filter
    repo_filter = None
    if "--repos" in sys.argv:
        idx = sys.argv.index("--repos")
        repo_filter = sys.argv[idx + 1:]

    results = survey(repos_dir, repo_filter)

    total = sum(r["open_count"] for r in results)
    output = {
        "total_open": total,
        "repos_with_open": len(results),
        "repos": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
