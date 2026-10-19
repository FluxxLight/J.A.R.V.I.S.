"""Guarda de importação Qt — o produto roda sem PySide6 (modo CLI).

Use:
    from jarvis.ui.hub.qt_compat import require_qt, HAS_QT
    require_qt()  # levanta RuntimeError com instrução de instalação
"""

from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui  # noqa: F401
    from PySide6.QtWidgets import QApplication  # noqa: F401
    HAS_QT = True
    QT_ERROR = ""
except Exception as exc:  # ImportError ou falta de lib do sistema
    HAS_QT = False
    QT_ERROR = str(exc)


def require_qt() -> None:
    if not HAS_QT:
        raise RuntimeError(
            "Interface gráfica indisponível (PySide6 não instalado/detectado). "
            "Instale com: pip install -r requirements-ui.txt "
            f"Detalhe: {QT_ERROR}")
