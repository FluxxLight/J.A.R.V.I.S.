"""Fila de fala: UMA fala por vez, sem sobreposição, com interrupção.

- worker único em thread dedicada;
- speak() enfileira; speak(interrupt=True) corta a fala atual;
- stop()/shutdown() liberam recursos.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

from jarvis.logger import get_logger
from jarvis.voice.tts import LocalTTS

log = get_logger("voice.queue")


class SpeechQueue:
    def __init__(self, tts: LocalTTS,
                 on_start: Optional[Callable[[str], None]] = None,
                 on_finish: Optional[Callable[[str], None]] = None) -> None:
        self._tts = tts
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._on_start = on_start
        self._on_finish = on_finish
        self._stop_event = threading.Event()
        self._speaking = threading.Event()
        self._current: Optional[str] = None
        self._lock = threading.RLock()
        self._worker = threading.Thread(target=self._run, name="jarvis-tts",
                                        daemon=True)
        self._worker.start()

    @property
    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    def set_tts(self, tts: LocalTTS) -> None:
        with self._lock:
            self._tts = tts

    def speak(self, text: str, interrupt: bool = False) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        if self._stop_event.is_set():
            return False
        if interrupt:
            self.stop_current()
        self._queue.put(text)
        log.debug("Fala enfileirada (%d na fila).", self._queue.qsize())
        return True

    def stop_current(self) -> None:
        """Interrompe a fala atual e limpa a fila."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            with self._lock:
                self._tts.stop()
        except Exception:
            log.exception("TTS stop falhou (não fatal)")

    def wait_until_done(self, timeout: Optional[float] = None) -> bool:
        import time
        deadline = None if timeout is None else time.time() + timeout
        while self._speaking.is_set() or not self._queue.empty():
            if deadline is not None and time.time() > deadline:
                return False
            time.sleep(0.05)
        return True

    def shutdown(self, wait: bool = True) -> None:
        self._stop_event.set()
        self.stop_current()
        self._queue.put("")  # acorda o worker
        if wait:
            self._worker.join(timeout=5)
        try:
            with self._lock:
                self._tts.close()
        except Exception:
            pass
        log.info("Fila de fala encerrada.")

    # -- worker -------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._stop_event.is_set():
                break
            if not text:
                continue
            self._speaking.set()
            self._current = text
            try:
                if self._on_start:
                    self._on_start(text)
                with self._lock:
                    tts = self._tts
                log.info("Falando: %r", text[:120])
                tts.speak(text)
            except Exception:
                log.exception("Falha na fala (não fatal)")
            finally:
                self._current = None
                # on_finish ANTES de liberar _speaking: quando wait_until_done()
                # retorna, as transições de estado já aconteceram (sem race).
                if self._on_finish:
                    try:
                        self._on_finish(text)
                    except Exception:
                        log.exception("on_finish falhou (não fatal)")
                self._speaking.clear()
