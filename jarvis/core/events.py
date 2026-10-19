"""Barramento de eventos simples (desacopla Core/UI/Voz)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List

from jarvis.logger import get_logger

log = get_logger("core.events")

Handler = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        with self._lock:
            self._handlers[event].append(handler)

    def off(self, event: str, handler: Handler) -> None:
        with self._lock:
            if handler in self._handlers.get(event, []):
                self._handlers[event].remove(handler)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                handler(*args, **kwargs)
            except Exception:
                log.exception("Handler do evento '%s' falhou", event)


# Eventos padrão
STATE_CHANGED = "state_changed"
COMMAND_RECEIVED = "command_received"
COMMAND_EXECUTED = "command_executed"
VOICE_TRANSCRIPT = "voice_transcript"
SPEECH_STARTED = "speech_started"
SPEECH_FINISHED = "speech_finished"
APP_SHUTDOWN = "app_shutdown"
