// Hero artwork: a small Monte Carlo fan + cumulative wealth chart.
// Built procedurally so it renders in any theme via CSS vars.

const { useMemo } = React;

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

function generatePaths(seedBase, n, years) {
  const paths = [];
  for (let k = 0; k < n; k++) {
    const r = rng(seedBase + k * 7);
    const escal = 0.02 + r() * 0.04; // 2-6% rate escalation
    const degr = 0.004 + r() * 0.004;
    const noise = () => (r() - 0.5) * 0.06;
    const upfront = -28000;
    let cum = upfront;
    const pts = [{ x: 0, y: cum }];
    let baseSavings = 1900 + r() * 500;
    for (let y = 1; y <= years; y++) {
      baseSavings *= (1 + escal) * (1 - degr);
      cum += baseSavings * (1 + noise());
      pts.push({ x: y, y: cum });
    }
    paths.push(pts);
  }
  return paths;
}

function HeroChart({ width = 720, height = 360, theme }) {
  const years = 25;
  const paths = useMemo(() => generatePaths(42, 28, years), []);
  const altPath = useMemo(() => {
    // HYSA alt: $28k @ 4.5%
    const pts = [{ x: 0, y: -28000 }];
    let v = -28000;
    for (let y = 1; y <= years; y++) {
      v = -28000 * Math.pow(1.045, y) + (-28000 - (-28000)); // grows toward 0+
      // actually show opportunity-cost line: capital deployed here would have grown
      pts.push({ x: y, y: -28000 + (28000 * (Math.pow(1.045, y) - 1)) });
    }
    return pts;
  }, []);

  const pad = { l: 56, r: 24, t: 18, b: 32 };
  const W = width, H = height;
  const allY = paths.flat().map(p => p.y).concat(altPath.map(p => p.y));
  const yMin = Math.min(...allY) * 1.05;
  const yMax = Math.max(...allY) * 1.05;
  const xScale = x => pad.l + (x / years) * (W - pad.l - pad.r);
  const yScale = y => pad.t + (1 - (y - yMin) / (yMax - yMin)) * (H - pad.t - pad.b);

  const toPath = pts => pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ');

  // Compute fan envelope: p10/p50/p90 at each year
  const envelope = useMemo(() => {
    const p10 = [], p50 = [], p90 = [];
    for (let y = 0; y <= years; y++) {
      const vals = paths.map(p => p[y].y).sort((a, b) => a - b);
      p10.push({ x: y, y: vals[Math.floor(vals.length * 0.1)] });
      p50.push({ x: y, y: vals[Math.floor(vals.length * 0.5)] });
      p90.push({ x: y, y: vals[Math.floor(vals.length * 0.9)] });
    }
    return { p10, p50, p90 };
  }, [paths]);

  const fanArea = [...envelope.p90, ...envelope.p10.slice().reverse()]
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${xScale(p.x).toFixed(1)},${yScale(p.y).toFixed(1)}`).join(' ') + ' Z';

  const yTicks = [];
  const tickStep = 25000;
  const tStart = Math.ceil(yMin / tickStep) * tickStep;
  for (let v = tStart; v <= yMax; v += tickStep) yTicks.push(v);

  const xTicks = [0, 5, 10, 15, 20, 25];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="fan-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.04" />
        </linearGradient>
      </defs>
      {/* gridlines */}
      {yTicks.map((v, i) => (
        <g key={`y${i}`}>
          <line x1={pad.l} x2={W - pad.r} y1={yScale(v)} y2={yScale(v)} stroke="var(--rule)" strokeWidth="1" />
          <text x={pad.l - 8} y={yScale(v) + 4} fill="var(--ink-faint)" fontSize="10" textAnchor="end" fontFamily="var(--mono-font)">
            {v >= 0 ? '$' + (v / 1000).toFixed(0) + 'k' : '−$' + (Math.abs(v) / 1000).toFixed(0) + 'k'}
          </text>
        </g>
      ))}
      {xTicks.map((v, i) => (
        <text key={`x${i}`} x={xScale(v)} y={H - 10} fill="var(--ink-faint)" fontSize="10" textAnchor="middle" fontFamily="var(--mono-font)">
          y{v}
        </text>
      ))}
      {/* zero line */}
      <line x1={pad.l} x2={W - pad.r} y1={yScale(0)} y2={yScale(0)} stroke="var(--rule-strong)" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />

      {/* fan */}
      <path d={fanArea} fill="url(#fan-grad)" stroke="none" />

      {/* individual sims, faint */}
      {paths.map((p, i) => (
        <path key={i} d={toPath(p)} fill="none" stroke="var(--accent)" strokeWidth="0.6" opacity="0.18" />
      ))}

      {/* alt-investment line (HYSA) */}
      <path d={toPath(altPath)} fill="none" stroke="var(--ink-dim)" strokeWidth="1.5" strokeDasharray="4 3" />

      {/* median */}
      <path d={toPath(envelope.p50)} fill="none" stroke="var(--accent)" strokeWidth="2.25" />

      {/* labels */}
      <g fontFamily="var(--mono-font)" fontSize="10">
        <text x={W - pad.r - 4} y={yScale(envelope.p50[years].y) - 6} fill="var(--accent)" textAnchor="end">solar · median</text>
        <text x={W - pad.r - 4} y={yScale(altPath[years].y) - 6} fill="var(--ink-dim)" textAnchor="end">HYSA 4.5% alt</text>
        <text x={W - pad.r - 4} y={yScale(envelope.p90[years].y) + 12} fill="var(--ink-faint)" textAnchor="end">p90</text>
        <text x={W - pad.r - 4} y={yScale(envelope.p10[years].y) + 12} fill="var(--ink-faint)" textAnchor="end">p10</text>
      </g>
    </svg>
  );
}

window.HeroChart = HeroChart;
