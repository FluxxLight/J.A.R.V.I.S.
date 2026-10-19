"""Ações centrais reutilizáveis (único lugar com efeitos no sistema)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from jarvis.commands.base import Action, ActionContext, ActionResult
from jarvis.logger import get_logger
from jarvis.system import launcher, windows

log = get_logger("actions")

_MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo"]


def _done(message: str, speak: str = "", **data: Any) -> ActionResult:
    return ActionResult(True, message, speak or message, data)


def _fail(message: str, speak: str = "") -> ActionResult:
    return ActionResult(False, message, speak or message)


class OpenApplication(Action):
    id = "OpenApplication"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        if not params.get("app"):
            return "Aplicativo não informado."
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        app = str(params.get("app", "")).strip()
        custom = str(params.get("path", "") or "").strip()
        if ctx.dry_run:
            return _done(f"[dry-run] abriria {app}", f"Abrindo {app}.", app=app)
        ok, msg = launcher.open_app(app, custom)
        label = app.capitalize()
        if ok:
            return _done(msg, f"Abrindo {label}.", app=app)
        return _fail(msg)


class CloseApplication(Action):
    id = "CloseApplication"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        if not str(params.get("app", "") or "").strip():
            return "Diga qual aplicativo fechar. Ex.: feche o Discord."
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        app = str(params.get("app", "")).strip()
        label = app.capitalize()
        if ctx.dry_run:
            return _done(f"[dry-run] fecharia {app}", f"Fechando {label}.", app=app)
        entry = launcher.APP_CATALOG.get(app.lower(), {})
        exe_names = list(entry.get("exe_names", [])) + [app, f"{app}.exe"]
        ok, msg = windows.close_app_windows(exe_names, title_hint=app)
        if ok:
            return _done(msg, f"Fechando {label}.", app=app)
        return _fail(msg if "Windows" not in msg else
                     f"Não consegui fechar {label}: {msg}")


class OpenUrl(Action):
    id = "OpenUrl"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        url = str(params.get("url", "") or "").strip()
        if not url:
            return "URL não informada."
        if not launcher.is_valid_url(url) and not launcher.extract_url(url):
            return f"URL inválida: {url}"
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        url = str(params.get("url", "")).strip()
        if not launcher.is_valid_url(url):
            url = launcher.extract_url(url) or url
        if ctx.dry_run:
            return _done(f"[dry-run] abriria {url}", "Abrindo link.", url=url)
        ok, msg = launcher.open_url(url)
        if ok:
            return _done(msg, "Abrindo link.", url=url)
        return _fail(msg)


class OpenFolder(Action):
    id = "OpenFolder"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        if not str(params.get("path", "") or "").strip():
            return "Pasta não informada."
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        path = str(params.get("path", "")).strip()
        if ctx.dry_run:
            return _done(f"[dry-run] abriria pasta {path}", "Abrindo pasta.", path=path)
        ok, msg = launcher.open_folder(path)
        if ok:
            return _done(msg, "Abrindo pasta.", path=path)
        return _fail(msg)


class OpenWindowsSettings(Action):
    id = "OpenWindowsSettings"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        section = str(params.get("section", "") or "").strip()
        if ctx.dry_run:
            return _done("[dry-run] abriria Configurações", "Abrindo configurações.")
        ok, msg = windows.open_windows_settings(section)
        if ok:
            return _done(msg, "Abrindo configurações.")
        return _fail(msg)


class GetTime(Action):
    id = "GetTime"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        now = datetime.datetime.now()
        text = f"Agora são {now.hour} horas e {now.minute} minutos."
        if now.minute == 0:
            text = f"Agora são {now.hour} horas em ponto."
        elif now.minute == 1:
            text = f"Agora são {now.hour} horas e 1 minuto."
        return _done(text, text, time=now.strftime("%H:%M"))


class GetDate(Action):
    id = "GetDate"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        now = datetime.datetime.now()
        text = (f"Hoje é { _DIAS[now.weekday()]}, {now.day} de "
                f"{_MESES[now.month]} de {now.year}.")
        return _done(text, text, date=now.strftime("%Y-%m-%d"))


class MinimizeWindow(Action):
    id = "MinimizeWindow"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if ctx.dry_run:
            return _done("[dry-run] minimizaria janela", "Janela minimizada.")
        ok, msg = windows.minimize_foreground()
        return _done(msg, msg) if ok else _fail(msg)


class MaximizeWindow(Action):
    id = "MaximizeWindow"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if ctx.dry_run:
            return _done("[dry-run] maximizaria janela", "Janela maximizada.")
        ok, msg = windows.maximize_foreground()
        return _done(msg, msg) if ok else _fail(msg)


class ToggleFullscreen(Action):
    id = "ToggleFullscreen"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if ctx.dry_run:
            return _done("[dry-run] alternaria tela cheia", "Tela cheia alternada.")
        ok, msg = windows.toggle_fullscreen_foreground()
        return _done(msg, msg) if ok else _fail(msg)


class LockComputer(Action):
    id = "LockComputer"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if ctx.dry_run:
            return _done("[dry-run] bloquearia o PC", "Bloqueando computador.")
        ok, msg = windows.lock_workstation()
        return _done(msg, "Bloqueando.") if ok else _fail(msg)


class RestartComputer(Action):
    id = "RestartComputer"
    requires_confirmation = True
    confirm_prompt = "Tem certeza que deseja REINICIAR o computador?"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if not ctx.confirmed:
            return _fail("Reinício exige confirmação.", "Reinício exige confirmação.")
        if ctx.dry_run:
            return _done("[dry-run] reiniciaria o PC", "Reiniciando.")
        ok, msg = windows.restart_computer()
        return _done(msg, "Reiniciando o computador.") if ok else _fail(msg)


class ShutdownComputer(Action):
    id = "ShutdownComputer"
    requires_confirmation = True
    confirm_prompt = "Tem certeza que deseja DESLIGAR o computador?"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if not ctx.confirmed:
            return _fail("Desligamento exige confirmação.", "Desligamento exige confirmação.")
        if ctx.dry_run:
            return _done("[dry-run] desligaria o PC", "Desligando.")
        ok, msg = windows.shutdown_computer()
        return _done(msg, "Desligando o computador.") if ok else _fail(msg)


class ExitJarvis(Action):
    id = "ExitJarvis"
    requires_confirmation = True
    confirm_prompt = "Deseja fechar o J.A.R.V.I.S.?"

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        if not ctx.confirmed:
            return _fail("Saída exige confirmação.", "Saída exige confirmação.")
        if callable(ctx.request_exit):
            ctx.request_exit()
        return _done("Encerrando J.A.R.V.I.S.", "Até logo, senhor.")


class Speak(Action):
    """Ação para comandos personalizados que apenas falam uma mensagem."""
    id = "Speak"

    def validate(self, params: dict[str, Any]) -> Optional[str]:
        if not str(params.get("text", "") or "").strip():
            return "Texto da mensagem não informado."
        return None

    def execute(self, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
        text = str(params.get("text", "")).strip()
        return _done(text, text)


def register_all(registry) -> None:
    """Registra todas as ações centrais no registry."""
    for cls in (OpenApplication, CloseApplication, OpenUrl, OpenFolder, OpenWindowsSettings,
                GetTime, GetDate, MinimizeWindow, MaximizeWindow,
                ToggleFullscreen, LockComputer, RestartComputer,
                ShutdownComputer, ExitJarvis, Speak):
        registry.register_action(cls())
    log.info("Ações centrais registradas.")
