"""Discretion probe: how often does the written rulebook leave an official a choice?

A clause may carry a subject (what it governs), a value (what it requires) and a scope
(which fact patterns it applies to). For one fact pattern and one subject, the clauses
that apply may agree or disagree. If they disagree, the official can pick between them.

Two readings are reported:
  raw       no precedence rule exists, so any applicable clause may be chosen
  resolved  the most specific applicable clauses win (a common interpretive rule); a
            choice remains only when equally specific clauses disagree

This is a measurement tool. What it reports about a generated corpus is a property of
that corpus and of the generator assumptions, not evidence about any real statute.
"""
from __future__ import annotations

import random
import statistics

DOMAINS = {
    "entity_type": ["company", "llp", "startup", "ngo"],
    "sector": ["tech", "mfg", "agri", "retail", "health"],
    "turnover_band": ["S", "M", "L"],
    "state": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
    "age_band": ["new", "old"],
}
VALUES = ["30d", "45d", "60d", "75d", "exempt"]


def applicable(clause: dict, fact: dict) -> bool:
    return all(fact.get(k) in vals for k, vals in (clause.get("scope") or {}).items())


def evaluate(clauses: list[dict], fact: dict, subject: str) -> dict:
    app = [c for c in clauses if c.get("subject") == subject and applicable(c, fact)]
    if not app:
        return {"applicable": 0, "raw_outcomes": 0, "resolved_outcomes": 0,
                "discretion_raw": False, "discretion_resolved": False, "deciding": []}
    raw = {c["value"] for c in app}
    top_spec = max(len(c.get("scope") or {}) for c in app)
    top = [c for c in app if len(c.get("scope") or {}) == top_spec]
    resolved = {c["value"] for c in top}
    return {
        "applicable": len(app),
        "raw_outcomes": len(raw),
        "resolved_outcomes": len(resolved),
        "discretion_raw": len(raw) > 1,
        "discretion_resolved": len(resolved) > 1,
        "deciding": sorted(c.get("clause_id", "?") for c in top),
    }


def state_clauses(states: dict[str, dict]) -> list[dict]:
    """Flatten {instrument_id: consolidated_state} into evaluable clauses."""
    out = []
    for inst, st in states.items():
        for cid, c in st.items():
            if c.get("subject"):
                out.append({"clause_id": f"{inst}:{cid}", "subject": c["subject"], "value": c["value"], "scope": c["scope"]})
    return out


def random_fact(rng: random.Random) -> dict:
    return {k: rng.choice(v) for k, v in DOMAINS.items()}


def random_edge_clause(rng: random.Random, cid: str, subject: str, max_keys: int = 3) -> dict:
    k = rng.randint(1, max_keys)
    keys = rng.sample(sorted(DOMAINS), k)
    scope = {key: rng.sample(DOMAINS[key], rng.randint(1, 2)) for key in keys}
    return {"clause_id": cid, "subject": subject, "value": rng.choice(VALUES), "scope": scope}


def generate_corpus(rng: random.Random, edge_clauses: int, subject: str = "annual_return_due") -> list[dict]:
    """One universal base rule plus `edge_clauses` narrower exception clauses."""
    corpus = [{"clause_id": "base", "subject": subject, "value": "60d", "scope": {}}]
    for i in range(edge_clauses):
        corpus.append(random_edge_clause(rng, f"edge{i}", subject))
    return corpus


def sweep(densities: list[int], seeds: int = 20, facts: int = 400, subject: str = "annual_return_due") -> list[dict]:
    rows = []
    for d in densities:
        raw_rates, res_rates, app_means = [], [], []
        for s in range(seeds):
            rng = random.Random(10_000 * d + s)
            corpus = generate_corpus(rng, d, subject)
            fact_rng = random.Random(999_000 + s)
            hits_raw = hits_res = 0
            app_total = 0
            for _ in range(facts):
                r = evaluate(corpus, random_fact(fact_rng), subject)
                hits_raw += r["discretion_raw"]
                hits_res += r["discretion_resolved"]
                app_total += r["applicable"]
            raw_rates.append(hits_raw / facts)
            res_rates.append(hits_res / facts)
            app_means.append(app_total / facts)
        rows.append({
            "edge_clauses": d,
            "raw_mean": statistics.mean(raw_rates),
            "raw_sd": statistics.pstdev(raw_rates),
            "resolved_mean": statistics.mean(res_rates),
            "resolved_sd": statistics.pstdev(res_rates),
            "applicable_mean": statistics.mean(app_means),
        })
    return rows


# ---------------------------------------------------------------- publication-time conflict gate
def scopes_overlap(a: dict, b: dict) -> bool:
    """True if some fact pattern can satisfy both scopes. Unshared attributes never block overlap."""
    for k in set(a) & set(b):
        if not set(a[k]) & set(b[k]):
            return False
    return True


def creates_tie(accepted: list[dict], proposal: dict) -> bool:
    """A proposal creates an unresolvable tie if an accepted clause on the same subject has the
    same specificity, an overlapping scope and a different value."""
    spec = len(proposal.get("scope") or {})
    for c in accepted:
        if (c.get("subject") == proposal.get("subject")
                and len(c.get("scope") or {}) == spec
                and scopes_overlap(c.get("scope") or {}, proposal.get("scope") or {})
                and c["value"] != proposal["value"]):
            return True
    return False


def sweep_gated(densities: list[int], seeds: int = 20, facts: int = 400, subject: str = "annual_return_due") -> list[dict]:
    """Same generator as sweep(), but each proposed edge clause is checked against the
    consolidated rulebook at publication and refused if it would create a tie."""
    rows = []
    for d in densities:
        rej_rates, res_rates, raw_rates, acc_counts = [], [], [], []
        for s in range(seeds):
            rng = random.Random(10_000 * d + s)
            accepted = [{"clause_id": "base", "subject": subject, "value": "60d", "scope": {}}]
            rejected = 0
            for i in range(d):
                prop = random_edge_clause(rng, f"edge{i}", subject)
                if creates_tie(accepted, prop):
                    rejected += 1
                else:
                    accepted.append(prop)
            fact_rng = random.Random(999_000 + s)
            hr = hs = 0
            for _ in range(facts):
                r = evaluate(accepted, random_fact(fact_rng), subject)
                hr += r["discretion_raw"]
                hs += r["discretion_resolved"]
            rej_rates.append(rejected / d if d else 0.0)
            res_rates.append(hs / facts)
            raw_rates.append(hr / facts)
            acc_counts.append(len(accepted) - 1)
        rows.append({
            "proposed": d,
            "accepted_mean": statistics.mean(acc_counts),
            "rejected_share": statistics.mean(rej_rates),
            "raw_mean": statistics.mean(raw_rates),
            "resolved_mean": statistics.mean(res_rates),
        })
    return rows
