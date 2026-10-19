"""Roteiro da intro: fases, duração, cues de SFX (sem Qt)."""

from jarvis.ui.hub import intro_script
from jarvis.ui.hub.intro_script import (INTRO_DURATION_MS, PHASES, SFX_CUES,
                                        due_cues, frame_at,
                                        progress_for_elapsed)


def test_duration_within_spec():
    assert 3000 <= INTRO_DURATION_MS <= 7000


def test_phases_ordered_and_overlapping():
    assert [p.id for p in PHASES] == ["signal", "lines", "rings", "core",
                                      "gauges", "title"]
    for ph in PHASES:
        assert 0.0 <= ph.start < ph.end <= 1.0
    # sobreposição: experiência contínua, não telas sequenciais
    for a, b in zip(PHASES, PHASES[1:]):
        assert a.end > b.start, (a.id, b.id)


def test_frame_monotonic_and_bounded():
    prev = None
    steps = [i / 20 for i in range(21)]
    for p in steps:
        frame = frame_at(p)
        for field in ("signal", "lines", "rings", "core", "gauges", "title"):
            value = getattr(frame, field)
            assert 0.0 <= value <= 1.0, (p, field, value)
        if prev is not None:
            for field in ("lines", "rings", "core", "gauges", "title"):
                assert getattr(frame, field) >= getattr(prev, field) - 1e-9
        prev = frame


def test_frame_start_and_end():
    start = frame_at(0.0)
    assert start.ready is False and start.status_text == ""
    end = frame_at(1.0)
    assert end.ready is True
    assert end.status_text == "SYSTEM READY"
    assert end.title == 1.0 and end.core == 1.0


def test_status_transitions():
    assert frame_at(0.5).status_text == ""
    assert frame_at(0.85).status_text == "SYSTEM INITIALIZING"
    assert frame_at(0.95).status_text == "SYSTEM READY"


def test_sfx_cues_ordered_and_known():
    from jarvis.ui.hub.sfx import SOUNDS
    ats = [at for at, _ in SFX_CUES]
    assert ats == sorted(ats)
    assert all(0.0 <= at <= 1.0 for at in ats)
    for _, name in SFX_CUES:
        assert name in SOUNDS, name


def test_due_cues_crossing():
    assert due_cues(0.0, 0.05) == ["boot"]
    assert due_cues(0.05, 0.05) == []
    assert "ready" in due_cues(0.5, 1.0)
    full = due_cues(-0.1, 1.0)
    assert len(full) == len(SFX_CUES)


def test_progress_for_elapsed():
    assert progress_for_elapsed(0) == 0.0
    assert progress_for_elapsed(INTRO_DURATION_MS) == 1.0
    assert progress_for_elapsed(INTRO_DURATION_MS * 10) == 1.0
    assert progress_for_elapsed(-5) == 0.0
