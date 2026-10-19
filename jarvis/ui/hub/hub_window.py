"""HUB do J.A.R.V.I.S. — centro de comando (PySide6/Qt6).

Consome exclusivamente Core/Engine/Voz/Storage/Settings/Estados existentes:
nenhuma lógica duplicada. Execuções pesadas (voz/ações) rodam em workers
fora da thread da UI; eventos chegam via ponte com queued connections.
"""

from __future__ import annotations

from typing import Optional

from jarvis import __version__
from jarvis.core.events import (COMMAND_EXECUTED, COMMAND_RECEIVED,
                                SPEECH_FINISHED, SPEECH_STARTED,
                                STATE_CHANGED, VOICE_TRANSCRIPT)
from jarvis.logger import get_logger
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.nucleus import NucleusWidget
from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import (SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XL,
                                  FeedbackView, Theme, build_stylesheet,
                                  cycle_theme, feedback_for, get_theme)
from jarvis.ui.hub.widgets import (ClockWidget, FeedbackCard, HistoryWidget,
                                   LogFeed, Panel, StateBadge, StatusRow,
                                   SysInfoWidget)

require_qt()

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QKeySequence, QPainter,
                           QPaintEvent, QResizeEvent)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QPushButton, QVBoxLayout,
                               QWidget)

log = get_logger("ui.hub")


# ---------------------------------------------------------------------------
# Fundo do HUB (gradiente + grade sutil, pintado uma vez por resize)
# ---------------------------------------------------------------------------

class HubBackground(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = get_theme("azul")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        from PySide6.QtGui import QLinearGradient
        p = QPainter(self)
        w, h = max(1, self.width()), max(1, self.height())
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, QColor(self._theme.background_top))
        gradient.setColorAt(1.0, QColor(self._theme.background_bottom))
        p.fillRect(0, 0, w, h, gradient)
        # grade pontilhada sutil
        dot = QColor(self._theme.primary)
        dot.setAlpha(14)
        p.setPen(dot)
        step = 46
        for x in range(step, w, step):
            for y in range(step, h, step):
                p.drawPoint(x, y)
        p.end()


# ---------------------------------------------------------------------------
# Ponte Core -> Qt (thread-safe: sinais com queued connection)
# ---------------------------------------------------------------------------

