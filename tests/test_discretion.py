from pramana import discretion as dz
from pramana.discretion import evaluate, scopes_overlap, state_clauses
from pramana.state import consolidate


def clauses(items, corpus_instruments=("SYN-FIL-02", "SYN-IMP-01", "SYN-STA-03")):
    states = {i: consolidate(items, i, "2025-04-01T00:00:00+05:30", "tora") for i in corpus_instruments}
    return state_clauses(states)


def test_startup_tech_is_left_to_the_official(items):
    fact = {"entity_type": "startup", "sector": "tech", "turnover_band": "M", "state": "S5", "age_band": "new"}
    r = evaluate(clauses(items), fact, "annual_return_due")
    assert r["discretion_resolved"] and set(r["deciding"]) == {"SYN-FIL-02:1.4", "SYN-STA-03:1.3"}


def test_specific_clause_settles_when_not_tied(items):
    fact = {"entity_type": "company", "sector": "tech", "turnover_band": "M", "state": "S3", "age_band": "old"}
    r = evaluate(clauses(items), fact, "annual_return_due")
    assert r["discretion_raw"] and not r["discretion_resolved"]


def test_no_applicable_clause():
    assert evaluate([], {"a": "b"}, "s")["applicable"] == 0


def test_overlap_logic():
    assert scopes_overlap({"a": ["1", "2"]}, {"a": ["2"], "b": ["x"]})
    assert not scopes_overlap({"a": ["1"]}, {"a": ["2"]})
    assert scopes_overlap({"a": ["1"]}, {"b": ["2"]})


def test_gate_leaves_no_unresolved_ties():
    rows = dz.sweep_gated([30], seeds=8, facts=200)
    assert rows[0]["resolved_mean"] == 0.0


def test_ungated_density_creates_ties():
    rows = dz.sweep([0, 30], seeds=8, facts=200)
    assert rows[0]["resolved_mean"] == 0.0 and rows[1]["resolved_mean"] > 0.1


def test_sweep_is_reproducible():
    assert dz.sweep([8], seeds=4, facts=100) == dz.sweep([8], seeds=4, facts=100)
