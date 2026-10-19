"""Tipos centrais: Command, Action, ActionResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ActionResult:
    success: bool
    message: str = ""        # mensagem técnica / log
    speak_text: str = ""     # o que o J.A.R.V.I.S. deve falar
    data: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success


@dataclass
class ActionContext:
    """Informações entregues à ação no momento da execução."""
    source: str = "text"          # "text" | "voice"
    raw_text: str = ""
    confirmed: bool = False       # True se passou por confirmação explícita
    request_exit: Any = None      # callable opcional p/ EXIT_JARVIS
    dry_run: bool = False         # True = simula sem executar (testes)


class Action:
    """Ação reutilizável. Toda execução real passa por aqui."""

    id: str = "BASE"
    requires_confirmation: bool = False
    confirm_prompt: str = "Tem certeza?"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        """Retorna mensagem de erro ou None se válido."""
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        raise NotImplementedError


@dataclass
class Command:
    id: str
    intent: str
    name: str
    description: str = ""
    phrases: list[str] = field(default_factory=list)   # frases principais
    aliases: list[str] = field(default_factory=list)   # variações
    action_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    category: str = "geral"
    priority: int = 50             # maior = preferido em empates
    requires_confirmation: bool = False
    enabled: bool = True
    source: str = "native"         # "native" | "custom"

    def all_patterns(self) -> list[str]:
        return list(self.phrases) + list(self.aliases)
