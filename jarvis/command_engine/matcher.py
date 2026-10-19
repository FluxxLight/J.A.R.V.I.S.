"""Matching determinístico (sem LLM): score 0.0–1.0 entre padrões e entrada.

Estratégia em camadas:
1. igualdade exata            -> 1.0
2. contenção (padrão ⊂ texto) -> 0.9 (com penalidade por tamanho extra)
3. token-set (Jaccard + cobertura + ordem + fuzzy por token)
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

EXACT_SCORE = 1.0
CONTAINS_BASE = 0.90
MIN_CONFIDENCE = 0.55   # abaixo disso = "não entendi"
FUZZY_TOKEN_THRESHOLD = 0.82


def _token_fuzzy(a: str, b: str) -> float:
    """Similaridade com limiar sensível ao tamanho (evita falsos positivos)."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if abs(la - lb) > 3 or min(la, lb) < 2:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    shortest = min(la, lb)
    if shortest >= 6:
        return ratio if ratio >= FUZZY_TOKEN_THRESHOLD else 0.0
    if shortest >= 4:
        # palavras curtas: exige mesma inicial ("abra"~"abre" ok, "abra"~"obra" não)
        return ratio if (ratio >= 0.75 and a[0] == b[0]) else 0.0
    return ratio if ratio >= 0.90 else 0.0


def _content_tokens(tokens: list[str]) -> list[str]:
    """Remove tokens de 1 letra (artigos/preposições) da comparação por tokens."""
    return [t for t in tokens if len(t) > 1]


@dataclass(frozen=True)
class MatchResult:
    score: float
    method: str  # "exact" | "contains" | "tokens" | "none"


def score_pattern(pattern_normalized: str, input_normalized: str) -> MatchResult:
    pattern = (pattern_normalized or "").strip()
    text = (input_normalized or "").strip()
    if not pattern or not text:
        return MatchResult(0.0, "none")

    # 1) exata
    if pattern == text:
        return MatchResult(EXACT_SCORE, "exact")

    # 2) contenção
    if pattern in text:
        extra = len(text) - len(pattern)
        penalty = min(0.25, extra / max(len(text), 1) * 0.5)
        return MatchResult(round(CONTAINS_BASE - penalty, 4), "contains")

    # 3) tokens
    p_tokens = _content_tokens(pattern.split())
    t_tokens = _content_tokens(text.split())
    if not p_tokens or not t_tokens:
        return MatchResult(0.0, "none")

    p_set, t_set = set(p_tokens), set(t_tokens)
    common = p_set & t_set
    jaccard = len(common) / len(p_set | t_set)
    coverage = len(common) / len(p_set)

    # ordem: fração de tokens do padrão que aparecem em ordem no texto
    order_hits = 0
    ti = 0
    for pt in p_tokens:
        found = False
        while ti < len(t_tokens):
            if t_tokens[ti] == pt:
                found = True
                ti += 1
                break
            ti += 1
        if found:
            order_hits += 1
        else:
            ti = 0  # continua procurando do início p/ próximos tokens
    order = order_hits / len(p_tokens)

    # fuzzy por token (tolerância a pequenos erros de digitação/transcrição;
    # _token_fuzzy já aplica os limiares e devolve 0.0 quando inaceitável)
    fuzzy_sum = 0.0
    for pt in p_tokens:
        if pt in t_set:
            fuzzy_sum += 1.0
        else:
            fuzzy_sum += max((_token_fuzzy(pt, tt) for tt in t_tokens), default=0.0)
    fuzzy = fuzzy_sum / len(p_tokens)

    # tokens extras no texto penalizam levemente
    extra_ratio = max(0, len(t_tokens) - len(p_tokens)) / max(len(t_tokens), 1)
    score = (0.38 * coverage + 0.22 * jaccard + 0.15 * order + 0.25 * fuzzy)
    score *= (1.0 - 0.30 * extra_ratio)
    return MatchResult(round(min(0.95, score), 4), "tokens")


def is_confident(result: MatchResult) -> bool:
    return result.score >= MIN_CONFIDENCE
