"""Confirmações explícitas para ações perigosas (com expiração)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.command_engine.normalizer import normalize

# Formas brutas + lematizadas (o normalizer converte "confirma"->"confirmar" etc.)
CONFIRM_WORDS = {"sim", "confirmo", "confirmar", "confirma", "pode confirmar",
                 "pode sim", "confirma sim", "confirmar sim", "isso", "isso mesmo",
                 "ok confirma", "ok confirmar", "pode", "pode ir", "vai",
                 "prossiga", "prosseguir", "prossiga sim", "prosseguir sim"}
CANCEL_WORDS = {"nao", "não", "cancelar", "cancela", "cancele", "cancela isso",
                "cancelar isso", "nao quero", "não quero", "para", "pare", "parar",
                "esquece", "esquecer", "deixa pra la", "deixa para la",
                "abortar", "aborta", "aborte"}

TIMEOUT_SECONDS = 60.0


@dataclass
class PendingConfirmation:
    intent: str
    command_id: str
    action_id: str
    params: dict[str, Any]
    prompt: str
    created_at: float = field(default_factory=time.time)
    source: str = "text"


class ConfirmationManager:
    def __init__(self, timeout: float = TIMEOUT_SECONDS) -> None:
        self._lock = threading.RLock()
        self._pending: Optional[PendingConfirmation] = None
        self._timeout = timeout

    def has_pending(self) -> bool:
        with self._lock:
            self._expire_if_needed()
            return self._pending is not None

    def request(self, pending: PendingConfirmation) -> None:
        with self._lock:
            self._pending = pending

    def peek(self) -> Optional[PendingConfirmation]:
        with self._lock:
            self._expire_if_needed()
            return self._pending

    def resolve(self, text: str) -> Optional[bool]:
        """Interpreta resposta: True=confirmou, False=cancelou, None=não é resposta.

        No 'sim' NÃO limpa o pendente aqui: quem consome é `take()`,
        chamado pelo executor logo em seguida (evita condição de corrida).
        """
        norm = normalize(text)
        with self._lock:
            self._expire_if_needed()
            if self._pending is None:
                return None
            if norm in CONFIRM_WORDS or norm.startswith("sim ") or norm.endswith(" sim"):
                return True
            if norm in CANCEL_WORDS or norm.startswith("nao ") or norm.startswith("não "):
                self._pending = None
                return False
            return None

    def take(self) -> Optional[PendingConfirmation]:
        with self._lock:
            self._expire_if_needed()
            pending, self._pending = self._pending, None
            return pending

    def cancel(self) -> bool:
        with self._lock:
            if self._pending is None:
                return False
            self._pending = None
            return True

    def _expire_if_needed(self) -> None:
        if self._pending and (time.time() - self._pending.created_at) > self._timeout:
            self._pending = None
