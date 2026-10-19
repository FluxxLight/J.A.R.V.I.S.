"""Reconhecimento de voz 100% LOCAL (Vosk) + fallbacks claros.

- Se `vosk` + modelo local existirem: transcrição offline real.
- Caso contrário: objeto explícito de indisponibilidade (motivo claro),
  sem crash, sem nuvem, sem envio de áudio.
"""

from __future__ import annotations

import json
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from jarvis.logger import get_logger
from jarvis.storage import paths

log = get_logger("voice.recognizer")


@dataclass
class Transcript:
    text: str
    is_final: bool = True


def default_model_dir() -> Path:
    return paths.base_dir() / "models" / "vosk"


def find_model(explicit: str = "") -> Optional[Path]:
    """Localiza modelo Vosk: caminho explícito ou diretório padrão."""
    if explicit:
        candidate = Path(explicit).expanduser()
        if _looks_like_model(candidate):
            return candidate
        log.warning("model_path configurado inválido: %s", explicit)
    base = default_model_dir()
    if _looks_like_model(base):
        return base
    try:
        if base.is_dir():
            for child in sorted(base.iterdir()):
                if _looks_like_model(child):
                    return child
    except OSError:
        pass
    return None


def _looks_like_model(directory: Path) -> bool:
    """Heurística: diretório existente, não vazio, com cara de modelo Vosk."""
    try:
        if not directory.is_dir():
            return False
        entries = list(directory.iterdir())
        if not entries:
            return False
        names = {e.name for e in entries}
        # modelo Vosk típico contém ao menos um destes marcadores
        return bool(names & {"am", "conf", "graph", "ivector", "rescore"})
    except OSError:
        return False


class LocalRecognizer:
    """Interface base."""

    name = "base"

    def is_ready(self) -> bool:
        return False

    def reason(self) -> str:
        return "não implementado"

    def transcribe_wav(self, wav_path: str | Path) -> Transcript:
        raise NotImplementedError

    def listen_once(self, mic, timeout: float = 8.0,
                    on_partial: Optional[Callable[[str], None]] = None) -> Transcript:
        raise NotImplementedError

    def close(self) -> None:
        pass


class UnavailableRecognizer(LocalRecognizer):
    """Marcador explícito: reconhecimento indisponível + motivo."""

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def reason(self) -> str:
        return self._reason

    def transcribe_wav(self, wav_path: str | Path) -> Transcript:
        return Transcript("", is_final=True)

    def listen_once(self, mic, timeout: float = 8.0,
                    on_partial: Optional[Callable[[str], None]] = None) -> Transcript:
        log.warning("Reconhecimento indisponível: %s", self._reason)
        return Transcript("", is_final=True)


class VoskRecognizer(LocalRecognizer):
    """Reconhecedor offline via Vosk (lazy import; modelo local)."""

    name = "vosk"

    def __init__(self, model_dir: str | Path, sample_rate: int = 16000) -> None:
        self._lock = threading.RLock()
        self._model_dir = Path(model_dir)
        self._sample_rate = sample_rate
        self._model = None
        self._error = ""
        self._init_model()

    def _init_model(self) -> None:
        try:
            from vosk import Model  # type: ignore[import-not-found]
        except ImportError:
            self._error = "Biblioteca 'vosk' não instalada (pip install vosk)."
            log.error(self._error)
            return
        try:
            log.info("Carregando modelo Vosk de %s ...", self._model_dir)
            self._model = Model(str(self._model_dir))
            log.info("Modelo Vosk carregado.")
        except Exception as exc:
            self._error = f"Falha ao carregar modelo Vosk: {exc}"
            log.exception("Vosk Model falhou")

    def is_ready(self) -> bool:
        return self._model is not None

    def reason(self) -> str:
        return "" if self.is_ready() else (self._error or "modelo não carregado")

    def _new_recognizer(self, sample_rate: Optional[float] = None):
        from vosk import KaldiRecognizer  # type: ignore[import-not-found]
        return KaldiRecognizer(self._model, sample_rate or self._sample_rate)

    def transcribe_wav(self, wav_path: str | Path) -> Transcript:
        if not self.is_ready():
            return Transcript("", is_final=True)
        try:
            with wave.open(str(wav_path), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    return Transcript("", is_final=True)
                rec = self._new_recognizer(wav.getframerate())
                while True:
                    data = wav.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
                result = json.loads(rec.FinalResult() or "{}")
                text = str(result.get("text", "") or "").strip()
                log.info("Transcrito (wav): %r", text)
                return Transcript(text, is_final=True)
        except Exception:
            log.exception("transcribe_wav falhou")
            return Transcript("", is_final=True)

    def listen_once(self, mic, timeout: float = 8.0,
                    on_partial: Optional[Callable[[str], None]] = None) -> Transcript:
        import time

        if not self.is_ready():
            return Transcript("", is_final=True)
        stream = mic.open_stream()
        if stream is None:
            return Transcript("", is_final=True)
        rec = self._new_recognizer()
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                chunk = stream.read(4000)  # RawInputStream.read -> bytes
                data = bytes(chunk)
                if not data:
                    continue
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result() or "{}")
                    text = str(result.get("text", "") or "").strip()
                    if text:
                        log.info("Transcrito (mic): %r", text)
                        return Transcript(text, is_final=True)
                elif on_partial:
                    try:
                        partial = json.loads(rec.PartialResult() or "{}")
                        if partial.get("partial"):
                            on_partial(str(partial["partial"]))
                    except Exception:
                        pass
            final = json.loads(rec.FinalResult() or "{}")
            text = str(final.get("text", "") or "").strip()
            log.info("Transcrito (mic, final): %r", text)
            return Transcript(text, is_final=True)
        except Exception:
            log.exception("listen_once falhou")
            return Transcript("", is_final=True)
        finally:
            mic.close_stream()

    def close(self) -> None:
        with self._lock:
            self._model = None


def create_recognizer(model_path: str = "", sample_rate: int = 16000) -> LocalRecognizer:
    """Fábrica: Vosk pronto OU indisponibilidade com motivo claro."""
    try:
        import vosk  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        return UnavailableRecognizer(
            "Vosk não instalado. Instale com: pip install vosk — "
            "e baixe um modelo pt-BR para "
            f"{default_model_dir()} (ex.: vosk-model-small-pt-0.3). "
            "Nenhum áudio sai do PC.")
    model = find_model(model_path)
    if model is None:
        expected = default_model_dir()
        return UnavailableRecognizer(
            f"Modelo Vosk não encontrado. Baixe um modelo pt-BR "
            f"(ex.: vosk-model-small-pt-0.3) e extraia em {expected} "
            f"ou configure voice.model_path. Veja README, seção Voz.")
    rec = VoskRecognizer(model, sample_rate)
    if not rec.is_ready():
        return UnavailableRecognizer(rec.reason() or "Vosk indisponível.")
    return rec
