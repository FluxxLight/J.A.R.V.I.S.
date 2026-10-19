"""VAD local por energia (RMS) — sem biblioteca extra, 100% offline.

Diferencia silêncio, ruído de fundo, fala, clipping e áudio baixo.
Usado para:
- não processar silêncio;
- não esperar o timeout inteiro depois que a pessoa parou de falar;
- não cortar a frase cedo demais (mínimo de fala + hangover).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Optional


def rms_peak(pcm: bytes) -> tuple[float, float]:
    """RMS e pico normalizados 0..1 a partir de PCM s16le mono."""
    if len(pcm) < 2:
        return 0.0, 0.0
    n = len(pcm) // 2
    samples = struct.unpack("<" + "h" * n, pcm[: n * 2])
    acc = 0
    peak = 0
    for sample in samples:
        mag = sample if sample >= 0 else -sample
        if mag > peak:
            peak = mag
        acc += sample * sample
    return math.sqrt(acc / n) / 32768.0, peak / 32768.0


def db_from_rms(rms: float) -> float:
    if rms <= 1e-8:
        return -80.0
    return 20.0 * math.log10(rms)


@dataclass
class FrameAnalysis:
    rms: float
    peak: float
    db: float
    is_speech: bool
    is_silence: bool
    is_clipping: bool
    is_too_quiet: bool
    phase: str          # calibrate | waiting | speech | ended
    noise_floor: float
    tag: str            # SILÊNCIO | RUÍDO | FALA | CLIP | BAIXO


class EnergyVAD:
    """Detector de atividade de voz com calibração automática de ruído."""

    def __init__(self, sample_rate: int = 16000,
                 sensitivity: float = 1.0,
                 min_speech_rms: float = 0.012,
                 calibrate_ms: float = 280.0,
                 silence_ms: float = 480.0,
                 min_speech_ms: float = 200.0,
                 max_utterance_ms: float = 8000.0) -> None:
        self.sample_rate = int(sample_rate) or 16000
        self.sensitivity = min(2.0, max(0.5, float(sensitivity)))
        self.min_speech_rms = float(min_speech_rms)
        self.calibrate_ms = float(calibrate_ms)
        self.silence_ms = float(silence_ms)
        self.min_speech_ms = float(min_speech_ms)
        self.max_utterance_ms = float(max_utterance_ms)
        self.reset()

    def reset(self) -> None:
        self.phase = "calibrate"
        self._cal_rms: list[float] = []
        self._cal_ms = 0.0
        self.noise_floor = 0.008
        self.started = False
        self.ended = False
        self.end_reason = ""
        self.speech_ms = 0.0
        self.silent_ms = 0.0
        self.peak_rms = 0.0
        self.utterance_ms = 0.0

    @property
    def threshold(self) -> float:
        # sensitivity alta = limiar mais baixo (pega fala mais quieta)
        factor = 2.6 / self.sensitivity
        return max(self.min_speech_rms, self.noise_floor * factor)

    def feed(self, pcm: bytes) -> FrameAnalysis:
        n = max(1, len(pcm) // 2)
        duration_ms = 1000.0 * n / self.sample_rate
        rms, peak = rms_peak(pcm)
        self.peak_rms = max(self.peak_rms, rms)
        clipping = peak >= 0.94
        too_quiet = rms < 0.004

        if self.phase == "calibrate":
            self._cal_rms.append(rms)
            self._cal_ms += duration_ms
            if self._cal_ms >= self.calibrate_ms:
                ordered = sorted(self._cal_rms) or [0.008]
                self.noise_floor = max(0.004, ordered[len(ordered) // 2] * 1.15)
                self.phase = "waiting"

        is_speech = rms >= self.threshold and not too_quiet
        is_silence = rms < max(self.noise_floor * 1.35, 0.006)

        if self.phase == "waiting":
            if is_speech:
                self.phase = "speech"
                self.started = True
                self.speech_ms = duration_ms
                self.silent_ms = 0.0
                self.utterance_ms = duration_ms
        elif self.phase == "speech":
            self.utterance_ms += duration_ms
            if is_speech:
                self.speech_ms += duration_ms
                self.silent_ms = 0.0
            else:
                self.silent_ms += duration_ms
            if self.utterance_ms >= self.max_utterance_ms:
                self._end("max_utterance")
            elif (self.silent_ms >= self.silence_ms
                  and self.speech_ms >= self.min_speech_ms):
                self._end("silence")

        if is_speech:
            tag = "CLIP" if clipping else "FALA"
        elif clipping:
            tag = "CLIP"
        elif too_quiet or is_silence:
            tag = "SILÊNCIO"
        else:
            tag = "RUÍDO"

        return FrameAnalysis(
            rms=rms, peak=peak, db=db_from_rms(rms),
            is_speech=is_speech, is_silence=is_silence,
            is_clipping=clipping, is_too_quiet=too_quiet,
            phase=self.phase, noise_floor=self.noise_floor, tag=tag)

    def _end(self, reason: str) -> None:
        self.ended = True
        self.end_reason = reason
        self.phase = "ended"


def unpack_pcm(chunk) -> bytes:
    """Normaliza o retorno de sounddevice RawInputStream.read() para bytes.

    sounddevice devolve `(data, overflowed)` — tratar o tuple como bytes
    quebrava a captura inteira (transcrição sempre vazia).
    """
    if chunk is None:
        return b""
    if isinstance(chunk, tuple):
        chunk = chunk[0] if chunk else b""
    if isinstance(chunk, (bytes, bytearray, memoryview)):
        return bytes(chunk)
    try:
        return bytes(chunk)
    except (TypeError, ValueError):
        return b""
