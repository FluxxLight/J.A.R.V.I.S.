"""Matching determinístico: exato, contenção e tokens."""

from jarvis.command_engine.matcher import MIN_CONFIDENCE, score_pattern


def test_exact():
    r = score_pattern("abra o navegador", "abra o navegador")
    assert r.score == 1.0 and r.method == "exact"


def test_contains_scores_high():
    r = score_pattern("abra o navegador", "por favor abra o navegador agora")
    assert r.method == "contains"
    assert r.score >= MIN_CONFIDENCE


def test_tokens_partial():
    r = score_pattern("abra a calculadora", "abre calculadora")
    assert r.score >= MIN_CONFIDENCE, r


def test_unrelated_scores_low():
    r = score_pattern("abra o navegador", "que horas sao")
    assert r.score < MIN_CONFIDENCE, r


def test_empty():
    assert score_pattern("", "algo").score == 0.0
    assert score_pattern("algo", "").score == 0.0


def test_deterministic():
    a = score_pattern("feche o jarvis", "fecha o jarvis por favor")
    b = score_pattern("feche o jarvis", "fecha o jarvis por favor")
    assert a == b
