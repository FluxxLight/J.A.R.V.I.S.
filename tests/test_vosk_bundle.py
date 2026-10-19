"""Empacotamento do Vosk: pasta _internal/vosk e import que não derruba o app."""

from pathlib import Path

from jarvis.packaging.vosk_bundle import (bundle_has_native, copy_vosk_into,
                                          native_basenames, pyinstaller_vosk_inputs,
                                          vosk_package_dir)
from jarvis.voice.recognizer import create_recognizer


def test_vosk_inputs_are_relative_destinations():
    datas, binaries, hidden = pyinstaller_vosk_inputs()
    assert "vosk" in hidden
    assert "cffi" in hidden
    for src, dest in datas + binaries:
        assert not dest.startswith("/") and not (len(dest) > 1 and dest[1] == ":")
        assert dest.replace("\\", "/").startswith("vosk")


def test_copy_and_detect_native(tmp_path):
    """Simula o pacote vosk (libvosk.dll + __init__.py) e o reparo do bundle."""
    fake = tmp_path / "site-packages" / "vosk"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("# fake vosk\n", encoding="utf-8")
    (fake / "libvosk.dll").write_bytes(b"MZ-fake")
    (fake / "libgcc_s_seh-1.dll").write_bytes(b"MZ-dep")
    names = native_basenames(fake)
    assert "libvosk.dll" in names
    datas, binaries, _ = pyinstaller_vosk_inputs(fake)
    dests = {d for _, d in binaries}
    assert "vosk" in dests
    srcs = {Path(s).name for s, _ in binaries}
    assert "libvosk.dll" in srcs

    internal = tmp_path / "_internal"
    written = copy_vosk_into(internal, fake)
    assert written
    assert bundle_has_native(internal)
    assert (internal / "vosk" / "libvosk.dll").is_file()
    assert (internal / "vosk" / "__init__.py").is_file()


def test_bundle_has_native_false_when_missing(tmp_path):
    assert bundle_has_native(tmp_path / "_internal") is False
    (tmp_path / "_internal" / "vosk").mkdir(parents=True)
    assert bundle_has_native(tmp_path / "_internal") is False


def test_create_recognizer_oserror_does_not_crash(monkeypatch):
    """O bug do EXE: import vosk levanta FileNotFoundError, não ImportError."""
    import builtins
    real = builtins.__import__

    def boom(name, *args, **kwargs):
        if name == "vosk" or name.startswith("vosk."):
            raise FileNotFoundError(
                r"D:\dist\JARVIS\_internal\vosk")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", boom)
    rec = create_recognizer()
    assert rec.is_ready() is False
    reason = rec.reason().lower()
    assert "vosk" in reason
    assert rec.listen_once(None, timeout=0.1).text == ""


def test_create_recognizer_import_error_still_unavailable():
    rec = create_recognizer()
    # neste sandbox vosk não está instalado
    if vosk_package_dir() is None:
        assert rec.is_ready() is False
        assert "vosk" in rec.reason().lower() or "modelo" in rec.reason().lower()


def test_spec_and_hook_point_at_vosk_dir():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "jarvis.spec").read_text(encoding="utf-8")
    hook = (root / "hooks" / "hook-vosk.py").read_text(encoding="utf-8")
    assert "pyinstaller_vosk_inputs" in spec
    assert "hookspath" in spec
    assert "vosk" in hook
    assert "libvosk" in hook or "nativos" in hook
