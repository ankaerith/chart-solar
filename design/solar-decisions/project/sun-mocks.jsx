// Sun backdrop options — 6 variations on the editorial sun-line motif.
// Each artboard reproduces a representative slice of the hero so the sun
// can be evaluated against the actual content density and panel chrome.

const { useState } = React;

// ---- shared mock content ---------------------------------------------

function MockHero({ children }) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', background: 'var(--bg)' }}>
      {children}
      <div style={{
        position: 'relative', zIndex: 2,
        display: 'grid', gridTemplateColumns: '1.05fr 1fr',
        gap: 56, padding: '60px 56px 0',
        height: '100%',
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.18em',
            textTransform: 'uppercase', color: 'var(--accent-2)', marginBottom: 16,
          }}>Plan it · Check it · Track it</div>
          <h1 style={{
            fontFamily: 'var(--display-font)', fontWeight: 500, letterSpacing: '-0.005em',
            fontSize: 72, lineHeight: 1.02, margin: '0 0 22px', textWrap: 'balance',
          }}>The honest math<br />for your roof.</h1>
          <p style={{
            fontSize: 17, lineHeight: 1.55, color: 'var(--ink-2)',
            maxWidth: 460, margin: '0 0 28px',
          }}>
            Residential solar is sold on 25-year promises built from optimistic
            assumptions. We run the numbers independently — hourly physics,
            Monte Carlo on rate paths, every alternative your capital could be
            doing instead.
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <button style={{
              padding: '12px 18px', background: 'var(--ink)', color: 'var(--bg)',
              border: 'none', borderRadius: 'var(--radius)', cursor: 'pointer',
              fontFamily: 'var(--body-font)', fontSize: 14, fontWeight: 500,
            }}>Start free forecast →</button>
            <button style={{
              padding: '12px 18px', background: 'transparent', color: 'var(--ink)',
              border: '1px solid var(--rule-strong)', borderRadius: 'var(--radius)',
              cursor: 'pointer', fontFamily: 'var(--body-font)', fontSize: 14, fontWeight: 500,
            }}>Audit my proposal · $79</button>
          </div>
        </div>
        <div style={{ position: 'relative' }}>
          <MockPanel />
        </div>
      </div>
    </div>
  );
}

function MockPanel() {
  return (
    <div style={{
      background: 'var(--panel)', border: '1px solid var(--rule)',
      borderRadius: 'var(--radius-lg)', padding: 22,
      display: 'flex', flexDirection: 'column', gap: 14,
      height: 'calc(100% - 60px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.14em',
          textTransform: 'uppercase', color: 'var(--ink-faint)',
        }}>cumulative net wealth · 25 yr</div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 10.5, color: 'var(--ink-dim)',
        }}>n = 28 sims</div>
      </div>
      {/* mock chart — fan of lines */}
      <svg viewBox="0 0 360 220" style={{ width: '100%', flex: 1 }}>
        {Array.from({ length: 18 }).map((_, i) => {
          const y0 = 200, y1 = 60 + (i % 5) * 14, y2 = 120 + (i % 7) * 10;
          return <path key={i} d={`M0 ${y0} Q120 ${y1} 360 ${y2}`}
            fill="none" stroke="var(--accent)" strokeWidth="0.7" opacity="0.35" />;
        })}
        <path d="M0 200 Q120 80 360 60" fill="none" stroke="var(--accent)" strokeWidth="2" />
        <line x1="0" y1="160" x2="360" y2="160" stroke="var(--rule-strong)" strokeWidth="0.8" strokeDasharray="3 3" />
      </svg>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid var(--rule)' }}>
        <div style={{ padding: '12px 14px 0 0', borderRight: '1px solid var(--rule)' }}>
          <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink-faint)' }}>median NPV</div>
          <div style={{ fontFamily: 'var(--display-font)', fontSize: 28, marginTop: 4, color: 'var(--accent)' }}>+$31,400</div>
        </div>
        <div style={{ padding: '12px 0 0 14px' }}>
          <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink-faint)' }}>payback</div>
          <div style={{ fontFamily: 'var(--display-font)', fontSize: 28, marginTop: 4 }}>11.2 yr</div>
        </div>
      </div>
    </div>
  );
}

// ---- the six sun variants --------------------------------------------

// V1 — current: small disc, far rings (baseline for compare)
function SunV1_Current() {
  const cx = 1100, cy = -40;
  const rings = [140, 220, 320, 440, 580, 740, 920];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent)" strokeWidth="1">
        {rings.map((r, i) => <circle key={i} cx={cx} cy={cy} r={r} opacity={0.18 - i * 0.018} />)}
      </g>
      <circle cx={cx} cy={cy} r={70} fill="var(--accent)" opacity="0.85" />
    </svg>
  );
}

