"""Interface de terminal (REPL) — fina; toda lógica está no Core/Engine."""

from __future__ import annotations

import argparse
import sys

from jarvis import __version__
from jarvis.core.app import JarvisApp
from jarvis.logger import get_logger

log = get_logger("ui.cli")

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
  Just A Rather Very Intelligent System — v{ver} (local, sem nuvem)
""".format(ver=__version__)

HELP = """Comandos do console:
  <texto>              envia comando ao J.A.R.V.I.S.
  :ouvir              captura uma fala do microfone (se configurado)
  :voz <texto>        simula uma transcrição de voz ("jarvis, abra ...")
  :mics               lista microfones
  :vozes              lista vozes de TTS disponíveis
  :estado             mostra estado atual
  :ajuda              esta ajuda
  :sair               encerra
"""


def run_repl(app: JarvisApp) -> int:
    print(BANNER)
    print(HELP)
    print(f"Reconhecimento: {app.recognizer_status()}")
    print("Digite um comando. Ex.: abra o navegador | que horas são?")
    print("-" * 60)
    app.speak("Sistemas online. Pois não, senhor?")
    while not app.exit_requested:
        try:
            line = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith(":"):
            if not _handle_meta(app, line):
                break
            continue
        result = app.handle_text(line)
        print(f"jarvis> {result.message}")
        if result.needs_confirmation:
            print("        (responda 'sim' ou 'não')")
    return 0


def _handle_meta(app: JarvisApp, line: str) -> bool:
    parts = line[1:].split(None, 1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    if cmd in ("sair", "exit", "quit"):
        return False
    if cmd == "ajuda":
        print(HELP)
    elif cmd == "ouvir":
        print("jarvis> ouvindo... (fale agora)")
        trace = app.listen_once()
        print(f"jarvis> [voz] {trace.result}")
    elif cmd == "voz":
        trace = app.handle_voice_transcript(arg)
        print(f"jarvis> [voz raw={trace.raw!r} wake={trace.wake_detected} "
              f"intent={trace.intent}] {trace.result}")
    elif cmd == "mics":
        devices = app.list_microphones()
        if devices:
            for dev in devices:
                print(f"  {dev}")
        else:
            print(f"  {app.mic.status_detail or 'Nenhum microfone.'}")
    elif cmd == "vozes":
        voices = app.list_voices()
        if voices:
            for v in voices:
                print(f"  {v.name} ({v.id})")
        else:
            print("  Nenhuma voz de TTS disponível.")
    elif cmd == "estado":
        print(f"  estado: {app.states.state}")
    else:
        print(f"  comando desconhecido: {line} (use :ajuda)")
    return True


def _should_open_hub(args) -> bool:
    """HUB é o padrão quando há Qt + (display ou Windows/frozen).

    Nunca abre HUB para comandos utilitários/não interativos.
    """
    if args.exec is not None or args.test_voice is not None:
        return False
    if args.list_mics or args.list_voices:
        return False
    try:
        from jarvis.ui.hub.qt_compat import HAS_QT
        if not HAS_QT:
            return False
    except Exception:
        return False
    import os
    import sys
    if getattr(sys, "frozen", False):
        return True
    if os.environ.get("QT_QPA_PLATFORM"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
                or sys.platform.startswith("win"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis", description="J.A.R.V.I.S. local")
    parser.add_argument("--gui", action="store_true", help="abre interface gráfica mínima")
    parser.add_argument("--hub", action="store_true",
                        help="abre o HUB gráfico (PySide6)")
    parser.add_argument("--cli", action="store_true",
                        help="força o console texto (padrão quando sem Qt/display)")
    parser.add_argument("--no-intro", action="store_true",
                        help="pula a intro cinematográfica")
    parser.add_argument("--fullscreen", action="store_true",
                        help="abre o HUB em tela cheia (não persiste)")
    parser.add_argument("--minimized", action="store_true",
                        help="abre o HUB minimizado (não persiste)")
    parser.add_argument("--dry-run", action="store_true",
                        help="simula ações sem executar (seguro p/ testes)")
    parser.add_argument("--data-dir", default=None, help="diretório de dados local")
    parser.add_argument("--test-voice", default=None, metavar="TEXTO",
                        help="simula uma transcrição de voz e sai")
    parser.add_argument("--exec", default=None, metavar="TEXTO",
                        help="executa um comando de texto e sai")
    parser.add_argument("--list-mics", action="store_true")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.hub or (not args.cli and _should_open_hub(args)):
        from jarvis.ui.hub.app_qt import run_hub
        return run_hub(data_dir=args.data_dir, dry_run=args.dry_run,
                       no_intro=args.no_intro,
                       fullscreen=args.fullscreen,
                       minimized=args.minimized)

    if args.gui:
        from jarvis.ui.gui_min import run_gui
        app = JarvisApp(data_dir=args.data_dir, dry_run=args.dry_run)
        app.start()
        try:
            return run_gui(app)
        finally:
            app.shutdown()

    app = JarvisApp(data_dir=args.data_dir, dry_run=args.dry_run)
    app.start()
    try:
        if args.list_mics:
            for dev in app.list_microphones():
                print(f"{dev.index}\t{dev.name}")
            return 0
        if args.list_voices:
            for v in app.list_voices():
                print(f"{v.id}\t{v.name}")
            return 0
        if args.test_voice is not None:
            trace = app.handle_voice_transcript(args.test_voice)
            print(f"RAW: {trace.raw}")
            print(f"WAKE: {trace.wake_detected} CMD: {trace.command_after_wake!r}")
            print(f"INTENT: {trace.intent} ACTION: {trace.action}")
            print(f"RESULT: {trace.result}")
            return 0 if trace.engine_result and trace.engine_result.success else 1
        if args.exec is not None:
            result = app.handle_text(args.exec)
            print(result.message)
            return 0 if result.success else 1
        return run_repl(app)
    finally:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())
