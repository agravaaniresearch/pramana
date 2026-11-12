import copy

import pytest

from pramana.ledger import Ledger
from pramana.model import ClockRegression, InvalidDiff
from pramana.synth import build_ledger


def mk(i, op="insert", cid="1.1", inst="I", text="x"):
    d = {"diff_id": f"D{i}", "instrument_id": inst, "op": op, "clause_id": cid, "authority": "a", "source_ref": "r"}
    if op != "repeal":
        d["clause"] = {"text": text, "scope": {}}
    return d


def test_chain_is_intact(ledger):
    assert ledger.verify().ok
    assert len(ledger) == 15


def test_publication_time_is_assigned_by_ledger_and_utc(ledger):
    assert all(e["published_at"].endswith("Z") for e in ledger.entries)


def test_clock_cannot_go_backwards():
    led = Ledger()
    led.append(mk(1), "2024-01-02T00:00:00Z")
    with pytest.raises(ClockRegression):
        led.append(mk(2, cid="1.2"), "2024-01-01T23:59:59Z")


def test_equal_time_is_allowed():
    led = Ledger()
    led.append(mk(1), "2024-01-02T00:00:00Z")
    led.append(mk(2, cid="1.2"), "2024-01-02T00:00:00Z")
    assert led.verify().ok


def test_references_are_checked():
    led = Ledger()
    with pytest.raises(InvalidDiff):
        led.append(mk(1, op="replace"), "2024-01-01T00:00:00Z")
    led.append(mk(1), "2024-01-01T00:00:00Z")
    with pytest.raises(InvalidDiff):
        led.append(mk(2), "2024-01-02T00:00:00Z")  # insert of existing clause
    led.append(mk(3, op="repeal"), "2024-01-03T00:00:00Z")
    with pytest.raises(InvalidDiff):
        led.append(mk(4, op="repeal"), "2024-01-04T00:00:00Z")


def test_duplicate_diff_id_rejected():
    led = Ledger()
    led.append(mk(1), "2024-01-01T00:00:00Z")
    with pytest.raises(InvalidDiff):
        led.append(mk(1, cid="2.2"), "2024-01-02T00:00:00Z")


def test_naive_timestamp_rejected():
    led = Ledger()
    with pytest.raises(ValueError):
        led.append(mk(1), "2024-01-01T00:00:00")


def test_edit_is_detected(ledger):
    es = copy.deepcopy(ledger.entries)
    es[4]["diff"]["clause"]["text"] = "changed quietly"
    res = Ledger(es).verify()
    assert not res.ok and res.failures[0]["seq"] == 4


def test_truncation_needs_an_anchor(ledger):
    anchor = ledger.anchor()
    short = Ledger(copy.deepcopy(ledger.entries[:-2]))
    assert short.verify().ok  # honest limit: the chain alone cannot see a cut tail
    assert not short.verify(anchor).ok


def test_save_load_roundtrip(tmp_path, ledger):
    p = tmp_path / "l.jsonl"
    ledger.save(p)
    assert Ledger.load(p).head_hash == ledger.head_hash


def test_publish_appends_under_lock_and_uses_clock(tmp_path):
    from pramana.ledger import publish
    p = tmp_path / "l.jsonl"
    e0 = publish(p, mk(1))
    e1 = publish(p, mk(2, cid="1.2"))
    assert e1["prev_hash"] == e0["hash"] and e0["published_at"] <= e1["published_at"]
    assert Ledger.load(p).verify().ok and len(Ledger.load(p)) == 2


def test_publish_refuses_a_broken_ledger(tmp_path):
    from pramana.ledger import publish
    from pramana.model import LedgerError
    p = tmp_path / "l.jsonl"
    publish(p, mk(1))
    p.write_text(p.read_text().replace('"text": "x"', '"text": "y"'))
    with pytest.raises(LedgerError):
        publish(p, mk(2, cid="1.2"))


def test_callers_cannot_supply_a_publication_time():
    led = Ledger()
    d = mk(1)
    d["published_at"] = "2020-01-01T00:00:00Z"
    with pytest.raises(InvalidDiff):
        led.append(d, "2024-01-01T00:00:00Z")
