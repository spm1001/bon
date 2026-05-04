"""Tests for the optional --how brief field."""
import json

from conftest import run_bon


class TestNewWithHow:
    def test_create_with_how(self, bon_dir, monkeypatch):
        """bon new with --how stores it in brief."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "API rate limited",
            "--why", "429s under load",
            "--how", "Redis-based limiter, don't touch auth middleware",
            "--what", "1. Add limiter 2. Test",
            "--done", "Load test passes",
            cwd=bon_dir
        )

        assert result.returncode == 0
        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "Redis-based limiter, don't touch auth middleware"

    def test_create_without_how(self, bon_dir, monkeypatch):
        """bon new without --how produces valid item with no how field."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "Simple fix",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert "how" not in item["brief"]
        assert item["brief"]["why"] == "w"

    def test_how_not_required(self, bon_dir, monkeypatch):
        """Missing --how does not cause error (unlike missing --why)."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "No how needed",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0


class TestEditHow:
    def test_edit_adds_how(self, bon_dir, monkeypatch):
        """bon edit --how adds how to item that didn't have one."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "Outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("edit", item_id, "--how", "Use approach X", cwd=bon_dir)
        assert result.returncode == 0

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "Use approach X"

    def test_edit_clears_how(self, bon_dir, monkeypatch):
        """bon edit --how '' removes how from item."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "Has how",
            "--why", "w", "--how", "approach", "--what", "x", "--done", "d",
            cwd=bon_dir
        )
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("edit", item_id, "--how", "", cwd=bon_dir)
        assert result.returncode == 0

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert "how" not in item["brief"]

    def test_edit_updates_how(self, bon_dir, monkeypatch):
        """bon edit --how replaces existing how."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "Evolving",
            "--why", "w", "--how", "old approach", "--what", "x", "--done", "d",
            cwd=bon_dir
        )
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        run_bon("edit", item_id, "--how", "new approach", cwd=bon_dir)

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "new approach"


class TestShowHow:
    def test_show_displays_how(self, bon_dir, monkeypatch):
        """bon show includes --how in text output."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "With how",
            "--why", "reason", "--how", "the approach", "--what", "stuff", "--done", "criteria",
            cwd=bon_dir
        )
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("show", item_id, cwd=bon_dir)
        assert "--how: the approach" in result.stdout
        # Verify ordering: why before how before what
        why_pos = result.stdout.index("--why:")
        how_pos = result.stdout.index("--how:")
        what_pos = result.stdout.index("--what:")
        assert why_pos < how_pos < what_pos

    def test_show_omits_how_when_absent(self, bon_dir, monkeypatch):
        """bon show doesn't print --how line when field is absent."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "No how", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("show", item_id, cwd=bon_dir)
        assert "--how:" not in result.stdout

    def test_show_json_has_how_null(self, bon_dir, monkeypatch):
        """bon show --json includes how: null for items without how."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "No how", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("show", item_id, "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert data["brief"]["how"] is None

    def test_show_json_has_how_value(self, bon_dir, monkeypatch):
        """bon show --json includes how value when present."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "With how",
            "--why", "w", "--how", "approach", "--what", "x", "--done", "d",
            cwd=bon_dir
        )
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon("show", item_id, "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert data["brief"]["how"] == "approach"


class TestListJsonHow:
    def test_list_json_normalizes_how(self, bon_dir, monkeypatch):
        """bon list --json includes how: null on items without how."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "No how", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)

        result = run_bon("list", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert data["outcomes"][0]["brief"]["how"] is None

    def test_list_json_preserves_how(self, bon_dir, monkeypatch):
        """bon list --json includes how value when present."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "With how",
            "--why", "w", "--how", "approach", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        result = run_bon("list", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert data["outcomes"][0]["brief"]["how"] == "approach"


class TestWorkSurfacesHow:
    def test_work_prints_approach(self, bon_dir, monkeypatch):
        """bon work prints Approach: line when how is present."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "Outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        oid = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        run_bon(
            "new", "Action with how",
            "--outcome", oid,
            "--why", "w", "--how", "use Redis", "--what", "1. Step one 2. Step two", "--done", "d",
            cwd=bon_dir
        )
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        aid = next(i["id"] for i in items if i["type"] == "action")

        result = run_bon("work", aid, cwd=bon_dir)
        assert "Approach: use Redis" in result.stdout

    def test_work_no_approach_without_how(self, bon_dir, monkeypatch):
        """bon work doesn't print Approach: when how is absent."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "Outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        oid = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        run_bon(
            "new", "Action no how",
            "--outcome", oid,
            "--why", "w", "--what", "1. Step one 2. Step two", "--done", "d",
            cwd=bon_dir
        )
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        aid = next(i["id"] for i in items if i["type"] == "action")

        result = run_bon("work", aid, cwd=bon_dir)
        assert "Approach:" not in result.stdout


class TestRoundTrip:
    def test_three_field_brief_loads_clean(self, bon_dir, monkeypatch):
        """Items with 3-field brief (no how) load and save without error."""
        monkeypatch.chdir(bon_dir)

        # Write a 3-field item directly (simulating pre-how data)
        item = {
            "id": "bon-legacy",
            "type": "outcome",
            "title": "Legacy item",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "status": "open",
            "order": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
        }
        (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")

        # Load and show — should work
        result = run_bon("show", "bon-legacy", cwd=bon_dir)
        assert result.returncode == 0
        assert "--why: w" in result.stdout
        assert "--how:" not in result.stdout

        # List should work
        result = run_bon("list", cwd=bon_dir)
        assert result.returncode == 0

    def test_four_field_brief_round_trips(self, bon_dir, monkeypatch):
        """Items with 4-field brief (with how) survive save/load cycle."""
        monkeypatch.chdir(bon_dir)

        run_bon(
            "new", "Four fields",
            "--why", "w", "--how", "h", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        # Edit something else to force a save/load cycle
        item_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]
        run_bon("edit", item_id, "--title", "Still four fields", cwd=bon_dir)

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "h"
        assert item["title"] == "Still four fields"
