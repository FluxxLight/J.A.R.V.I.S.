"""TTS 100% LOCAL (pyttsx3/SAPI no Windows) + fallback silencioso.

- Lista SOMENTE vozes realmente disponíveis.
- Sem pyttsx3: NullTTS (registra em log, não fala, não crasha).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import List, Optional

from jarvis.logger import get_logger

log = get_logger("voice.tts")


@dataclass
class VoiceInfo:
    id: str
    name: str
    lang: str = ""


class LocalTTS:
    name = "base"

    def is_ready(self) -> bool:
        return False

    def list_voices(self) -> List[VoiceInfo]:
        return []

    def speak(self, text: str) -> bool:
        return False

    def stop(self) -> None:
        pass

    def set_voice(self, voice_id: str) -> bool:
        return False

    def set_rate(self, rate: int) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass

    def close(self) -> None:
        pass


class NullTTS(LocalTTS):
    """Fallback: não fala, mas registra (modo texto)."""

    name = "null"

    def __init__(self, reason: str = "TTS desativado/indisponível") -> None:
        self._reason = reason

    def speak(self, text: str) -> bool:
        log.info("[TTS:null] %s", text)
        return False


class Pyttsx3TTS(LocalTTS):
    """TTS local via pyttsx3 (SAPI5 no Windows). Thread-safe."""

    name = "pyttsx3"

    def __init__(self, voice_id: str = "", rate: int = 170,
                 volume: float = 0.9) -> None:
        self._lock = threading.RLock()
        self._engine = None
        self._error = ""
        try:
            import pyttsx3  # type: ignore[import-not-found]
        except ImportError:
            self._error = "pyttsx3 não instalado (pip install pyttsx3)."
            log.error(self._error)
            return
        try:
            self._engine = pyttsx3.init()
            self.set_rate(rate)
            self.set_volume(volume)
            if voice_id:
                if not self.set_voice(voice_id):
                    log.warning("Voz '%s' não encontrada. Usando padrão.", voice_id)
            log.info("pyttsx3 inicializado.")
        except Exception as exc:
            self._engine = None
            self._error = f"Falha ao iniciar pyttsx3: {exc}"
            log.exception("pyttsx3.init falhou")

    def is_ready(self) -> bool:
        return self._engine is not None

    def reason(self) -> str:
        return "" if self.is_ready() else self._error

    def list_voices(self) -> List[VoiceInfo]:
        with self._lock:
            if not self.is_ready():
                return []
            try:
                voices = self._engine.getProperty("voices") or []
                result = []
                for v in voices:
                    langs = ""
                    try:
                        raw = getattr(v, "languages", []) or []
                        langs = ",".join(str(x) for x in raw)
                    except Exception:
                        pass
                    result.append(VoiceInfo(id=str(v.id),
                                            name=str(v.name), lang=langs))
                return result
            except Exception:
                log.exception("list_voices falhou")
                return []

    def speak(self, text: str) -> bool:
        with self._lock:
            if not self.is_ready() or not (text or "").strip():
                return False
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                return True
            except Exception:
                log.exception("TTS speak falhou")
                return False

    def stop(self) -> None:
        with self._lock:
            if self.is_ready():
                try:
                    self._engine.stop()
                except Exception:
                    pass

    def set_voice(self, voice_id: str) -> bool:
        with self._lock:
            if not self.is_ready():
                return False
            try:
                ids = [v.id for v in self.list_voices()]
                if voice_id not in ids:
                    return False
                self._engine.setProperty("voice", voice_id)
                return True
            except Exception:
                log.exception("set_voice falhou")
                return False

    def set_rate(self, rate: int) -> None:
        with self._lock:
            if self.is_ready():
                try:
                    self._engine.setProperty("rate", int(rate))
                except Exception:
                    pass

    def set_volume(self, volume: float) -> None:
        with self._lock:
            if self.is_ready():
                try:
                    self._engine.setProperty(
                        "volume", min(1.0, max(0.0, float(volume))))
                except Exception:
                    pass

    def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.stop()
                except Exception:
                    pass
                self._engine = None


def create_tts(enabled: bool = True, voice_id: str = "",
               rate: int = 170, volume: float = 0.9) -> LocalTTS:
    if not enabled:
        return NullTTS("TTS desativado nas configurações.")
    tts = Pyttsx3TTS(voice_id=voice_id, rate=rate, volume=volume)
    if tts.is_ready():
        return tts
    return NullTTS(tts.reason() or "TTS indisponível.")
