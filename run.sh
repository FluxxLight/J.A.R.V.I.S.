#!/usr/bin/env bash
# J.A.R.V.I.S. — execução (Linux/macOS; alvo principal é Windows)
cd "$(dirname "$0")" || exit 1
exec python3 main.py "$@"
