"""Componentes do HUB: distintivo de estado, relógio, info, histórico,
cartão de feedback, feed de eventos e painéis. Consomem Core/temas reais."""

from __future__ import annotations

import datetime
import platform
from typing import Optional

from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import (FONT_MONO_BODY, FONT_SMALL, SPACE_MD, SPACE_SM,
                                  SPACE_XS, FeedbackView, Theme, get_theme,
                                  role_color, state_color, state_label)

require_qt()

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QVBoxLayout,
                               QWidget)


def mono_font(size: int = FONT_MONO_BODY) -> QFont:
    font = QFont("Consolas")
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class Panel(QFrame):
    """Painel de vidro do design system."""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None,
                 accent: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("panelAccent" if accent else "panel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_MD, SPACE_MD)
        self._layout.setSpacing(SPACE_SM)
        if title:
            header = QLabel(title.upper())
            header.setObjectName("section")
            self._layout.addWidget(header)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)


class StateBadge(QLabel):
    """Distintivo do estado real do sistema (STARTING..ERROR)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("stateBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._theme = get_theme("azul")
        self._state = "IDLE"
        self.refresh()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.refresh()

    def set_state(self, state: str) -> None:
        self._state = state or "IDLE"
        self.refresh()

    def refresh(self) -> None:
        color = state_color(self._theme, self._state)
        self.setText(state_label(self._state))
        self.setStyleSheet(
            f"QLabel#stateBadge {{ color: {color}; "
            f"border: 1px solid {color}; background: rgba(0,0,0,90); }}")


class ClockWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("title")
        self.time_label.setFont(mono_font(24))
        self.date_label = QLabel("")
        self.date_label.setObjectName("dim")
        layout.addWidget(self.time_label)
        layout.addWidget(self.date_label)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    def refresh(self) -> None:
        now = datetime.datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sábado", "domingo"]
        meses = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        self.date_label.setText(
            f"{dias[now.weekday()]}, {now.day} de {meses[now.month]}")


class SysInfoWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XS)
        import os
        from jarvis import __version__
        rows = [
            ("SISTEMA", f"{platform.system()} {platform.release()}"),
            ("MODO", "LOCAL • OFFLINE"),
            ("VERSÃO", __version__),
            ("NÚCLEOS CPU", str(os.cpu_count() or "?")),
        ]
        for key, value in rows:
            row = QLabel(f"<span style='color:#8fa3b8'>{key}</span>  {value}")
            row.setObjectName("body")
            row.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(row)


class HistoryWidget(QListWidget):
    """Comandos recentes (vindos da memória real)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMaximumHeight(150)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def refresh(self, memory) -> None:
        try:
            items = memory.recent_history(12)
        except Exception:
            items = []
        self.clear()
        for entry in reversed(items):
            ok = "●" if entry.get("success") else "○"
            text = f"{ok} {(entry.get('text') or '')[:42]}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.addItem(item)
        if not items:
            item = QListWidgetItem("— nenhum comando ainda —")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.addItem(item)


class FeedbackCard(Panel):
    """Cartão COMANDO → PROCESSAMENTO → EXECUÇÃO → RESULTADO (real)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("", parent, accent=True)
        self._theme = get_theme("azul")
        self.cmd_label = QLabel("AGUARDANDO COMANDO")
        self.cmd_label.setObjectName("mono")
        self.status_label = QLabel("—")
        self.status_label.setObjectName("section")
        self.detail_label = QLabel("Digite abaixo ou pressione OUVIR e fale.")
        self.detail_label.setObjectName("dim")
        self.detail_label.setWordWrap(True)
        self.add(self.cmd_label)
        self.add(self.status_label)
        self.add(self.detail_label)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme

    def set_busy(self, stage: str, command: str) -> None:
        color = role_color(self._theme, "primary")
        self.cmd_label.setText((command or "—").upper()[:60])
        self.status_label.setText(stage.upper())
        self.status_label.setStyleSheet(f"color: {color};")
        self.detail_label.setText("Processando comando local…")

    def set_feedback(self, view: FeedbackView) -> None:
        color = role_color(self._theme, view.role)
        self.cmd_label.setText(view.title[:60])
        self.status_label.setText(view.status)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 800;")
        self.detail_label.setText(view.detail[:280] or "—")


class LogFeed(QPlainTextEdit):
    """Feed de eventos do sistema (voz, comandos, voz/TTS)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(mono_font(FONT_SMALL + 1))
        self.setMaximumBlockCount(200)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def append_event(self, tag: str, message: str) -> None:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.appendPlainText(f"[{now}] [{tag}] {message}")
        bar = self.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())


class StatusRow(QWidget):
    """Linha 'rótulo .... valor' para o painel de status."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.key = QLabel(label.upper())
        self.key.setObjectName("dim")
        self.value = QLabel("—")
        self.value.setObjectName("body")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.key)
        layout.addStretch(1)
        layout.addWidget(self.value)

    def set_value(self, text: str, color: str = "") -> None:
        self.value.setText(text)
        if color:
            pal = self.value.palette()
            pal.setColor(self.value.foregroundRole(), QColor(color))
            self.value.setPalette(pal)
