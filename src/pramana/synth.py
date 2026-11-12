"""Synthetic corpus: invented instruments, invented authorities, invented dates.

Everything here is fictional and exists only to exercise the engine. Nothing is a
real regulation, a real department or a real company.
"""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from .ledger import Ledger
from .model import fmt_ts, parse_ts

IST = "+05:30"

INSTRUMENTS = [
    {"instrument_id": "SYN-FIL-02", "title": "Annual Filing Regulations (synthetic)", "authority": "Synthetic Department of Filings"},
    {"instrument_id": "SYN-IMP-01", "title": "Import Licence Rules (synthetic)", "authority": "Synthetic Directorate of Trade"},
    {"instrument_id": "SYN-STA-03", "title": "Startup Compliance Order (synthetic)", "authority": "Synthetic Office of Enterprise"},
]


def _clause(text, subject=None, value=None, scope=None):
    c = {"text": text}
    if subject:
        c["subject"] = subject
    if value:
        c["value"] = value
    c["scope"] = scope or {}
    return c


def _diff(diff_id, inst, op, cid, authority, ref, clause=None, eff=None, note=None):
    d = {"diff_id": diff_id, "instrument_id": inst, "op": op, "clause_id": cid, "authority": authority, "source_ref": ref}
    if clause is not None:
        d["clause"] = clause
    if eff:
        d["effective_from"] = eff
    if note:
        d["note"] = note
    return d


FIL, IMP, STA = "Synthetic Department of Filings", "Synthetic Directorate of Trade", "Synthetic Office of Enterprise"

# (publication time, diff). The publication time is the ledger clock at the moment of appending.
TIMELINE = [
    (f"2023-04-01T10:00:00{IST}", _diff("D-001", "SYN-FIL-02", "insert", "1.1", FIL, "Reg 1/2023",
        _clause("Every company shall file its annual return within 60 days of the close of the financial year.", "annual_return_due", "60d"))),
    (f"2023-04-01T10:05:00{IST}", _diff("D-002", "SYN-FIL-02", "insert", "1.2", FIL, "Reg 1/2023",
        _clause("A company in turnover band S shall file within 90 days.", "annual_return_due", "90d", {"turnover_band": ["S"]}))),
    (f"2023-04-01T10:10:00{IST}", _diff("D-003", "SYN-FIL-02", "insert", "1.3", FIL, "Reg 1/2023",
        _clause("A late return attracts a fee of 100 per day.", "late_fee", "100/day"))),
    (f"2023-04-01T11:00:00{IST}", _diff("D-004", "SYN-IMP-01", "insert", "1.1", IMP, "Rule 1/2023",
        _clause("An import licence is valid for 365 days from grant.", "licence_validity", "365d"))),
    (f"2023-04-01T11:05:00{IST}", _diff("D-005", "SYN-IMP-01", "insert", "1.2", IMP, "Rule 1/2023",
        _clause("A licence application shall be decided within 45 days.", "licence_decision_time", "45d"))),
    (f"2023-04-01T11:10:00{IST}", _diff("D-006", "SYN-IMP-01", "insert", "1.3", IMP, "Rule 1/2023",
        _clause("An applicant shall have lodged Form 7 before sunrise on the day of application.", "form7_timing", "before_sunrise"),
        note="Deliberately arbitrary. What the text says is what applies; it need not be logical.")),
    (f"2023-09-15T10:00:00{IST}", _diff("D-007", "SYN-STA-03", "insert", "1.1", STA, "Order 1/2023",
        _clause("A startup shall file its annual return within 90 days.", "annual_return_due", "90d", {"entity_type": ["startup"]}))),
    (f"2023-09-15T10:05:00{IST}", _diff("D-008", "SYN-STA-03", "insert", "1.2", STA, "Order 1/2023",
        _clause("A new startup is exempt from the late fee.", "late_fee", "exempt", {"entity_type": ["startup"], "age_band": ["new"]}))),
    (f"2024-02-28T15:00:00{IST}", _diff("D-009", "SYN-FIL-02", "replace", "1.3", FIL, "Reg 2/2024",
        _clause("A late return attracts a fee of 200 per day.", "late_fee", "200/day"), eff=f"2024-03-01T00:00:00{IST}")),
    (f"2024-06-10T12:00:00{IST}", _diff("D-010", "SYN-IMP-01", "replace", "1.2", IMP, "Rule 3/2024",
        _clause("A licence application shall be decided within 30 days.", "licence_decision_time", "30d"), eff=f"2024-07-01T00:00:00{IST}")),
    (f"2024-09-20T10:00:00{IST}", _diff("D-011", "SYN-FIL-02", "insert", "1.4", FIL, "Reg 5/2024",
        _clause("A technology company in turnover band M shall file within 75 days.", "annual_return_due", "75d",
                {"sector": ["tech"], "turnover_band": ["M"]}))),
    # The 4 pm / 5 pm case: published at 17:00 IST on 12 Dec 2024 but stated to apply from 1 Dec.
    (f"2024-12-12T17:00:00{IST}", _diff("D-012", "SYN-FIL-02", "replace", "1.1", FIL, "Circular 41/2024",
        _clause("Every company shall file its annual return within 45 days of the close of the financial year.", "annual_return_due", "45d"),
        eff=f"2024-12-01T00:00:00{IST}", note="Backdated by eleven days relative to publication.")),
    (f"2024-12-13T10:00:00{IST}", _diff("D-013", "SYN-STA-03", "repeal", "1.2", STA, "Order 4/2024",
        eff=f"2024-11-15T00:00:00{IST}", note="Repeal stated to apply from before it was published.")),
    (f"2025-02-05T10:00:00{IST}", _diff("D-014", "SYN-IMP-01", "replace", "1.1", IMP, "Rule 6/2025",
        _clause("An import licence is valid for 180 days from grant.", "licence_validity", "180d"), eff=f"2025-02-05T10:00:00{IST}")),
    (f"2025-03-18T10:00:00{IST}", _diff("D-015", "SYN-STA-03", "insert", "1.3", STA, "Order 2/2025",
        _clause("A technology startup shall file within 60 days.", "annual_return_due", "60d",
                {"entity_type": ["startup"], "sector": ["tech"]}))),
]

