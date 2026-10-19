"""HUB Qt real em offscreen — integração UI<->Core.

Pula automaticamente se PySide6 indisponível. No sandbox sem GL do
sistema, rode com os stubs documentados em docs/BUG_AUDIT.md (BUG-001).
"""

import os
import time

import pytest

from jarvis.ui.hub.qt_compat import HAS_QT

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 indisponível")

if HAS_QT:
    from PySide6.QtWidgets import QApplication


def _ensure_offscreen():
    import sys
    if not sys.platform.startswith("win") and not os.environ.get("DISPLAY") \
            and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app():
    _ensure_offscreen()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def hub_env(qt_app, tmp_path):
    """HUB real sobre Core real (dry-run) em dados temporários."""
    from jarvis.core.app import JarvisApp
    from jarvis.ui.hub.audio import SfxPlayer
    from jarvis.ui.hub.hub_window import HubWindow
    from jarvis.ui.hub.themes import build_stylesheet, get_theme

    core = JarvisApp(data_dir=tmp_path, dry_run=True)
    core.start()
    qt_app.setStyleSheet(build_stylesheet(get_theme("azul")))
    hub = HubWindow(core, sfx=SfxPlayer(enabled=False))
    hub.resize(1280, 720)
    hub.show()
    qt_app.processEvents()
    yield qt_app, core, hub
    try:
        hub._bridge.detach()
    except Exception:
        pass
    try:
        hub.deleteLater()
    except Exception:
        pass
    qt_app.processEvents()
    core.shutdown()


def _pump(qt_app, seconds=0.2):
    deadline = time.time() + seconds
    while time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)


def _wait_until(predicate, qt_app, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qt_app.processEvents()
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(0.02)
    return False


def _grab_bytes(widget) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice
    pix = widget.grab()
    assert not pix.isNull()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buffer, "PNG")
    return bytes(buffer.data())


# -- núcleo ---------------------------------------------------------------------

def test_nucleus_renders_all_states(qt_app):
    from jarvis.ui.hub.nucleus import NucleusWidget
    from jarvis.ui.hub.themes import PARTICLE_COUNT
    widget = NucleusWidget()
    assert widget.particle_count() == PARTICLE_COUNT
    widget.resize(360, 360)
    widget.show()
    qt_app.processEvents()
    for state in ("IDLE", "LISTENING", "PROCESSING", "EXECUTING",
                  "SPEAKING", "READY", "ERROR"):
        widget.set_state(state)
        widget.set_frozen_time(2.0)
        qt_app.processEvents()
        data = _grab_bytes(widget)
        assert len(data) > 2000, state
    widget.set_animated(False)
    assert widget.is_animated() is False
    widget.set_animated(True)
    assert widget.is_animated() is True
    widget.deleteLater()


def test_nucleus_themes_repaint(qt_app):
    from jarvis.ui.hub.nucleus import NucleusWidget
    from jarvis.ui.hub.themes import THEME_ORDER, get_theme
    widget = NucleusWidget()
    widget.resize(300, 300)
    widget.show()
    qt_app.processEvents()
    shots = set()
    for tid in THEME_ORDER:
        widget.set_theme(get_theme(tid))
        widget.set_frozen_time(1.0)
        qt_app.processEvents()
        shots.add(_grab_bytes(widget))
    assert len(shots) == 5  # cada tema rende pixels diferentes
    widget.deleteLater()


# -- HUB --------------------------------------------------------------------------

def test_hub_opens_and_grabs(hub_env):
    qt_app, core, hub = hub_env
    hub.nucleus.set_frozen_time(2.5)
    qt_app.processEvents()
    data = _grab_bytes(hub)
    assert len(data) > 20000


def test_hub_state_badge_follows_core(hub_env):
    qt_app, core, hub = hub_env
    assert hub.state_badge.text() == "EM ESPERA"
    assert core.states.to(core.states.state.__class__.LISTENING)
    assert _wait_until(lambda: hub.state_badge.text() == "OUVINDO", qt_app)
    assert core.states.to(core.states.state.__class__.IDLE)
    assert _wait_until(lambda: hub.state_badge.text() == "EM ESPERA", qt_app)


