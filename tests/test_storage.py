"""JsonStore: escrita atômica, corrupção recuperada, backup."""

from jarvis.storage.json_store import JsonStore


def test_save_load_roundtrip(tmp_path):
    store = JsonStore(tmp_path / "x.json", default_factory=dict)
    assert store.save({"a": 1}) is True
    assert store.load() == {"a": 1}


def test_missing_returns_default(tmp_path):
    store = JsonStore(tmp_path / "nope.json", default_factory=list)
    assert store.load() == []


def test_corrupt_returns_default_and_backups(tmp_path, data_dir):
    from jarvis.storage import paths
    target = tmp_path / "bad.json"
    target.write_text("{{{", encoding="utf-8")
    store = JsonStore(target, default_factory=dict)
    assert store.load() == {}
    backups = list(paths.base_dir().glob("backup/*"))
    assert len(backups) >= 1
