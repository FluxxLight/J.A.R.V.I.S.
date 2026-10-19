"""Armazenamento JSON local com escrita atômica e recuperação."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from jarvis.logger import get_logger
from jarvis.storage import paths

log = get_logger("storage.json")


class JsonStore:
    """Leitura/escrita JSON thread-safe, atômica e tolerante a corrupção."""

    def __init__(self, path: Path | str,
                 default_factory: Callable[[], Any] = dict) -> None:
        self.path = Path(path)
        self._default_factory = default_factory
        self._lock = threading.RLock()

    def load(self) -> Any:
        with self._lock:
            if not self.path.exists():
                log.info("Arquivo inexistente, usando padrão: %s", self.path)
                return self._default_factory()
            try:
                text = self.path.read_text(encoding="utf-8")
                if not text.strip():
                    log.warning("Arquivo vazio, usando padrão: %s", self.path)
                    return self._default_factory()
                return json.loads(text)
            except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
                log.error("Arquivo corrompido/ilegível (%s): %s", self.path, exc)
                self._backup_corrupt()
                return self._default_factory()

    def save(self, data: Any) -> bool:
        """Escrita atômica (arquivo temporário + replace)."""
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_name = tempfile.mkstemp(
                    dir=str(self.path.parent), prefix=self.path.stem + "_", suffix=".tmp"
                )
                try:
                    with open(fd, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, ensure_ascii=False, indent=2)
                    Path(tmp_name).replace(self.path)
                except BaseException:
                    try:
                        Path(tmp_name).unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise
                return True
            except OSError as exc:
                log.error("Falha ao salvar %s: %s", self.path, exc)
                return False

    def _backup_corrupt(self) -> Optional[Path]:
        try:
            backup_dir = paths.base_dir() / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dest = backup_dir / f"{self.path.stem}.corrupt-{stamp}{self.path.suffix}"
            shutil.copy2(self.path, dest)
            log.info("Backup do arquivo corrompido em %s", dest)
            return dest
        except OSError as exc:
            log.error("Não foi possível fazer backup de %s: %s", self.path, exc)
            return None