class EventBridge(QObject):
    state_changed = Signal(str)
    command_received = Signal(str, str)   # text, source
    command_result = Signal(object)       # EngineResult
    voice_text = Signal(str)
    speech_event = Signal(str, bool)      # text, started?

    def __init__(self, app, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._app = app
        self._subs = (
            (STATE_CHANGED, self._on_state),
            (COMMAND_RECEIVED, self._on_received),
            (COMMAND_EXECUTED, self._on_result),
            (VOICE_TRANSCRIPT, self._on_voice),
            (SPEECH_STARTED, self._on_speech_start),
            (SPEECH_FINISHED, self._on_speech_end),
        )
        for event, handler in self._subs:
            app.events.on(event, handler)

    def detach(self) -> None:
        """Remove os handlers do EventBus (evita chamadas após deleteLater)."""
        try:
            for event, handler in self._subs:
                self._app.events.off(event, handler)
        except Exception:
            pass

    def _on_state(self, old=None, new=None, **_) -> None:
        self.state_changed.emit(str(getattr(new, "value", new)))

    def _on_received(self, text="", source="", **_) -> None:
        self.command_received.emit(str(text), str(source))

    def _on_result(self, result=None, **_) -> None:
        self.command_result.emit(result)

    def _on_voice(self, transcript="", **_) -> None:
        self.voice_text.emit(str(transcript))

    def _on_speech_start(self, text="", **_) -> None:
        self.speech_event.emit(str(text), True)

    def _on_speech_end(self, text="", **_) -> None:
        self.speech_event.emit(str(text), False)


# ---------------------------------------------------------------------------
# Workers (nunca bloqueiam a UI)
# ---------------------------------------------------------------------------

class TextWorker(QThread):
    done = Signal(object)  # EngineResult

    def __init__(self, app, text: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._app = app
        self._text = text

    def run(self) -> None:  # noqa: D102
        try:
            self.done.emit(self._app.handle_text(self._text))
        except Exception as exc:  # pragma: no cover - defesa em profundidade
            log.exception("TextWorker falhou")
            from jarvis.command_engine.engine import EngineResult
            self.done.emit(EngineResult(success=False, message=f"Erro: {exc}",
                                        speak_text="Ocorreu um erro."))


class VoiceWorker(QThread):
    done = Signal(object)  # VoiceTrace

    def __init__(self, app, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._app = app

    def run(self) -> None:  # noqa: D102
        try:
            self.done.emit(self._app.listen_once())
        except Exception as exc:  # pragma: no cover - defesa em profundidade
            log.exception("VoiceWorker falhou")
            from jarvis.voice.pipeline import VoiceTrace
            self.done.emit(VoiceTrace(result=f"Erro: {exc}", ignored=True,
                                      ignore_reason=str(exc)))


# ---------------------------------------------------------------------------
# HUB
# ---------------------------------------------------------------------------

class HubWindow(QMainWindow):
    def __init__(self, app, sfx: Optional[SfxPlayer] = None) -> None:
        super().__init__()
        self._app = app
        self._sfx = sfx or SfxPlayer(enabled=False)
        self._theme: Theme = get_theme(app.settings.get("ui.theme", "azul"))
        self._busy = False
        self._worker: Optional[QThread] = None

        self.setWindowTitle("J.A.R.V.I.S. — Centro de Comando")
        self.setMinimumSize(1100, 680)
        self.resize(1440, 860)

        self._bg = HubBackground(self)
        self.setCentralWidget(self._bg)
        root = QVBoxLayout(self._bg)
        root.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        root.setSpacing(SPACE_MD)

        root.addWidget(self._build_topbar())
        main = QHBoxLayout()
        main.setSpacing(SPACE_MD)
        main.addWidget(self._build_left(), 0)
        main.addWidget(self._build_center(), 1)
        main.addWidget(self._build_right(), 0)
        root.addLayout(main, 1)

        self._status_label = QLabel("INICIANDO")
        self._status_label.setObjectName("dim")
        self.statusBar().addWidget(self._status_label, 1)
        offline = QLabel("LOCAL • OFFLINE")
        offline.setObjectName("dim")
        self.statusBar().addPermanentWidget(offline)

        self._bridge = EventBridge(app, self)
        self._bridge.state_changed.connect(self._on_state)
        self._bridge.command_received.connect(self._on_received)
        self._bridge.command_result.connect(self._on_result)
        self._bridge.voice_text.connect(self._on_voice_text)
        self._bridge.speech_event.connect(self._on_speech)

        self._build_shortcuts()
        self.apply_theme(self._theme.id, persist=False)
        self._refresh_status_panel()
        # sincroniza distintivo/núcleo/linhas com o estado REAL atual
        try:
            current = app.states.state
            self._on_state(current.value if current is not None else "IDLE")
        except Exception:
            self._on_state("IDLE")
        self.history.refresh(self._app.memory)
        QTimer.singleShot(0, self._after_show)

    # -- construção ------------------------------------------------------------
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("J.A.R.V.I.S.")
        title.setObjectName("title")
        subtitle = QLabel("JUST A RATHER VERY INTELLIGENT SYSTEM")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)
        self.state_badge = StateBadge()
        self.state_badge.setMinimumWidth(190)
        layout.addWidget(self.state_badge)
        layout.addStretch(1)
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("dim")
        layout.addWidget(ver)
        self.btn_theme = QPushButton("TEMA")
        self.btn_theme.clicked.connect(self.cycle_theme_ui)
        self.btn_full = QPushButton("TELA CHEIA")
        self.btn_full.clicked.connect(self.toggle_fullscreen)
        self.btn_cmds = QPushButton("COMANDOS")
        self.btn_cmds.clicked.connect(self.open_commands)
        self.btn_cfg = QPushButton("CONFIG")
        self.btn_cfg.setObjectName("primary")
        self.btn_cfg.clicked.connect(self.open_settings)
        for btn in (self.btn_theme, self.btn_full, self.btn_cmds, self.btn_cfg):
            layout.addWidget(btn)
        return bar

    def _build_left(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(300)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_MD)

        status = Panel("Estado do sistema")
        self.row_state = StatusRow("Núcleo")
        self.row_mic = StatusRow("Microfone")
        self.row_rec = StatusRow("Reconhecimento")
        self.row_tts = StatusRow("Voz")
        for row in (self.row_state, self.row_mic, self.row_rec, self.row_tts):
            status.add(row)
        layout.addWidget(status)

        clock_panel = Panel("Tempo local")
        clock_panel.add(ClockWidget())
        layout.addWidget(clock_panel)

        sys_panel = Panel("Computador")
        sys_panel.add(SysInfoWidget())
        layout.addWidget(sys_panel)

        hist_panel = Panel("Comandos recentes")
        self.history = HistoryWidget()
        hist_panel.add(self.history)
        layout.addWidget(hist_panel)
        layout.addStretch(1)
        return col

    def _build_center(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_MD)

        self.nucleus = NucleusWidget()
        try:
            self.nucleus.set_fps(int(self._app.settings.get("ui.nucleus_fps", 60)))
        except (TypeError, ValueError):
            pass
        layout.addWidget(self.nucleus, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(SPACE_SM)
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            'Digite um comando…  (ex.: "abra o navegador" • "que horas são?")')
        self.input.returnPressed.connect(self.submit_text)
        self.btn_listen = QPushButton("◉ OUVIR")
        self.btn_listen.setObjectName("primary")
        self.btn_listen.setMinimumWidth(120)
        self.btn_listen.clicked.connect(self.start_listening)
        self.btn_send = QPushButton("ENVIAR")
        self.btn_send.clicked.connect(self.submit_text)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.btn_listen)
        input_row.addWidget(self.btn_send)
        layout.addLayout(input_row)

        self.feedback = FeedbackCard()
        layout.addWidget(self.feedback)
        return col

    def _build_right(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(320)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_MD)

        feed_panel = Panel("Atividade")
        self.feed = LogFeed()
        feed_panel.add(self.feed)
        layout.addWidget(feed_panel, 1)

        quick = Panel("Ações rápidas")
        for label, slot in (("Ouvir comando de voz", self.start_listening),
                            ("Alternar tema", self.cycle_theme_ui),
                            ("Tela cheia (F11)", self.toggle_fullscreen),
                            ("Gerenciar comandos", self.open_commands),
                            ("Abrir configurações", self.open_settings)):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            quick.add(btn)
        layout.addWidget(quick)

        keys = Panel("Atalhos")
        shortcuts = QLabel(
            "F11 — tela cheia\n"
            "Ctrl+T — alternar tema\n"
            "Ctrl+L — ouvir voz\n"
            "Ctrl+, — configurações\n"
            "Esc — fechar janelas")
        shortcuts.setObjectName("dim")
        keys.add(shortcuts)
        layout.addWidget(keys)
        return col

    def _build_shortcuts(self) -> None:
        def add(key: str, slot) -> None:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

        add("F11", self.toggle_fullscreen)
        add("Ctrl+T", self.cycle_theme_ui)
        add("Ctrl+L", self.start_listening)
        add("Ctrl+,", self.open_settings)

    # -- tema -------------------------------------------------------------------
    def apply_theme(self, theme_id: str, persist: bool = True) -> None:
        theme = get_theme(theme_id)
        self._theme = theme
        if persist:
            try:
                self._app.settings.set("ui.theme", theme.id)
            except Exception:
                log.exception("Falha ao persistir tema (não fatal)")
        QApplication.instance().setStyleSheet(build_stylesheet(theme))
        self._bg.set_theme(theme)
        self.nucleus.set_theme(theme)
        self.state_badge.set_theme(theme)
        self.feedback.set_theme(theme)
        self._refresh_status_panel()
        log.info("Tema aplicado: %s", theme.id)

    def cycle_theme_ui(self) -> None:
        self.apply_theme(cycle_theme(self._theme.id))

    # -- tela cheia ----------------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -- diálogos -------------------------------------------------------------------
    def open_settings(self) -> None:
        from jarvis.ui.hub.settings_ui import SettingsDialog
        dialog = SettingsDialog(self._app, self)
        dialog.exec()
        self._apply_runtime_settings()
        self._refresh_status_panel()

    def open_commands(self) -> None:
        from jarvis.ui.hub.commands_ui import CommandsDialog
        dialog = CommandsDialog(self._app, self)
        dialog.exec()

    def _apply_runtime_settings(self) -> None:
        try:
            fps = int(self._app.settings.get("ui.nucleus_fps", 60))
            self.nucleus.set_fps(fps)
        except (TypeError, ValueError):
            pass
        try:
            animated = bool(self._app.settings.get("ui.animations", True))
            self.nucleus.set_animated(animated)
        except Exception:
            pass

    # -- envio -----------------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.btn_listen.setEnabled(not busy)
        self.btn_send.setEnabled(not busy)
        self.input.setEnabled(not busy)
        if busy:
            self.btn_listen.setText("◉ OCUPADO")
        else:
            self.btn_listen.setText("◉ OUVIR")

    def submit_text(self) -> None:
        if self._busy:
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._set_busy(True)
        self.feedback.set_busy("PROCESSANDO", text)
        self._worker = TextWorker(self._app, text, self)
        self._worker.done.connect(self._on_worker_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def start_listening(self) -> None:
        if self._busy:
            self.feed.append_event("voz", "Sistema ocupado; aguarde.")
            return
        if not bool(self._app.settings.get("voice.enabled", True)):
            self.feed.append_event("voz", "Reconhecimento desativado nas configurações.")
            self.feedback.set_feedback(FeedbackView(
                "VOZ", "DESATIVADO", "warning",
                "Ative o reconhecimento na aba Microfone das configurações."))
            return
        self._set_busy(True)
        self.feedback.set_busy("OUVINDO", "fale agora…")
        self._worker = VoiceWorker(self._app, self)
        self._worker.done.connect(self._on_voice_done)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_worker_done(self, result) -> None:
        self._set_busy(False)
        try:
            view = feedback_for(result.intent, result.success, result.executed,
                                result.needs_confirmation, result.message)
        except Exception:
            view = FeedbackView("ERRO", "ERRO", "danger", "Falha interna.")
        self.feedback.set_feedback(view)
        self.history.refresh(self._app.memory)
        if getattr(result, "needs_confirmation", False):
            self.feed.append_event("cmd", "Aguardando confirmação: diga 'sim' ou 'não'.")

    def _on_voice_done(self, trace) -> None:
        self._set_busy(False)
        result = getattr(trace, "engine_result", None)
        if result is None:
            reason = getattr(trace, "ignore_reason", "") or "ignorado"
            self.feedback.set_feedback(FeedbackView(
                "VOZ", "NÃO EXECUTADO", "dim",
                getattr(trace, "result", "") or f"Ignorado: {reason}"))
            if not getattr(trace, "ignored", False):
                self.feed.append_event("voz", f"sem resultado ({reason})")
            return
        self._on_worker_done(result)
        if getattr(trace, "wake_detected", False):
            self.feed.append_event(
                "voz", f"wake detectada → \"{trace.command_after_wake}\"")

    # -- slots de eventos --------------------------------------------------------------
    def _on_state(self, state: str) -> None:
        self.state_badge.set_state(state)
        self.nucleus.set_state(state)
        self.row_state.set_value(state)
        self._status_label.setText(f"Estado: {state}")
        if state == "ERROR":
            try:
                self._sfx.play("error", volume=0.5)
            except Exception:
                pass

    def _on_received(self, text: str, source: str) -> None:
        tag = "voz" if source == "voice" else "texto"
        self.feed.append_event(tag, f"← {text[:120]}")

    def _on_result(self, result) -> None:
        try:
            self.feed.append_event(
                "cmd", f"→ {result.intent} [{'OK' if result.success else 'FALHA'}]")
        except Exception:
            pass

    def _on_voice_text(self, transcript: str) -> None:
        self.feed.append_event("mic", f"transcrito: \"{transcript[:120]}\"")

    def _on_speech(self, text: str, started: bool) -> None:
        if started:
            self.feed.append_event("tts", f"♪ {text[:120]}")

    # -- miscelânea -----------------------------------------------------------------------
    def _refresh_status_panel(self) -> None:
        from jarvis.ui.hub.themes import role_color
        t = self._theme
        try:
            mic_ok = self._app.mic.check_available() if bool(
                self._app.settings.get("voice.enabled", True)) else False
        except Exception:
            mic_ok = False
        self.row_mic.set_value(
            "PRONTO" if mic_ok else "INDISPONÍVEL",
            role_color(t, "success" if mic_ok else "danger"))
        ready = False
        try:
            ready = self._app.recognizer.is_ready()
        except Exception:
            pass
        self.row_rec.set_value(
            "LOCAL PRONTO" if ready else "AUSENTE",
            role_color(t, "success" if ready else "warning"))
        tts_ready = False
        try:
            tts = getattr(self._app.speech, "_tts", None)
            tts_ready = bool(tts is not None and tts.is_ready())
        except Exception:
            pass
        self.row_tts.set_value(
            "PRONTA" if tts_ready else "TEXTO",
            role_color(t, "success" if tts_ready else "dim"))

    def _after_show(self) -> None:
        try:
            if bool(self._app.settings.get("startup.start_minimized", False)):
                self.showMinimized()
            elif bool(self._app.settings.get("ui.fullscreen", False)):
                self.showFullScreen()
        except Exception:
            pass
        self._apply_runtime_settings()
        self.feed.append_event("sys", "HUB online. Núcleo sincronizado com o Core.")
        self.history.refresh(self._app.memory)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        super().keyPressEvent(event)

    def show_and_focus(self) -> None:
        """Traz a instância existente para frente (single instance)."""
        try:
            if self.isMinimized():
                self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception:
            log.exception("show_and_focus falhou (não fatal)")

    def closeEvent(self, event) -> None:  # noqa: N802
        log.info("HUB fechando; encerrando workers e Core…")
        try:
            self._bridge.detach()
        except Exception:
            pass
        try:
            worker, self._worker = self._worker, None
            if worker is not None and worker.isRunning():
                worker.wait(3000)
        except Exception:
            pass
        try:
            self._app.shutdown()
        except Exception:
            log.exception("shutdown falhou (não fatal)")
        event.accept()
