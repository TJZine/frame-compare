from __future__ import annotations

from dataclasses import replace

import pytest

from frame_compare.vsview.alignment_selection import OpeningHint, SelectedCohort


def test_any_anchor_a_b_before_reference_and_fixed_prediction_basis():
    state = SelectedCohort.empty((20000, 20000, 20000)).set_anchor(1, 96)
    hints = (OpeningHint(0), OpeningHint(504), OpeningHint(-12))
    assert [state.predict(i, hints).frame for i in range(3)] == [600, 96, 612]
    state = state.select(2, 611)
    assert state.selected == (None, 96, 611)
    assert state.predict(2, hints).frame == 612
    state = state.select(2, 612).set_anchor(2, 612)
    assert state.selected == (None, 96, 612)
    assert state.predict(1, hints).frame == 96


def test_new_moment_clears_pins_same_selection_reanchor_preserves_and_clear_is_local():
    state = SelectedCohort.empty((1000, 1000, 1000)).set_anchor(1, 0).select(2, 0)
    assert not state.needs_new_moment(2, 0)
    assert state.set_anchor(2, 0).selected == (None, 0, 0)
    assert state.clear(2).selected == (None, 0, None)
    assert state.clear(1).selected == (None, None, None)
    assert state.set_anchor(2, 1).selected == (None, None, 1)
    assert state.reset().anchor is None


def test_prediction_zero_missing_weakest_edge_and_intermediate_reference_bounds():
    state = SelectedCohort.empty((5, 1000, 1000)).set_anchor(1, 96)
    hints = (OpeningHint(0), OpeningHint(504), OpeningHint(-12, True))
    assert state.predict(0, hints).frame is None
    assert state.predict(2, hints).frame == 612  # REF600 out of physical range is irrelevant.
    assert "Provisional" in state.predict(2, hints).description
    assert state.predict(2, (OpeningHint(0), OpeningHint(None), OpeningHint(0))).frame is None
    assert state.predict(2, (OpeningHint(0), OpeningHint(0), OpeningHint(0))).frame == 96
    assert state.predict(1, (OpeningHint(0), OpeningHint(None), OpeningHint(None))).frame == 96


@pytest.mark.parametrize("number", [-1, 5, True])
def test_numeric_bounds_at_state_owner(number):
    with pytest.raises(ValueError):
        SelectedCohort.empty((5, 5)).set_anchor(0, number)


def test_sign_negative_control():
    state = SelectedCohort.empty((20000,) * 3).set_anchor(1, 96)
    hints = (OpeningHint(0), OpeningHint(504), OpeningHint(-12))
    assert state.predict(2, hints).frame == 612
    reversed_hints = tuple(replace(h, offset=-h.offset) for h in hints if h.offset is not None)
    assert state.predict(2, reversed_hints).frame != 612
