"""Core data model, timestamp handling and hashing for Pramana.

All timestamps are timezone-aware and normalised to UTC with second precision.
All hashing is done over canonical JSON so that the same entry always hashes the same.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64
OPS = ("insert", "replace", "repeal")
REGIMES = ("legacy", "tora")


def parse_ts(value) -> datetime:
    """Parse an ISO 8601 timestamp that carries an explicit offset; return UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must carry a timezone offset: {value!r}")
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_ist(value) -> str:
    """Display form in India Standard Time. Storage stays UTC."""
    from datetime import timedelta
    dt = parse_ts(value) + timedelta(hours=5, minutes=30)
    return dt.strftime("%d %b %Y %H:%M IST")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def entry_hash(seq: int, prev_hash: str, published_at: str, diff: dict) -> str:
    payload = {"seq": seq, "prev_hash": prev_hash, "published_at": published_at, "diff": diff}
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


class LedgerError(Exception):
    """Base class for ledger failures."""


class ClockRegression(LedgerError):
    """A publication was attempted with a time earlier than the current head."""


class InvalidDiff(LedgerError):
    """The submitted amendment is structurally invalid or refers to nothing."""


def validate_diff(diff: dict) -> None:
    """Structural validation. The JSON Schema in schemas/ is the normative version."""
    allowed = {"diff_id", "instrument_id", "op", "clause_id", "authority", "source_ref", "effective_from", "note", "clause"}
    extra = set(diff) - allowed
    if extra:
        raise InvalidDiff(f"unexpected field(s) {sorted(extra)}; publication time is assigned by the ledger, never supplied")
    required = ("diff_id", "instrument_id", "op", "clause_id", "authority", "source_ref")
    for key in required:
        if key not in diff or not isinstance(diff[key], str) or not diff[key]:
            raise InvalidDiff(f"missing or empty field: {key}")
    if diff["op"] not in OPS:
        raise InvalidDiff(f"unknown op: {diff['op']!r}")
    if diff["op"] in ("insert", "replace"):
        clause = diff.get("clause")
        if not isinstance(clause, dict) or not isinstance(clause.get("text"), str) or not clause["text"]:
            raise InvalidDiff("insert/replace needs a clause with non-empty text")
        extra_c = set(clause) - {"text", "subject", "value", "scope"}
        if extra_c:
            raise InvalidDiff(f"unexpected clause field(s) {sorted(extra_c)}")
        scope = clause.get("scope", {})
        if not isinstance(scope, dict) or any(
            not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v)
            for v in scope.values()
        ):
            raise InvalidDiff("clause.scope must map attribute names to non-empty lists of strings")
    elif "clause" in diff and diff["clause"] is not None:
        raise InvalidDiff("repeal must not carry a clause body")
    eff = diff.get("effective_from")
    if eff is not None:
        try:
            parse_ts(eff)
        except ValueError as exc:
            raise InvalidDiff(f"bad effective_from: {exc}") from exc
