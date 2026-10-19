"""SFX do J.A.R.V.I.S. — 100% sintetizados localmente (stdlib `wave`/`math`).

Nenhum áudio baixado, nenhuma música, nenhum asset proprietário:
apenas efeitos curtos de sistema (boot, anel, tick, confirmação,
pronto, erro), gerados de forma determinística.

Uso:
    python -m jarvis.ui.hub.sfx --write   # grava os .wav em assets/sfx/
"""

from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "sfx"


def _envelope(i: int, n: int, attack: float = 0.02, release: float = 0.25) -> float:
    """Envelope attack/decay simples 0..1."""
    t = i / max(n - 1, 1)
    a = min(1.0, t / max(attack, 1e-6))
    r = min(1.0, (1.0 - t) / max(release, 1e-6))
    return min(a, r)


def _tone(freq: float, seconds: float, volume: float = 0.5,
          attack: float = 0.02, release: float = 0.3,
          freq_end: float | None = None, harmonic: float = 0.25) -> list[float]:
    """Seno com sweep opcional + leve 2º harmônico."""
    n = int(SAMPLE_RATE * seconds)
    out: list[float] = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        frac = i / max(n - 1, 1)
        f = freq if freq_end is None else freq + (freq_end - freq) * frac
        phase += 2.0 * math.pi * f / SAMPLE_RATE
        s = math.sin(phase) + harmonic * math.sin(2.0 * phase)
        out.append(s * volume * _envelope(i, n, attack, release))
    return out


def _mix(*tracks: list[float]) -> list[float]:
    n = max((len(t) for t in tracks), default=0)
    out = [0.0] * n
    for track in tracks:
        for i, sample in enumerate(track):
            out[i] += sample
    peak = max((abs(s) for s in out), default=1.0)
    if peak > 0.95:
        out = [s / peak * 0.95 for s in out]
    return out


def make_boot() -> list[float]:
    """Inicialização: subida de energia 140->880Hz + pulso."""
    return _mix(
        _tone(140, 0.55, volume=0.45, attack=0.05, release=0.35, freq_end=880),
        _tone(1100, 0.12, volume=0.25, attack=0.6, release=0.4),
    )


def make_ring() -> list[float]:
    """Anéis se formando: acorde cintilante."""
    return _mix(
        _tone(523.25, 0.5, volume=0.30, attack=0.15, release=0.5),
        _tone(659.25, 0.5, volume=0.25, attack=0.25, release=0.5),
        _tone(783.99, 0.5, volume=0.20, attack=0.35, release=0.5),
    )


def make_tick() -> list[float]:
    """Tick de HUD: clique curto e agudo."""
    return _tone(1900, 0.07, volume=0.35, attack=0.01, release=0.7, freq_end=1500)


def make_confirm() -> list[float]:
    """Confirmação: dois tons ascendentes."""
    part1 = _tone(660, 0.12, volume=0.4, attack=0.05, release=0.5)
    part2 = _tone(880, 0.18, volume=0.4, attack=0.05, release=0.6)
    gap = [0.0] * int(SAMPLE_RATE * 0.03)
    return part1 + gap + part2


def make_ready() -> list[float]:
    """Sistema pronto: arpejo maior com brilho."""
    seq = [523.25, 659.25, 783.99, 1046.5]
    out: list[float] = []
    for freq in seq:
        out += _tone(freq, 0.22, volume=0.35, attack=0.03, release=0.55)
    return out


def make_error() -> list[float]:
    """Erro: zumbido baixo com decaimento."""
    return _mix(
        _tone(150, 0.35, volume=0.5, attack=0.01, release=0.6, freq_end=110,
              harmonic=0.5),
        _tone(75, 0.35, volume=0.3, attack=0.01, release=0.6, freq_end=60),
    )


SOUNDS: dict[str, callable] = {
    "boot": make_boot,
    "ring": make_ring,
    "tick": make_tick,
    "confirm": make_confirm,
    "ready": make_ready,
    "error": make_error,
}


def to_wav_bytes(samples: list[float]) -> bytes:
    import io
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        frames = struct.pack(
            "<" + "h" * len(samples),
            *(max(-32767, min(32767, int(s * 32767))) for s in samples))
        wav.writeframes(frames)
    return buffer.getvalue()


def write_all(target_dir: Path | str = ASSETS_DIR) -> list[Path]:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, maker in SOUNDS.items():
        path = target / f"{name}.wav"
        path.write_bytes(to_wav_bytes(maker()))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera os SFX locais do J.A.R.V.I.S.")
    parser.add_argument("--write", action="store_true",
                        help="grava os .wav em assets/sfx/")
    parser.add_argument("--dir", default=str(ASSETS_DIR))
    args = parser.parse_args(argv)
    if not args.write:
        parser.print_help()
        return 0
    for path in write_all(args.dir):
        print(f"{path.name}: {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
