"""Tests for app/storage/storage.py's Storage facade construction."""
from app.storage.storage import Storage


def test_storage_defaults_to_data_dir_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    storage = Storage()

    assert storage.base_dir.resolve() == (tmp_path / "data").resolve()


def test_storage_uses_data_dir_env_var_when_set(tmp_path, monkeypatch):
    """docs/16, 16-21: DATA_DIR makes the persistent-volume coupling
    explicit instead of relying on a bare relative path plus WORKDIR."""
    target = tmp_path / "explicit-data-dir"
    monkeypatch.setenv("DATA_DIR", str(target))

    storage = Storage()

    assert storage.base_dir == target
    assert target.exists()


def test_storage_explicit_base_dir_overrides_env_var(tmp_path, monkeypatch):
    """An explicitly-passed base_dir (what every other test in this suite
    does) must still win over DATA_DIR -- tests must stay isolated to their
    own tmp_path regardless of what's in the environment."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "should-not-be-used"))
    explicit = tmp_path / "explicit"

    storage = Storage(str(explicit))

    assert storage.base_dir == explicit
