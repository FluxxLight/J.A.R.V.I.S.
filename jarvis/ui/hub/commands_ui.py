"""Gerenciador de comandos — nativos (ativar/desativar) e personalizados
(CRUD completo). Opera diretamente sobre registry/CustomCommandManager reais."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from jarvis.commands.custom import CustomCommandError
from jarvis.logger import get_logger
from jarvis.ui.hub.qt_compat import require_qt

require_qt()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QSpinBox, QTabWidget, QTextEdit, QVBoxLayout,
                               QWidget)

if TYPE_CHECKING:  # pragma: no cover
    from jarvis.core.app import JarvisApp

log = get_logger("ui.commands")

ACTIONS = (
    ("open_app", "Abrir aplicativo"),
    ("open_url", "Abrir URL"),
    ("open_folder", "Abrir pasta"),
    ("speak", "Falar mensagem"),
)

ACTION_PARAMS: dict[str, list[tuple[str, str]]] = {
    "open_app": [("app", "Aplicativo (ex.: discord, calculator, code)"),
                 ("path", "Caminho personalizado (opcional)")],
    "open_url": [("url", "URL (https://...)")],
    "open_folder": [("path", "Caminho da pasta")],
    "speak": [("text", "Mensagem a falar")],
}


class CommandDialog(QDialog):
    """Criar/editar UM comando personalizado (com validação real)."""

    def __init__(self, parent: Optional[QWidget] = None,
                 item: Optional[dict[str, Any]] = None) -> None:
        super().__init__(parent)
        self._item = item
        self.setWindowTitle("Editar comando" if item else "Novo comando")
        self.setMinimumSize(520, 560)
        self.setModal(True)
        form = QFormLayout(self)

        self.name_edit = QLineEdit()
        form.addRow("Nome:", self.name_edit)

        self.desc_edit = QLineEdit()
        form.addRow("Descrição:", self.desc_edit)

        self.phrases_edit = QTextEdit()
        self.phrases_edit.setPlaceholderText(
            "Uma frase por linha. Ex.:\nabra o discord\ninicie o discord")
        self.phrases_edit.setMaximumHeight(90)
        form.addRow("Frases:*", self.phrases_edit)

        self.aliases_edit = QTextEdit()
        self.aliases_edit.setPlaceholderText("Variações extras (uma por linha).")
        self.aliases_edit.setMaximumHeight(70)
        form.addRow("Aliases:", self.aliases_edit)

        self.action_combo = QComboBox()
        for action_id, label in ACTIONS:
            self.action_combo.addItem(label, action_id)
        self.action_combo.currentIndexChanged.connect(self._rebuild_params)
        form.addRow("Ação:*", self.action_combo)

        self.params_box = QWidget()
        self.params_form = QFormLayout(self.params_box)
        form.addRow("Parâmetros:", self.params_box)
        self._param_edits: dict[str, QLineEdit] = {}

        self.category_edit = QLineEdit("personalizado")
        form.addRow("Categoria:", self.category_edit)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        self.priority_spin.setValue(55)
        form.addRow("Prioridade:", self.priority_spin)

        self.confirm_check = QCheckBox("Exigir confirmação antes de executar")
        form.addRow("", self.confirm_check)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff5d5d;")
        self.error_label.setWordWrap(True)
        form.addRow("", self.error_label)

        row = QHBoxLayout()
        row.addStretch(1)
        ok_btn = QPushButton("Salvar")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel_btn)
        form.addRow("", row)

        self._rebuild_params()
        if item:
            self._load(item)
        self.result_item: Optional[dict[str, Any]] = None

    def _rebuild_params(self) -> None:
        while self.params_form.count():
            child = self.params_form.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._param_edits.clear()
        action = self.action_combo.currentData()
        for key, label in ACTION_PARAMS.get(action, []):
            edit = QLineEdit()
            edit.setPlaceholderText(label)
            self._param_edits[key] = edit
            self.params_form.addRow(f"{key}:", edit)
        # restaura valores ao trocar de ação durante edição
        if self._item and self._item.get("action") == action:
            for key, value in (self._item.get("params") or {}).items():
                if key in self._param_edits:
                    self._param_edits[key].setText(str(value))

    def _load(self, item: dict[str, Any]) -> None:
        self.name_edit.setText(str(item.get("name", "")))
        self.desc_edit.setText(str(item.get("description", "") or ""))
        self.phrases_edit.setPlainText("\n".join(item.get("phrases", [])))
        self.aliases_edit.setPlainText("\n".join(item.get("aliases", [])))
        idx = self.action_combo.findData(item.get("action", ""))
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)
        self._rebuild_params()
        self.category_edit.setText(str(item.get("category", "personalizado")))
        try:
            self.priority_spin.setValue(int(item.get("priority", 55)))
        except (TypeError, ValueError):
            pass
        self.confirm_check.setChecked(bool(item.get("requires_confirmation", False)))

    def _collect(self) -> dict[str, Any]:
        action = self.action_combo.currentData()
        params = {k: e.text().strip() for k, e in self._param_edits.items()}
        return {
            "name": self.name_edit.text(),
            "description": self.desc_edit.text(),
            "phrases": [l.strip() for l in
                        self.phrases_edit.toPlainText().splitlines() if l.strip()],
            "aliases": [l.strip() for l in
                        self.aliases_edit.toPlainText().splitlines() if l.strip()],
            "action": action,
            "params": params,
            "category": self.category_edit.text().strip() or "personalizado",
            "priority": int(self.priority_spin.value()),
            "requires_confirmation": bool(self.confirm_check.isChecked()),
        }

    def _on_save(self) -> None:
        # Validação antecipada (a mesma do manager, sem persistir).
        from jarvis.commands.custom import _validate_payload
        data = self._collect()
        try:
            _validate_payload(data["name"], data["phrases"],
                              data["action"], data["params"])
        except CustomCommandError as exc:
            self.error_label.setText(str(exc))
            return
        self.result_item = data
        self.accept()


class CommandsDialog(QDialog):
    def __init__(self, app: "JarvisApp", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._app = app
        self.setWindowTitle("Comandos — J.A.R.V.I.S.")
        self.setMinimumSize(660, 520)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)
        self._build_native_tab()
        self._build_custom_tab()
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        btn = QPushButton("Fechar")
        btn.clicked.connect(self.accept)
        close_row.addWidget(btn)
        layout.addLayout(close_row)

    # -- nativos ---------------------------------------------------------------
    def _build_native_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.native_list = QListWidget()
        layout.addWidget(self.native_list)
        row = QHBoxLayout()
        self.native_toggle = QPushButton("Ativar/Desativar")
        self.native_toggle.clicked.connect(self._toggle_native)
        row.addWidget(self.native_toggle)
        row.addStretch(1)
        layout.addLayout(row)
        self.tabs.addTab(page, "Nativos")
        self._reload_native()

    def _reload_native(self) -> None:
        self.native_list.clear()
        for cmd in sorted(self._app.registry.all(), key=lambda c: c.name):
            if cmd.source != "native":
                continue
            mark = "●" if cmd.enabled else "○"
            item = QListWidgetItem(f"{mark} {cmd.name}  [{cmd.intent}]")
            item.setData(Qt.ItemDataRole.UserRole, cmd.id)
            self.native_list.addItem(item)

    def _toggle_native(self) -> None:
        item = self.native_list.currentItem()
        if item is None:
            return
        cmd_id = item.data(Qt.ItemDataRole.UserRole)
        cmd = self._app.registry.get(cmd_id)
        if cmd is None:
            return
        self._app.registry.set_enabled(cmd_id, not cmd.enabled)
        log.info("Comando nativo %s %s", cmd_id,
                 "ativado" if not cmd.enabled else "desativado")
        self._reload_native()

    # -- personalizados ---------------------------------------------------------------
    def _build_custom_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.custom_list = QListWidget()
        layout.addWidget(self.custom_list)
        row = QHBoxLayout()
        for label, slot in (("Novo", self._new_custom),
                            ("Editar", self._edit_custom),
                            ("Ativar/Desativar", self._toggle_custom),
                            ("Excluir", self._delete_custom)):
            btn = QPushButton(label)
            if label == "Excluir":
                btn.setObjectName("danger")
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)
        hint = QLabel("Dica: após criar, teste por texto e por voz (ex.: “jarvis, …”).")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs.addTab(page, "Personalizados")
        self._reload_custom()

    def _reload_custom(self) -> None:
        self.custom_list.clear()
        for item in self._app.custom_commands.list():
            mark = "●" if item.get("enabled") else "○"
            phrases = ", ".join(item.get("phrases", [])[:2])
            widget_item = QListWidgetItem(
                f"{mark} {item.get('name')}  —  {phrases}")
            widget_item.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.custom_list.addItem(widget_item)

    def _selected_custom_id(self) -> Optional[str]:
        item = self.custom_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _new_custom(self) -> None:
        dialog = CommandDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_item:
            return
        try:
            self._app.custom_commands.create(**dialog.result_item)
        except CustomCommandError as exc:
            QMessageBox.warning(self, "Novo comando", str(exc))
            return
        self._reload_custom()

    def _edit_custom(self) -> None:
        cmd_id = self._selected_custom_id()
        if not cmd_id:
            return
        item = self._app.custom_commands.get(cmd_id)
        if not item:
            return
        dialog = CommandDialog(self, item)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_item:
            return
        try:
            self._app.custom_commands.update(cmd_id, **dialog.result_item)
        except CustomCommandError as exc:
            QMessageBox.warning(self, "Editar comando", str(exc))
            return
        self._reload_custom()

    def _toggle_custom(self) -> None:
        cmd_id = self._selected_custom_id()
        if not cmd_id:
            return
        item = self._app.custom_commands.get(cmd_id)
        if item:
            self._app.custom_commands.set_enabled(
                cmd_id, not item.get("enabled", True))
            self._reload_custom()

    def _delete_custom(self) -> None:
        cmd_id = self._selected_custom_id()
        if not cmd_id:
            return
        item = self._app.custom_commands.get(cmd_id)
        name = item.get("name", cmd_id) if item else cmd_id
        answer = QMessageBox.question(
            self, "Excluir comando", f'Excluir "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._app.custom_commands.delete(cmd_id)
            self._reload_custom()
