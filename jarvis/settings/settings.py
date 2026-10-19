"""Configurações locais do J.A.R.V.I.S. (JSON, com validação e recuperação).

Qualquer valor ausente/inválido/corrompido é detectado, registrado em log,
substituído pelo padrão e o app continua funcionando — nunca crasha.
"""

from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any, Optional

from jarvis.logger import get_logger
from jarvis.storage.json_store import JsonStore
from jarvis.storage import paths

log = get_logger("settings")

DEFAULTS: dict[str, Any] = {
    "language": "pt-BR",
    "theme": "dark",  # usado pelo HUB (etapa visual futura)
    "behavior": {
        "confirm_dangerous": True,
        "response_style": "short",  # short | normal
        "unknown_command_help": True,
    },
    "voice": {
        "enabled": True,
        "wake_word_required": False,  # True = exige "Jarvis" antes do comando
        "wake_words": ["jarvis"],
        "model_path": "",  # vazio = <data>/models/vosk (auto)
        "device_index": None,  # None = microfone padrão
        "sample_rate": 16000,
        "listen_timeout": 8,
    },
    "tts": {
        "enabled": True,
        "voice_id": "",  # vazio = voz padrão do sistema
        "rate": 170,     # palavras por minuto (aprox.)
        "volume": 0.9,   # 0.0 - 1.0
    },
    "intro": {
        "enabled": True,  # intro cinematográfica (etapa visual futura)
        "sound": True,
    },
    "startup": {
        "start_minimized": False,
        "autostart": False,
    },
    "ui": {
        "theme": "azul",       # azul | vermelho | verde | amarelo | cinza
        "animations": True,
        "fullscreen": False,   # iniciar em fullscreen
        "nucleus_fps": 60,     # 30 | 60
    },
    "apps": {
        # Atalhos de aplicativos conhecidos (podem ser sobrescritos).
        # Chave -> caminho/alias. Resolvidos por jarvis.system.launcher.
        "browser": "",
        "calculator": "",
        "notepad": "",
        "explorer": "",
        "discord": "",
    },
}

_SCHEMA: dict[str, Any] = {
    "language": str,
    "theme": str,
    "behavior": {"confirm_dangerous": bool, "response_style": str,
                 "unknown_command_help": bool},
    "voice": {"enabled": bool, "wake_word_required": bool, "wake_words": list,
              "model_path": str, "device_index": (int, type(None)),
              "sample_rate": int, "listen_timeout": (int, float)},
    "tts": {"enabled": bool, "voice_id": str, "rate": int, "volume": (int, float)},
    "intro": {"enabled": bool, "sound": bool},
    "startup": {"start_minimized": bool, "autostart": bool},
    "ui": {"theme": str, "animations": bool, "fullscreen": bool,
           "nucleus_fps": int},
    "apps": dict,  # livre: str -> str
}


def _validate(node: Any, schema: Any, defaults: Any, trail: str = "") -> Any:
    """Valida `node` contra `schema`; usa `defaults` quando inválido."""
    if isinstance(schema, dict):
        if not isinstance(node, dict):
            log.warning("Config '%s' inválida (esperado objeto). Restaurando padrão.",
                        trail or "root")
            return copy.deepcopy(defaults)
        result: dict[str, Any] = {}
        defaults = defaults if isinstance(defaults, dict) else {}
        for key, sub_schema in schema.items():
            sub_default = defaults.get(key)
            sub_trail = f"{trail}.{key}" if trail else key
            if key not in node:
                result[key] = copy.deepcopy(sub_default)
            else:
                result[key] = _validate(node[key], sub_schema, sub_default, sub_trail)
        # preserva chaves extras desconhecidas? Não: remove para manter schema limpo,
        # exceto em seções livres (apps).
        return result
    if schema is dict:  # seção livre (apps): garante str->str
        if not isinstance(node, dict):
            log.warning("Config '%s' inválida. Restaurando padrão.", trail)
            return copy.deepcopy(defaults)
        clean = {str(k): str(v) for k, v in node.items()}
        merged = copy.deepcopy(defaults) if isinstance(defaults, dict) else {}
        merged.update(clean)
        return merged
    expected = schema if isinstance(schema, tuple) else (schema,)
    if isinstance(node, expected) and not isinstance(node, bool) or \
            (bool in expected and isinstance(node, bool)):
        # validação extra de intervalos
        if trail == "tts.volume":
            try:
                return min(1.0, max(0.0, float(node)))
            except (TypeError, ValueError):
                pass
        if trail == "tts.rate":
            try:
                return min(400, max(50, int(node)))
            except (TypeError, ValueError):
                pass
        return node
    log.warning("Config '%s' inválida (%r). Restaurando padrão %r.",
                trail, node, defaults)
    return copy.deepcopy(defaults)


VALID_THEMES = ("azul", "vermelho", "verde", "amarelo", "cinza")


def _validate_ui(data: dict[str, Any]) -> None:
    """Validação extra da seção ui (enums/intervalos). Mutação in-place."""
    ui = data.get("ui")
    if not isinstance(ui, dict):
        data["ui"] = copy.deepcopy(DEFAULTS["ui"])
        return
    if ui.get("theme") not in VALID_THEMES:
        log.warning("Tema inválido (%r). Restaurando 'azul'.", ui.get("theme"))
        ui["theme"] = "azul"
    try:
        fps = int(ui.get("nucleus_fps", 60))
    except (TypeError, ValueError):
        fps = 60
    ui["nucleus_fps"] = 60 if fps >= 45 else 30


class SettingsManager:
    """Gerencia settings.json com validação, recuperação e acesso por pontos."""

    def __init__(self, file_path: Optional[Path | str] = None) -> None:
        self._lock = threading.RLock()
        path = Path(file_path) if file_path else paths.settings_file()
        self._store = JsonStore(path, default_factory=lambda: copy.deepcopy(DEFAULTS))
        self._data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.reload()

    @property
    def file_path(self) -> Path:
        return self._store.path

    def reload(self) -> dict[str, Any]:
        with self._lock:
            raw = self._store.load()
            if not isinstance(raw, dict):
                log.warning("settings.json com estrutura inesperada. Restaurando padrões.")
                raw = {}
            clean = _validate(raw, _SCHEMA, DEFAULTS)
            # garante chaves de topo que possam faltar
            for key, default in DEFAULTS.items():
                clean.setdefault(key, copy.deepcopy(default))
            _validate_ui(clean)
            self._data = clean
            # persiste a versão saneada (auto-recuperação)
            self._store.save(self._data)
            log.info("Configurações carregadas de %s", self._store.path)
            return copy.deepcopy(self._data)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for part in dotted_key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return copy.deepcopy(node)

    def set(self, dotted_key: str, value: Any) -> bool:
        with self._lock:
            parts = dotted_key.split(".")
            node = self._data
            for part in parts[:-1]:
                if not isinstance(node.get(part), dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value
            # revalida tudo e persiste
            self._data = _validate(self._data, _SCHEMA, DEFAULTS)
            for key, default in DEFAULTS.items():
                self._data.setdefault(key, copy.deepcopy(default))
            _validate_ui(self._data)
            ok = self._store.save(self._data)
            log.info("Config '%s' atualizada (persistido=%s)", dotted_key, ok)
            return ok

    def all(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def reset_defaults(self) -> None:
        with self._lock:
            self._data = copy.deepcopy(DEFAULTS)
            self._store.save(self._data)
            log.info("Configurações restauradas para o padrão.")
