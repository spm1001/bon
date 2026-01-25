"""Tests for arc init command."""
import os
from pathlib import Path

import pytest

from conftest import run_arc


def test_init_creates_arc_directory(tmp_path, monkeypatch):
    """arc init creates .arc/ directory with items.jsonl and prefix."""
    monkeypatch.chdir(tmp_path)

    result = run_arc("init", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".arc").is_dir()
    assert (tmp_path / ".arc" / "items.jsonl").exists()
    assert (tmp_path / ".arc" / "prefix").read_text() == "arc"
    assert "Initialized .arc/" in result.stdout


def test_init_custom_prefix(tmp_path, monkeypatch):
    """arc init --prefix sets custom prefix."""
    monkeypatch.chdir(tmp_path)

    result = run_arc("init", "--prefix", "myproject", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".arc" / "prefix").read_text() == "myproject"
    assert "myproject" in result.stdout


def test_init_already_exists(tmp_path, monkeypatch):
    """arc init when .arc/ exists errors."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".arc").mkdir()

    result = run_arc("init", cwd=tmp_path)

    assert result.returncode == 1
    assert ".arc/ already exists" in result.stderr


def test_init_prefix_no_trailing_newline(tmp_path, monkeypatch):
    """Prefix file has no trailing newline."""
    monkeypatch.chdir(tmp_path)

    run_arc("init", cwd=tmp_path)

    content = (tmp_path / ".arc" / "prefix").read_bytes()
    assert not content.endswith(b"\n")


def test_init_prefix_with_hyphen_rejected(tmp_path, monkeypatch):
    """Prefix with hyphen is rejected."""
    monkeypatch.chdir(tmp_path)

    result = run_arc("init", "--prefix", "my-project", cwd=tmp_path)

    assert result.returncode == 1
    assert "alphanumeric" in result.stderr
    assert not (tmp_path / ".arc").exists()


def test_init_prefix_with_space_rejected(tmp_path, monkeypatch):
    """Prefix with space is rejected."""
    monkeypatch.chdir(tmp_path)

    result = run_arc("init", "--prefix", "my project", cwd=tmp_path)

    assert result.returncode == 1
    assert "alphanumeric" in result.stderr
    assert not (tmp_path / ".arc").exists()


def test_init_prefix_alphanumeric_accepted(tmp_path, monkeypatch):
    """Alphanumeric prefix is accepted."""
    monkeypatch.chdir(tmp_path)

    result = run_arc("init", "--prefix", "myProject123", cwd=tmp_path)

    assert result.returncode == 0
    assert (tmp_path / ".arc" / "prefix").read_text() == "myProject123"
