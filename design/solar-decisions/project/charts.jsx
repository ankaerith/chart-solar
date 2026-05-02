// Charts module — additional chart primitives beyond the hero.

const { useMemo: useMemoCh } = React;

// Sparkline-style monthly bar chart (production vs consumption)
function MonthlyBars({ data, height = 160 }) {
  // data: [{ m, gen, use }]
  const max = Math.max(...data.map(d => Math.max(d.gen, d.use))) * 1.1;
  const W = 600, H = height, pad = { l: 36, r: 12, t: 12, b: 22 };
  const bw = (W - pad.l - pad.r) / data.length;
  const yScale = v => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="xMidYMid meet" style={{ display: 'block' }}>
      {[0.25, 0.5, 0.75, 1].map((p, i) => (
        <line key={i} x1={pad.l} x2={W - pad.r} y1={pad.t + (1 - p) * (H - pad.t - pad.b)} y2={pad.t + (1 - p) * (H - pad.t - pad.b)} stroke="var(--rule)" strokeDasharray="2 3" strokeWidth="0.8" />
      ))}
      {data.map((d, i) => {
        const x = pad.l + i * bw;
        const cx = x + bw / 2;
        return (
          <g key={i}>
            <rect x={x + 4} y={yScale(d.use)} width={bw / 2 - 5} height={H - pad.b - yScale(d.use)} fill="var(--rule-strong)" opacity="0.18" />
            <rect x={x + bw / 2 + 1} y={yScale(d.gen)} width={bw / 2 - 5} height={H - pad.b - yScale(d.gen)} fill="var(--accent)" />
            <text x={cx} y={H - 8} textAnchor="middle" fontSize="9" fontFamily="var(--mono-font)" fill="var(--ink-faint)">{d.m}</text>
          </g>
        );
      })}
      <text x={pad.l} y={pad.t - 2} fontSize="9" fontFamily="var(--mono-font)" fill="var(--ink-faint)">kWh</text>
    </svg>
  );
}

// 24-hour battery dispatch chart (rule-based: charge off-peak, discharge at peak)
function BatteryDispatch({ height = 200 }) {
  const hours = useMemoCh(() => {
    const h = [];
    for (let i = 0; i < 24; i++) {
      const solar = Math.max(0, Math.sin((i - 6) / 12 * Math.PI)) * 4.5;
      const load = 0.8 + (i >= 17 && i <= 22 ? 2.4 : 0.4) + Math.sin(i / 4) * 0.2;
      const isOnPeak = i >= 16 && i <= 21;
      const isOffPeak = i >= 0 && i <= 6;
      let battery = 0; // +charge, -discharge
      if (isOffPeak) battery = 1.5;
      else if (isOnPeak) battery = -2.2;
      else if (solar > load) battery = Math.min(solar - load, 1.5);
      h.push({ i, solar, load, battery, isOnPeak });
    }
    return h;
  }, []);
  const W = 700, H = height, pad = { l: 36, r: 60, t: 14, b: 24 };
  const max = 5.5, min = -3;
  const yS = v => pad.t + (1 - (v - min) / (max - min)) * (H - pad.t - pad.b);
  const xS = i => pad.l + (i / 23) * (W - pad.l - pad.r);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="xMidYMid meet" style={{ display: 'block' }}>
      {/* on-peak band */}
      <rect x={xS(16)} y={pad.t} width={xS(21) - xS(16)} height={H - pad.t - pad.b} fill="var(--accent-2)" opacity="0.06" />
      <text x={(xS(16) + xS(21)) / 2} y={pad.t + 10} fontSize="9" fontFamily="var(--mono-font)" textAnchor="middle" fill="var(--accent-2)" letterSpacing="0.1em">ON-PEAK</text>
      {/* zero line */}
      <line x1={pad.l} x2={W - pad.r} y1={yS(0)} y2={yS(0)} stroke="var(--rule-strong)" strokeWidth="0.8" />
      {/* solar */}
      <path d={hours.map((d, i) => `${i === 0 ? 'M' : 'L'}${xS(d.i)},${yS(d.solar)}`).join(' ') + ` L${xS(23)},${yS(0)} L${xS(0)},${yS(0)} Z`}
        fill="var(--accent)" opacity="0.18" />
      <path d={hours.map((d, i) => `${i === 0 ? 'M' : 'L'}${xS(d.i)},${yS(d.solar)}`).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="1.6" />
      {/* load */}
      <path d={hours.map((d, i) => `${i === 0 ? 'M' : 'L'}${xS(d.i)},${yS(d.load)}`).join(' ')} fill="none" stroke="var(--ink)" strokeWidth="1.4" strokeDasharray="3 3" />
      {/* battery bars */}
      {hours.map((d, i) => (
        <rect key={i}
          x={xS(d.i) - 6} y={d.battery >= 0 ? yS(d.battery) : yS(0)}
          width={12} height={Math.abs(yS(d.battery) - yS(0))}
          fill={d.battery >= 0 ? 'var(--good)' : 'var(--accent-2)'}
          opacity="0.7" />
      ))}
      {/* x ticks */}
      {[0, 6, 12, 18, 23].map(i => (
        <text key={i} x={xS(i)} y={H - 8} fontSize="9" fontFamily="var(--mono-font)" textAnchor="middle" fill="var(--ink-faint)">{String(i).padStart(2, '0')}:00</text>
      ))}
      {/* legend */}
      <g fontFamily="var(--mono-font)" fontSize="9.5">
        <text x={W - pad.r + 6} y={yS(4) + 3} fill="var(--accent)">solar</text>
        <text x={W - pad.r + 6} y={yS(2.5) + 3} fill="var(--ink-2)">load</text>
        <text x={W - pad.r + 6} y={yS(1) + 3} fill="var(--good)">+chg</text>
        <text x={W - pad.r + 6} y={yS(-1.5) + 3} fill="var(--accent-2)">−dis</text>
      </g>
    </svg>
  );
}

