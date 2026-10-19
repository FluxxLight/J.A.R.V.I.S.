"""Roteiro da intro cinematográfica — matemática pura (sem Qt, testável).

Duração total: 5.2s. Curva única de progresso 0..1 com fases sobrepostas
(uma experiência contínua, não uma sequência de telas):

    0.00-0.10  sinal de atividade (ponto pulsante no escuro)
    0.05-0.30  linhas surgem (scanlines / construção do HUD)
    0.25-0.55  anéis começam a se formar
    0.50-0.75  núcleo é ativado (pulso de energia)
    0.70-0.88  indicadores carregam (barras laterais)
    0.80-1.00  "J.A.R.V.I.S." + SYSTEM INITIALIZING -> SYSTEM READY
    1.00       transição para o HUB (fade)

SFX sincronizados: boot@0.02, tick@0.12, ring@0.30, tick@0.55,
confirm@0.78, ready@0.90.
"""

from __future__ import annotations

from dataclasses import dataclass

INTRO_DURATION_MS = 5200


@dataclass(frozen=True)
class IntroPhase:
    id: str
    start: float  # progresso 0..1
    end: float
    label: str


PHASES: tuple[IntroPhase, ...] = (
    IntroPhase("signal", 0.00, 0.12, "SINAL"),
    IntroPhase("lines", 0.05, 0.32, "HUD"),
    IntroPhase("rings", 0.25, 0.58, "ANÉIS"),
    IntroPhase("core", 0.50, 0.76, "NÚCLEO"),
    IntroPhase("gauges", 0.68, 0.90, "INDICADORES"),
    IntroPhase("title", 0.78, 1.00, "TÍTULO"),
)

SFX_CUES: tuple[tuple[float, str], ...] = (
    (0.02, "boot"),
    (0.12, "tick"),
    (0.30, "ring"),
    (0.55, "tick"),
    (0.78, "confirm"),
    (0.90, "ready"),
)


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = clamp01((x - edge0) / (edge1 - edge0)) if edge1 > edge0 else 1.0
    return t * t * (3.0 - 2.0 * t)


@dataclass(frozen=True)
class IntroFrame:
    """Estado visual completo da intro num instante (0..1)."""
    progress: float
    signal: float      # 0..1 intensidade do ponto inicial
    lines: float       # 0..1 tanto das linhas HUD
    rings: float       # 0..1 formação dos anéis
    core: float        # 0..1 ativação do núcleo
    gauges: float      # 0..1 indicadores
    title: float       # 0..1 título J.A.R.V.I.S.
    status_text: str   # "" | "SYSTEM INITIALIZING" | "SYSTEM READY"
    ready: bool        # True quando atingiu o fim


def frame_at(progress: float) -> IntroFrame:
    p = clamp01(progress)

    def phase(id_: str) -> float:
        for ph in PHASES:
            if ph.id == id_:
                return smoothstep(ph.start, ph.end, p)
        return 0.0

    signal = phase("signal") * (1.0 - smoothstep(0.25, 0.45, p))
    if p >= 1.0:
        status, ready = "SYSTEM READY", True
    elif p >= 0.80:
        status, ready = ("SYSTEM READY" if p >= 0.93 else "SYSTEM INITIALIZING"), False
    else:
        status, ready = "", False
    return IntroFrame(
        progress=p,
        signal=signal,
        lines=phase("lines"),
        rings=phase("rings"),
        core=phase("core"),
        gauges=phase("gauges"),
        title=phase("title"),
        status_text=status,
        ready=ready,
    )


def due_cues(previous: float, current: float) -> list[str]:
    """SFX cujos pontos foram cruzados entre dois progressos."""
    return [name for at, name in SFX_CUES if previous < at <= current]


def progress_for_elapsed(elapsed_ms: int) -> float:
    return clamp01(elapsed_ms / INTRO_DURATION_MS)
