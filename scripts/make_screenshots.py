#!/usr/bin/env python3
"""Regenerate every image in docs/screenshots from real runs of the real CLI.

Terminal screenshots are the captured stdout of the commands shown in each title bar,
rendered to HTML and photographed with headless Chrome. Charts are drawn from the JSON
produced by `pramana fuzz --json` and `pramana sweep --json`. Nothing is mocked.

Requires: google-chrome (or chromium) on PATH, matplotlib.
Usage: python scripts/make_screenshots.py
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
RES = ROOT / "docs" / "results"

# Warm palette. Deliberately no blues.
CREAM, PAPER, INK, MUTED = "#FBF3E4", "#FFFBF2", "#2B2118", "#7A6A58"
SAFFRON, TERRA, OLIVE, MAROON, SAND = "#D98E04", "#B5472B", "#5F7A2A", "#7A2E3B", "#E9D9BC"

CHROME = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")


def run(args, cwd=ROOT) -> str:
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.stdout + p.stderr


def colourise(line: str) -> str:
    s = html.escape(line)
    s = re.sub(r"\b(BROKEN)\b", rf'<b style="color:{TERRA}">\1</b>', s)
    s = re.sub(r"\b(INTACT)\b", rf'<b style="color:{OLIVE}">\1</b>', s)
    s = re.sub(r"(CHOICE LEFT TO OFFICIAL)", rf'<b style="color:{MAROON}">\1</b>', s)
    s = re.sub(r"(settled by specificity|settled)\b", rf'<span style="color:{OLIVE}">\1</span>', s)
    s = re.sub(r"(\[backdating clipped to publication\]|\[UNPUBLISHED CIRCULAR\])", rf'<b style="color:{TERRA}">\1</b>', s)
    s = re.sub(r"(no difference)", rf'<b style="color:{OLIVE}">\1</b>', s)
    s = re.sub(r"^(\[[^\]]+\]|PRAMANA DEMONSTRATION|Exposure for|Integrity|Consolidated view)", rf'<b style="color:{SAFFRON}">\1</b>', s)
    s = re.sub(r"^(={10,}|-{10,})", rf'<span style="color:{SAND}">\1</span>', s)
    return s


def terminal_html(title: str, body: str, width: int = 1180) -> tuple[str, int]:
    lines = body.rstrip("\n").split("\n")
    lh, pad = 21, 22
    height = 46 + len(lines) * lh + 2 * pad + 8
    rows = "".join(f"<div style=\"height:{lh}px;white-space:pre\">{colourise(l) or '&nbsp;'}</div>" for l in lines)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{CREAM};}}
.win{{margin:14px;border-radius:10px;overflow:hidden;background:{PAPER};border:1px solid {SAND};box-shadow:0 2px 0 {SAND};}}
.bar{{height:34px;background:{SAND};display:flex;align-items:center;padding:0 14px;gap:8px;font:600 13px 'DejaVu Sans Mono',monospace;color:{INK}}}
.dot{{width:11px;height:11px;border-radius:50%;display:inline-block}}
.body{{padding:{pad}px 24px;font:14px/{lh}px 'DejaVu Sans Mono',monospace;color:{INK};white-space:pre}}
</style></head><body><div class="win"><div class="bar">
<span class="dot" style="background:{TERRA}"></span><span class="dot" style="background:{SAFFRON}"></span><span class="dot" style="background:{OLIVE}"></span>
<span style="margin-left:10px">{html.escape(title)}</span></div>
<div class="body">{rows}</div></div></body></html>"""
    return page, height + 28


