"""Append-only, hash-chained publication ledger.

The ledger is the single source of truth. An amendment exists in law only if it is
an entry here. The publication time is assigned by the ledger from its clock at the
moment of appending; the caller cannot choose it, and it can never move backwards.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

from .model import (
    GENESIS_HASH,
    ClockRegression,
    InvalidDiff,
    LedgerError,
    entry_hash,
    fmt_ts,
    parse_ts,
    validate_diff,
)


@dataclass
class VerifyResult:
    ok: bool
    length: int
    head_hash: str
    failures: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "length": self.length, "head_hash": self.head_hash, "failures": self.failures}


class Ledger:
    def __init__(self, entries: list | None = None):
        self.entries: list[dict] = list(entries or [])

    # ------------------------------------------------------------------ reads
    def __len__(self) -> int:
        return len(self.entries)

    @property
    def head_hash(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS_HASH

    def anchor(self) -> dict:
        """A short commitment that can be published elsewhere (Gazette, notice board)."""
        return {"length": len(self.entries), "head_hash": self.head_hash}

    # ----------------------------------------------------------------- writes
    def append(self, diff: dict, now) -> dict:
        validate_diff(diff)
        now_dt = parse_ts(now)
        if self.entries and now_dt < parse_ts(self.entries[-1]["published_at"]):
            raise ClockRegression(
                f"publication time {fmt_ts(now_dt)} is earlier than the head "
                f"{self.entries[-1]['published_at']}; history cannot be rewritten"
            )
        if any(e["diff"]["diff_id"] == diff["diff_id"] for e in self.entries):
            raise InvalidDiff(f"duplicate diff_id {diff['diff_id']}")
        self._check_reference(diff)
        seq = len(self.entries)
        published_at = fmt_ts(now_dt)
        diff = copy.deepcopy(diff)
        entry = {
            "seq": seq,
            "prev_hash": self.head_hash,
            "published_at": published_at,
            "diff": diff,
            "hash": entry_hash(seq, self.head_hash, published_at, diff),
        }
        self.entries.append(entry)
        return entry

    def _check_reference(self, diff: dict) -> None:
        exists = set()
        for e in self.entries:
            d = e["diff"]
            key = (d["instrument_id"], d["clause_id"])
            if d["op"] == "repeal":
                exists.discard(key)
            else:
                exists.add(key)
        key = (diff["instrument_id"], diff["clause_id"])
        if diff["op"] == "insert" and key in exists:
            raise InvalidDiff(f"insert of an existing clause {key}; use replace")
        if diff["op"] in ("replace", "repeal") and key not in exists:
            raise InvalidDiff(f"{diff['op']} of a clause that does not exist {key}")

    # ----------------------------------------------------------------- verify
    def verify(self, anchor: dict | None = None) -> VerifyResult:
        failures: list[dict] = []
        prev = GENESIS_HASH
        prev_time = None
        seen_ids: set = set()
        for i, e in enumerate(self.entries):
            if e.get("seq") != i:
                failures.append({"seq": i, "reason": "sequence gap or reorder"})
            if e.get("prev_hash") != prev:
                failures.append({"seq": i, "reason": "broken hash link"})
            try:
                recomputed = entry_hash(e["seq"], e["prev_hash"], e["published_at"], e["diff"])
            except Exception:
                recomputed = None
            if recomputed != e.get("hash"):
                failures.append({"seq": i, "reason": "entry content does not match its hash"})
            try:
                t = parse_ts(e["published_at"])
                if prev_time is not None and t < prev_time:
                    failures.append({"seq": i, "reason": "publication time moves backwards"})
                prev_time = t
            except Exception:
                failures.append({"seq": i, "reason": "unreadable publication time"})
            did = e.get("diff", {}).get("diff_id")
            if did in seen_ids:
                failures.append({"seq": i, "reason": "duplicate diff_id"})
            seen_ids.add(did)
            prev = e.get("hash", "")
        if anchor is not None:
            if len(self.entries) < anchor["length"]:
                failures.append({"seq": len(self.entries), "reason": "ledger shorter than anchored length (truncation)"})
            elif anchor["length"] > 0 and self.entries[anchor["length"] - 1].get("hash") != anchor["head_hash"]:
                failures.append({"seq": anchor["length"] - 1, "reason": "anchored head hash does not match"})
        return VerifyResult(not failures, len(self.entries), self.head_hash, failures)

    # ------------------------------------------------------------ persistence
    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for e in self.entries:
                fh.write(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path) -> "Ledger":
        entries = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        return cls(entries)


def publish(path, diff: dict, now=None) -> dict:
    """Append one amendment to a ledger file under an exclusive lock and return the entry.

    The publication time is the system clock unless `now` is given (tests and the synthetic
    builder only). The file is opened in append mode and fsynced, so existing lines are never
    rewritten. Production deployments should wrap this behind an authenticated publisher.
    """
    import fcntl

    path = str(path)
    when = now if now is not None else datetime.now(timezone.utc)
    lock_path = path + ".lock"
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            led = Ledger.load(path) if os.path.exists(path) else Ledger()
            res = led.verify()
            if not res.ok:
                raise LedgerError(f"refusing to append to a ledger that fails verification: {res.failures[0]}")
            entry = led.append(diff, when)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return entry
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
