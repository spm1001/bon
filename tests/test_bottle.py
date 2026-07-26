"""Tests for the bottle refresh path (bon-perare).

.bon/README.md (the message in a bottle, bon-miheza) refreshes to current
BOARD_README wording on the back of every save — the same parasitic pattern
as Dolt repos-table registration — and `bon doctor --fix` is the deliberate
route for boards that aren't being written.
"""
from bon.storage import BOARD_README
from conftest import run_bon


def new_stub(cwd):
    return run_bon("new", "Stub", "--why", "w", "--what", "x", "--done", "d", "-q", cwd=cwd)


def test_save_creates_missing_bottle(bon_dir):
    """A board with no README.md (pre-miheza) gains one on any write."""
    readme = bon_dir / ".bon" / "README.md"
    readme.unlink()
    result = new_stub(bon_dir)
    assert result.returncode == 0
    assert readme.read_text() == BOARD_README


def test_save_refreshes_stale_bottle(bon_dir):
    """Stale wording converges to current on any write."""
    readme = bon_dir / ".bon" / "README.md"
    readme.write_text("old bottle\n")
    result = new_stub(bon_dir)
    assert result.returncode == 0
    assert readme.read_text() == BOARD_README


def test_done_refreshes_bottle(bon_dir):
    """The refresh rides every save path, not just new."""
    result = new_stub(bon_dir)
    item_id = result.stdout.strip()
    readme = bon_dir / ".bon" / "README.md"
    readme.write_text("old bottle\n")
    result = run_bon("done", item_id, cwd=bon_dir)
    assert result.returncode == 0
    assert readme.read_text() == BOARD_README


def test_move_refreshes_target_bottle(tmp_path):
    """Cross-repo writes (save_items_at) refresh the target board's bottle."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    for root, prefix in ((src, "srcpfx"), (dst, "dstpfx")):
        bon = root / ".bon"
        bon.mkdir(parents=True)
        (bon / "items.jsonl").touch()
        (bon / "prefix").write_text(prefix)
    result = new_stub(src)
    assert result.returncode == 0
    item_id = result.stdout.strip()
    result = run_bon("move", item_id, "--to", str(dst), cwd=src)
    assert result.returncode == 0
    assert (dst / ".bon" / "README.md").read_text() == BOARD_README
