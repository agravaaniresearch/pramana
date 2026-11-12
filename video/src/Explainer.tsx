import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import fuzz from "../../docs/results/fuzz.json";
import sweep from "../../docs/results/discretion_sweep.json";

// Warm palette. Deliberately no blues.
const C = { cream: "#FBF3E4", paper: "#FFFBF2", ink: "#2B2118", muted: "#7A6A58", saffron: "#D98E04", terra: "#B5472B", olive: "#5F7A2A", maroon: "#7A2E3B", sand: "#E9D9BC" };
const FONT = "'DejaVu Sans', Helvetica, Arial, sans-serif";
const MONO = "'DejaVu Sans Mono', Menlo, monospace";
const TRANS = 18;

const S = (s: number) => Math.round(s * 30);
const DURS = [S(5), S(8), S(8), S(8), S(9), S(8), S(8), S(6)];
export const TOTAL_FRAMES = DURS.reduce((a, b) => a + b, 0) - TRANS * (DURS.length - 1);

const Frame: React.FC<{ title?: string; children: React.ReactNode }> = ({ title, children }) => (
  <AbsoluteFill style={{ background: C.cream, fontFamily: FONT, color: C.ink, padding: "54px 70px" }}>
    {title && <div style={{ fontSize: 40, fontWeight: 700, marginBottom: 6 }}>{title}</div>}
    {children}
    <div style={{ position: "absolute", left: 70, bottom: 24, fontSize: 15, color: C.muted }}>
      Synthetic data, for illustrative purposes only.
    </div>
  </AbsoluteFill>
);

