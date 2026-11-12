"""The test bed. Small trial counts here keep the suite fast; `pramana fuzz` runs the full 1000."""
import pytest

from pramana import fuzz


@pytest.mark.parametrize("kind", [k for k in fuzz.TAMPER_KINDS if k not in ("rewrite_chain", "truncate_tail")])
def test_chain_alone_catches(kind):
    row = next(r for r in fuzz.tamper_detection(40, seed=1) if r["attack"] == kind)
    assert row["detected_without_anchor"] == row["trials"]


@pytest.mark.parametrize("kind", ["rewrite_chain", "truncate_tail"])
def test_known_blind_spots_are_closed_only_by_anchor(kind):
    row = next(r for r in fuzz.tamper_detection(40, seed=1) if r["attack"] == kind)
    assert row["detected_without_anchor"] == 0, "documented limitation: needs an external anchor"
    assert row["detected_with_anchor"] == row["trials"]


def test_clock_regression_always_rejected():
    r = fuzz.clock_regression(150)
    assert r["rejected"] == r["trials"]


def test_stability_invariant_holds_under_pramana_and_fails_under_legacy():
    r = fuzz.stability_invariant(ledgers=40, probes=8, retro_share=0.25)
    assert r["tora_changed_after_the_fact"] == 0
    assert r["legacy_changed_after_the_fact"] > 0


def test_no_backdating_means_no_drift_even_under_legacy():
    r = fuzz.stability_invariant(ledgers=30, probes=8, retro_share=0.0)
    assert r["legacy_changed_after_the_fact"] == 0


def test_wilson_interval_sane():
    lo, hi = fuzz.wilson(1000, 1000)
    assert hi == 1.0 and 0.99 < lo < 1.0
    assert fuzz.wilson(0, 0) == (0.0, 0.0)