// V2 — visible sun: bigger, lower; light tone, more rings, all subtle
function SunV2_VisibleLight() {
  const cx = 1080, cy = 80, R = 110;
  const rings = [150, 200, 260, 330, 410, 500, 600, 720, 860];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent)" strokeWidth="1">
        {rings.map((r, i) => <circle key={i} cx={cx} cy={cy} r={r} opacity={0.10 - i * 0.008} />)}
      </g>
      <circle cx={cx} cy={cy} r={R} fill="var(--accent)" opacity="0.16" />
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="var(--accent)" strokeWidth="1" opacity="0.22" />
    </svg>
  );
}

// V3 — most visible: bigger sun, fully on-canvas, slight warm fill
function SunV3_Prominent() {
  const cx = 1020, cy = 140, R = 130;
  const rings = [170, 230, 300, 380, 470, 570, 690, 830];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent)" strokeWidth="1">
        {rings.map((r, i) => <circle key={i} cx={cx} cy={cy} r={r} opacity={0.13 - i * 0.011} />)}
      </g>
      <circle cx={cx} cy={cy} r={R + 6} fill="none" stroke="var(--accent)" strokeWidth="1" opacity="0.30" />
      <circle cx={cx} cy={cy} r={R} fill="var(--accent)" opacity="0.20" />
    </svg>
  );
}

// V4 — varied stroke weights: thicker disc-edge, thinner outer rings
function SunV4_Tonal() {
  const cx = 1060, cy = 110, R = 120;
  const rings = [
    { r: 165, w: 1.2, op: 0.22 },
    { r: 220, w: 1.0, op: 0.18 },
    { r: 285, w: 0.9, op: 0.14 },
    { r: 360, w: 0.8, op: 0.11 },
    { r: 445, w: 0.7, op: 0.09 },
    { r: 540, w: 0.6, op: 0.07 },
    { r: 650, w: 0.5, op: 0.05 },
    { r: 780, w: 0.5, op: 0.04 },
  ];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent)">
        {rings.map((rr, i) => <circle key={i} cx={cx} cy={cy} r={rr.r} strokeWidth={rr.w} opacity={rr.op} />)}
      </g>
      <circle cx={cx} cy={cy} r={R} fill="var(--accent)" opacity="0.18" />
    </svg>
  );
}

// V5 — dashed alternation: solid disc + alternating solid/dashed rings
function SunV5_Dashed() {
  const cx = 1060, cy = 90, R = 115;
  const rings = [155, 210, 275, 350, 430, 525, 635, 760];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent)" strokeWidth="0.9">
        {rings.map((r, i) => (
          <circle key={i} cx={cx} cy={cy} r={r}
            opacity={0.16 - i * 0.013}
            strokeDasharray={i % 2 ? '0' : '3 5'} />
        ))}
      </g>
      <circle cx={cx} cy={cy} r={R} fill="var(--accent)" opacity="0.22" />
    </svg>
  );
}

// V6 — secondary color (oxblood accent-2) for an editorial twist
function SunV6_Oxblood() {
  const cx = 1060, cy = 100, R = 115;
  const rings = [160, 220, 290, 370, 460, 560, 680, 820];
  return (
    <svg viewBox="0 0 1280 720" preserveAspectRatio="xMaxYMin slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
      <g fill="none" stroke="var(--accent-2)" strokeWidth="1">
        {rings.map((r, i) => <circle key={i} cx={cx} cy={cy} r={r} opacity={0.12 - i * 0.010} />)}
      </g>
      <circle cx={cx} cy={cy} r={R} fill="var(--accent-2)" opacity="0.18" />
    </svg>
  );
}

// ---- canvas ----------------------------------------------------------

const ART_W = 1280;
const ART_H = 720;

function App() {
  const variants = [
    { id: 'v1', label: 'V1 · current (baseline)', sub: 'small disc anchored above viewport, 7 rings, single opacity ramp', cmp: SunV1_Current },
    { id: 'v2', label: 'V2 · visible & light', sub: 'bigger disc on-canvas, lighter fill, more rings', cmp: SunV2_VisibleLight },
    { id: 'v3', label: 'V3 · prominent', sub: 'larger disc lower in the field, halo ring, warm fill', cmp: SunV3_Prominent },
    { id: 'v4', label: 'V4 · tonal weights', sub: 'thicker rings near the disc, taper to hairline outside', cmp: SunV4_Tonal },
    { id: 'v5', label: 'V5 · dashed alternation', sub: 'alternating solid/dashed rings — more architectural', cmp: SunV5_Dashed },
    { id: 'v6', label: 'V6 · oxblood accent', sub: 'secondary color — editorial, off-brand for "sun" but striking', cmp: SunV6_Oxblood },
  ];
  return (
    <DesignCanvas>
      <DCSection id="suns" title="Hero sun backdrop — six options"
        subtitle="Each artboard is a 1280 × 720 slice of the hero. Click any to focus.">
        {variants.map(v => (
          <DCArtboard key={v.id} id={v.id} label={v.label}
            width={ART_W} height={ART_H}>
            <MockHero>
              <v.cmp />
            </MockHero>
          </DCArtboard>
        ))}
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
