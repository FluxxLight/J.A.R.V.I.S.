"""Intro cinematográfica — UMA experiência animada contínua (~5.2s).

Roteiro em `intro_script.py` (testável); este widget apenas pinta o frame
e dispara os SFX sincronizados. Respeita o tema ativo. Pulável com
clique, ESPAÇO, ENTER ou ESC.
"""

from __future__ import annotations

import math
from typing import Optional

from jarvis.logger import get_logger
from jarvis.ui.hub import intro_script
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import Theme, get_theme

require_qt()

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

log = get_logger("ui.intro")


class IntroCanvas(QWidget):
    """Pinta `IntroFrame` — também usável para screenshots de teste."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme: Theme = get_theme("azul")
        self._progress: float = 0.0
        self.setMinimumSize(640, 400)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = max(1, self.width()), max(1, self.height())
        frame = intro_script.frame_at(self._progress)
        t = self._theme

        # fundo escuro
        p.fillRect(0, 0, w, h, QColor(t.background_top))
        cx, cy = w / 2.0, h * 0.44

        def alpha_pen(color: str, width: int, alpha: float) -> QPen:
            c = QColor(color)
            c.setAlpha(int(255 * max(0.0, min(1.0, alpha))))
            pen = QPen(c)
            pen.setWidth(width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            return pen

        # 1) sinal de atividade: ponto pulsante no escuro
        if frame.signal > 0.01:
            pulse = 0.6 + 0.4 * math.sin(self._progress * 60.0)
            c = QColor(t.primary)
            c.setAlpha(int(220 * frame.signal * pulse))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(c))
            r = 5 + 3 * pulse
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # 2) linhas HUD: varredura horizontal que constrói a moldura
        if frame.lines > 0.01:
            y = h * 0.12 + (h * 0.76) * frame.lines
            p.setPen(alpha_pen(t.primary, 1, 0.5 * frame.lines))
            p.drawLine(int(w * 0.06), int(y), int(w * 0.94), int(y))
            # cantos da moldura
            m = int(18 + 30 * (1 - frame.lines))
            p.setPen(alpha_pen(t.primary, 2, 0.8 * frame.lines))
            corners = [(m, m, 1, 1), (w - m, m, -1, 1),
                       (m, h - m, 1, -1), (w - m, h - m, -1, -1)]
            L = 26
            for x, yy, dx, dy in corners:
                p.drawLine(x, yy, x + dx * L, yy)
                p.drawLine(x, yy, x, yy + dy * L)

        # 3) anéis se formando (arcos parciais crescentes)
        if frame.rings > 0.01:
            base_r = min(w, h) * 0.22
            for k, frac in enumerate((1.0, 0.78, 0.58)):
                rr = base_r * frac
                rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
                span = 360 * frame.rings
                start = -90 - k * 40 + self._progress * 120 * (1 if k % 2 == 0 else -1)
                p.setPen(alpha_pen(t.primary, 2 if k else 3, 0.85 * frame.rings))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(rect, int(start * 16), int(span * 16))

        # 4) núcleo ativado: pulso de energia
        if frame.core > 0.01:
            glow = QColor(t.primary)
            glow.setAlpha(int(120 * frame.core))
            p.setPen(Qt.PenStyle.NoPen)
            for mult in (3.2, 2.2, 1.5):
                gr = 12 * mult * frame.core
                p.setBrush(QBrush(glow))
                p.drawEllipse(QRectF(cx - gr, cy - gr, gr * 2, gr * 2))
            p.setBrush(QBrush(QColor("#ffffff")))
            cr = 7 * frame.core
            p.drawEllipse(QRectF(cx - cr, cy - cr, cr * 2, cr * 2))

        # 5) indicadores laterais (barras carregando)
        if frame.gauges > 0.01:
            p.setPen(alpha_pen(t.secondary, 2, 0.7 * frame.gauges))
            for side in (-1, 1):
                x = cx + side * min(w, h) * 0.30
                for i in range(5):
                    y0 = cy - 44 + i * 20
                    frac = max(0.0, min(1.0, frame.gauges * 5 - i))
                    p.drawLine(int(x), int(y0), int(x + side * 44 * frac), int(y0))

        # 6) título + status
        if frame.title > 0.01:
            c = QColor(t.text)
            c.setAlpha(int(255 * frame.title))
            p.setPen(QPen(c))
            font = QFont("Segoe UI")
            font.setPointSize(max(18, int(min(w, h) * 0.075)))
            font.setWeight(QFont.Weight.ExtraBold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
            p.setFont(font)
            p.drawText(QRectF(0, h * 0.66, w, h * 0.16),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S.")
            sub = QFont("Segoe UI")
            sub.setPointSize(max(9, int(min(w, h) * 0.028)))
            sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
            p.setFont(sub)
            sc = QColor(t.success if frame.ready else t.secondary)
            sc.setAlpha(int(255 * frame.title))
            p.setPen(QPen(sc))
            if frame.status_text:
                p.drawText(QRectF(0, h * 0.80, w, h * 0.08),
                           Qt.AlignmentFlag.AlignCenter, frame.status_text)
        p.end()


class IntroWindow(QDialog):
    finished_ok = Signal()

    def __init__(self, theme: Optional[Theme] = None,
                 sfx: Optional[SfxPlayer] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("J.A.R.V.I.S.")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(960, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = IntroCanvas(self)
        if theme is not None:
            self.canvas.set_theme(theme)
        layout.addWidget(self.canvas)
        self._sfx = sfx
        self._clock = QElapsedTimer()
        self._last_progress = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._skipped = False

    @property
    def skipped(self) -> bool:
        return self._skipped

    def start(self) -> None:
        self._clock.start()
        self._timer.start(33)  # ~30 fps
        log.info("Intro iniciada.")

    def _advance(self) -> None:
        progress = intro_script.progress_for_elapsed(int(self._clock.elapsed()))
        self.canvas.set_progress(progress)
        if self._sfx is not None:
            for cue in intro_script.due_cues(self._last_progress, progress):
                self._sfx.play(cue, volume=0.7)
        self._last_progress = progress
        if progress >= 1.0:
            self._done()

    def _done(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        log.info("Intro concluída (pulada=%s).", self._skipped)
        self.finished_ok.emit()
        self.accept()

    def skip(self) -> None:
        """Pula para o fim imediatamente (com READY visível por um instante)."""
        self._skipped = True
        self.canvas.set_progress(1.0)
        if self._sfx is not None:
            self._sfx.play("ready", volume=0.6)
        QTimer.singleShot(250, self._done)

    # -- eventos de pulo ------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.skip()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self.skip()
