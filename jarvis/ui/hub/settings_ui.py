"""Central de configurações — 6 seções, 100% funcionais.

Toda alteração aplica imediatamente, persiste em settings.json e é
restaurada no próximo início. Nenhum controle falso.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from jarvis import __version__
from jarvis.logger import get_logger
from jarvis.ui.hub.autostart import AutostartManager, default_start_command
from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import THEME_ORDER, THEMES

require_qt()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSlider, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

if TYPE_CHECKING:  # pragma: no cover
    from jarvis.core.app import JarvisApp

log = get_logger("ui.settings")


class SettingsDialog(QDialog):
    def __init__(self, app: "JarvisApp", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._app = app
        self._settings = app.settings
        self.setWindowTitle("Configurações — J.A.R.V.I.S.")
        self.setMinimumSize(620, 520)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)
        self._build_appearance()
        self._build_voice()
        self._build_mic()
        self._build_commands()
        self._build_startup()
        self._build_system()
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

    # -- helpers ---------------------------------------------------------------
    def _get(self, key: str, default=None):
        return self._settings.get(key, default)

    def _set(self, key: str, value) -> None:
        self._settings.set(key, value)

    # -- Aparência ---------------------------------------------------------------
    def _build_appearance(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.theme_combo = QComboBox()
        for tid in THEME_ORDER:
            self.theme_combo.addItem(THEMES[tid].label, tid)
        self.theme_combo.setCurrentIndex(
            THEME_ORDER.index(self._get("ui.theme", "azul")))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Tema:", self.theme_combo)

        self.anim_check = QCheckBox("Animações do núcleo e HUD")
        self.anim_check.setChecked(bool(self._get("ui.animations", True)))
        self.anim_check.toggled.connect(self._on_anim_changed)
        form.addRow("", self.anim_check)

        self.intro_check = QCheckBox("Mostrar animação de inicialização")
        self.intro_check.setChecked(bool(self._get("intro.enabled", True)))
        self.intro_check.toggled.connect(self._on_intro_changed)
        form.addRow("", self.intro_check)

        self.intro_sound_check = QCheckBox("Efeitos sonoros da intro")
        self.intro_sound_check.setChecked(bool(self._get("intro.sound", True)))
        self.intro_sound_check.toggled.connect(
            lambda v: self._set("intro.sound", bool(v)))
        form.addRow("", self.intro_sound_check)

        self.fs_check = QCheckBox("Iniciar em tela cheia")
        self.fs_check.setChecked(bool(self._get("ui.fullscreen", False)))
        self.fs_check.toggled.connect(
            lambda v: self._set("ui.fullscreen", bool(v)))
        form.addRow("", self.fs_check)

        self.fps_combo = QComboBox()
        self.fps_combo.addItem("60 FPS (fluido)", 60)
        self.fps_combo.addItem("30 FPS (econômico)", 30)
        fps = int(self._get("ui.nucleus_fps", 60))
        self.fps_combo.setCurrentIndex(0 if fps >= 45 else 1)
        self.fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        form.addRow("Taxa do núcleo:", self.fps_combo)
        self.tabs.addTab(page, "Aparência")

    def _on_theme_changed(self, index: int) -> None:
        theme_id = self.theme_combo.itemData(index)
        self._set("ui.theme", theme_id)
        parent = self.parent()
        if parent is not None and hasattr(parent, "apply_theme"):
            try:
                parent.apply_theme(theme_id)
            except Exception:
                log.exception("Falha ao aplicar tema (não fatal)")

    def _on_fps_changed(self, index: int) -> None:
        fps = int(self.fps_combo.itemData(index))
        self._set("ui.nucleus_fps", fps)
        parent = self.parent()
        if parent is not None and hasattr(parent, "nucleus"):
            try:
                parent.nucleus.set_fps(fps)
            except Exception:
                log.exception("Falha ao aplicar FPS (não fatal)")

    def _on_anim_changed(self, value: bool) -> None:
        self._set("ui.animations", bool(value))
        parent = self.parent()
        if parent is not None and hasattr(parent, "nucleus"):
            try:
                parent.nucleus.set_animated(bool(value))
            except Exception:
                log.exception("Falha ao aplicar animações (não fatal)")

    def _on_intro_changed(self, value: bool) -> None:
        """Uma única fonte de verdade: os dois checkboxes (Aparência + Inicialização)."""
        enabled = bool(value)
        self._set("intro.enabled", enabled)
        for box in (getattr(self, "intro_check", None),
                    getattr(self, "intro_check_startup", None)):
            if box is None:
                continue
            if box.isChecked() != enabled:
                box.blockSignals(True)
                box.setChecked(enabled)
                box.blockSignals(False)

    # -- Voz (TTS) ---------------------------------------------------------------
    def _build_voice(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.tts_enabled = QCheckBox("Voz ativada (TTS local)")
        self.tts_enabled.setChecked(bool(self._get("tts.enabled", True)))
        self.tts_enabled.toggled.connect(
            lambda v: self._set("tts.enabled", bool(v)))
        form.addRow("", self.tts_enabled)

        self.voice_combo = QComboBox()
        self._voices_connected = False
        self._reload_voices()
        form.addRow("Voz:", self.voice_combo)

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(50, 400)
        self.rate_spin.setValue(int(self._get("tts.rate", 170)))
        self.rate_spin.valueChanged.connect(
            lambda v: (self._set("tts.rate", int(v)), self._apply_tts()))
        form.addRow("Velocidade:", self.rate_spin)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(float(self._get("tts.volume", 0.9)) * 100))
        self.vol_slider.valueChanged.connect(self._on_volume)
        form.addRow("Volume:", self.vol_slider)

        test_btn = QPushButton("Testar voz")
        test_btn.clicked.connect(self._test_voice)
        form.addRow("", test_btn)
        self.tabs.addTab(page, "Voz")

    def _reload_voices(self) -> None:
        self.voice_combo.clear()
        self.voice_combo.addItem("Padrão do sistema", "")
        try:
            voices = self._app.list_voices()
        except Exception:
            voices = []
        current = str(self._get("tts.voice_id", "") or "")
        selected = 0
        for i, voice in enumerate(voices, start=1):
            label = voice.name or voice.id
            self.voice_combo.addItem(label[:60], voice.id)
            if voice.id == current:
                selected = i
        self.voice_combo.setCurrentIndex(selected)
        if not self._voices_connected:
            self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
            self._voices_connected = True
        if not voices:
            self.voice_combo.setToolTip(
                "Nenhuma voz local detectada (instale pyttsx3 no Windows).")

    def _on_voice_changed(self, index: int) -> None:
        self._set("tts.voice_id", str(self.voice_combo.itemData(index) or ""))
        self._apply_tts()

    def _on_volume(self, value: int) -> None:
        self._set("tts.volume", round(value / 100.0, 2))
        self._apply_tts()

    def _apply_tts(self) -> None:
        """Aplica voz/velocidade/volume no backend TTS real, a quente."""
        try:
            tts = getattr(self._app.speech, "_tts", None)
            if tts is None or not tts.is_ready():
                return
            voice_id = str(self._get("tts.voice_id", "") or "")
            if voice_id:
                tts.set_voice(voice_id)
            tts.set_rate(int(self._get("tts.rate", 170)))
            tts.set_volume(float(self._get("tts.volume", 0.9)))
        except Exception:
            log.exception("Falha ao aplicar TTS (não fatal)")

    def _test_voice(self) -> None:
        self._app.speak("Sistemas operacionais. Esta é a minha voz.", interrupt=True)

    # -- Microfone ---------------------------------------------------------------
    def _build_mic(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.mic_enabled = QCheckBox("Reconhecimento de voz ativado")
        self.mic_enabled.setChecked(bool(self._get("voice.enabled", True)))
        self.mic_enabled.toggled.connect(
            lambda v: self._set("voice.enabled", bool(v)))
        form.addRow("", self.mic_enabled)

        self.mic_combo = QComboBox()
        self._mics_connected = False
        self._reload_mics()
        form.addRow("Dispositivo:", self.mic_combo)

        self.wake_check = QCheckBox('Exigir "Jarvis" antes do comando')
        self.wake_check.setChecked(bool(self._get("voice.wake_word_required", False)))
        self.wake_check.toggled.connect(self._on_wake_changed)
        form.addRow("", self.wake_check)

        self.recog_label = QLabel(self._app.recognizer_status())
        self.recog_label.setWordWrap(True)
        form.addRow("Reconhecedor:", self.recog_label)
        self.tabs.addTab(page, "Microfone")

    def _reload_mics(self) -> None:
        self.mic_combo.clear()
        self.mic_combo.addItem("Microfone padrão", None)
        try:
            devices = self._app.list_microphones()
        except Exception:
            devices = []
        current = self._get("voice.device_index", None)
        selected = 0
        for i, dev in enumerate(devices, start=1):
            self.mic_combo.addItem(str(dev)[:60], dev.index)
            if dev.index == current:
                selected = i
        self.mic_combo.setCurrentIndex(selected)
        if not self._mics_connected:
            self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)
            self._mics_connected = True
        if not devices:
            detail = getattr(self._app.mic, "status_detail", "") or "sem dispositivos"
            self.mic_combo.setToolTip(detail)

    def _on_mic_changed(self, index: int) -> None:
        device = self.mic_combo.itemData(index)
        self._set("voice.device_index", device)
        try:
            self._app.mic.set_device(device)
        except Exception:
            log.exception("Falha ao trocar microfone (não fatal)")

    def _on_wake_changed(self, value: bool) -> None:
        self._set("voice.wake_word_required", bool(value))
        try:
            self._app.voice_pipeline.configure(bool(value))
        except Exception:
            log.exception("Falha ao reconfigurar wake word (não fatal)")

    # -- Comandos ---------------------------------------------------------------
    def _build_commands(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Gerencie comandos nativos e personalizados. "
            "Alterações valem imediatamente.")
        info.setWordWrap(True)
        layout.addWidget(info)
        open_btn = QPushButton("Abrir gerenciador de comandos")
        open_btn.clicked.connect(self._open_commands)
        layout.addWidget(open_btn)
        layout.addStretch(1)
        self.tabs.addTab(page, "Comandos")

    def _open_commands(self) -> None:
        from jarvis.ui.hub.commands_ui import CommandsDialog
        dialog = CommandsDialog(self._app, self)
        dialog.exec()

    # -- Inicialização ---------------------------------------------------------------
    def _build_startup(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self._autostart = AutostartManager()
        available, reason = self._autostart.is_available()
        self.autostart_check = QCheckBox("Inicializar J.A.R.V.I.S. com o Windows")
        self.autostart_check.setEnabled(available)
        if not available:
            self.autostart_check.setToolTip(reason)
        try:
            cmd = default_start_command()
            self.autostart_check.setChecked(
                self._autostart.is_enabled(cmd) if available else False)
        except Exception:
            self.autostart_check.setChecked(False)
        self.autostart_check.toggled.connect(self._on_autostart)
        form.addRow("", self.autostart_check)
        if not available:
            note = QLabel(reason)
            note.setWordWrap(True)
            form.addRow("", note)

        self.min_check = QCheckBox("Iniciar minimizado")
        self.min_check.setChecked(bool(self._get("startup.start_minimized", False)))
        self.min_check.toggled.connect(
            lambda v: self._set("startup.start_minimized", bool(v)))
        form.addRow("", self.min_check)

        self.intro_check_startup = QCheckBox("Mostrar animação de inicialização")
        self.intro_check_startup.setChecked(bool(self._get("intro.enabled", True)))
        self.intro_check_startup.toggled.connect(self._on_intro_changed)
        form.addRow("", self.intro_check_startup)
        self.tabs.addTab(page, "Inicialização")

    def _on_autostart(self, value: bool) -> None:
        try:
            cmd = default_start_command()
            ok, message = self._autostart.set_enabled(bool(value), cmd)
            if ok:
                self._set("startup.autostart", bool(value))
            else:
                self.autostart_check.blockSignals(True)
                self.autostart_check.setChecked(not value)
                self.autostart_check.blockSignals(False)
                QMessageBox.warning(self, "Inicialização", message)
        except Exception as exc:
            log.exception("Falha no autostart")
            QMessageBox.warning(self, "Inicialização", f"Falha: {exc}")

    # -- Sistema ---------------------------------------------------------------
    def _build_system(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Informações")
        form = QFormLayout(box)
        form.addRow("Versão:", QLabel(__version__))
        form.addRow("Reconhecimento:", QLabel(self._app.recognizer_status()))
        form.addRow("TTS:", QLabel(
            "pronto" if getattr(getattr(self._app.speech, "_tts", None),
                                "is_ready", lambda: False)() else "indisponível"))
        form.addRow("Dados:", QLabel(str(self._app.layout["base"])))
        layout.addWidget(box)

        diag_box = QGroupBox("Diagnóstico")
        diag_layout = QVBoxLayout(diag_box)
        self.diag_label = QLabel("Clique em executar para verificar o sistema.")
        self.diag_label.setWordWrap(True)
        diag_layout.addWidget(self.diag_label)
        diag_btn = QPushButton("Executar diagnóstico")
        diag_btn.clicked.connect(self._run_diagnostics)
        diag_layout.addWidget(diag_btn)
        layout.addWidget(diag_box)

        row = QHBoxLayout()
        logs_btn = QPushButton("Abrir pasta de logs")
        logs_btn.clicked.connect(self._open_logs)
        reset_btn = QPushButton("Restaurar padrões")
        reset_btn.clicked.connect(self._reset_settings)
        row.addWidget(logs_btn)
        row.addWidget(reset_btn)
        layout.addLayout(row)
        layout.addStretch(1)
        self.tabs.addTab(page, "Sistema")

    def _run_diagnostics(self) -> None:
        try:
            from jarvis.ui.hub.diagnostics import run_diagnostics
            results = run_diagnostics(self._app)
        except Exception as exc:
            self.diag_label.setText(f"Falha no diagnóstico: {exc}")
            return
        lines = []
        for name, ok, detail in results:
            mark = "OK " if ok else "!! "
            lines.append(f"{mark}{name}: {detail}")
        self.diag_label.setText("\n".join(lines))

    def _open_logs(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._app.layout["logs"])))

    def _reset_settings(self) -> None:
        answer = QMessageBox.question(
            self, "Restaurar padrões",
            "Restaurar TODAS as configurações para o padrão?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._settings.reset_defaults()
            self._reload_mics()
            self._reload_voices()
            QMessageBox.information(self, "Configurações",
                                    "Padrões restaurados. Reabra a janela.")
