"""Memória local do J.A.R.V.I.S. (preferências, estatísticas, histórico útil).

Tudo permanece no computador (memory.json). Nada é enviado a servidores.
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from jarvis.logger import get_logger
from jarvis.storage.json_store import JsonStore
from jarvis.storage import paths

log = get_logger("memory")

_MAX_HISTORY = 50


class MemoryManager:
    def __init__(self, file_path: Optional[Path | str] = None) -> None:
        self._lock = threading.RLock()
        path = Path(file_path) if file_path else paths.memory_file()
        self._store = JsonStore(path, default_factory=dict)
        self._data: dict[str, Any] = {"preferences": {}, "stats": {},
                                      "history": [], "facts": {}}
        self.reload()

    def reload(self) -> None:
        with self._lock:
            raw = self._store.load()
            if not isinstance(raw, dict):
                log.warning("memory.json inválida. Recriando vazia.")
                raw = {}
            self._data = {
                "preferences": raw.get("preferences", {}) if isinstance(raw.get("preferences"), dict) else {},
                "stats": raw.get("stats", {}) if isinstance(raw.get("stats"), dict) else {},
                "history": raw.get("history", []) if isinstance(raw.get("history"), list) else [],
                "facts": raw.get("facts", {}) if isinstance(raw.get("facts"), dict) else {},
            }

    def _persist(self) -> None:
        self._store.save(self._data)

    # -- preferências ------------------------------------------------------
    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data["preferences"].get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        with self._lock:
            self._data["preferences"][key] = value
            self._persist()
            log.debug("Preferência salva: %s", key)

    # -- fatos ("lembre-se que...") ----------------------------------------
    def remember_fact(self, key: str, value: str) -> None:
        with self._lock:
            self._data["facts"][key] = value
            self._persist()

    def recall_fact(self, key: str) -> Optional[str]:
        with self._lock:
            value = self._data["facts"].get(key)
            return str(value) if value is not None else None

    def forget_fact(self, key: str) -> bool:
        with self._lock:
            if key in self._data["facts"]:
                del self._data["facts"][key]
                self._persist()
                return True
            return False

    # -- estatísticas / histórico ------------------------------------------
    def record_execution(self, intent: str, text: str, success: bool) -> None:
        with self._lock:
            stats = Counter(self._data["stats"])
            stats[intent] += 1
            self._data["stats"] = dict(stats)
            self._data["history"].append({
                "ts": time.time(), "intent": intent,
                "text": text[:200], "success": success,
            })
            self._data["history"] = self._data["history"][-_MAX_HISTORY:]
            self._persist()

    def top_intents(self, limit: int = 5) -> list[tuple[str, int]]:
        with self._lock:
            stats = Counter(self._data["stats"])
            return stats.most_common(limit)

    def recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._data["history"][-limit:])
