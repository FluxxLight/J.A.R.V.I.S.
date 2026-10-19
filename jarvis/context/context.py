"""Contexto conversacional local (janela recente, sem IA generativa).

Resolve por regras:
- pronomes ("feche ele" -> último app relevante);
- continuação ("agora o youtube" após abrir navegador -> abrir youtube);
- repetição ("de novo" -> repete última ação quando seguro).
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from jarvis.logger import get_logger

log = get_logger("context")

_MAX_TURNS = 8
_CONTEXT_TTL = 120.0  # segundos: contexto expira

_PRONOUNS = {"ele", "ela", "eles", "elas", "isso", "isto", "esse", "essa",
             "este", "esta", "aquele", "aquela", "o mesmo", "a mesma"}

_CONTINUATION_PREFIXES = ("agora ", "e ", "depois ", "tambem ", "também ")

_UNSAFE_REPEAT_INTENTS = {
    "RESTART_COMPUTER", "SHUTDOWN_COMPUTER", "LOCK_COMPUTER", "EXIT_JARVIS",
}


@dataclass
class Interaction:
    text: str
    normalized: str
    intent: Optional[str] = None
    entities: dict[str, Any] = field(default_factory=dict)
    app: Optional[str] = None       # app relevante (ex.: "discord")
    url: Optional[str] = None
    success: bool = True
    ts: float = field(default_factory=time.time)


@dataclass
class ContextResolution:
    rewritten_text: Optional[str]  # texto reescrito com contexto aplicado
    note: str                      # explicação da resolução
    applied: bool


class ContextManager:
    def __init__(self, max_turns: int = _MAX_TURNS, ttl: float = _CONTEXT_TTL) -> None:
        self._lock = threading.RLock()
        self._turns: deque[Interaction] = deque(maxlen=max_turns)
        self._ttl = ttl

    # -- registro ----------------------------------------------------------
    def push(self, interaction: Interaction) -> None:
        with self._lock:
            self._turns.append(interaction)
            log.debug("Contexto: registrado intent=%s app=%s",
                      interaction.intent, interaction.app)

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()
            log.info("Contexto limpo.")

    def last(self) -> Optional[Interaction]:
        with self._lock:
            self._prune()
            return self._turns[-1] if self._turns else None

    def last_with_app(self) -> Optional[Interaction]:
        with self._lock:
            self._prune()
            for turn in reversed(self._turns):
                if turn.app:
                    return turn
            return None

    def _prune(self) -> None:
        now = time.time()
        while self._turns and (now - self._turns[0].ts) > self._ttl:
            self._turns.popleft()

    # -- resolução ---------------------------------------------------------
    def resolve(self, normalized: str) -> ContextResolution:
        """Tenta aplicar contexto ao texto normalizado. Puro e determinístico."""
        with self._lock:
            self._prune()
            if not self._turns:
                return ContextResolution(None, "sem contexto", False)

            tokens = set(normalized.split())

            # 1) Repetição: "de novo" / "repete"
            if normalized in {"de novo", "denovo", "repete", "repetir",
                              "outra vez", "novamente"} or \
                    normalized.endswith(" de novo") or normalized.endswith(" outra vez"):
                last = self._turns[-1]
                if last.intent and last.intent not in _UNSAFE_REPEAT_INTENTS:
                    log.info("Contexto: repetindo '%s'", last.text)
                    return ContextResolution(last.normalized, "repeticao", True)
                return ContextResolution(None, "repeticao insegura/indisponivel", False)

            # 2) Pronomes: "feche ele" -> "feche <app>"
            if tokens & _PRONOUNS:
                ref = self.last_with_app()
                if ref and ref.app:
                    rewritten = normalized
                    for pron in sorted(_PRONOUNS, key=len, reverse=True):
                        rewritten = re.sub(rf"\b{re.escape(pron)}\b", ref.app, rewritten)
                    log.info("Contexto: pronome resolvido para app='%s'", ref.app)
                    return ContextResolution(rewritten, f"pronome->{ref.app}", True)
                return ContextResolution(None, "pronome sem referente", False)

            # 3) Continuação: "agora o youtube" / "e o discord"
            lowered = normalized
            for prefix in _CONTINUATION_PREFIXES:
                if lowered.startswith(prefix):
                    remainder = lowered[len(prefix):].strip()
                    last = self._turns[-1]
                    if last.intent in {"OPEN_BROWSER", "OPEN_APP", "OPEN_URL"} and remainder:
                        rewritten = f"abrir {remainder}"
                        log.info("Contexto: continuacao '%s' -> '%s'", normalized, rewritten)
                        return ContextResolution(rewritten, "continuacao->abra", True)
                    break

            return ContextResolution(None, "sem regra aplicavel", False)
