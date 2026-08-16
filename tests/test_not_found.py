"""Lookup misses name the board they searched (bon-vomuzi).

A wrong-cwd read returns a clean, confident null that reads exactly like a
real absence — the incident was `bon show bon-walile` reporting "not found"
as a finding while the item sat done on its own board; an earlier cd had
moved the board under the session. The error now names the board and cwd,
and calls out an id-prefix mismatch as the likelier truth.
"""
import json

import pytest
from conftest import run_bon


def _board(tmp_path, name, prefix):
    root = tmp_path / name
    bon = root / ".bon"
    bon.mkdir(parents=True)
    (bon / "items.jsonl").touch()
    (bon / "prefix").write_text(prefix)
    return root


def _new(cwd, title):
    r = run_bon("new", "-q", cwd=cwd,
                input=json.dumps({"type": "action", "title": title,
                                  "brief": {"why": "w", "what": "x", "done": "d"}}))
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class TestLookupMissNamesBoard:
    def test_miss_names_board_and_cwd(self, bon_dir):
        r = run_bon("show", "bon-zzzzzz", cwd=bon_dir)
        assert r.returncode == 1
        assert "board 'bon'" in r.stderr
        assert str(bon_dir) in r.stderr  # the cwd it resolved from

    def test_valid_id_from_wrong_board(self, tmp_path):
        """The incident shape: an id that EXISTS elsewhere, looked up here."""
        home = _board(tmp_path, "home", "alpha")
        away = _board(tmp_path, "away", "beta")
        real = _new(home, "Real work")  # alpha-xxxxxx
        r = run_bon("show", real, cwd=away)
        assert r.returncode == 1
        assert "board 'beta'" in r.stderr  # names what it searched
        assert "alpha" in r.stderr  # names the mismatched prefix
        assert "wrong directory?" in r.stderr

    def test_same_board_miss_no_mismatch_hint(self, bon_dir):
        r = run_bon("show", "bon-zzzzzz", cwd=bon_dir)
        assert "wrong directory?" not in r.stderr

    def test_prefixless_arg_no_mismatch_hint(self, bon_dir):
        """Prefix-tolerant lookup arg ('zzzzzz') carries no id prefix."""
        r = run_bon("show", "zzzzzz", cwd=bon_dir)
        assert r.returncode == 1
        assert "board 'bon'" in r.stderr
        assert "wrong directory?" not in r.stderr

    @pytest.mark.parametrize("verb", [
        ("done",), ("edit", "--title", "x"), ("wait", "reason"),
        ("work",), ("unwait",), ("someday", "cond"),
    ])
    def test_mutating_verbs_name_board(self, bon_dir, verb):
        r = run_bon(verb[0], "bon-zzzzzz", *verb[1:], cwd=bon_dir)
        assert r.returncode == 1, f"{verb[0]} rc={r.returncode}"
        assert "board 'bon'" in r.stderr, f"{verb[0]}: {r.stderr}"

    def test_parent_miss_names_board(self, bon_dir):
        r = run_bon("new", "Child", "--parent", "bon-zzzzzz",
                    "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        assert r.returncode == 1
        assert "Parent 'bon-zzzzzz' not found on board 'bon'" in r.stderr
