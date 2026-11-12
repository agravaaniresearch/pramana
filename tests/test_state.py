from pramana.state import compare_states, consolidate, exposure

FIL = "SYN-FIL-02"
T_4PM = "2024-12-12T16:00:00+05:30"
T_501 = "2024-12-12T17:01:00+05:30"
NOW = "2025-06-01T00:00:00+05:30"


def test_four_pm_and_five_pm_example(items):
    before = consolidate(items, FIL, T_4PM, "tora", known_at=NOW)
    after = consolidate(items, FIL, T_501, "tora", known_at=NOW)
    assert "60 days" in before["1.1"]["text"]
    assert "45 days" in after["1.1"]["text"]


def test_backdating_is_clipped_to_publication(items):
    st = consolidate(items, FIL, T_501, "tora", known_at=NOW)
    assert st["1.1"]["operative_from"] == "2024-12-12T11:30:00Z"
    assert st["1.1"]["retro_clipped"] is True


def test_legacy_applies_backdated_text_to_an_earlier_act(items):
    st = consolidate(items, FIL, T_4PM, "legacy", known_at=NOW)
    assert "45 days" in st["1.1"]["text"]


def test_unpublished_circular_does_not_exist_under_tora(items):
    st = consolidate(items, "SYN-IMP-01", "2025-02-01T00:00:00+05:30", "tora", known_at=NOW)
    assert "30 days" in st["1.2"]["text"]
    legacy = consolidate(items, "SYN-IMP-01", "2025-02-01T00:00:00+05:30", "legacy", known_at=NOW)
    assert "90 days" in legacy["1.2"]["text"] and legacy["1.2"]["shadow"]


def test_shadow_is_not_visible_before_it_surfaced(items):
    st = consolidate(items, "SYN-IMP-01", "2025-02-01T00:00:00+05:30", "legacy", known_at="2025-01-01T00:00:00+05:30")
    assert "30 days" in st["1.2"]["text"]


def test_prospective_effective_date_is_honoured(items):
    june = consolidate(items, "SYN-IMP-01", "2024-06-15T00:00:00+05:30", "tora", known_at=NOW)
    july = consolidate(items, "SYN-IMP-01", "2024-07-02T00:00:00+05:30", "tora", known_at=NOW)
    assert "45 days" in june["1.2"]["text"] and "30 days" in july["1.2"]["text"]


def test_repeal_removes_clause(items):
    sta_before = consolidate(items, "SYN-STA-03", "2024-12-13T09:00:00+05:30", "tora", known_at=NOW)
    sta_after = consolidate(items, "SYN-STA-03", "2024-12-13T11:00:00+05:30", "tora", known_at=NOW)
    assert "1.2" in sta_before and "1.2" not in sta_after


def test_before_anything_is_published_there_is_no_law(items):
    assert consolidate(items, FIL, "2023-01-01T00:00:00Z", "tora") == {}


def test_exposure_shows_legacy_drift_but_none_under_pramana(items):
    ex = exposure(items, FIL, T_4PM, NOW)
    assert {d["clause_id"] for d in ex["legacy_delta"]} == {"1.1", "1.5"}
    assert ex["tora_delta"] == []
    assert {c["kind"] for c in ex["causes"]} == {"backdated amendment", "unpublished circular"}


def test_compare_states_symmetry(items):
    a = consolidate(items, FIL, T_4PM, "tora")
    b = consolidate(items, FIL, T_501, "tora")
    d = compare_states(a, b)
    assert [x["clause_id"] for x in d] == ["1.1"]


def test_unknown_regime_rejected(items):
    import pytest
    with pytest.raises(ValueError):
        consolidate(items, FIL, T_4PM, "other")
