"""Adversarial test bed and failure-rate measurement.

Every number the README quotes about robustness comes from this module. Each trial is
seeded, so a published rate can be reproduced exactly.
"""
from __future__ import annotations

import copy
import math
import random
from datetime import timedelta

from .ledger import Ledger
from .model import ClockRegression, InvalidDiff, entry_hash, fmt_ts, parse_ts
from .state import consolidate, items_from
from .synth import random_ledger


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def _rehash_from(entries: list, start: int) -> None:
    prev = entries[start - 1]["hash"] if start > 0 else "0" * 64
    for i in range(start, len(entries)):
        e = entries[i]
        e["seq"] = i
        e["prev_hash"] = prev
        e["hash"] = entry_hash(i, prev, e["published_at"], e["diff"])
        prev = e["hash"]


def _edit_text(entries, rng):
    cands = [i for i, e in enumerate(entries) if e["diff"].get("clause")]
    i = rng.choice(cands)
    entries[i]["diff"]["clause"]["text"] += " (edited)"
    return i


def tamper(entries: list, kind: str, rng: random.Random) -> list:
    es = copy.deepcopy(entries)
    n = len(es)
    if kind == "edit_text":
        _edit_text(es, rng)
    elif kind == "edit_published_at":
        i = rng.randrange(n)
        es[i]["published_at"] = fmt_ts(parse_ts(es[i]["published_at"]) + timedelta(hours=rng.randint(1, 48)))
    elif kind == "delete_middle":
        del es[rng.randint(1, n - 2)]
    elif kind == "swap_adjacent":
        i = rng.randint(0, n - 2)
        es[i], es[i + 1] = es[i + 1], es[i]
    elif kind == "forge_insert":
        i = rng.randint(1, n - 1)
        forged = copy.deepcopy(es[i])
        forged["diff"]["diff_id"] = "FORGED"
        es.insert(i, forged)
    elif kind == "rewrite_chain":
        i = _edit_text(es, rng)
        _rehash_from(es, i)
    elif kind == "truncate_tail":
        del es[-rng.randint(1, min(3, n - 1)):]
    elif kind == "backdated_append_rehashed":
        last = es[-1]
        forged_diff = copy.deepcopy(last["diff"])
        forged_diff["diff_id"] = "FORGED-LATE"
        when = fmt_ts(parse_ts(last["published_at"]) - timedelta(days=30))
        forged = {"seq": n, "prev_hash": last["hash"], "published_at": when, "diff": forged_diff}
        forged["hash"] = entry_hash(n, last["hash"], when, forged_diff)
        es.append(forged)
    else:
        raise ValueError(kind)
    return es


TAMPER_KINDS = [
    "edit_text", "edit_published_at", "delete_middle", "swap_adjacent", "forge_insert",
    "rewrite_chain", "truncate_tail", "backdated_append_rehashed",
]


def tamper_detection(trials: int = 1000, seed: int = 7) -> list[dict]:
    rows = []
    for kind in TAMPER_KINDS:
        det_plain = det_anchor = 0
        for t in range(trials):
            rng = random.Random(f"{seed}-{kind}-{t}")
            led = random_ledger(rng, rng.randint(10, 40))
            anchor = led.anchor()
            bad = Ledger(tamper(led.entries, kind, rng))
            if not bad.verify().ok:
                det_plain += 1
            if not bad.verify(anchor).ok:
                det_anchor += 1
        lo_p, hi_p = wilson(det_plain, trials)
        lo_a, hi_a = wilson(det_anchor, trials)
        rows.append({
            "attack": kind, "trials": trials,
            "detected_without_anchor": det_plain, "rate_without_anchor": det_plain / trials,
            "ci_without_anchor": [lo_p, hi_p],
            "detected_with_anchor": det_anchor, "rate_with_anchor": det_anchor / trials,
            "ci_with_anchor": [lo_a, hi_a],
        })
    return rows


def clock_regression(trials: int = 1000, seed: int = 11) -> dict:
    rejected = 0
    for t in range(trials):
        rng = random.Random(f"{seed}-clock-{t}")
        led = random_ledger(rng, rng.randint(3, 20))
        head = parse_ts(led.entries[-1]["published_at"])
        when = head - timedelta(seconds=rng.randint(1, 10**7))
        diff = {"diff_id": f"X-{t}", "instrument_id": "R-00", "op": "insert", "clause_id": f"9.{t}",
                "authority": "a", "source_ref": "r", "clause": {"text": "x", "scope": {}}}
        try:
            led.append(diff, fmt_ts(when))
        except ClockRegression:
            rejected += 1
        except InvalidDiff:
            pass
    lo, hi = wilson(rejected, trials)
    return {"trials": trials, "rejected": rejected, "rate": rejected / trials, "ci": [lo, hi]}


def stability_invariant(ledgers: int = 300, probes: int = 12, retro_share: float = 0.2, seed: int = 3) -> dict:
    """For a fixed act time T, does the law judged at T ever change as later amendments arrive?

    tora must never change. legacy changes whenever a backdated amendment is published later.
    """
    probes_total = tora_viol = legacy_viol = 0
    for k in range(ledgers):
        rng = random.Random(f"{seed}-stab-{retro_share}-{k}")
        led = random_ledger(rng, rng.randint(10, 40), retro_share=retro_share)
        items = items_from(led)
        times = [parse_ts(e["published_at"]) for e in led.entries]
        lo, hi = times[0], times[-1]
        span = int((hi - lo).total_seconds())
        for _ in range(probes):
            act = lo + timedelta(seconds=rng.randint(0, span))
            hind = act + timedelta(seconds=rng.randint(0, max(1, int((hi - act).total_seconds()))))
            for inst in sorted({e["diff"]["instrument_id"] for e in led.entries}):
                probes_total += 1
                a = consolidate(items, inst, act, "tora", known_at=act)
                b = consolidate(items, inst, act, "tora", known_at=hind)
                tora_viol += strip(a) != strip(b)
                c = consolidate(items, inst, act, "legacy", known_at=act)
                d = consolidate(items, inst, act, "legacy", known_at=hind)
                legacy_viol += strip(c) != strip(d)
    return {
        "retro_share": retro_share, "probes": probes_total,
        "tora_changed_after_the_fact": tora_viol, "tora_rate": tora_viol / probes_total,
        "legacy_changed_after_the_fact": legacy_viol, "legacy_rate": legacy_viol / probes_total,
        "legacy_ci": list(wilson(legacy_viol, probes_total)),
    }


def strip(state: dict) -> dict:
    return {k: (v["text"], v["value"], v["diff_id"]) for k, v in state.items()}


def run_all(trials: int = 1000) -> dict:
    return {
        "tamper_detection": tamper_detection(trials),
        "clock_regression": clock_regression(trials),
        "stability": [stability_invariant(retro_share=r) for r in (0.0, 0.05, 0.10, 0.25)],
    }