const useIn = (delay = 0, len = 20) => {
  const f = useCurrentFrame();
  return interpolate(f, [delay, delay + len], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
};

const Caption: React.FC<{ text: string; delay?: number; size?: number; color?: string }> = ({ text, delay = 0, size = 28, color = C.ink }) => {
  const o = useIn(delay);
  return <div style={{ opacity: o, transform: `translateY(${(1 - o) * 14}px)`, fontSize: size, lineHeight: 1.4, color, marginTop: 14, maxWidth: 1080 }}>{text}</div>;
};

// ------------------------------------------------------------------ scene 1
const Title: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sc = spring({ frame: f, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ background: C.cream, fontFamily: FONT, color: C.ink, alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${0.92 + 0.08 * sc})`, opacity: sc, textAlign: "center" }}>
        <div style={{ fontSize: 120, fontWeight: 800, letterSpacing: 2, color: C.saffron }}>Pramana</div>
        <div style={{ fontSize: 32, marginTop: 8 }}>A timestamped source of truth for rules, shown on synthetic data.</div>
        <div style={{ fontSize: 20, marginTop: 26, color: C.muted }}>Agravaani Research</div>
      </div>
      <div style={{ position: "absolute", bottom: 40, fontSize: 18, color: C.muted }}>Everything in this video is synthetic and for illustrative purposes only.</div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ scene 2
const Timeline: React.FC<{ showCircular: number; showAct: number; showBack: number }> = ({ showCircular, showAct, showBack }) => {
  const x = (d: number) => 100 + (d / 12) * 760; // not to scale near the right end
  const actX = 800, circX = 890;
  return (
    <svg width={1140} height={270} style={{ marginTop: 14 }}>
      <line x1={80} y1={150} x2={1000} y2={150} stroke={C.muted} strokeWidth={3} />
      {[1, 4, 8, 12].map((d) => (
        <g key={d}>
          <line x1={x(d - 1)} y1={142} x2={x(d - 1)} y2={158} stroke={C.muted} strokeWidth={2} />
          <text x={x(d - 1)} y={184} fontSize={18} fill={C.muted} textAnchor="middle">{d} Dec</text>
        </g>
      ))}
      <g opacity={showAct}>
        <circle cx={actX} cy={150} r={11} fill={C.olive} />
        <text x={actX + 20} y={214} fontSize={20} fill={C.olive} textAnchor="end" fontWeight={700}>Return filed, 4:00 pm</text>
      </g>
      <g opacity={showCircular}>
        <circle cx={circX} cy={150} r={11} fill={C.terra} />
        <text x={circX + 30} y={246} fontSize={20} fill={C.terra} textAnchor="end" fontWeight={700}>Circular published, 5:00 pm</text>
      </g>
      <g opacity={showBack}>
        <path d={`M ${circX} 134 C ${x(8)} 14, ${x(2)} 14, ${x(0)} 134`} fill="none" stroke={C.terra} strokeWidth={4} strokeDasharray="10 8" />
        <polygon points={`${x(0) - 10},128 ${x(0) + 10},128 ${x(0)},148`} fill={C.terra} />
        <text x={x(5.5)} y={34} fontSize={20} fill={C.terra} textAnchor="middle" fontWeight={700}>States that it applies from 1 December</text>
      </g>
    </svg>
  );
};

const Problem: React.FC = () => {
  const a = useIn(10), b = useIn(60), c = useIn(110);
  return (
    <Frame title="The problem">
      <Timeline showAct={a} showCircular={b} showBack={c} />
      <Caption delay={10} text="A company files its annual return at 4:00 pm on 12 December." />
      <Caption delay={60} text="An hour later, a circular is published that shortens the deadline." />
      <Caption delay={110} color={C.terra} text="The circular says it applies from 1 December, so the filing is now judged by a rule that did not exist when it was made." />
    </Frame>
  );
};

// ------------------------------------------------------------------ scene 3
const Lane: React.FC<{ label: string; verdict: string; sub: string; color: string; delay: number }> = ({ label, verdict, sub, color, delay }) => {
  const o = useIn(delay, 24);
  return (
    <div style={{ opacity: o, transform: `translateX(${(1 - o) * -40}px)`, flex: 1, background: C.paper, border: `3px solid ${color}`, borderRadius: 14, padding: "24px 28px" }}>
      <div style={{ fontSize: 22, color, fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 40, fontWeight: 800, margin: "10px 0" }}>{verdict}</div>
      <div style={{ fontSize: 22, lineHeight: 1.4 }}>{sub}</div>
    </div>
  );
};
const Regimes: React.FC = () => (
  <Frame title="Two ways to judge the same act">
    <div style={{ display: "flex", gap: 28, marginTop: 28 }}>
      <Lane delay={8} color={C.terra} label="Legacy practice" verdict="45 days" sub="The backdated circular is applied afterwards, so a filing that was on time becomes late." />
      <Lane delay={40} color={C.olive} label="The Pramana rule" verdict="60 days" sub="The circular operates only from the moment it was published, so the 4:00 pm filing is judged by the 60 day rule, then and always." />
    </div>
    <Caption delay={90} text="From 5:00 pm onwards, the 45 day rule applies to everyone, and the record shows exactly when it began." />
  </Frame>
);

// ------------------------------------------------------------------ scene 4
const Card: React.FC<{ n: string; head: string; body: string; code: string; delay: number }> = ({ n, head, body, code, delay }) => {
  const o = useIn(delay, 22);
  return (
    <div style={{ opacity: o, transform: `translateY(${(1 - o) * 30}px)`, flex: 1, background: C.paper, border: `3px solid ${C.saffron}`, borderRadius: 14, padding: "22px 24px" }}>
      <div style={{ fontSize: 44, fontWeight: 800, color: C.saffron }}>{n}</div>
      <div style={{ fontSize: 26, fontWeight: 700, margin: "6px 0 10px" }}>{head}</div>
      <div style={{ fontSize: 20, lineHeight: 1.45 }}>{body}</div>
      <div style={{ fontFamily: MONO, fontSize: 16, marginTop: 14, background: C.sand, display: "inline-block", padding: "2px 8px", borderRadius: 4 }}>{code}</div>
    </div>
  );
};
const Elements: React.FC = () => (
  <Frame title="Three simple requirements, one engine">
    <div style={{ display: "flex", gap: 22, marginTop: 28 }}>
      <Card delay={8} n="1" head="One source of truth" body="A rule that is not published in the ledger does not apply." code="ledger.py" />
      <Card delay={38} n="2" head="Every change timestamped" body="The ledger sets the publication time, and it can never move backwards." code="model.py" />
      <Card delay={68} n="3" head="The law shown as a whole" body="The diffs are folded into the whole instrument as it stood at any moment." code="state.py" />
    </div>
    <Caption delay={110} size={24} text="These are the properties of a diff-first state engine, applied here to rules instead of clinical records." />
  </Frame>
);

// ------------------------------------------------------------------ scene 5
const Chain: React.FC = () => {
  const f = useCurrentFrame();
  const n = 6;
  const tamperAt = 110;
  const broken = f > tamperAt;
  const anchorO = useIn(190, 20);
  return (
    <Frame title="Tampering leaves a trace">
      <svg width={1140} height={230} style={{ marginTop: 28 }}>
        {Array.from({ length: n }).map((_, i) => {
          const o = interpolate(f, [8 + i * 12, 22 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const bad = broken && i >= 3;
          const col = bad ? C.terra : C.olive;
          const x = 20 + i * 185;
          return (
            <g key={i} opacity={o}>
              {i > 0 && <line x1={x - 22} y1={100} x2={x} y2={100} stroke={bad ? C.terra : C.muted} strokeWidth={4} strokeDasharray={bad && i === 3 ? "6 6" : "0"} />}
              <rect x={x} y={50} width={150} height={100} rx={12} fill={C.paper} stroke={col} strokeWidth={4} />
              <text x={x + 75} y={88} fontSize={20} fontWeight={700} textAnchor="middle" fill={C.ink}>Entry {i + 10}</text>
              <text x={x + 75} y={118} fontSize={14} fontFamily={MONO} textAnchor="middle" fill={C.muted}>{bad ? "hash mismatch" : "hash ok"}</text>
            </g>
          );
        })}
        {f > tamperAt && f < tamperAt + 60 && (
          <text x={20 + 3 * 185 + 75} y={40} fontSize={20} fontWeight={700} fill={C.terra} textAnchor="middle">Quiet edit</text>
        )}
        <g opacity={anchorO}>
          <rect x={780} y={180} width={340} height={42} rx={8} fill={C.sand} />
          <text x={950} y={208} fontSize={18} fontFamily={MONO} textAnchor="middle" fill={C.ink}>anchor published elsewhere</text>
        </g>
      </svg>
      <Caption delay={110} color={C.terra} text="A quiet edit to one amendment breaks the chain at exactly that entry." />
      <Caption delay={150} text="A fully rewritten history looks clean to the chain alone, so the head hash must be published somewhere the operator does not control." />
    </Frame>
  );
};

// ------------------------------------------------------------------ scene 6
const Stability: React.FC = () => {
  const st: any[] = (fuzz as any).stability;
  const max = 10;
  const f = useCurrentFrame();
  return (
    <Frame title="Does the law judged at a fixed moment stay put?">
      <svg width={1140} height={330} style={{ marginTop: 10 }}>
        <line x1={70} y1={290} x2={1100} y2={290} stroke={C.muted} strokeWidth={2} />
        {st.map((s, i) => {
          const g = interpolate(f, [12 + i * 14, 40 + i * 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const h = (s.legacy_rate * 100 / max) * 240 * g;
          const x = 130 + i * 250;
          return (
            <g key={i}>
              <rect x={x} y={290 - h} width={80} height={h} fill={C.terra} />
              <text x={x + 40} y={290 - h - 8} fontSize={20} textAnchor="middle" fontWeight={700}>{(s.legacy_rate * 100).toFixed(1)}%</text>
              <rect x={x + 90} y={286} width={80} height={4} fill={C.olive} />
              <text x={x + 130} y={278} fontSize={18} textAnchor="middle" fill={C.olive} fontWeight={700}>0</text>
              <text x={x + 85} y={322} fontSize={18} textAnchor="middle" fill={C.muted}>{(s.retro_share * 100).toFixed(0)}% backdated</text>
            </g>
          );
        })}
      </svg>
      <Caption delay={60} size={24} text="Red is legacy practice and green is the Pramana rule, across thousands of probes on random synthetic ledgers." />
      <Caption delay={95} size={24} color={C.muted} text="The zero is true by construction and is checked, not discovered. The red bars show that the measurement works, not how often this happens in practice." />
    </Frame>
  );
};

// ------------------------------------------------------------------ scene 7
const Discretion: React.FC = () => {
  const f = useCurrentFrame();
  const ung: any[] = (sweep as any).ungated;
  const gat: any[] = (sweep as any).gated;
  const X = (d: number) => 90 + (d / 40) * 960;
  const Y = (v: number) => 300 - v * 260;
  const path = (rows: any[], key: string) => rows.map((r, i) => `${i ? "L" : "M"} ${X(r.edge_clauses ?? r.proposed)} ${Y(r[key])}`).join(" ");
  const reveal = interpolate(f, [10, 120], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const L = 2000;
  return (
    <Frame title="How often does the rulebook leave a choice?">
      <svg width={1140} height={350} style={{ marginTop: 6 }}>
        <line x1={90} y1={300} x2={1060} y2={300} stroke={C.muted} strokeWidth={2} />
        <line x1={90} y1={40} x2={90} y2={300} stroke={C.muted} strokeWidth={2} />
        <text x={575} y={338} fontSize={18} fill={C.muted} textAnchor="middle">Exception clauses added to one universal rule</text>
        {[
          { d: path(ung, "raw_mean"), c: C.terra, t: "No precedence rule" },
          { d: path(ung, "resolved_mean"), c: C.saffron, t: "Most specific clause wins" },
          { d: path(gat, "resolved_mean"), c: C.olive, t: "Conflict gate at publication" },
        ].map((p, i) => (
          <g key={i}>
            <path d={p.d} fill="none" stroke={p.c} strokeWidth={5} pathLength={1} strokeDasharray="1" strokeDashoffset={1 - reveal} strokeLinecap="round" />
            <rect x={600} y={76 + i * 30} width={18} height={6} fill={p.c} />
            <text x={628} y={84 + i * 30} fontSize={18}>{p.t}</text>
          </g>
        ))}
      </svg>
      <Caption delay={80} size={24} text="Detail written in to settle rare disputes can leave an official with more choice, because more clauses now apply to the same facts." />
      <Caption delay={120} size={22} color={C.muted} text="These curves belong to the synthetic generator and say nothing about any real statute." />
    </Frame>
  );
};

// ------------------------------------------------------------------ scene 8
const Close: React.FC = () => {
  const o = useIn(6, 24);
  return (
    <AbsoluteFill style={{ background: C.cream, fontFamily: FONT, color: C.ink, alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ opacity: o }}>
        <div style={{ fontSize: 64, fontWeight: 800, color: C.saffron }}>Pramana</div>
        <div style={{ fontSize: 30, marginTop: 16 }}>The engine, the schemas, the test bed and the deployment guide are open.</div>
        <div style={{ fontFamily: MONO, fontSize: 26, marginTop: 22, background: C.sand, display: "inline-block", padding: "6px 16px", borderRadius: 6 }}>github.com/agravaaniresearch/pramana</div>
        <div style={{ fontSize: 20, marginTop: 30, color: C.muted, maxWidth: 900, margin: "30px auto 0" }}>
          The proposal behind it was described by Sanjeev Sanyal. This prototype is independent and has not been reviewed by him or by anyone drafting the law.
        </div>
        <div style={{ fontSize: 18, marginTop: 18, color: C.muted }}>Code and runs are synthetic and for illustrative purposes only.</div>
      </div>
    </AbsoluteFill>
  );
};

export const Explainer: React.FC = () => {
  const t = linearTiming({ durationInFrames: TRANS });
  const scenes = [Title, Problem, Regimes, Elements, Chain, Stability, Discretion, Close];
  const pres = [fade(), slide({ direction: "from-right" }), fade(), slide({ direction: "from-bottom" }), fade(), slide({ direction: "from-right" }), fade()];
  return (
    <TransitionSeries>
      {scenes.map((Sc, i) => (
        <React.Fragment key={i}>
          <TransitionSeries.Sequence durationInFrames={DURS[i]}><Sc /></TransitionSeries.Sequence>
          {i < scenes.length - 1 && <TransitionSeries.Transition presentation={pres[i]} timing={t} />}
        </React.Fragment>
      ))}
    </TransitionSeries>
  );
};
