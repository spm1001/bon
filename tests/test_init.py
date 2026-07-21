"""Tests for bon init command."""


from conftest import run_bon


def test_init_creates_bon_directory(tmp_path, monkeypatch):
    """bon init creates .bon/ directory with items.jsonl and prefix."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".bon").is_dir()
    assert (tmp_path / ".bon" / "items.jsonl").exists()
    assert (tmp_path / ".bon" / "prefix").read_text() == "bon"
    assert "Initialized .bon/" in result.stdout


def test_init_custom_prefix(tmp_path, monkeypatch):
    """bon init --prefix sets custom prefix."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", "--prefix", "myproject", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".bon" / "prefix").read_text() == "myproject"
    assert "myproject" in result.stdout


def test_init_already_exists(tmp_path, monkeypatch):
    """bon init when an initialized .bon/ (has prefix) exists errors."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".bon").mkdir()
    (tmp_path / ".bon" / "prefix").write_text("x")

    result = run_bon("init", cwd=tmp_path)

    assert result.returncode == 1
    assert ".bon/ already exists" in result.stderr


def test_init_completes_markerless_bon(tmp_path, monkeypatch):
    """bon init on a .bon without prefix completes it (cloned-repo reconnect)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".bon").mkdir()

    result = run_bon("init", "--prefix", "abc", cwd=tmp_path)

    assert result.returncode == 0
    assert "Reconnected" in result.stdout


def test_init_prefix_no_trailing_newline(tmp_path, monkeypatch):
    """Prefix file has no trailing newline."""
    monkeypatch.chdir(tmp_path)

    run_bon("init", cwd=tmp_path)

    content = (tmp_path / ".bon" / "prefix").read_bytes()
    assert not content.endswith(b"\n")


def test_init_prefix_with_hyphen_rejected(tmp_path, monkeypatch):
    """Prefix with hyphen is rejected."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", "--prefix", "my-project", cwd=tmp_path)

    assert result.returncode == 1
    assert "alphanumeric" in result.stderr
    assert not (tmp_path / ".bon").exists()


def test_init_prefix_with_space_rejected(tmp_path, monkeypatch):
    """Prefix with space is rejected."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", "--prefix", "my project", cwd=tmp_path)

    assert result.returncode == 1
    assert "alphanumeric" in result.stderr
    assert not (tmp_path / ".bon").exists()


def test_init_prefix_alphanumeric_accepted(tmp_path, monkeypatch):
    """Alphanumeric prefix is accepted."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", "--prefix", "myProject123", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".bon" / "prefix").read_text() == "myProject123"


def test_init_writes_board_readme(tmp_path, monkeypatch):
    """bon init writes the .bon/README.md message-in-a-bottle."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", cwd=tmp_path)

    assert result.returncode == 0
    readme = tmp_path / ".bon" / "README.md"
    assert readme.exists()
    content = readme.read_text()
    assert "bon board" in content
    assert "items.jsonl" in content
    assert "Candidates" in content  # the no-CLI write path
    assert "dolt" in content  # the unreachable-backend branch


def test_init_refreshes_readme_on_reconnect(tmp_path, monkeypatch):
    """Reconnect (markerless .bon) refreshes a stale README to current content."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".bon").mkdir()
    (tmp_path / ".bon" / "README.md").write_text("old bottle\n")

    result = run_bon("init", "--prefix", "abc", cwd=tmp_path)

    assert result.returncode == 0
    assert "Reconnected" in result.stdout
    content = (tmp_path / ".bon" / "README.md").read_text()
    assert "old bottle" not in content
    assert "bon board" in content


def test_init_prints_discovery_stanza(tmp_path, monkeypatch):
    """bon init suggests a discovery stanza for CLAUDE.md and AGENTS.md."""
    monkeypatch.chdir(tmp_path)

    result = run_bon("init", cwd=tmp_path)

    assert result.returncode == 0
    assert "CLAUDE.md" in result.stdout
    assert "AGENTS.md" in result.stdout
    assert ".bon/README.md" in result.stdout
