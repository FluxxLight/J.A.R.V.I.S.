"""Estados reais do sistema J.A.R.V.I.S.

Fluxo normal:
    STARTING -> READY -> IDLE -> LISTENING -> PROCESSING -> EXECUTING
        -> SPEAKING -> READY (-> IDLE ...)

Erro:
    QUALQUER -> ERROR -> READY
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Callable, List, Optional

from jarvis.logger import get_logger

log = get_logger("core.states")


class SystemState(str, Enum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    READY = "READY"
    ERROR = "ERROR"
    SHUTDOWN = "SHUTDOWN"


# Transições válidas (None = estado inicial, antes de STARTING).
_ALLOWED: dict[Optional[SystemState], set[SystemState]] = {
    None: {SystemState.STARTING},
    SystemState.STARTING: {SystemState.READY, SystemState.ERROR, SystemState.SHUTDOWN},
    SystemState.READY: {
        SystemState.IDLE, SystemState.LISTENING, SystemState.PROCESSING,
        SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.IDLE: {
        SystemState.LISTENING, SystemState.PROCESSING, SystemState.SPEAKING,
        SystemState.READY, SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.LISTENING: {
        SystemState.PROCESSING, SystemState.IDLE, SystemState.READY,
        SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.PROCESSING: {
        SystemState.EXECUTING, SystemState.SPEAKING, SystemState.READY,
        SystemState.IDLE, SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.EXECUTING: {
        SystemState.SPEAKING, SystemState.READY, SystemState.IDLE,
        SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.SPEAKING: {
        SystemState.READY, SystemState.IDLE, SystemState.ERROR, SystemState.SHUTDOWN,
    },
    SystemState.ERROR: {
        SystemState.READY, SystemState.IDLE, SystemState.SHUTDOWN,
        SystemState.LISTENING, SystemState.PROCESSING,
    },
    SystemState.SHUTDOWN: set(),
}

StateListener = Callable[[SystemState, SystemState], None]


class StateMachine:
    """Máquina de estados thread-safe com listeners (para a UI futura)."""

    def __init__(self, initial: Optional[SystemState] = None) -> None:
        self._lock = threading.RLock()
        self._state: Optional[SystemState] = initial
        self._listeners: List[StateListener] = []

    @property
    def state(self) -> Optional[SystemState]:
        with self._lock:
            return self._state

    def add_listener(self, listener: StateListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def can_go(self, new_state: SystemState) -> bool:
        with self._lock:
            return new_state in _ALLOWED.get(self._state, set())

    def to(self, new_state: SystemState, force: bool = False) -> bool:
        """Transiciona de estado. Retorna False se a transição for inválida."""
        with self._lock:
            old = self._state
            if not force and new_state not in _ALLOWED.get(old, set()):
                log.warning("Transição de estado inválida: %s -> %s", old, new_state)
                return False
            self._state = new_state
        log.debug("Estado: %s -> %s", old, new_state)
        for listener in list(self._listeners):
            try:
                listener(old, new_state)  # type: ignore[arg-type]
            except Exception:  # listener nunca pode quebrar o core
                log.exception("Listener de estado falhou")
        return True

    def fail(self, reason: str = "") -> None:
        if reason:
            log.error("Estado ERROR: %s", reason)
        self.to(SystemState.ERROR, force=True)

    def recover(self) -> None:
        """ERROR -> READY (recuperação padrão após falha tratada)."""
        self.to(SystemState.READY, force=True)
