"""J.A.R.V.I.S. — entry point.

Uso:
    python main.py                 # console interativo
    python main.py --gui           # janela mínima (até o HUB chegar)
    python main.py --exec "que horas são?"
    python main.py --test-voice "jarvis, abra o navegador"
    python main.py --list-mics
    python main.py --list-voices
"""

import sys

from jarvis.ui.cli import main

if __name__ == "__main__":
    sys.exit(main())
