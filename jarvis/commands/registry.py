"""Registro central de comandos + ações (thread-safe)."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from jarvis.commands.base import Action, Command
from jarvis.logger import get_logger

log = get_logger("commands.registry")


class CommandRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._commands: Dict[str, Command] = {}
        self._actions: Dict[str, Action] = {}

    # -- ações -------------------------------------------------------------
    def register_action(self, action: Action) -> None:
        with self._lock:
            self._actions[action.id] = action
            log.debug("Ação registrada: %s", action.id)

    def get_action(self, action_id: str) -> Optional[Action]:
        with self._lock:
            return self._actions.get(action_id)

    # -- comandos ----------------------------------------------------------
    def register(self, command: Command) -> None:
        with self._lock:
            self._commands[command.id] = command
            log.debug("Comando registrado: %s (%s)", command.id, command.intent)

    def unregister(self, command_id: str) -> bool:
        with self._lock:
            return self._commands.pop(command_id, None) is not None

    def get(self, command_id: str) -> Optional[Command]:
        with self._lock:
            return self._commands.get(command_id)

    def set_enabled(self, command_id: str, enabled: bool) -> bool:
        with self._lock:
            cmd = self._commands.get(command_id)
            if not cmd:
                return False
            cmd.enabled = enabled
            return True

    def all(self) -> List[Command]:
        with self._lock:
            return list(self._commands.values())

    def enabled(self) -> List[Command]:
        with self._lock:
            return [c for c in self._commands.values() if c.enabled]

    def by_intent(self, intent: str) -> List[Command]:
        with self._lock:
            return [c for c in self._commands.values() if c.intent == intent]

    def count(self) -> int:
        with self._lock:
            return len(self._commands)