// Tornado sensitivity chart
function TornadoChart({ items, height = 220 }) {
  // items: [{ name, low, high }] — impact range on NPV
  const max = Math.max(...items.flatMap(i => [Math.abs(i.low), Math.abs(i.high)]));
  const W = 600, H = height, pad = { l: 200, r: 80, t: 12, b: 12 };
  const rowH = (H - pad.t - pad.b) / items.length;
  const xS = v => pad.l + (W - pad.l - pad.r) / 2 + (v / max) * (W - pad.l - pad.r) / 2;
  const center = pad.l + (W - pad.l - pad.r) / 2;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" preserveAspectRatio="xMidYMid meet" style={{ display: 'block' }}>
      <line x1={center} x2={center} y1={pad.t} y2={H - pad.b} stroke="var(--rule-strong)" strokeWidth="1" />
      {items.map((it, i) => {
        const y = pad.t + i * rowH + rowH / 2;
        const lowX = xS(it.low), highX = xS(it.high);
        const left = Math.min(lowX, highX), right = Math.max(lowX, highX);
        return (
          <g key={i}>
            <text x={pad.l - 12} y={y + 3} textAnchor="end" fontSize="11.5" fontFamily="var(--body-font)" fill="var(--ink-2)">{it.name}</text>
            <rect x={left} y={y - 9} width={right - left} height={18} fill="var(--accent)" opacity="0.85" />
            <text x={lowX < center ? left - 4 : right + 4} y={y + 3} fontSize="9.5" fontFamily="var(--mono-font)" fill="var(--ink-dim)" textAnchor={lowX < center ? 'end' : 'start'}>
              {(it.low / 1000).toFixed(0)}k
            </text>
            <text x={highX > center ? right + 4 : left - 4} y={y + 3} fontSize="9.5" fontFamily="var(--mono-font)" fill="var(--ink-dim)" textAnchor={highX > center ? 'start' : 'end'}>
              {(it.high / 1000).toFixed(0)}k
            </text>
          </g>
        );
      })}
    </svg>
  );
}

Object.assign(window, { MonthlyBars, BatteryDispatch, TornadoChart });
