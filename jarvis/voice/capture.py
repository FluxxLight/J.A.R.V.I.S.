"""Captura de UMA fala: calibração → espera → fala → silêncio → para.

Independente do reconhecedor (Vosk). Garante timeout, não escuta para
sempre, e descreve o motivo do fim (silêncio, timeout, sem mic, corte).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from jarvis.logger import get_logger
from jarvis.voice.vad import EnergyVAD, FrameAnalysis, unpack_pcm

log = get_logger("voice.capture")

OnLevel = Callable[[FrameAnalysis], None]
OnEvent = Callable[[str, str], None]


@dataclass
class CaptureResult:
    frames: list[bytes] = field(default_factory=list)
    reason: str = "silence"     # speech | silence | timeout | error | no_mic | interrupted
    duration_s: float = 0.0
    noise_floor: float = 0.0
    peak_rms: float = 0.0
    speech_ms: float = 0.0
    calibrated: bool = False
    started: bool = False


def iter_utterance(mic, vad: EnergyVAD, timeout: float = 8.0,
                   block_size: int = 1600,
                   on_level: Optional[OnLevel] = None,
                   on_event: Optional[OnEvent] = None
                   ) -> Iterator[tuple[bytes, FrameAnalysis]]:
    """Gera frames PCM até o fim da fala ou timeout. Fecha o stream sempre."""
    def emit(tag: str, detail: str = "") -> None:
        log.info("[%s] %s", tag, detail)
        if on_event:
            try:
                on_event(tag, detail)
            except Exception:
                log.exception("on_event falhou (não fatal)")

    stream = None
    try:
        stream = mic.open_stream(block_size=block_size)
    except TypeError:
        # microfones de teste sem block_size
        try:
            stream = mic.open_stream()
        except Exception as exc:
            emit("VOICE", f"falha ao abrir microfone: {exc}")
            return
    except Exception as exc:
        emit("VOICE", f"falha ao abrir microfone: {exc}")
        return
    if stream is None:
        emit("VOICE", "microfone ausente")
        return

    emit("VOICE", "microfone detectado")
    emit("LISTENING", f"início da captura timeout={timeout:.1f}s")
    deadline = time.time() + max(0.4, float(timeout))
    idle = 0
    last_audio_log = 0.0
    speech_logged = False
    try:
        while time.time() < deadline:
            try:
                raw = stream.read(block_size)
            except Exception as exc:
                emit("VOICE", f"leitura interrompida: {exc}")
                return
            data = unpack_pcm(raw)
            if not data:
                idle += 1
                if idle >= 12:
                    emit("VOICE", "entrada interrompida (sem dados)")
                    return
                continue
            idle = 0
            analysis = vad.feed(data)
            now = time.time()
            if now - last_audio_log >= 0.25:
                log.info("[AUDIO] rms=%.3f pico=%.3f ruído=%.3f tag=%s fase=%s",
                         analysis.rms, analysis.peak, analysis.noise_floor,
                         analysis.tag, analysis.phase)
                last_audio_log = now
            if on_level:
                try:
                    on_level(analysis)
                except Exception:
                    log.exception("on_level falhou (não fatal)")
            if analysis.is_speech and not speech_logged:
                emit("VOICE ACTIVITY", f"fala detectada rms={analysis.rms:.3f}")
                speech_logged = True
            yield data, analysis
            if vad.ended:
                emit("SPEECH END",
                     f"motivo={vad.end_reason} fala={vad.speech_ms:.0f}ms")
                return
        emit("SPEECH END", "motivo=timeout")
    finally:
        try:
            mic.close_stream()
        except Exception:
            log.exception("close_stream falhou (não fatal)")


def capture_utterance(mic, vad: Optional[EnergyVAD] = None,
                      timeout: float = 8.0,
                      on_level: Optional[OnLevel] = None,
                      on_event: Optional[OnEvent] = None) -> CaptureResult:
    vad = vad or EnergyVAD()
    frames: list[bytes] = []
    t0 = time.time()
    try:
        for data, _analysis in iter_utterance(
                mic, vad, timeout=timeout, on_level=on_level, on_event=on_event):
            frames.append(data)
    except Exception as exc:
        log.exception("capture_utterance falhou")
        return CaptureResult(reason="error", duration_s=time.time() - t0)
    duration = time.time() - t0
    if not frames:
        reason = "no_mic"
    elif vad.started:
        reason = "speech"
    elif duration >= timeout * 0.9:
        reason = "timeout"
    else:
        reason = "silence"
    return CaptureResult(
        frames=frames, reason=reason, duration_s=duration,
        noise_floor=vad.noise_floor, peak_rms=vad.peak_rms,
        speech_ms=vad.speech_ms, calibrated=vad.phase != "calibrate",
        started=vad.started)
