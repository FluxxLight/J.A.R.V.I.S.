"""Bootstrap da interface gráfica: single instance -> Core -> intro -> HUB.

Uso:
    python main.py --hub
"""

from __future__ import annotations

import sys
from typing import Optional

from jarvis.core.app import JarvisApp
from jarvis.logger import get_logger
from jarvis.ui.hub.audio import SfxPlayer
from jarvis.ui.hub.qt_compat import require_qt
from jarvis.ui.hub.themes import Theme, build_stylesheet, get_theme

log = get_logger("ui.app")


def make_icon(theme: Theme, size: int = 64):
    """Ícone da janela pintado em runtime (anel + núcleo, sem asset externo)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    m = size * 0.08
    p.setPen(QPen(QColor(theme.primary), max(2, size // 16)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(m, m, size - 2 * m, size - 2 * m))
    c = QColor(theme.primary)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(c))
    r = size * 0.13
    cx = cy = size / 2
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    p.end()
    return QIcon(pix)


def _configure_dpi() -> None:
    """DPI do Windows: scaling nativo, sem arredondar 125%/150% para 100%/200%."""
    import os
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass


def run_hub(data_dir: Optional[str] = None, dry_run: bool = False,
            no_intro: bool = False, fullscreen: bool = False,
            minimized: bool = False) -> int:
    require_qt()
    _configure_dpi()
    from PySide6.QtWidgets import QApplication

    from jarvis.ui.hub.hub_window import HubWindow
    from jarvis.ui.hub.intro import IntroWindow
    from jarvis.ui.hub.single_instance import (QtSingleServer,
                                               try_notify_existing)

    # 1) single instance: avisa a existente e sai (código 0, sem erro)
    try:
        if try_notify_existing():
            print("J.A.R.V.I.S. já está em execução. Focando a janela existente.")
            return 0
    except Exception:
        log.exception("Falha no handshake single-instance (seguindo)")

    qt_app = QApplication(sys.argv)
    qt_app.setOrganizationName("JARVIS")
    qt_app.setApplicationName("J.A.R.V.I.S.")
    qt_app.setStyle("Fusion")  # visual consistente em qualquer DPI do Windows

    # 2) Core (o mesmo do CLI — nada duplicado)
    app = JarvisApp(data_dir=data_dir, dry_run=dry_run)
    app.start()
    theme = get_theme(app.settings.get("ui.theme", "azul"))
    qt_app.setStyleSheet(build_stylesheet(theme))
    qt_app.setWindowIcon(make_icon(theme))

    sfx = SfxPlayer(enabled=bool(app.settings.get("intro.sound", True)))

    hub = HubWindow(app, sfx=sfx,
                    start_fullscreen=fullscreen,
                    start_minimized=minimized)
    qt_app.setWindowIcon(make_icon(hub._theme))

    # 3) servidor single-instance (foca esta janela quando uma 2ª abrir)
    server: Optional[QtSingleServer] = None
    try:
        server = QtSingleServer(hub.show_and_focus)
        if not server.listening:
            log.error("Outra instância assumiu o servidor. Encerrando.")
            app.shutdown()
            return 1
    except Exception:
        log.exception("Single-instance indisponível (seguindo sem ele)")
        server = None

    # 4) intro (se ativada) -> HUB
    show_intro = bool(app.settings.get("intro.enabled", True)) and not no_intro
    if show_intro:
        intro = IntroWindow(theme=hub._theme, sfx=sfx)
        intro.start()
        intro.exec()
    hub.show()

    # 5) loop
    code = 0
    try:
        code = int(qt_app.exec())
    finally:
        try:
            if server is not None:
                server.close()
        except Exception:
            pass
        try:
            sfx.stop_all()
        except Exception:
            pass
        # app.shutdown() já é chamado pelo closeEvent do HUB; garante idem aqui
        # caso o loop termine por outro caminho.
        try:
            if app.states.state is not None and \
                    str(app.states.state) != "SystemState.SHUTDOWN":
                app.shutdown()
        except Exception:
            pass
    return code
