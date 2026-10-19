"""Single instance: trava de arquivo + handshake Qt (sem servidor => False)."""

from jarvis.ui.hub.single_instance import FileLock, try_notify_existing


def test_file_lock_exclusive(tmp_path):
    lock_path = tmp_path / "jarvis.lock"
    first = FileLock(lock_path)
    second = FileLock(lock_path)
    assert first.acquire() is True
    assert second.acquire() is False  # já detida
    first.release()
    assert second.acquire() is True  # liberou -> ok
    second.release()


def test_file_lock_reentrant_and_cleanup(tmp_path):
    lock_path = tmp_path / "jarvis.lock"
    lock = FileLock(lock_path)
    assert lock.acquire() is True
    assert lock.acquire() is True
    lock.release()
    assert not lock_path.exists()


def test_file_lock_context_manager(tmp_path):
    with FileLock(tmp_path / "x.lock") as lock:
        assert lock._fh is not None


def test_notify_without_server_returns_false():
    # Sem Qt ou sem servidor escutando: False, sem exceção.
    assert try_notify_existing(timeout_ms=200) is False
