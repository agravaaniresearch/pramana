"""Command line interface. Plain text output so it can be read, diffed and screenshotted."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from . import discretion, fuzz, synth
from .ledger import Ledger, publish
from .model import fmt_ist, fmt_ts, parse_ts
from .state import consolidate, exposure, items_from, render

DEFAULT_LEDGER = "data/synthetic_ledger.jsonl"
DEFAULT_CORPUS = "data/synthetic_corpus.json"


def load(ledger_path: str, corpus_path: str):
    led = Ledger.load(ledger_path)
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    return led, corpus, items_from(led, corpus.get("shadows", []))


def title_of(corpus: dict, inst: str) -> str:
    for i in corpus.get("instruments", []):
        if i["instrument_id"] == inst:
            return f"{inst}  {i['title']}"
    return inst


def rule(ch="=", n=72):
    return ch * n


def cmd_build(args):
    lp, cp = synth.write_synthetic(args.out)
    print(f"wrote {lp} and {cp}")
    print("SYNTHETIC AND ILLUSTRATIVE ONLY.")


def cmd_asof(args):
    led, corpus, items = load(args.ledger, args.corpus)
    known = args.known_at
    st = consolidate(items, args.instrument, args.at, args.regime, known_at=known)
    print(render(st, title_of(corpus, args.instrument), args.at, args.regime))


def cmd_verify(args):
    led = Ledger.load(args.ledger)
    anchor = json.loads(args.anchor) if args.anchor else None
    res = led.verify(anchor)
    print(f"entries      : {res.length}")
    print(f"head hash    : {res.head_hash}")
    print(f"chain status : {'INTACT' if res.ok else 'BROKEN'}")
    for f in res.failures:
        print(f"  entry {f['seq']}: {f['reason']}")
    return 0 if res.ok else 2


def cmd_publish(args):
    diff = json.loads(Path(args.diff).read_text(encoding="utf-8"))
    entry = publish(args.ledger, diff)
    print(f"published {entry['diff']['diff_id']} as entry {entry['seq']} at {entry['published_at']}")
    print(f"head hash {entry['hash']}")


def cmd_anchor(args):
    print(json.dumps(Ledger.load(args.ledger).anchor()))


def cmd_exposure(args):
    led, corpus, items = load(args.ledger, args.corpus)
    ex = exposure(items, args.instrument, args.act, args.hindsight)
    print(f"Exposure for {title_of(corpus, args.instrument)}")
    print(f"Act judged at     : {fmt_ist(ex['act_time'])}")
    print(f"Hindsight (today) : {fmt_ist(ex['hindsight'])}")
    print(rule("-"))
    print("Legacy practice: law visible to the citizen vs law applied in hindsight")
    if not ex["legacy_delta"]:
        print("  no difference")
    for d in ex["legacy_delta"]:
        print(f"  clause {d['clause_id']}  {d['change'].upper()} by {d['diff_id']}")
        if d["before"]:
            print(f"      visible then : {d['before']}")
        if d["after"]:
            print(f"      applied later: {d['after']}")
    for c in ex["causes"]:
        print(f"  cause: {c['kind']} {c['diff_id']} ({c['source_ref']})")
    print(rule("-"))
    print("Pramana rule: the same act judged then and judged later")
    print("  no difference" if not ex["tora_delta"] else f"  {len(ex['tora_delta'])} clause(s) differ")


def cmd_discretion(args):
    led, corpus, items = load(args.ledger, args.corpus)
    states = {i["instrument_id"]: consolidate(items, i["instrument_id"], args.at, "tora", known_at=args.at)
              for i in corpus["instruments"]}
    clauses = discretion.state_clauses(states)
    subjects = sorted({c["subject"] for c in clauses})
    print(f"Discretion probe at {fmt_ist(args.at)} across {len(states)} instruments, {len(clauses)} tagged clauses")
    print(rule("-"))
    for fact in corpus["facts"]:
        print(fact["label"])
        attrs = {k: v for k, v in fact.items() if k != "label"}
        for s in subjects:
            r = discretion.evaluate(clauses, attrs, s)
            if r["applicable"] == 0:
                continue
            verdict = "CHOICE LEFT TO OFFICIAL" if r["discretion_resolved"] else ("settled by specificity" if r["discretion_raw"] else "settled")
            print(f"  {s:<22} applicable={r['applicable']} raw={r['raw_outcomes']} resolved={r['resolved_outcomes']}  {verdict}")
            if r["discretion_resolved"]:
                print(f"      tied clauses: {', '.join(r['deciding'])}")
    print()


def cmd_sweep(args):
    rows = discretion.sweep(list(range(0, args.max + 1, args.step)), seeds=args.seeds, facts=args.facts)
    print("Share of fact patterns where applicable clauses disagree (mean over seeds)")
    print(f"{'edge clauses':>12}  {'no precedence':>14}  {'specificity wins':>17}  {'avg applicable':>15}")
    for r in rows:
        print(f"{r['edge_clauses']:>12}  {r['raw_mean']:>14.3f}  {r['resolved_mean']:>17.3f}  {r['applicable_mean']:>15.2f}")
    gated = discretion.sweep_gated(list(range(0, args.max + 1, args.step)), seeds=args.seeds, facts=args.facts)
    print()
    print("Same proposals, but a conflict gate at publication refuses any clause that would create a tie")
    print(f"{'proposed':>9}  {'accepted':>9}  {'refused':>8}  {'no precedence':>14}  {'specificity wins':>17}")
    for r in gated:
        print(f"{r['proposed']:>9}  {r['accepted_mean']:>9.1f}  {r['rejected_share']*100:>7.1f}%  {r['raw_mean']:>14.3f}  {r['resolved_mean']:>17.3f}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"ungated": rows, "gated": gated}, indent=2) + "\n", encoding="utf-8")


def cmd_fuzz(args):
    res = fuzz.run_all(args.trials)
    print(f"Tamper detection, {args.trials} seeded trials per attack")
    print(f"{'attack':<28}{'ledger alone':>14}{'with anchor':>14}")
    for r in res["tamper_detection"]:
        print(f"{r['attack']:<28}{r['rate_without_anchor']*100:>13.1f}%{r['rate_with_anchor']*100:>13.1f}%")
    c = res["clock_regression"]
    print(f"\nClock regression rejected: {c['rejected']}/{c['trials']}")
    print("\nStability of law judged at a fixed act time, as later amendments arrive")
    print(f"{'backdated share':>16}{'probes':>9}{'pramana changed':>17}{'legacy changed':>16}")
    for s in res["stability"]:
        print(f"{s['retro_share']*100:>15.0f}%{s['probes']:>9}{s['tora_changed_after_the_fact']:>17}{s['legacy_rate']*100:>15.1f}%")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")


def cmd_demo(args):
    led, corpus, items = load(args.ledger, args.corpus)
    inst = "SYN-FIL-02"
    print(rule())
    print("PRAMANA DEMONSTRATION  |  synthetic data, illustrative only")
    print(rule())
    print(f"Ledger: {len(led)} published amendments, head {led.head_hash[:16]}...")
    print(f"Shadow circulars applied by officials but never published: {len(corpus['shadows'])}\n")
    t1, t2 = "2024-12-12T16:00:00+05:30", "2024-12-12T17:01:00+05:30"
    hind = "2025-06-01T00:00:00+05:30"
    for label, t in (("4:00 pm", t1), ("5:01 pm", t2)):
        print(f"[{label} on 12 Dec 2024]  clause 1.1 under the Pramana rule")
        st = consolidate(items, inst, t, "tora", known_at=hind)
        print(f"   {st['1.1']['text']}")
        print(f"   operative from {fmt_ist(st['1.1']['operative_from'])}\n")
    print("The 5 pm circular says it applies from 1 Dec. Under legacy practice, the act at 4 pm is judged afterwards like this:")
    ex = exposure(items, inst, t1, hind)
    for d in ex["legacy_delta"]:
        print(f"   clause {d['clause_id']} {d['change']} by {d['diff_id']}: {d['after']}")
    print("Under the Pramana rule the same act is judged identically then and now: "
          f"{len(ex['tora_delta'])} clause(s) differ.\n")
    print(rule("-"))
    print("Consolidated view at 5:01 pm (the whole instrument, not a stack of circulars)")
    print(render(consolidate(items, inst, t2, "tora", known_at=hind), title_of(corpus, inst), t2, "tora"))
    print()
    print(rule("-"))
    print("Integrity")
    anchor = led.anchor()
    print(f"   anchor published elsewhere: length={anchor['length']} head={anchor['head_hash'][:16]}...")
    forged = copy.deepcopy(led.entries)
    forged[11]["diff"]["clause"]["text"] = forged[11]["diff"]["clause"]["text"].replace("45", "30")
    res = Ledger(forged).verify(anchor)
    print(f"   after quietly editing entry 11: {'INTACT' if res.ok else 'BROKEN'}; {res.failures[0]['reason']}")
    print()
    print(rule("-"))
    cmd_discretion(argparse.Namespace(ledger=args.ledger, corpus=args.corpus, at="2025-04-01T00:00:00+05:30"))


def build_parser():
    p = argparse.ArgumentParser(prog="pramana", description="Synthetic prototype of a timestamped source of truth for rules.")
    p.add_argument("--ledger", default=DEFAULT_LEDGER)
    p.add_argument("--corpus", default=DEFAULT_CORPUS)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build-synthetic", help="write the synthetic ledger and corpus")
    s.add_argument("--out", default="data")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("asof", help="consolidated instrument at a moment")
    s.add_argument("--instrument", required=True)
    s.add_argument("--at", required=True)
    s.add_argument("--regime", default="tora", choices=["tora", "legacy"])
    s.add_argument("--known-at", default=None)
    s.set_defaults(fn=cmd_asof)

    s = sub.add_parser("verify", help="check hash chain integrity")
    s.add_argument("--anchor", default=None, help='JSON like {"length":15,"head_hash":"..."}')
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("publish", help="append one amendment (JSON file) using the system clock")
    s.add_argument("--diff", required=True, help="path to a JSON file matching schemas/diff.schema.json")
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("anchor", help="print a head commitment")
    s.set_defaults(fn=cmd_anchor)

    s = sub.add_parser("exposure", help="retrospective exposure of an act")
    s.add_argument("--instrument", required=True)
    s.add_argument("--act", required=True)
    s.add_argument("--hindsight", required=True)
    s.set_defaults(fn=cmd_exposure)

    s = sub.add_parser("discretion", help="where the rulebook leaves a choice")
    s.add_argument("--at", required=True)
    s.set_defaults(fn=cmd_discretion)

    s = sub.add_parser("sweep", help="discretion versus rule density on generated corpora")
    s.add_argument("--max", type=int, default=40)
    s.add_argument("--step", type=int, default=4)
    s.add_argument("--seeds", type=int, default=20)
    s.add_argument("--facts", type=int, default=400)
    s.add_argument("--json", default=None)
    s.set_defaults(fn=cmd_sweep)

    s = sub.add_parser("fuzz", help="adversarial test bed with failure rates")
    s.add_argument("--trials", type=int, default=1000)
    s.add_argument("--json", default=None)
    s.set_defaults(fn=cmd_fuzz)

    s = sub.add_parser("demo", help="the full walkthrough on synthetic data")
    s.set_defaults(fn=cmd_demo)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    rc = args.fn(args)
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
