"""Consolidation: fold the ledger into the law as it stood at a chosen moment.

Two regimes are modelled side by side so the difference is measurable.

legacy  Today's practice as the Transparency of Rules Act describes it. An amendment
        applies from the effective date its circular states, which may precede its
        publication; circulars never published to the source of truth can also be
        applied by officials ("shadow" items).
tora    The proposed rule. Only published amendments exist, and an amendment operates
        from the later of its publication time and its stated effective date. It can
        never reach back before the moment it was published.

Two clocks are used throughout. valid_at is the moment of the act being judged.
known_at is how much of the ledger has been published when the judgement is made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .model import REGIMES, fmt_ist, fmt_ts, parse_ts


@dataclass(frozen=True)
class Item:
    kind: str  # "ledger" or "shadow"
    order: int
    published_at: datetime | None
    surfaced_at: datetime | None
    diff: dict


def items_from(ledger, shadows: list | None = None) -> list[Item]:
    items = [
        Item("ledger", e["seq"], parse_ts(e["published_at"]), None, e["diff"]) for e in ledger.entries
    ]
    for i, s in enumerate(shadows or []):
        items.append(Item("shadow", i, None, parse_ts(s["surfaced_at"]), s["diff"]))
    return items


def operative_from(item: Item, regime: str) -> datetime:
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}")
    eff = item.diff.get("effective_from")
    if item.kind == "shadow":
        return parse_ts(eff) if eff else item.surfaced_at
    pub = item.published_at
    eff_dt = parse_ts(eff) if eff else pub
    return max(pub, eff_dt) if regime == "tora" else eff_dt


def is_retro(item: Item) -> bool:
    """True when the stated effective date precedes publication (or there was none)."""
    if item.kind == "shadow":
        return True
    eff = item.diff.get("effective_from")
    return bool(eff) and parse_ts(eff) < item.published_at


def natural_key(s: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]


def consolidate(
    items: list[Item],
    instrument_id: str,
    valid_at,
    regime: str = "tora",
    known_at=None,
    include_shadow: bool | None = None,
) -> dict:
    """Return {clause_id: clause_state} for one instrument.

    known_at limits the ledger to what had been published by then. include_shadow
    defaults to True only in the legacy regime.
    """
    valid = parse_ts(valid_at)
    known = parse_ts(known_at) if known_at is not None else None
    if include_shadow is None:
        include_shadow = regime == "legacy"
    if regime == "tora":
        include_shadow = False  # unpublished circulars do not exist under the rule

    chosen = []
    for it in items:
        if it.diff["instrument_id"] != instrument_id:
            continue
        if it.kind == "ledger":
            if known is not None and it.published_at > known:
                continue
        else:
            if not include_shadow:
                continue
            if known is not None and it.surfaced_at > known:
                continue
        op_time = operative_from(it, regime)
        if op_time > valid:
            continue
        chosen.append((op_time, 0 if it.kind == "ledger" else 1, it.order, it))
    chosen.sort(key=lambda x: (x[0], x[1], x[2]))

    state: dict = {}
    for op_time, _, _, it in chosen:
        d = it.diff
        cid = d["clause_id"]
        if d["op"] == "repeal":
            state.pop(cid, None)
            continue
        c = d["clause"]
        state[cid] = {
            "clause_id": cid,
            "text": c["text"],
            "subject": c.get("subject"),
            "value": c.get("value"),
            "scope": c.get("scope", {}),
            "diff_id": d["diff_id"],
            "authority": d["authority"],
            "source_ref": d["source_ref"],
            "published_at": fmt_ts(it.published_at) if it.published_at else None,
            "operative_from": fmt_ts(op_time),
            "retro_clipped": regime == "tora" and it.kind == "ledger" and is_retro(it),
            "shadow": it.kind == "shadow",
        }
    return dict(sorted(state.items(), key=lambda kv: natural_key(kv[0])))


def compare_states(a: dict, b: dict) -> list[dict]:
    """Clause-level difference between two consolidated states (a -> b)."""
    out = []
    for cid in sorted(set(a) | set(b), key=natural_key):
        ca, cb = a.get(cid), b.get(cid)
        if ca is None:
            out.append({"clause_id": cid, "change": "added", "before": None, "after": cb["text"], "diff_id": cb["diff_id"]})
        elif cb is None:
            out.append({"clause_id": cid, "change": "removed", "before": ca["text"], "after": None, "diff_id": ca["diff_id"]})
        elif ca["text"] != cb["text"] or ca["value"] != cb["value"] or ca["scope"] != cb["scope"]:
            out.append({"clause_id": cid, "change": "changed", "before": ca["text"], "after": cb["text"], "diff_id": cb["diff_id"]})
    return out


def exposure(items: list[Item], instrument_id: str, act_time, hindsight) -> dict:
    """What a citizen could see at act_time versus what is applied to that act later.

    citizen  = legacy law at act_time using only what was published by act_time
    applied  = legacy law at act_time as determined with everything surfaced by hindsight
    tora     = the same act judged under the proposed rule, which cannot change after the act
    """
    act = parse_ts(act_time)
    hind = parse_ts(hindsight)
    citizen = consolidate(items, instrument_id, act, "legacy", known_at=act, include_shadow=False)
    applied = consolidate(items, instrument_id, act, "legacy", known_at=hind, include_shadow=True)
    tora_then = consolidate(items, instrument_id, act, "tora", known_at=act)
    tora_later = consolidate(items, instrument_id, act, "tora", known_at=hind)
    causes = []
    for it in items:
        if it.diff["instrument_id"] != instrument_id:
            continue
        if operative_from(it, "legacy") > act:
            continue
        if it.kind == "shadow":
            if it.surfaced_at <= hind:
                causes.append({"diff_id": it.diff["diff_id"], "kind": "unpublished circular", "source_ref": it.diff["source_ref"]})
        elif it.published_at > act and it.published_at <= hind:
            causes.append({"diff_id": it.diff["diff_id"], "kind": "backdated amendment", "source_ref": it.diff["source_ref"],
                           "published_at": fmt_ts(it.published_at)})
    return {
        "instrument_id": instrument_id,
        "act_time": fmt_ts(act),
        "hindsight": fmt_ts(hind),
        "legacy_delta": compare_states(citizen, applied),
        "tora_delta": compare_states(tora_then, tora_later),
        "causes": causes,
    }


def render(state: dict, title: str, valid_at, regime: str) -> str:
    lines = [f"{title}", f"Law as it stood at {fmt_ist(valid_at)} ({regime} regime)", "-" * 72]
    if not state:
        lines.append("(no operative clauses at this moment)")
    for cid, c in state.items():
        flag = ""
        if c["shadow"]:
            flag = "  [UNPUBLISHED CIRCULAR]"
        elif c["retro_clipped"]:
            flag = "  [backdating clipped to publication]"
        lines.append(f"{cid}  {c['text']}{flag}")
        lines.append(f"      operative from {fmt_ist(c['operative_from'])} | {c['diff_id']} | {c['source_ref']}")
    return "\n".join(lines)