def shoot(page: str, path: Path, width: int, height: int) -> None:
    if not CHROME:
        sys.exit("google-chrome or chromium is required to render screenshots")
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "p.html"
        f.write_text(page, encoding="utf-8")
        subprocess.run(
            [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={width},{height}", f"--screenshot={path}", f"file://{f}"],
            check=True, capture_output=True,
        )


def term(name: str, title: str, body: str, width: int = 1320) -> None:
    page, h = terminal_html(title, body, width)
    shoot(page, OUT / name, width, h)
    print("wrote", OUT / name)


def charts() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK, "text.color": INK})

    def frame(w=9.6, h=5.2):
        fig, ax = plt.subplots(figsize=(w, h), dpi=130)
        fig.patch.set_facecolor(CREAM)
        ax.set_facecolor(PAPER)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color=SAND, linewidth=0.8)
        ax.set_axisbelow(True)
        return fig, ax

    sw = json.loads((RES / "discretion_sweep.json").read_text())
    ung, gat = sw["ungated"], sw["gated"]
    fig, ax = frame()
    x = [r["edge_clauses"] for r in ung]
    ax.plot(x, [r["raw_mean"] * 100 for r in ung], color=TERRA, lw=2.6, marker="o", label="No precedence rule: any applicable clause may be chosen")
    ax.plot(x, [r["resolved_mean"] * 100 for r in ung], color=SAFFRON, lw=2.6, marker="o", label="Most specific clause wins; ties remain")
    ax.plot(x, [r["resolved_mean"] * 100 for r in gat], color=OLIVE, lw=2.6, marker="s", label="Most specific wins, with a conflict gate at publication")
    ax.set_xlabel("Exception clauses added to one universal rule (synthetic generator)")
    ax.set_ylabel("Fact patterns left to official choice (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Where the rulebook leaves a choice, by rule density", loc="left", fontsize=13, fontweight="bold", color=INK)
    ax.legend(frameon=False, fontsize=9, loc="lower right", bbox_to_anchor=(1.0, 0.07))
    fig.text(0.01, 0.01, "Synthetic and illustrative only. A property of the generator's assumptions, not of any real statute.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "07_discretion_sweep.png", facecolor=CREAM)
    plt.close(fig)
    print("wrote", OUT / "07_discretion_sweep.png")

    fz = json.loads((RES / "fuzz.json").read_text())
    st = fz["stability"]
    fig, ax = frame(8.6, 4.8)
    xs = [f"{s['retro_share']*100:.0f}%" for s in st]
    xi = range(len(xs))
    ax.bar([i - 0.19 for i in xi], [s["legacy_rate"] * 100 for s in st], 0.38, color=TERRA, label="Legacy practice")
    ax.bar([i + 0.19 for i in xi], [s["tora_rate"] * 100 for s in st], 0.38, color=OLIVE, label="Pramana rule")
    for i, s in enumerate(st):
        ax.text(i - 0.19, s["legacy_rate"] * 100 + 0.2, f"{s['legacy_rate']*100:.1f}%", ha="center", fontsize=9)
        ax.text(i + 0.19, 0.2, "0", ha="center", fontsize=9, color=OLIVE)
    ax.set_xticks(list(xi))
    ax.set_xticklabels(xs)
    ax.set_xlabel("Share of amendments stated to apply from before they were published")
    ax.set_ylabel("Acts whose governing law changed afterwards (%)")
    ax.set_title("Does the law an act was judged under stay put?", loc="left", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.01, 0.01, "Random synthetic ledgers, seeded. Zero under the Pramana rule holds by construction and is checked, not discovered.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "08_stability.png", facecolor=CREAM)
    plt.close(fig)
    print("wrote", OUT / "08_stability.png")

    td = fz["tamper_detection"]
    fig, ax = frame(9.6, 5.0)
    names = [r["attack"].replace("_", " ") for r in td]
    yi = range(len(names))
    ax.barh([i + 0.2 for i in yi], [r["rate_without_anchor"] * 100 for r in td], 0.38, color=SAFFRON, label="Chain alone")
    ax.barh([i - 0.2 for i in yi], [r["rate_with_anchor"] * 100 for r in td], 0.38, color=OLIVE, label="Chain plus published anchor")
    ax.set_yticks(list(yi))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlim(0, 108)
    ax.set_xlabel("Tampering detected (%), 1000 seeded trials per attack")
    ax.grid(axis="x", color=SAND, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_title("Tamper detection: where the chain alone is blind", loc="left", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "09_tamper_detection.png", facecolor=CREAM)
    plt.close(fig)
    print("wrote", OUT / "09_tamper_detection.png")


ARCH = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:{CREAM};font-family:'DejaVu Sans',sans-serif;color:{INK}}}
.wrap{{padding:26px 30px;width:1120px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:{MUTED};font-size:13px;margin-bottom:18px}}
.row{{display:flex;gap:14px;align-items:stretch;margin-bottom:14px}}
.box{{flex:1;background:{PAPER};border:1.5px solid {SAND};border-radius:10px;padding:12px 14px;font-size:12.5px;line-height:1.45}}
.box b{{display:block;font-size:13.5px;margin-bottom:4px}}
.hot{{border-color:{SAFFRON};border-width:2.5px}}
.arrow{{align-self:center;font-size:22px;color:{TERRA}}}
.tag{{display:inline-block;font:11px 'DejaVu Sans Mono',monospace;background:{SAND};border-radius:4px;padding:1px 6px;margin-right:4px}}
.note{{font-size:12px;color:{MUTED};margin-top:6px}}
</style></head><body><div class="wrap">
<h1>Pramana: how the three elements map to the engine</h1>
<div class="sub">Synthetic prototype. The three elements are as described on a public podcast; the draft law itself was not seen.</div>
<div class="row">
 <div class="box hot"><b>1. One source of truth</b>Append-only ledger. An amendment exists in law only if it is an entry here. Unpublished circulars are void.<div class="note"><span class="tag">ledger.py</span><span class="tag">server.py</span></div></div>
 <div class="arrow">&rarr;</div>
 <div class="box hot"><b>2. Every change timestamped</b>The ledger clock assigns publication time. It cannot move backwards. Each entry is hash-linked to the one before. A stated effective date can never precede publication.<div class="note"><span class="tag">model.py</span><span class="tag">fuzz.py</span></div></div>
 <div class="arrow">&rarr;</div>
 <div class="box hot"><b>3. Law shown as a whole</b>Fold the diffs in order into the current instrument, or into the instrument as it stood at any past moment. Every clause carries its provenance.<div class="note"><span class="tag">state.py</span><span class="tag">cli.py asof</span></div></div>
</div>
<div class="row">
 <div class="box"><b>Two clocks</b>valid_at is the moment of the act. known_at is how much had been published when it was judged. Under the rule, changing known_at never changes the answer.</div>
 <div class="box"><b>Exposure</b>The gap between the law a citizen could see at the time and the law applied later. Zero by construction under the rule; measured under legacy practice.</div>
 <div class="box"><b>Discretion probe</b>For a fact pattern, do the applicable clauses agree? Counts the choices the written rulebook leaves open, with and without a precedence rule and a publication-time conflict gate.<div class="note"><span class="tag">discretion.py</span></div></div>
</div>
<div class="row">
 <div class="box"><b>Anchor</b>Publish the head hash elsewhere (a notice board, an independent register). Closes the two blind spots of a bare chain: a fully re-hashed history and a cut tail.</div>
 <div class="box"><b>Not in the prototype</b>Authenticated publication, signing keys, who may publish, the legal definition of published, and delegated legislation. See POLICY.md and DEPLOYMENT.md.</div>
</div></div></body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "data" / "synthetic_ledger.jsonl").exists():
        run(["pramana", "build-synthetic"])
    cli = ["pramana"]

    # 1. as-of at 4 pm and 5:01 pm
    a = run(cli + ["asof", "--instrument", "SYN-FIL-02", "--at", "2024-12-12T16:00:00+05:30"])
    b = run(cli + ["asof", "--instrument", "SYN-FIL-02", "--at", "2024-12-12T17:01:00+05:30"])
    term("01_asof_four_pm_five_pm.png",
         "pramana asof --instrument SYN-FIL-02 --at 2024-12-12T16:00:00+05:30   (then 17:01)",
         a + "\n" + b)

    # 2. full demo
    term("02_demo_walkthrough.png", "pramana demo", run(cli + ["demo"]))

    # 3. exposure
    ex = run(cli + ["exposure", "--instrument", "SYN-FIL-02", "--act", "2024-12-12T16:00:00+05:30", "--hindsight", "2025-06-01T00:00:00+05:30"])
    ex2 = run(cli + ["exposure", "--instrument", "SYN-IMP-01", "--act", "2025-01-10T10:00:00+05:30", "--hindsight", "2025-06-01T00:00:00+05:30"])
    term("03_exposure_report.png", "pramana exposure --instrument SYN-FIL-02 --act ... --hindsight ...   (then SYN-IMP-01)", ex + "\n" + ex2)

    # 4. tamper detection on a copy
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        lines = (ROOT / "data" / "synthetic_ledger.jsonl").read_text().splitlines()
        anchor = run(cli + ["anchor"]).strip()
        clean = run(cli + ["verify"])
        lines[11] = lines[11].replace("45 days", "30 days")
        (td / "tampered.jsonl").write_text("\n".join(lines) + "\n")
        bad = run(cli + ["--ledger", str(td / "tampered.jsonl"), "verify"]).replace(str(td) + "/", "")
        body = f"$ pramana verify\n{clean}\n$ pramana anchor\n{anchor}\n\n$ pramana --ledger tampered.jsonl verify     # entry 11 quietly edited\n{bad}"
        term("04_tamper_detection.png", "pramana verify", body)

    # 5. discretion
    term("05_discretion_probe.png", "pramana discretion --at 2025-04-01T00:00:00+05:30",
         run(cli + ["discretion", "--at", "2025-04-01T00:00:00+05:30"]))

    # 6. fuzz + sweep outputs (also refreshes the JSON the charts use)
    fz = run(cli + ["fuzz", "--trials", "1000", "--json", str(RES / "fuzz.json")])
    term("06_failure_rates.png", "pramana fuzz --trials 1000", fz)
    sw = run(cli + ["sweep", "--json", str(RES / "discretion_sweep.json")])
    term("10_sweep_table.png", "pramana sweep", sw)

    charts()

    shoot(ARCH, OUT / "00_architecture.png", 1180, 540)
    print("wrote", OUT / "00_architecture.png")
    (RES / "fuzz.txt").write_text(fz)
    (RES / "sweep.txt").write_text(sw)


if __name__ == "__main__":
    main()
