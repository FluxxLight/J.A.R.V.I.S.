"""Player de SFX locais (efeitos da intro/HUB).

Estratégia em camadas, sem crash em nenhum ambiente:
1. QSoundEffect (QtMultimedia) quando Qt + backend disponíveis;
2. winsound no Windows;
3. silencioso (registra em log).

Respeita a configuração `intro.sound` (Liga/desliga efeitos da intro).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from jarvis.logger import get_logger
from jarvis.ui.hub.sfx import ASSETS_DIR, SOUNDS
from jarvis.utils.platform import is_windows

log = get_logger("ui.audio")


def sfx_path(name: str) -> Path | None:
    if name not in SOUNDS:
        return None
    candidates = [
        ASSETS_DIR / f"{name}.wav",
        Path(__file__).resolve().parent / "assets" / "sfx" / f"{name}.wav",
    ]
    # Bundle PyInstaller (one-dir / one-file): _MEIPASS ou ao lado do EXE.
    import sys
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
        exe_dir = Path(sys.executable).resolve().parent
        rel = Path("jarvis") / "ui" / "hub" / "assets" / "sfx" / f"{name}.wav"
        candidates.extend([
            meipass / rel,
            exe_dir / "_internal" / rel,
            exe_dir / "assets" / "sfx" / f"{name}.wav",
        ])
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


class SfxPlayer:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.RLock()
        self._effects: dict[str, object] = {}
        self._backend = "null"
        self._init_backend()

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def _init_backend(self) -> None:
        try:
            from PySide6.QtMultimedia import QSoundEffect  # type: ignore[import-not-found]
            from PySide6.QtCore import QUrl
            self._QSoundEffect = QSoundEffect
            self._QUrl = QUrl
            self._backend = "qt"
            log.info("SFX backend: QtMultimedia.")
        except Exception as exc:
            log.warning("QtMultimedia indisponível (%s). Tentando winsound.", exc)
            if is_windows():
                try:
                    import winsound  # type: ignore[import-not-found]
                    self._winsound = winsound
                    self._backend = "winsound"
                    log.info("SFX backend: winsound.")
                    return
                except Exception:
                    pass
            self._backend = "null"
            log.info("SFX backend: silencioso.")

    def play(self, name: str, volume: float = 0.8) -> bool:
        """Toca um efeito. Nunca levanta exceção. Retorna True se emitiu som."""
        if name not in SOUNDS:
            return False
        with self._lock:
            if not self._enabled:
                return False
            backend = self._backend
        try:
            if backend == "qt":
                return self._play_qt(name, volume)
            if backend == "winsound":
                return self._play_winsound(name)
        except Exception:
            log.exception("Falha ao tocar SFX '%s' (não fatal)", name)
        return False

    def _play_qt(self, name: str, volume: float) -> bool:
        path = sfx_path(name)
        if path is None:
            log.warning("SFX ausente: %s", name)
            return False
        with self._lock:
            effect = self._effects.get(name)
            if effect is None:
                effect = self._QSoundEffect()
                effect.setSource(self._QUrl.fromLocalFile(str(path)))
                self._effects[name] = effect
        try:
            effect.setVolume(max(0.0, min(1.0, volume)))
            if effect.status() == self._QSoundEffect.Status.Error:
                return False
            effect.play()
            return True
        except RuntimeError:
            # backend de áudio ausente (ex.: sandbox headless)
            return False

    def _play_winsound(self, name: str) -> bool:
        path = sfx_path(name)
        if path is None:
            return False
        try:
            self._winsound.PlaySound(
                str(path),
                self._winsound.SND_FILENAME | self._winsound.SND_ASYNC)
            return True
        except Exception:
            return False

    def stop_all(self) -> None:
        with self._lock:
            effects = list(self._effects.values())
        for effect in effects:
            try:
                effect.stop()
            except Exception:
                pass
