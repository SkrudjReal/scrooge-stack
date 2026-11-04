"""Mounted vaults must not enter excluded caches or follow external symlinks."""
import os
from pathlib import Path

import pytest

from scripts import scan_vault
from scripts.memory_index import scan_files


def test_prunes_unreadable_cache_before_scandir(tmp_path, monkeypatch):
    (tmp_path / ".smart-env" / "multi").mkdir(parents=True)
    (tmp_path / "note.md").write_text("# Note")
    original = os.scandir

    def guarded(path):
        if ".smart-env" in Path(path).parts:
            raise OSError("unreadable Windows cache")
        return original(path)

    monkeypatch.setattr(os, "scandir", guarded)
    assert scan_vault.scan_vault(tmp_path)["titles"] == ["note"]
    assert list(scan_files(tmp_path)) == ["note.md"]


def test_external_symlinks_are_not_scanned(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (tmp_path / "secret.md").write_text("outside")
    (vault / "leak.md").symlink_to(tmp_path / "secret.md")
    (vault / "outside").symlink_to(tmp_path, target_is_directory=True)
    assert list(scan_vault.iter_vault_notes(vault)) == []


def test_real_scan_error_is_not_silently_indexed_as_deletion(tmp_path, monkeypatch):
    def denied(path):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "scandir", denied)
    with pytest.raises(PermissionError):
        scan_files(tmp_path)
