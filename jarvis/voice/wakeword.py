"""Wake word 'J.A.R.V.I.S.' — detecção e separação do comando restante.

REGRA CRÍTICA: nunca descartar o comando após a wake word.
"J.A.R.V.I.S., abra o navegador." -> (True, "abra o navegador.")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

# "jarvis", "j.a.r.v.i.s", "j a r v i s", "jarvis," ... (com ou sem pontos/espaços)
_JARVIS_CORE = r"j\s*\.?\s*a\s*\.?\s*r\s*\.?\s*v\s*\.?\s*i\s*\.?\s*s"
_LEADING_WAKE_RE = re.compile(
    rf"^\s*{_JARVIS_CORE}\s*[.,;:!?\-]*\s*", re.IGNORECASE)
_ANY_WAKE_RE = re.compile(_JARVIS_CORE, re.IGNORECASE)


@dataclass(frozen=True)
class WakeResult:
    detected: bool
    command_text: str   # comando restante (ou texto original se sem wake)
    wake_word: str = ""  # trecho da wake word encontrado


def _build_leading_pattern(extra_words: List[str]) -> "re.Pattern[str]":
    words = [_JARVIS_CORE]
    for word in extra_words or []:
        w = (word or "").strip()
        if w and w.lower() != "jarvis":
            words.append(re.escape(w))
    return re.compile(
        r"^\s*(?:" + "|".join(words) + r")\s*[.,;:!?\-]*\s*", re.IGNORECASE)


def detect(text: str | None, extra_wake_words: List[str] | None = None) -> WakeResult:
    """Detecta wake word no INÍCIO e devolve o comando restante intacto."""
    if not text or not str(text).strip():
        return WakeResult(False, "")
    original = str(text)
    pattern = _build_leading_pattern(extra_wake_words or [])
    match = pattern.match(original)
    if match:
        wake = original[match.start():match.end()].strip(" .,;:!?-\t")
        rest = original[match.end():].strip()
        return WakeResult(True, rest, wake)
    # wake word no meio da frase ("por favor jarvis abra...")? aceita,
    # mas preserva o texto ANTERIOR também (nunca descarta nada).
    anywhere = _ANY_WAKE_RE.search(original)
    if anywhere:
        # remove apenas a ocorrência da wake word, mantém o resto
        rest = (_ANY_WAKE_RE.sub(" ", original, count=1)).strip(" .,;:!?\t")
        rest = re.sub(r"\s+", " ", rest).strip()
        return WakeResult(True, rest, anywhere.group(0))
    return WakeResult(False, original.strip())


def strip_wake_word(text: str | None) -> str:
    """Conveniência: devolve só o comando restante."""
    return detect(text).command_text
