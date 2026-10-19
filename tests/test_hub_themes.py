"""Design system: 5 temas, estados, feedback e QSS (sem Qt)."""

import re

import pytest

from jarvis.ui.hub.themes import (THEME_ORDER, THEMES, build_stylesheet,
                                  cycle_theme, feedback_for, get_theme,
                                  role_color, state_color, state_label)


def test_five_themes_exist():
    assert set(THEMES) == {"azul", "vermelho", "verde", "amarelo", "cinza"}
    assert tuple(THEME_ORDER) == ("azul", "vermelho", "verde", "amarelo", "cinza")


def test_theme_primaries_distinct():
    primaries = [THEMES[t].primary for t in THEME_ORDER]
    assert len(set(primaries)) == 5
    for color in primaries:
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", color), color


def test_get_theme_fallback():
    assert get_theme("azul").id == "azul"
    assert get_theme("ROXO").id == "azul"
    assert get_theme("").id == "azul"
    assert get_theme(None).id == "azul"


def test_cycle_theme_roundtrip():
    seen = set()
    current = "azul"
    for _ in range(5):
        current = cycle_theme(current)
        seen.add(current)
    assert seen == set(THEME_ORDER)
    assert cycle_theme("cinza") == "azul"


def test_all_core_states_have_labels():
    from jarvis.core.states import SystemState
    for state in SystemState:
        label = state_label(state.value)
        assert label and label != state.value or state.value == label
        color = state_color(get_theme("azul"), state.value)
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", color), (state, color)


def test_error_state_is_danger_in_every_theme():
    for tid in THEME_ORDER:
        theme = get_theme(tid)
        assert state_color(theme, "ERROR") == theme.danger


def test_feedback_reflects_real_result():
    ok = feedback_for("OPEN_BROWSER", True, True, False, "Abrindo.")
    assert (ok.status, ok.role) == ("CONCLUÍDO", "success")
    fail = feedback_for("OPEN_BROWSER", False, True, False, "Falhou.")
    assert (fail.status, fail.role) == ("ERRO", "danger")
    assert fail.title == "OPEN BROWSER"
    pending = feedback_for("SHUTDOWN_COMPUTER", False, False, True, "Certeza?")
    assert pending.status == "AGUARDANDO CONFIRMAÇÃO"
    unknown = feedback_for("UNKNOWN", False, False, False, "???")
    assert unknown.title == "NÃO RECONHECIDO"


def test_feedback_never_claims_success_on_failure():
    view = feedback_for("OPEN_APP", False, True, False, "boom")
    assert view.status != "CONCLUÍDO"
    assert view.role == "danger"


@pytest.mark.parametrize("tid", list(THEME_ORDER))
def test_stylesheet_contains_theme(tid):
    theme = get_theme(tid)
    qss = build_stylesheet(theme)
    assert theme.primary in qss
    assert theme.background_top in qss
    assert "QPushButton#primary" in qss
    assert "QLabel#stateBadge" in qss
    # sem placeholders
    assert "{" not in qss or "{theme" not in qss
    assert "None" not in qss


def test_stylesheet_deterministic():
    a = build_stylesheet(get_theme("verde"))
    b = build_stylesheet(get_theme("verde"))
    assert a == b
    assert build_stylesheet(get_theme("verde")) != build_stylesheet(get_theme("azul"))
