"""Comandos personalizados criados pelo usuário (CRUD real, persistido).

Tipos de ação suportados:
- open_app  -> params: {app, path?}
- open_url  -> params: {url}
- open_folder -> params: {path}
- speak     -> params: {text}
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any, Optional

from jarvis.commands.base import Command
from jarvis.commands.registry import CommandRegistry
from jarvis.logger import get_logger
from jarvis.storage.json_store import JsonStore
from jarvis.storage import paths
from jarvis.system import launcher

log = get_logger("commands.custom")

_ACTION_MAP = {
    "open_app": "OpenApplication",
    "open_url": "OpenUrl",
    "open_folder": "OpenFolder",
    "speak": "Speak",
}


class CustomCommandError(ValueError):
    pass


def _validate_payload(name: str, phrases: list[str], action: str,
                      params: dict[str, Any]) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise CustomCommandError("Nome do comando é obrigatório.")
    clean_phrases = [p.strip() for p in (phrases or []) if p and p.strip()]
    if not clean_phrases:
        raise CustomCommandError("Informe ao menos uma frase de ativação.")
    if action not in _ACTION_MAP:
        raise CustomCommandError(f"Ação inválida: {action}. "
                                 f"Use: {', '.join(sorted(_ACTION_MAP))}.")
    params = dict(params or {})
    if action == "open_url":
        url = str(params.get("url", "")).strip()
        if not url:
            raise CustomCommandError("URL é obrigatória para ação open_url.")
        if not launcher.is_valid_url(url):
            extracted = launcher.extract_url(url)
            if not extracted:
                raise CustomCommandError(f"URL inválida: {url}")
            params["url"] = extracted
    elif action == "open_app":
        if not str(params.get("app", "") or "").strip():
            raise CustomCommandError("Aplicativo é obrigatório para ação open_app.")
    elif action == "open_folder":
        if not str(params.get("path", "") or "").strip():
            raise CustomCommandError("Caminho é obrigatório para ação open_folder.")
    elif action == "speak":
        if not str(params.get("text", "") or "").strip():
            raise CustomCommandError("Texto é obrigatório para ação speak.")
    return {"name": name, "phrases": clean_phrases, "params": params}


class CustomCommandManager:
    """CRUD + persistência + sincronização com o registry/engine."""

    def __init__(self, registry: CommandRegistry,
                 file_path: Optional[Path | str] = None) -> None:
        self._registry = registry
        self._lock = threading.RLock()
        path = Path(file_path) if file_path else paths.custom_commands_file()
        self._store = JsonStore(path, default_factory=list)
        self._items: list[dict[str, Any]] = []
        self.reload()

    # -- persistência ------------------------------------------------------
    def reload(self) -> None:
        with self._lock:
            raw = self._store.load()
            if not isinstance(raw, list):
                log.warning("custom_commands.json inválido. Recriando vazio.")
                raw = []
            self._items = [i for i in raw if isinstance(i, dict)]
            self._sync_registry()
            log.info("Comandos personalizados carregados: %d", len(self._items))

    def _persist(self) -> bool:
        return self._store.save(self._items)

    def _sync_registry(self) -> None:
        # remove registros antigos de custom e reinsere
        for cmd in self._registry.all():
            if cmd.source == "custom":
                self._registry.unregister(cmd.id)
        for item in self._items:
            try:
                self._registry.register(self._to_command(item))
            except Exception:
                log.exception("Comando personalizado inválido ignorado: %s",
                              item.get("id"))

    @staticmethod
    def _to_command(item: dict[str, Any]) -> Command:
        return Command(
            id=str(item.get("id")),
            intent=f"CUSTOM_{item.get('id', '')}",
            name=str(item.get("name", "")),
            description=str(item.get("description", "") or ""),
            phrases=list(item.get("phrases", [])),
            aliases=list(item.get("aliases", [])),
            action_id=_ACTION_MAP.get(str(item.get("action", "")), "Speak"),
            params=dict(item.get("params", {})),
            category=str(item.get("category", "personalizado") or "personalizado"),
            priority=int(item.get("priority", 55) or 55),
            requires_confirmation=bool(item.get("requires_confirmation", False)),
            enabled=bool(item.get("enabled", True)),
            source="custom",
        )

    # -- CRUD --------------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(i) for i in self._items]

    def get(self, command_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            for item in self._items:
                if item.get("id") == command_id:
                    return dict(item)
            return None

    def create(self, name: str, phrases: list[str], action: str,
               params: Optional[dict[str, Any]] = None,
               aliases: Optional[list[str]] = None,
               description: str = "", category: str = "personalizado",
               priority: int = 55,
               requires_confirmation: bool = False) -> dict[str, Any]:
        with self._lock:
            clean = _validate_payload(name, phrases, action, params or {})
            item = {
                "id": f"custom_{uuid.uuid4().hex[:8]}",
                "name": clean["name"],
                "description": description.strip(),
                "phrases": clean["phrases"],
                "aliases": [a.strip() for a in (aliases or []) if a and a.strip()],
                "action": action,
                "params": clean["params"],
                "category": category or "personalizado",
                "priority": int(priority),
                "requires_confirmation": bool(requires_confirmation),
                "enabled": True,
            }
            self._items.append(item)
            self._persist()
            self._registry.register(self._to_command(item))
            log.info("Comando personalizado criado: %s (%s)", item["id"], item["name"])
            return dict(item)

    def update(self, command_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            for index, item in enumerate(self._items):
                if item.get("id") != command_id:
                    continue
                merged = dict(item)
                merged.update({k: v for k, v in fields.items() if k != "id"})
                clean = _validate_payload(
                    merged.get("name", ""), merged.get("phrases", []),
                    merged.get("action", ""), merged.get("params", {}))
                merged["name"] = clean["name"]
                merged["phrases"] = clean["phrases"]
                merged["params"] = clean["params"]
                if "aliases" in merged and merged["aliases"] is not None:
                    merged["aliases"] = [str(a).strip() for a in merged["aliases"] if str(a).strip()]
                self._items[index] = merged
                self._persist()
                self._registry.register(self._to_command(merged))
                log.info("Comando personalizado atualizado: %s", command_id)
                return dict(merged)
            raise CustomCommandError(f"Comando não encontrado: {command_id}")

    def delete(self, command_id: str) -> bool:
        with self._lock:
            for index, item in enumerate(self._items):
                if item.get("id") == command_id:
                    del self._items[index]
                    self._persist()
                    self._registry.unregister(command_id)
                    log.info("Comando personalizado excluído: %s", command_id)
                    return True
            return False

    def set_enabled(self, command_id: str, enabled: bool) -> bool:
        with self._lock:
            for item in self._items:
                if item.get("id") == command_id:
                    item["enabled"] = bool(enabled)
                    self._persist()
                    self._registry.set_enabled(command_id, enabled)
                    log.info("Comando %s %s", command_id,
                             "ativado" if enabled else "desativado")
                    return True
            return False
