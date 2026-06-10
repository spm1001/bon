# /// script
# requires-python = ">=3.9"
# ///
"""Audit survey — recursively scans all .bon/ directories under the scan
roots and produces a JSON summary of open items with full briefs and age flags.

Default roots: whichever of ~/repos, ~/Repos, ~/notes exist (deduped by
realpath — on case-insensitive APFS the first two are the same directory).
REPOS_DIR env var overrides with a single root; --roots overrides both.

Supports both JSONL and Dolt backends. Dolt repos are read via `bon list --jsonl`.

Built for the /audit skill. For human-readable overviews, use bon-survey.py.

Usage:
    uv run --script audit_survey.py              # JSON to stdout
    uv run --script audit_survey.py --repos trousse passe  # Filter to specific repos
    uv run --script audit_survey.py --roots ~/repos ~/notes  # Explicit roots
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_items_jsonl(bon_path: Path) -> list[dict]:
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


def load_items_dolt(repo_path: Path) -> list[dict]:
    """Load items from a Dolt-backed repo via `bon list --jsonl`."""
    try:
        result = subprocess.run(
            ["bon", "list", "--jsonl"],
            cwd=repo_path,
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        items = {}
        for line in result.stdout.strip().splitlines():
            if line:
                item = json.loads(line)
                items[item["id"]] = item
        return list(items.values())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_backend(bon_dir: Path) -> str:
    """Read .bon/backend to determine storage type. Absent = jsonl."""
    backend_file = bon_dir / "backend"
    if backend_file.exists():
        return backend_file.read_text().strip()
    return "jsonl"


def load_items(bon_dir: Path, repo_path: Path) -> list[dict]:
    """Load items from a .bon/ directory, dispatching by backend."""
    backend = get_backend(bon_dir)
    if backend == "dolt":
        return load_items_dolt(repo_path)
    items_path = bon_dir / "items.jsonl"
    if items_path.exists():
        return load_items_jsonl(items_path)
    return []


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


def repo_label(repo_path: Path, root: Path) -> str:
    """Derive a human-readable repo label relative to its scan root."""
    try:
        label = str(repo_path.relative_to(root))
    except ValueError:
        return repo_path.name
    # A board at the root itself (e.g. ~/notes/.bon) labels as the root's name
    return root.name if label == "." else label


def discover_bon_dirs(root: Path) -> list[Path]:
    """Recursively find all .bon/ directories under root."""
    return sorted(root.rglob(".bon"))


def default_roots() -> list[Path]:
    """Existing scan roots, deduped by realpath (Mac's ~/Repos == ~/repos)."""
    candidates = [Path.home() / "repos", Path.home() / "Repos", Path.home() / "notes"]
    seen, roots = set(), []
    for c in candidates:
        if c.is_dir():
            rp = c.resolve()
            if rp not in seen:
                seen.add(rp)
                roots.append(rp)
    return roots


def survey(roots: list[Path], repo_filter: list[str] | None = None) -> tuple[list[dict], int]:
    """Scan all roots and return (structured audit data, boards discovered)."""
    results = []
    seen_dirs: set[Path] = set()
    boards_found = 0

    for root in roots:
        for bon_dir in discover_bon_dirs(root):
            if not bon_dir.is_dir():
                continue
            real = bon_dir.resolve()
            if real in seen_dirs:
                continue
            seen_dirs.add(real)
            # Skip nested .bon inside node_modules, .git, etc.
            parts = bon_dir.parts
            if any(p.startswith(".") and p != ".bon" for p in parts):
                continue
            if "node_modules" in parts:
                continue

            boards_found += 1
            repo_path = bon_dir.parent
            label = repo_label(repo_path, root)

            if repo_filter and not any(f in label for f in repo_filter):
                continue

            items = load_items(bon_dir, repo_path)
            open_items = [i for i in items if i.get("status") == "open"]

            if not open_items:
                continue

            outcomes = [item_record(i) for i in open_items if i["type"] == "outcome"]
            actions = [item_record(i) for i in open_items if i["type"] == "action"]

            results.append({
                "repo": label,
                "repo_path": str(repo_path),
                "open_count": len(open_items),
                "outcomes": outcomes,
                "actions": actions,
            })

    results.sort(key=lambda r: r["open_count"], reverse=True)
    return results, boards_found


def main():
    # Root priority: --roots flag > REPOS_DIR env > defaults
    if "--roots" in sys.argv:
        idx = sys.argv.index("--roots")
        vals = []
        for a in sys.argv[idx + 1:]:
            if a.startswith("--"):
                break
            vals.append(a)
        roots = [Path(v).expanduser() for v in vals]
    elif os.environ.get("REPOS_DIR"):
        roots = [Path(os.environ["REPOS_DIR"])]
    else:
        roots = default_roots()

    # Parse --repos filter
    repo_filter = None
    if "--repos" in sys.argv:
        idx = sys.argv.index("--repos")
        repo_filter = []
        for a in sys.argv[idx + 1:]:
            if a.startswith("--"):
                break
            repo_filter.append(a)

    results, boards_found = survey(roots, repo_filter)

    if boards_found == 0:
        print(
            f"Warning: no .bon directories found under: "
            f"{', '.join(str(r) for r in roots)}",
            file=sys.stderr,
        )

    total = sum(r["open_count"] for r in results)
    output = {
        "roots": [str(r) for r in roots],
        "total_open": total,
        "repos_with_open": len(results),
        "repos": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
