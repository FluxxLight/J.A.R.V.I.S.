"""VAD local e captura: silêncio, fala, timeout, unpack do sounddevice."""

from __future__ import annotations

import math
import struct

from jarvis.voice.capture import capture_utterance
from jarvis.voice.vad import EnergyVAD, rms_peak, unpack_pcm


def _pcm(n: int, amp: float = 0.0, freq: float = 180.0, rate: int = 16000) -> bytes:
    samples = []
    for i in range(n):
        val = amp * math.sin(2 * math.pi * freq * i / rate)
        samples.append(max(-32767, min(32767, int(val * 32767))))
    return struct.pack("<" + "h" * n, *samples)


def test_unpack_pcm_tuple_from_sounddevice():
    payload = b"\x01\x00\x02\x00"
    assert unpack_pcm((payload, False)) == payload
    assert unpack_pcm(payload) == payload
    assert unpack_pcm(None) == b""
    assert unpack_pcm(()) == b""


def test_rms_silence_and_tone():
    silent = _pcm(1600, amp=0.0)
    tone = _pcm(1600, amp=0.4)
    r0, p0 = rms_peak(silent)
    r1, p1 = rms_peak(tone)
    assert r0 < 0.001 and p0 < 0.001
    assert r1 > 0.2 and p1 > 0.3


def test_vad_silence_never_starts():
    vad = EnergyVAD(calibrate_ms=200, silence_ms=300, min_speech_ms=150)
    frame = _pcm(1600, amp=0.0)  # 100 ms
    for _ in range(20):
        vad.feed(frame)
    assert vad.started is False
    assert vad.ended is False


def test_vad_detects_speech_and_end():
    vad = EnergyVAD(calibrate_ms=200, silence_ms=300, min_speech_ms=150,
                    max_utterance_ms=4000)
    quiet = _pcm(1600, amp=0.0)
    speech = _pcm(1600, amp=0.45)
    for _ in range(3):
        vad.feed(quiet)          # calibração
    started = False
    for _ in range(5):
        a = vad.feed(speech)
        started = started or a.is_speech
    assert started and vad.started
    ended = False
    for _ in range(8):
        vad.feed(quiet)
        if vad.ended:
            ended = True
            break
    assert ended
    assert vad.end_reason == "silence"


def test_vad_does_not_end_before_min_speech():
    vad = EnergyVAD(calibrate_ms=100, silence_ms=200, min_speech_ms=400)
    quiet = _pcm(800, amp=0.0)
    blip = _pcm(800, amp=0.5)
    vad.feed(quiet)
    vad.feed(blip)  # ~50ms de fala
    for _ in range(6):
        vad.feed(quiet)
    assert vad.ended is False  # blip curto demais


def test_vad_sensitivity_changes_threshold():
    low = EnergyVAD(sensitivity=0.5)
    high = EnergyVAD(sensitivity=2.0)
    low.noise_floor = high.noise_floor = 0.01
    assert high.threshold < low.threshold


def test_capture_utterance_fake_mic_speech():
    quiet = _pcm(1600, amp=0.0)
    speech = _pcm(1600, amp=0.5)

    class Stream:
        def __init__(self):
            self.chunks = [quiet] * 3 + [speech] * 6 + [quiet] * 8

        def read(self, _n):
            return (self.chunks.pop(0), False) if self.chunks else (quiet, False)

    class Mic:
        def open_stream(self, block_size=1600):
            return Stream()

        def close_stream(self):
            self.closed = True

    mic = Mic()
    result = capture_utterance(mic, EnergyVAD(calibrate_ms=200, silence_ms=300,
                                              min_speech_ms=150), timeout=3.0)
    assert result.started is True
    assert result.reason == "speech"
    assert result.frames
    assert getattr(mic, "closed", False) is True


def test_capture_no_mic():
    class Mic:
        def open_stream(self, block_size=1600):
            return None

        def close_stream(self):
            pass

    result = capture_utterance(Mic(), timeout=0.5)
    assert result.reason == "no_mic"
    assert result.frames == []


def test_listen_once_unavailable_extra_kwargs(app):
    """Assinatura nova não quebra o reconhecedor ausente."""
    t = app.recognizer.listen_once(app.mic, timeout=0.2, on_level=lambda *_: None,
                                   vad=EnergyVAD())
    assert t.text == ""
    assert t.reason in ("unavailable", "")
