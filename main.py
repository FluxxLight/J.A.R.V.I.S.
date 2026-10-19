"""J.A.R.V.I.S. — entry point.

Uso:
    python main.py                 # HUB (quando Qt+display) ou console
    python main.py --hub           # força o HUB gráfico
    python main.py --cli           # força o console texto
    python main.py --gui           # janela mínima tkinter (fallback)
    python main.py --no-intro      # HUB sem intro
    python main.py --fullscreen    # HUB em tela cheia (não persiste)
    python main.py --minimized     # HUB minimizado (não persiste)
    python main.py --exec "que horas são?"
    python main.py --test-voice "jarvis, abra o navegador"
    python main.py --list-mics
    python main.py --list-voices
"""

import sys

from jarvis.ui.cli import main

if __name__ == "__main__":
    sys.exit(main())
