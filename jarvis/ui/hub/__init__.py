"""HUB gráfico do J.A.R.V.I.S. (PySide6/Qt6 + lógica headless testável)."""

from jarvis.ui.hub.qt_compat import HAS_QT, QT_ERROR, require_qt

__all__ = ["HAS_QT", "QT_ERROR", "require_qt"]