def test_hub_text_command_end_to_end(hub_env):
    qt_app, core, hub = hub_env
    hub.input.setText("que horas são?")
    hub.submit_text()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() == "CONCLUÍDO"
    assert "GET TIME" in hub.feedback.cmd_label.text()
    assert hub.history.count() >= 1


def test_hub_unknown_command_shows_not_executed(hub_env):
    qt_app, core, hub = hub_env
    hub.input.setText("xyz comando inexistente blargh")
    hub.submit_text()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() == "NÃO EXECUTADO"


def test_hub_confirmation_flow(hub_env):
    qt_app, core, hub = hub_env
    hub.input.setText("desligue o computador")
    hub.submit_text()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() == "AGUARDANDO CONFIRMAÇÃO"
    hub.input.setText("não")
    hub.submit_text()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() == "CONCLUÍDO"
    assert "cancel" in hub.feedback.detail_label.text().lower()


def test_hub_voice_disabled_message(hub_env):
    qt_app, core, hub = hub_env
    core.settings.set("voice.enabled", False)
    hub.start_listening()
    qt_app.processEvents()
    assert hub.feedback.status_label.text() == "DESATIVADO"
    core.settings.set("voice.enabled", True)


def test_hub_voice_worker_without_recognizer(hub_env):
    """Sem Vosk: worker conclui com NÃO EXECUTADO (sem travar/crashar)."""
    qt_app, core, hub = hub_env
    core.settings.set("voice.enabled", True)
    hub.start_listening()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() in ("NÃO EXECUTADO", "DESATIVADO")


def test_hub_theme_cycle_persists(hub_env):
    qt_app, core, hub = hub_env
    start = hub._theme.id
    for _ in range(5):
        hub.cycle_theme_ui()
        qt_app.processEvents()
    assert hub._theme.id == start
    assert core.settings.get("ui.theme") == start


def test_hub_fullscreen_toggle(hub_env):
    qt_app, core, hub = hub_env
    assert hub.isFullScreen() is False
    hub.toggle_fullscreen()
    qt_app.processEvents()
    assert hub.isFullScreen() is True
    hub.toggle_fullscreen()
    qt_app.processEvents()
    assert hub.isFullScreen() is False


def test_hub_resolutions(hub_env):
    qt_app, core, hub = hub_env
    for width, height in ((800, 600), (1280, 720), (1366, 768),
                          (1920, 1080), (2560, 1440)):
        hub.resize(width, height)
        qt_app.processEvents()
        assert hub.nucleus.width() > 80, (width, height, hub.nucleus.width())
        assert hub.nucleus.height() > 80, (width, height, hub.nucleus.height())
        assert hub._left_col.width() <= 320
        assert hub._right_col.width() <= 320
        if width < 1024:
            assert hub._left_col.width() <= 200
        assert len(_grab_bytes(hub)) > 8000


def test_hub_custom_command_end_to_end(hub_env):
    qt_app, core, hub = hub_env
    core.custom_commands.create(
        name="Falar Oi", phrases=["fale oi teste hub"],
        action="speak", params={"text": "Oi do HUB!"})
    hub.input.setText("fale oi teste hub")
    hub.submit_text()
    assert _wait_until(lambda: not hub._busy, qt_app, timeout=15)
    assert hub.feedback.status_label.text() == "CONCLUÍDO"


# -- diálogos ------------------------------------------------------------------------

def test_settings_dialog_theme_change(hub_env):
    qt_app, core, hub = hub_env
    from jarvis.ui.hub.settings_ui import SettingsDialog
    from jarvis.ui.hub.themes import THEME_ORDER
    dialog = SettingsDialog(core, hub)
    dialog.show()
    qt_app.processEvents()
    idx = list(THEME_ORDER).index("verde")
    dialog.theme_combo.setCurrentIndex(idx)
    qt_app.processEvents()
    assert core.settings.get("ui.theme") == "verde"
    assert hub._theme.id == "verde"
    dialog.close()