# Circulars that officials applied but that were never published to the source of truth.
SHADOWS = [
    {"surfaced_at": f"2025-01-20T09:00:00{IST}",
     "diff": _diff("S-001", "SYN-IMP-01", "replace", "1.2", IMP, "Office Memorandum 7/2024 (never published)",
                   _clause("A licence application shall be decided within 90 days.", "licence_decision_time", "90d"),
                   eff=f"2024-08-01T00:00:00{IST}")},
    {"surfaced_at": f"2025-03-02T09:00:00{IST}",
     "diff": _diff("S-002", "SYN-FIL-02", "insert", "1.5", FIL, "Office Memorandum 11/2024 (never published)",
                   _clause("No late fee waiver is available to a technology company.", "late_fee", "no_waiver", {"sector": ["tech"]}),
                   eff=f"2024-10-01T00:00:00{IST}")},
]

DEMO_FACTS = [
    {"label": "Asha Technologies Pvt Ltd (fictional)", "entity_type": "company", "sector": "tech",
     "turnover_band": "M", "state": "S3", "age_band": "old"},
    {"label": "Kiran Labs (fictional startup)", "entity_type": "startup", "sector": "tech",
     "turnover_band": "M", "state": "S5", "age_band": "new"},
]


def build_ledger() -> Ledger:
    led = Ledger()
    for when, diff in TIMELINE:
        led.append(copy.deepcopy(diff), when)
    return led


def build_corpus() -> dict:
    return {
        "disclaimer": "Synthetic and illustrative only. No real regulation, authority or company is represented.",
        "instruments": INSTRUMENTS,
        "shadows": SHADOWS,
        "facts": DEMO_FACTS,
    }


def write_synthetic(out_dir) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    led = build_ledger()
    lp, cp = out / "synthetic_ledger.jsonl", out / "synthetic_corpus.json"
    led.save(lp)
    cp.write_text(json.dumps(build_corpus(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return lp, cp


# ------------------------------------------------------------------ random ledgers for fuzzing
def random_ledger(rng: random.Random, n_entries: int, retro_share: float = 0.2, instruments: int = 3) -> Ledger:
    """A valid random ledger. retro_share is the fraction of amendments stated to apply earlier
    than their publication time."""
    led = Ledger()
    t = parse_ts("2023-01-01T00:00:00Z")
    existing: dict = {}
    insts = [f"R-{i:02d}" for i in range(instruments)]
    from datetime import timedelta

    for n in range(n_entries):
        t = t + timedelta(hours=rng.randint(1, 400))
        inst = rng.choice(insts)
        have = sorted(existing.setdefault(inst, set()))
        if have and rng.random() < 0.45:
            cid = rng.choice(have)
            op = "repeal" if rng.random() < 0.2 else "replace"
        else:
            cid = f"{rng.randint(1, 3)}.{rng.randint(1, 9)}"
            while cid in existing[inst]:
                cid = f"{rng.randint(1, 5)}.{rng.randint(1, 20)}"
            op = "insert"
        eff = None
        r = rng.random()
        if r < retro_share:
            eff = fmt_ts(t - timedelta(hours=rng.randint(1, 600)))
        elif r < retro_share + 0.15:
            eff = fmt_ts(t + timedelta(hours=rng.randint(1, 600)))
        clause = None if op == "repeal" else {"text": f"Clause {cid} version {n}.", "subject": "s", "value": f"v{n}", "scope": {}}
        diff = _diff(f"F-{n:04d}", inst, op, cid, "Synthetic Authority", f"Ref {n}", clause=clause, eff=eff)
        led.append(diff, fmt_ts(t))
        if op == "repeal":
            existing[inst].discard(cid)
        else:
            existing[inst].add(cid)
    return led
