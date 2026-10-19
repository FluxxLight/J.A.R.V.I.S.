"""Núcleo do J.A.R.V.I.S. — widget animado (QPainter raster, sem OpenGL).

Camadas: anel tracejado orbital, anel de ticks, órbitas com satélites,
arcos de energia, disco com glow em camadas, partículas em pool fixo,
ondulações (ripples) e flashes por estado.

Comportamento por estado (vindo do Core real):
- IDLE/READY: respiração sutil + órbitas lentas
- LISTENING: anéis expandindo do centro + pulso acelerado
- PROCESSING: cometa orbital rápido
- EXECUTING: flash de energia (ping)
- SPEAKING: batimento do núcleo (level 0..1)
- ERROR: véu vermelho pulsante
"""

from __future__ import annotations

import math
import random
import time
from typing import Optional

from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import PARTICLE_COUNT, Theme, get_theme, state_color

require_qt()

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class _Particle:
    __slots__ = ("angle", "radius", "speed", "size", "alpha", "wobble")

    def __init__(self, rng: random.Random) -> None:
        self.angle = rng.uniform(0, math.tau)
        self.radius = rng.uniform(0.32, 0.52)
        self.speed = rng.uniform(0.05, 0.22) * rng.choice((-1.0, 1.0))
        self.size = rng.uniform(1.0, 2.6)
        self.alpha = rng.uniform(0.25, 0.85)
        self.wobble = rng.uniform(0, math.tau)


class NucleusWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None, seed: int = 7,
                 fps: int = 60) -> None:
        super().__init__(parent)
        self._theme: Theme = get_theme("azul")
        self._state: str = "IDLE"
        self._level: float = 0.0
        self._formation: float = 1.0  # 0..1 (intro: anéis se formando)
        self._ripples: list[float] = []  # progressos 0..1
        self._flash: float = 0.0
        self._frozen_time: Optional[float] = None  # testes/screenshots
        self._t0 = time.monotonic()
        rng = random.Random(seed)
        self._particles = [_Particle(rng) for _ in range(PARTICLE_COUNT)]
        self._pens: dict[str, QPen] = {}
        self._brushes: dict[str, QBrush] = {}
        self.setMinimumSize(200, 200)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.set_fps(fps)
        self._rebuild_tools()
        self._timer.start()

    # -- API ---------------------------------------------------------------
    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._rebuild_tools()
        self.update()

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            if state in ("EXECUTING",):
                self.ping(strength=1.0)
            self.update()

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))

    def set_formation(self, value: float) -> None:
        self._formation = max(0.0, min(1.0, value))
        self.update()

    def set_fps(self, fps: int) -> None:
        self._timer.setInterval(max(16, int(1000 / max(1, fps))))

    def set_animated(self, animated: bool) -> None:
        """Liga/desliga o loop de animação (quadro estático continua válido)."""
        if animated and not self._timer.isActive():
            self._timer.start()
        elif not animated and self._timer.isActive():
            self._timer.stop()
        self.update()

    def is_animated(self) -> bool:
        return self._timer.isActive()

    def set_frozen_time(self, t: Optional[float]) -> None:
        """Congela o tempo (screenshots determinísticos / testes)."""
        self._frozen_time = t
        self.update()

    def ping(self, strength: float = 1.0) -> None:
        if len(self._ripples) < 6:
            self._ripples.append(0.0)
        self._flash = max(self._flash, min(1.0, strength))

    def particle_count(self) -> int:
        return len(self._particles)

    # -- internals ----------------------------------------------------------
    def _now(self) -> float:
        if self._frozen_time is not None:
            return self._frozen_time
        return time.monotonic() - self._t0

    def _tick(self) -> None:
        if not self.isVisible():
            return
        dt = self._timer.interval() / 1000.0
        for p in self._particles:
            p.angle += p.speed * dt * (2.5 if self._state == "LISTENING" else 1.0)
        self._ripples = [r + dt * 0.9 for r in self._ripples if r < 1.0]
        if self._flash > 0:
            self._flash = max(0.0, self._flash - dt * 2.2)
        # respiração do level quando falando/ouvindo (orgânico, sem áudio real)
        if self._state in ("SPEAKING", "LISTENING"):
            self._level = 0.55 + 0.45 * abs(math.sin(self._now() * 7.0))
        else:
            self._level = max(0.0, self._level - dt * 3.0)
        self.update()

    def _rebuild_tools(self) -> None:
        t = self._theme
        base = QColor(t.primary)
        self._pens = {
            "ring": self._pen(base, 2, 200),
            "ring_dim": self._pen(base, 1, 90),
            "tick": self._pen(base, 2, 150),
            "arc": self._pen(QColor(t.secondary), 3, 220),
            "orbit": self._pen(base, 1, 70),
            "sat": self._pen(QColor("#ffffff"), 2, 230),
        }
        self._brushes = {
            "core": QBrush(base),
            "white": QBrush(QColor("#ffffff")),
        }
        # cache de brushes de partícula por nível de alpha (10 níveis)
        self._particle_brushes: list[QBrush] = []
        for level in range(10):
            c = QColor(base)
            c.setAlpha(int(255 * (level + 1) / 10))
            self._particle_brushes.append(QBrush(c))

    def _particle_brush(self, alpha: float) -> QBrush:
        idx = min(9, max(0, int(alpha * 10) - 1))
        return self._particle_brushes[idx]

    @staticmethod
    def _pen(color: QColor, width: int, alpha: int) -> QPen:
        c = QColor(color)
        c.setAlpha(alpha)
        pen = QPen(c)
        pen.setWidth(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _with_alpha(self, key: str, alpha: int) -> QPen:
        pen = QPen(self._pens[key])
        color = pen.color()
        color.setAlpha(max(0, min(255, alpha)))
        pen.setColor(color)
        return pen

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (assinatura Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        side = min(self.width(), self.height())
        if side <= 0:
            p.end()
            return
        cx, cy = self.width() / 2.0, self.height() / 2.0
        radius = side / 2.0 - 6.0
        t = self._now()
        formation = self._formation

        state_col = QColor(state_color(self._theme, self._state))
        is_error = self._state == "ERROR"

        # 1) anel externo tracejado (rotação lenta)
        if formation > 0.25:
            pen = self._with_alpha("ring_dim", int(90 * formation))
            pen.setDashPattern([6.0, 8.0])
            pen.setDashOffset(t * 12.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # 2) anel de ticks (gauge)
        if formation > 0.45:
            p.setPen(self._with_alpha("tick", int(150 * formation)))
            rr = radius * 0.88
            for i in range(60):
                ang = math.tau * i / 60.0 + t * 0.05
                long = (i % 5 == 0)
                r1 = rr - (14 if long else 7)
                x1, y1 = cx + math.cos(ang) * r1, cy + math.sin(ang) * r1
                x2, y2 = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
                p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # 3) órbitas + satélites
        if formation > 0.6:
            p.setPen(self._pens["orbit"])
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k, (frac, speed, phase) in enumerate(
                    ((0.74, 0.35, 0.0), (0.62, -0.55, 2.1))):
                rr = radius * frac
                p.setBrush(Qt.BrushStyle.NoBrush)  # satélite anterior sujou o brush
                p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))
                ang = phase + t * speed
                sx, sy = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._brushes["white"] if k == 0 else self._brushes["core"])
                dot = 3.2 if k == 0 else 2.4
                p.drawEllipse(QRectF(sx - dot, sy - dot, dot * 2, dot * 2))
                p.setPen(self._pens["orbit"])

        # 4) arcos de energia (velocidade varia com o estado)
        if formation > 0.7:
            speed = {"LISTENING": 3.2, "PROCESSING": 4.5, "SPEAKING": 2.2,
                     "EXECUTING": 5.0}.get(self._state, 1.1)
            rr = radius * 0.50
            rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
            p.setPen(self._with_alpha("arc", 220))
            p.setBrush(Qt.BrushStyle.NoBrush)
            sweep = 70 + 60 * self._level
            if self._state == "PROCESSING":
                # cometa: arco curto e rápido
                a0 = -math.degrees(t * speed) % 360
                p.drawArc(rect, int(a0 * 16), int(46 * 16))
                a1 = (-math.degrees(t * speed) + 180) % 360
                p.setPen(self._with_alpha("arc", 110))
                p.drawArc(rect, int(a1 * 16), int(30 * 16))
            else:
                a0 = math.degrees(t * speed) % 360
                p.drawArc(rect, int(a0 * 16), int(sweep * 16))
                a1 = (-math.degrees(t * speed * 0.7) + 140) % 360
                p.setPen(self._with_alpha("arc", 130))
                p.drawArc(rect, int(a1 * 16), int((sweep * 0.7) * 16))

        # 5) partículas (alpha via cor do brush; NUNCA QPainter.setOpacity —
        # provoca refcount crash cumulativo no binding; ver docs/BUG_AUDIT.md)
        if formation > 0.8:
            p.setPen(Qt.PenStyle.NoPen)
            for pt in self._particles:
                wob = 1.0 + 0.03 * math.sin(t * 2.0 + pt.wobble)
                rr = radius * pt.radius * wob
                x = cx + math.cos(pt.angle) * rr
                y = cy + math.sin(pt.angle) * rr
                p.setBrush(self._particle_brush(pt.alpha * formation))
                s = pt.size
                p.drawEllipse(QRectF(x - s, y - s, s * 2, s * 2))

        # 6) disco com glow em camadas + núcleo pulsante
        breath = 1.0 + 0.035 * math.sin(t * 1.6) + 0.06 * self._level
        core_r = radius * 0.24 * breath * max(formation, 0.05)
        glow_col = state_col if is_error else QColor(self._theme.primary)
        p.setPen(Qt.PenStyle.NoPen)
        for mult, alpha in ((2.0, 10), (1.6, 20), (1.3, 38)):
            c = QColor(glow_col)
            c.setAlpha(int(alpha * formation))
            p.setBrush(QBrush(c))
            gr = core_r * mult
            p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
        core_c = QColor("#ffffff" if formation > 0.9 else self._theme.primary)
        p.setBrush(QBrush(core_c))
        hot = core_r * 0.32
        p.drawEllipse(QRectF(cx - hot, cy - hot, hot * 2, hot * 2))
        # anel do núcleo
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(self._with_alpha("ring", int(200 * formation)))
        p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # 7) ripples (pings) — LISTENING emite continuamente
        if self._state == "LISTENING" and not self._ripples:
            self._ripples.append(0.0)
        for r in self._ripples:
            rr = core_r + r * (radius - core_r)
            alpha = int(160 * (1.0 - r) * formation)
            if alpha <= 0:
                continue
            p.setPen(self._with_alpha("ring", alpha))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # 8) flash de execução
        if self._flash > 0:
            c = QColor("#ffffff")
            c.setAlpha(int(90 * self._flash))
            p.setPen(QPen(c))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rr = core_r * (1.0 + (1.0 - self._flash) * 1.2)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # 9) véu de erro (halo de alarme ao redor do núcleo, contido)
        if is_error:
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            c = QColor(self._theme.danger)
            c.setAlpha(int(22 + 26 * pulse))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(c))
            vr = radius * 0.52
            p.drawEllipse(QRectF(cx - vr, cy - vr, vr * 2, vr * 2))

        p.end()