def test_settings_intro_checkboxes_stay_in_sync(hub_env):
    qt_app, core, hub = hub_env
    from jarvis.ui.hub.settings_ui import SettingsDialog
    dialog = SettingsDialog(core, hub)
    dialog.show()
    qt_app.processEvents()
    assert dialog.intro_check.isChecked() is True
    assert dialog.intro_check_startup.isChecked() is True
    dialog.intro_check.setChecked(False)
    qt_app.processEvents()
    assert core.settings.get("intro.enabled") is False
    assert dialog.intro_check_startup.isChecked() is False
    dialog.intro_check_startup.setChecked(True)
    qt_app.processEvents()
    assert core.settings.get("intro.enabled") is True
    assert dialog.intro_check.isChecked() is True
    dialog.close()


def test_settings_dialog_diagnostics(hub_env):
    qt_app, core, hub = hub_env
    from jarvis.ui.hub.settings_ui import SettingsDialog
    dialog = SettingsDialog(core, hub)
    dialog._run_diagnostics()
    assert "Command Engine" in dialog.diag_label.text()
    dialog.close()


def test_command_dialog_validation(hub_env):
    qt_app, core, hub = hub_env
    from jarvis.ui.hub.commands_ui import CommandDialog, CommandsDialog
    dialog = CommandDialog()
    dialog.name_edit.setText("Site X")
    dialog.phrases_edit.setPlainText("abra o site x teste")
    idx = dialog.action_combo.findData("open_url")
    dialog.action_combo.setCurrentIndex(idx)
    dialog._param_edits["url"].setText("notaurl")
    dialog._on_save()
    assert dialog.result_item is None  # URL inválida bloqueia
    assert dialog.error_label.text() != ""
    dialog._param_edits["url"].setText("https://example.com/test")
    dialog._on_save()
    assert dialog.result_item is not None
    assert dialog.result_item["params"]["url"] == "https://example.com/test"

    manager = CommandsDialog(core, hub)
    manager.show()
    qt_app.processEvents()
    before = manager.custom_list.count()
    core.custom_commands.create(**dialog.result_item)
    manager._reload_custom()
    assert manager.custom_list.count() == before + 1
    manager.close()


def test_commands_dialog_toggle_native(hub_env):
    qt_app, core, hub = hub_env
    from jarvis.ui.hub.commands_ui import CommandsDialog
    manager = CommandsDialog(core, hub)
    assert manager.native_list.count() >= 17
    manager.native_list.setCurrentRow(0)
    cmd_id = manager.native_list.currentItem().data(0x0100)  # UserRole
    before = core.registry.get(cmd_id).enabled
    manager._toggle_native()
    assert core.registry.get(cmd_id).enabled is (not before)
    manager.native_list.setCurrentRow(0)
    manager._toggle_native()
    assert core.registry.get(cmd_id).enabled is before
    manager.close()


# -- intro ------------------------------------------------------------------------------

def test_intro_canvas_frames_render(qt_app):
    from jarvis.ui.hub.intro import IntroCanvas
    from jarvis.ui.hub.themes import get_theme
    canvas = IntroCanvas()
    canvas.set_theme(get_theme("vermelho"))
    canvas.resize(960, 600)
    canvas.show()
    qt_app.processEvents()
    for progress in (0.0, 0.15, 0.45, 0.70, 0.97, 1.0):
        canvas.set_progress(progress)
        qt_app.processEvents()
        assert len(_grab_bytes(canvas)) > 1500, progress
    canvas.deleteLater()


def test_intro_skip_finishes(qt_app):
    from jarvis.ui.hub.audio import SfxPlayer
    from jarvis.ui.hub.intro import IntroWindow
    from jarvis.ui.hub.themes import get_theme
    window = IntroWindow(theme=get_theme("azul"), sfx=SfxPlayer(enabled=False))
    window.show()
    window.start()
    qt_app.processEvents()
    window.skip()
    assert _wait_until(lambda: not window.isVisible(), qt_app, timeout=5)
    assert window.skipped is True


# -- single instance Qt ------------------------------------------------------------------

def test_qt_single_server_handshake(qt_app):
    from jarvis.ui.hub.single_instance import (QtSingleServer,
                                               try_notify_existing)
    calls = []
    server = QtSingleServer(lambda: calls.append(True))
    assert server.listening is True
    qt_app.processEvents()
    assert try_notify_existing(timeout_ms=2000) is True
    assert _wait_until(lambda: len(calls) == 1, qt_app, timeout=5)
    server.close()
    qt_app.processEvents()
