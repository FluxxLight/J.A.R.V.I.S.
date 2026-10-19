"""Utilitários de texto (normalização auxiliar, sem dependências)."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def strip_accents(text: str) -> str:
    """Remove acentos: 'calculadora' permanece, 'lâmpada' -> 'lampada'."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def collapse_spaces(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def remove_punctuation(text: str, keep: str = "") -> str:
    """Remove pontuação. `keep` preserva caracteres extras (ex.: URLs)."""
    if keep:
        pattern = re.compile(r"[^\w\s" + re.escape(keep) + r"]+", re.UNICODE)
        return pattern.sub(" ", text)
    return _PUNCT_RE.sub(" ", text)


def safe_lower(text: str) -> str:
    return text.casefold()
