"""Comandos nativos do J.A.R.V.I.S. (frases + aliases em pt-BR)."""

from __future__ import annotations

from jarvis.commands.base import Command
from jarvis.commands.registry import CommandRegistry
from jarvis.logger import get_logger

log = get_logger("commands.native")


def _cmd(cmd_id: str, intent: str, name: str, phrases: list[str],
         action_id: str, aliases: list[str] | None = None,
         params: dict | None = None, category: str = "sistema",
         priority: int = 50, requires_confirmation: bool = False,
         description: str = "") -> Command:
    return Command(
        id=cmd_id, intent=intent, name=name, description=description or name,
        phrases=phrases, aliases=aliases or [], action_id=action_id,
        params=params or {}, category=category, priority=priority,
        requires_confirmation=requires_confirmation, enabled=True, source="native",
    )


def build_native_commands() -> list[Command]:
    return [
        _cmd("native.open_browser", "OPEN_BROWSER", "Abrir navegador",
             ["abra o navegador", "abrir navegador", "abre o navegador"],
             "OpenApplication",
             aliases=["pode abrir o navegador", "inicia o navegador",
                      "inicie o navegador", "abrir o navegador",
                      "abra meu navegador", "quero navegar na internet",
                      "abre o browser", "abra o browser"],
             params={"app": "browser"}, category="apps", priority=60),

        _cmd("native.open_calculator", "OPEN_CALCULATOR", "Abrir calculadora",
             ["abra a calculadora", "abrir calculadora", "abre a calculadora"],
             "OpenApplication",
             aliases=["pode abrir a calculadora", "inicie a calculadora",
                      "abrir a calculadora", "abra minha calculadora",
                      "quero fazer calculos", "quero fazer cálculos"],
             params={"app": "calculator"}, category="apps", priority=60),

        _cmd("native.open_notepad", "OPEN_NOTEPAD", "Abrir bloco de notas",
             ["abra o bloco de notas", "abrir bloco de notas", "abre o bloco de notas"],
             "OpenApplication",
             aliases=["pode abrir o bloco de notas", "inicie o bloco de notas",
                      "abrir o bloco de notas", "abra o notepad",
                      "quero escrever uma nota", "abrir notepad"],
             params={"app": "notepad"}, category="apps", priority=60),

        _cmd("native.open_explorer", "OPEN_EXPLORER", "Abrir explorador de arquivos",
             ["abra o explorador de arquivos", "abrir explorador de arquivos"],
             "OpenApplication",
             aliases=["abre o explorador", "abra o explorador",
                      "abrir o explorador", "abra meus arquivos",
                      "abrir arquivos", "abre meus arquivos",
                      "abra a pasta de arquivos"],
             params={"app": "explorer"}, category="apps", priority=60),

        _cmd("native.open_settings", "OPEN_SETTINGS", "Abrir configurações",
             ["abra as configuracoes", "abrir configurações", "abre as configurações"],
             "OpenWindowsSettings",
             aliases=["abra as configuraçoes do windows", "abrir as configuracoes",
                      "configuracoes do windows", "abra o painel de configuracoes",
                      "quero abrir as configuracoes"],
             category="sistema", priority=60),

        _cmd("native.open_discord", "OPEN_APP", "Abrir Discord",
             ["abra o discord", "abrir discord"],
             "OpenApplication",
             aliases=["abre o discord", "inicie o discord", "abrir o discord",
                      "pode abrir o discord"],
             params={"app": "discord"}, category="apps", priority=60),

        _cmd("native.open_url", "OPEN_URL", "Abrir site/link",
             ["abra o site", "abrir site", "abra o link"],
             "OpenUrl",
             aliases=["abre o site", "abrir o link", "abra essa url",
                      "abrir url", "acesse o site", "acessar site",
                      "abra a pagina", "abrir pagina"],
             category="apps", priority=40),

        _cmd("native.get_time", "GET_TIME", "Dizer as horas",
             ["que horas sao", "que horas são"],
             "GetTime",
             aliases=["me diga as horas", "diga as horas", "qual o horario",
                      "qual o horário", "que hora e", "que hora é",
                      "me fala a hora", "qual hora e agora"],
             category="info", priority=60),

        _cmd("native.get_date", "GET_DATE", "Dizer a data",
             ["que dia e hoje", "qual a data de hoje"],
             "GetDate",
             aliases=["me diga a data", "diga a data", "qual dia e hoje",
                      "que dia e", "data de hoje", "qual e a data"],
             category="info", priority=60),

        _cmd("native.minimize", "MINIMIZE_WINDOW", "Minimizar janela",
             ["minimize a janela", "minimizar janela"],
             "MinimizeWindow",
             aliases=["minimiza a janela", "minimizar a janela",
                      "minimize", "minimiza", "ocultar janela"],
             category="janelas", priority=60),

        _cmd("native.maximize", "MAXIMIZE_WINDOW", "Maximizar janela",
             ["maximize a janela", "maximizar janela"],
             "MaximizeWindow",
             aliases=["maximiza a janela", "maximizar a janela",
                      "maximize", "maximiza", "expandir janela"],
             category="janelas", priority=60),

        _cmd("native.fullscreen", "TOGGLE_FULLSCREEN", "Tela cheia",
             ["tela cheia", "modo tela cheia"],
             "ToggleFullscreen",
             aliases=["fullscreen", "coloca em tela cheia",
                      "colocar em tela cheia", "alternar tela cheia",
                      "expandir tela cheia"],
             category="janelas", priority=60),

        _cmd("native.lock", "LOCK_COMPUTER", "Bloquear computador",
             ["bloqueie o computador", "bloquear computador"],
             "LockComputer",
             aliases=["bloqueia o pc", "bloqueie o pc", "bloquear o pc",
                      "bloquear computador", "trave o pc", "travar o pc",
                      "bloquear a tela", "bloqueie a tela"],
             category="sistema", priority=70),

        _cmd("native.restart", "RESTART_COMPUTER", "Reiniciar computador",
             ["reinicie o computador", "reiniciar computador"],
             "RestartComputer",
             aliases=["reinicia o pc", "reinicie o pc", "reiniciar o pc",
                      "reiniciar o computador", "quero reiniciar o pc"],
             category="sistema", priority=80, requires_confirmation=True),

        _cmd("native.shutdown", "SHUTDOWN_COMPUTER", "Desligar computador",
             ["desligue o computador", "desligar computador"],
             "ShutdownComputer",
             aliases=["desliga o pc", "desligue o pc", "desligar o pc",
                      "desligar o computador", "quero desligar o pc",
                      "apague o pc", "desligar tudo"],
             category="sistema", priority=80, requires_confirmation=True),

        _cmd("native.exit", "EXIT_JARVIS", "Fechar J.A.R.V.I.S.",
             ["feche o jarvis", "fechar jarvis"],
             "ExitJarvis",
             aliases=["encerre o jarvis", "encerrar jarvis", "desligue o jarvis",
                      "desligar jarvis", "saia do jarvis", "sair do jarvis",
                      "feche o programa", "adeus jarvis", "ate logo jarvis"],
             category="sistema", priority=80, requires_confirmation=True),

        _cmd("native.help", "HELP", "Ajuda",
             ["ajuda", "me ajude"],
             "Speak",
             aliases=["o que voce pode fazer", "o que você pode fazer",
                      "quais comandos", "listar comandos", "socorro",
                      "como funciona", "help"],
             params={"text": ("Posso abrir programas e sites, dizer horas e data, "
                              "controlar janelas, bloquear, reiniciar ou desligar o "
                              "PC, e executar comandos personalizados. Diga, por "
                              "exemplo: abra o navegador.")},
             category="info", priority=30),
    ]


def register_all(registry: CommandRegistry) -> None:
    for command in build_native_commands():
        registry.register(command)
    log.info("Comandos nativos registrados: %d", registry.count())
