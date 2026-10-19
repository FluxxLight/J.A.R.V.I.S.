"""Autostart: backend fake (roundtrip) + backend real sem crash fora do Win."""

from jarvis.ui.hub.autostart import (AutostartManager, MemoryBackend,
                                      WindowsRegistryBackend,
                                      default_start_command)


def test_memory_backend_roundtrip():
    mgr = AutostartManager(MemoryBackend())
    assert mgr.is_available()[0] is True
    assert mgr.is_enabled() is False
    ok, _ = mgr.set_enabled(True, '"x" --hub')
    assert ok is True
    assert mgr.is_enabled() is True
    assert mgr.is_enabled('"outro"') is False  # comando diferente
    ok, _ = mgr.set_enabled(False, "")
    assert ok is True
    assert mgr.is_enabled() is False


def test_memory_backend_unavailable():
    mgr = AutostartManager(MemoryBackend(available=False))
    assert mgr.is_available()[0] is False
    ok, msg = mgr.set_enabled(True, "x")
    assert ok is False and msg


def test_memory_backend_rejects_empty_command():
    mgr = AutostartManager(MemoryBackend())
    ok, msg = mgr.set_enabled(True, "   ")
    assert ok is False and "vazio" in msg.lower()


def test_real_backend_safe_off_windows():
    import sys
    mgr = AutostartManager(WindowsRegistryBackend())
    available, reason = mgr.is_available()
    if sys.platform.startswith("win"):
        assert available is True
    else:
        assert available is False
        assert "Windows" in reason
        assert mgr.is_enabled() is False
        ok, msg = mgr.set_enabled(True, "x")
        assert ok is False and msg


def test_default_start_command_format():
    cmd = default_start_command()
    assert "--hub" in cmd
    assert cmd.strip() != ""
