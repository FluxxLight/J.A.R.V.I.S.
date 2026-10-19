"""Single instance do J.A.R.V.I.S.

1ª escolha (com Qt): QLocalServer — a 2ª instância envia "show" e sai;
a 1ª recebe e restaura/foca a janela.
Fallback headless (testável sem Qt): trava exclusiva em arquivo.

Ambos usam o mesmo nome canônico por usuário.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, Optional

from jarvis.logger import get_logger
from jarvis.storage import paths

log = get_logger("ui.single")

SERVER_NAME = "jarvis-hub-single-instance"


class FileLock:
    """Trava exclusiva via arquivo (fallback sem Qt / para testes)."""

    def __init__(self, lock_path: Path | str | None = None) -> None:
        self.path = Path(lock_path) if lock_path else paths.base_dir() / "jarvis.lock"
        self._fh = None
        self._lock = threading.RLock()

    def acquire(self) -> bool:
        with self._lock:
            if self._fh is not None:
                return True
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fh = open(self.path, "w")
                if os.name == "nt":
                    import msvcrt
                    try:
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError:
                        fh.close()
                        return False
                else:
                    import fcntl
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        fh.close()
                        return False
                fh.write(str(os.getpid()))
                fh.flush()
                self._fh = fh
                return True
            except OSError:
                log.exception("Falha ao adquirir trava de instância")
                return False

    def release(self) -> None:
        with self._lock:
            fh, self._fh = self._fh, None
            if fh is not None:
                try:
                    if os.name == "nt":
                        import msvcrt
                        try:
                            fh.seek(0)
                            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                    else:
                        import fcntl
                        try:
                            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass
                    fh.close()
                except Exception:
                    pass
                try:
                    self.path.unlink(missing_ok=True)
                except OSError:
                    pass

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def try_notify_existing(timeout_ms: int = 1500) -> bool:
    """Tenta avisar a instância existente via QLocalSocket. Sem Qt -> False."""
    try:
        from PySide6.QtNetwork import QLocalSocket
    except Exception:
        return False
    try:
        sock = QLocalSocket()
        sock.connectToServer(SERVER_NAME)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write(b"show")
        sock.waitForBytesWritten(timeout_ms)
        sock.disconnectFromServer()
        return True
    except Exception:
        return False


class QtSingleServer:
    """Servidor QLocalServer. `on_show_request` foca a janela existente."""

    def __init__(self, on_show_request: Callable[[], None]) -> None:
        from PySide6.QtNetwork import QLocalServer
        self._server = QLocalServer()
        self._on_show = on_show_request
        # Remove socket órfão de crash anterior (Linux) — seguro.
        QLocalServer.removeServer(SERVER_NAME)
        if not self._server.listen(SERVER_NAME):
            log.error("Não foi possível escutar single-instance: %s",
                      self._server.errorString())
        self._server.newConnection.connect(self._handle)

    @property
    def listening(self) -> bool:
        try:
            return bool(self._server.isListening())
        except Exception:
            return False

    def _handle(self) -> None:
        try:
            sock = self._server.nextPendingConnection()
            if sock is not None:
                sock.waitForReadyRead(500)
                sock.disconnectFromServer()
        except Exception:
            log.exception("Falha ao atender pedido de foco (não fatal)")
        try:
            self._on_show()
        except Exception:
            log.exception("on_show_request falhou (não fatal)")

    def close(self) -> None:
        try:
            self._server.close()
        except Exception:
            pass
