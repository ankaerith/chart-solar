// Tier system + Locked primitive.
//
// Three tiers:
//   free      — Basic forecast: median NPV, payback, headline grid (n=50 sims).
//                Hides: capital-allocation diff, tornado sensitivity, battery
//                hourly dispatch, NEM 3.0 modeling, methodology PDF, scenario diff.
//   pack      — $79 one-time. Decision Pack. Full Explore depth + 1 audit credit.
//                Unlocks everything above + Monte Carlo n=500 + scenario versioning.
//   founders  — $129 one-time. Decision Pack + 3 audit credits + first 12 months
//                of Track included. The "we paid for the build" tier.

const TIERS = {
  free: {
    label: 'Basic',
    price: 'Free',
    blurb: 'Get the verdict. Not the workshop.',
    features: ['median_npv', 'payback', 'crossover', 'co2', 'sims_50'],
  },
  pack: {
    label: 'Decision Pack',
    price: '$79',
    priceSub: 'one-time',
    blurb: 'Every knob, every scenario, plus one proposal audit.',
    features: ['median_npv','payback','crossover','co2','sims_500',
      'scenarios','sensitivity','battery_hourly','nem3','tou_arbitrage',
      'opportunity_cost','sale_scenario','methodology_pdf','share_link',
      'audit_credits_1'],
  },
  founders: {
    label: 'Founders',
    price: '$129',
    priceSub: 'one-time · limited · year 1',
    blurb: 'Decision Pack + 3 audit credits + 12 months of Track.',
    features: ['median_npv','payback','crossover','co2','sims_500',
      'scenarios','sensitivity','battery_hourly','nem3','tou_arbitrage',
      'opportunity_cost','sale_scenario','methodology_pdf','share_link',
      'audit_credits_3','track_12mo','dealer_fee_audit','priority_support'],
  },
};

function hasFeature(tier, key) { return TIERS[tier].features.includes(key); }

// Pass-through if entitled; render nothing if locked. Locking is now
// consolidated into the WorkshopTeaser block, so the per-section gate
// just hides locked content rather than reserving its full height.
function Locked({ feature, tier, children }) {
  if (hasFeature(tier, feature)) return children;
  return null;
}

// ---- DEMO DATA for previews -----------------------------------------------
// Deliberately rounded / "obviously sample" — real audits feel granular.
const DEMO_SCENARIOS = [
  { label: 'Solar — cash', value: 38000, delta: 'best NPV', bar: undefined },
  { label: 'Solar — loan (8.0% eff.)', value: 16000, delta: 'dealer fee drag' },
  { label: 'Solar — lease (3.0% esc.)', value: 4000, delta: 'title with installer', bar: 'var(--warn)' },
  { label: 'Solar — PPA', value: -2000, delta: 'net negative' },
  { label: 'HYSA @ 4.5%', value: 28000, delta: 'opportunity cost', bar: 'var(--ink-dim)' },
  { label: 'S&P 500 @ 7%', value: 50000, delta: 'higher risk', bar: 'var(--ink-dim)' },
  { label: 'Mortgage paydown @ 5.5%', value: 30000, delta: 'zero-risk equiv.', bar: 'var(--ink-dim)' },
];
const DEMO_TORNADO = [
  { name: 'Utility rate escalation', low: -20000, high: 36000 },
  { name: 'Hold duration (5–25 yr)', low: -8000, high: 18000 },
  { name: 'Federal credit availability', low: -14000, high: 4000 },
  { name: 'Annual degradation rate', low: -6000, high: 4000 },
  { name: 'Discount rate assumption', low: -10000, high: 9000 },
  { name: 'Year-1 production (±15%)', low: -7000, high: 7000 },
];

// Each preview is the real component fed obviously-sample data, behind a
// DEMO watermark and inside a Modal.
function PreviewBody({ kind }) {
  const wrap = inner => (
    <div style={{ position: 'relative' }}>
      <DemoWatermark />
      {inner}
    </div>
  );
  if (kind === 'capital') {
    const max = 60000;
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        {DEMO_SCENARIOS.map((s, i) => <ScenarioRow key={i} {...s} max={max} />)}
        <div style={{
          marginTop: 16, padding: 14, borderLeft: '2px solid var(--accent-2)',
          background: 'var(--panel-2)', fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink-2)',
        }}>
          <strong style={{ fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.1em' }}>READ:</strong>{' '}
          The financing wrapper matters more than the panels. Cash narrowly beats S&P; the loan loses to the mortgage; the PPA loses to the mattress.
        </div>
      </div>
    );
  }
  if (kind === 'tornado') {
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        <TornadoChart items={DEMO_TORNADO} />
        <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
          Rate escalation dwarfs everything. Installer estimates that hard-code 4.5% are doing you a quiet disservice.
        </div>
      </div>
    );
  }
  if (kind === 'battery') {
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        <BatteryDispatch />
        <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
          Off-peak charge fills the bank; the on-peak window discharges into your load. Under NEM 3.0 this is what makes batteries pay back.
        </div>
      </div>
    );
  }
  if (kind === 'sale') {
    const years = [5, 7, 10, 12, 15, 20, 25];
    const vals = [-4000, 2000, 12000, 19000, 26000, 32000, 38000];
    const probs = [0.06, 0.10, 0.18, 0.22, 0.18, 0.15, 0.11];
    const max = 40000;
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        <MonoLabel>Net wealth at sale year · weighted by hold-duration probability</MonoLabel>
        <div style={{ marginTop: 14 }}>
          {years.map((y, i) => (
            <div key={y} style={{ display: 'grid', gridTemplateColumns: '60px 1fr 90px 60px', gap: 12, alignItems: 'center', padding: '8px 0', borderBottom: '1px dashed var(--rule)' }}>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 12, color: 'var(--ink-2)' }}>year {y}</div>
              <div style={{ position: 'relative', height: 14, background: 'var(--panel-2)', borderRadius: 2 }}>
                <div style={{ position: 'absolute', top: 0, bottom: 0, left: vals[i] >= 0 ? '50%' : `${50 - Math.abs(vals[i])/max*50}%`, width: `${Math.abs(vals[i])/max*50}%`, background: vals[i] >= 0 ? 'var(--accent)' : 'var(--bad)' }} />
                <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'var(--ink)' }} />
              </div>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 12, color: vals[i] >= 0 ? 'var(--good)' : 'var(--bad)', textAlign: 'right', fontWeight: 600 }}>{vals[i] >= 0 ? '+' : ''}${(vals[i]/1000).toFixed(0)}k</div>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-faint)', textAlign: 'right' }}>p={probs[i].toFixed(2)}</div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
          ZIP-defaulted hold distribution. Selling at year 7 is the second-most-likely outcome and the worst financial one — installers never show this curve.
        </div>
      </div>
    );
  }
  if (kind === 'audit') {
    const flags = [
      { sev: 'high', tag: 'dealer fee', body: '21.5% fee embedded in "0.99% APR" loan. Effective real cost of capital 8.4%, not 1%.' },
      { sev: 'high', tag: 'year-1 kWh', body: 'Installer projects 11,800 kWh; our PVWatts run for this roof returns 9,940 kWh ± 8%. Overstated by ~19%.' },
      { sev: 'med', tag: 'escalation', body: 'Proposal hard-codes 4.5% utility escalation. Historical CAGR for this utility is 3.1%; over 25 yr that\u2019s a $9,400 swing.' },
      { sev: 'med', tag: 'DC:AC ratio', body: '1.41 — aggressive. Expect ~3% clipping loss on summer afternoons not reflected in the year-1 number.' },
      { sev: 'low', tag: 'panel warranty', body: '12-yr product warranty (Tier-2 module). Industry baseline is 25-yr.' },
      { sev: 'low', tag: 'monitoring', body: 'Free monitoring is 5 years; renewal is $14/mo not disclosed.' },
    ];
    const sevColor = s => s === 'high' ? 'var(--bad)' : s === 'med' ? 'var(--warn)' : 'var(--ink-dim)';
    const questions = [
      'What is the system price excluding the dealer fee, paid in cash?',
      'Which production model (PVWatts / Aurora / proprietary) generated the 11,800 kWh year-1 figure, and what shading factor was used?',
      'Will you commit to the 4.5% escalation assumption in writing if it underperforms?',
      'Why a 1.41 DC:AC ratio for this roof orientation, and what clipping loss is modeled?',
    ];
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0, border: '1px solid var(--rule)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 18 }}>
          {[
            { k: 'Quoted year-1', v: '11,800 kWh' },
            { k: 'Our model', v: '9,940 kWh' },
            { k: 'Variance', v: '−19%', tone: 'var(--bad)' },
          ].map((c, i) => (
            <div key={i} style={{ padding: '14px 16px', borderRight: i < 2 ? '1px solid var(--rule)' : 'none', background: 'var(--panel-2)' }}>
              <MonoLabel>{c.k}</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 22, marginTop: 4, fontVariantNumeric: 'tabular-nums', color: c.tone || 'var(--ink)' }}>{c.v}</div>
            </div>
          ))}
        </div>
        <MonoLabel>Flags · 6 found</MonoLabel>
        <div style={{ marginTop: 12 }}>
          {flags.map((f, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '60px 130px 1fr', gap: 12, alignItems: 'flex-start', padding: '10px 0', borderBottom: i < flags.length - 1 ? '1px dashed var(--rule)' : 'none' }}>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em', color: sevColor(f.sev), textTransform: 'uppercase', borderTop: `2px solid ${sevColor(f.sev)}`, paddingTop: 4, fontWeight: 600 }}>{f.sev}</div>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.06em', color: 'var(--ink-2)', paddingTop: 2 }}>{f.tag}</div>
              <div style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--ink-2)' }}>{f.body}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 18, padding: 14, borderLeft: '2px solid var(--accent)', background: 'var(--panel-2)' }}>
          <MonoLabel>Ask your installer</MonoLabel>
          <ol style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13, lineHeight: 1.55, color: 'var(--ink-2)' }}>
            {questions.map((q, i) => <li key={i} style={{ marginBottom: 4 }}>{q}</li>)}
          </ol>
        </div>
      </div>
    );
  }
  if (kind === 'methodology') {
    const lines = [
      { tag: 'engine', v: 'pvlib 0.11.0 · ModelChain · NREL PSM3 (lat 40.015, lon -105.270)' },
      { tag: 'irradiance', v: 'TMY 1998–2022 · GHI 4.83 kWh/m²/d · DNI 5.91 · DHI 1.74' },
      { tag: 'system', v: '7.2 kW DC · 6.0 kW AC · DC:AC 1.20 · SE5000H · azimuth 178° · tilt 18°' },
      { tag: 'losses', v: 'soiling 2% · shading 0% · clipping 0.4% · degradation yr1 2.0% then 0.55%' },
      { tag: 'tariff', v: 'Xcel CO RE-TOU · summer-on-peak $0.2891/kWh · NEM 1:1 (legacy)' },
      { tag: 'finance', v: 'discount 5.5% mortgage · escalation Monte Carlo CAGR 3.4%±1.1% · n=500 paths' },
      { tag: 'incentives', v: 'CO state tax credit 0% (none) · Xcel rebate $0 (closed) · federal credit $0 (post-2025)' },
      { tag: 'snapshot', v: 'engine v1.4.2 · tariff hash a4f9b2 · rendered 2026-04-22 14:31 MDT' },
    ];
    return wrap(
      <div style={{ padding: '8px 4px' }}>
        <MonoLabel>Methodology · every input, every source</MonoLabel>
        <div style={{ marginTop: 14, fontFamily: 'var(--mono-font)', fontSize: 12, lineHeight: 1.7, color: 'var(--ink-2)', background: 'var(--panel-2)', padding: 16, borderRadius: 'var(--radius)', border: '1px solid var(--rule)' }}>
          {lines.map((l, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: 12 }}>
              <span style={{ color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: 10.5, paddingTop: 4 }}>{l.tag}</span>
              <span>{l.v}</span>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
          Re-opening this saved forecast next year never silently re-computes. Engine, irradiance, and tariff are pinned by hash.
        </div>
      </div>
    );
  }
  return null;
}

// Single consolidated upgrade surface for Basic. Replaces three separate
// per-section gates that all said the same thing. Lists what is inside the
// Decision Pack workshop as a tight inventory, with one CTA — and each row
// has a "Preview" affordance that opens a sample-data modal so users can
// see exactly what they'd unlock before paying.
function WorkshopTeaser({ tier, onUpgrade }) {
  const [preview, setPreview] = React.useState(null);
  if (tier !== 'free') return null;
  const items = [
    { k: 'capital allocation', kind: 'capital', title: 'Compare solar vs your other capital options',
      sub: 'Solar isn\'t free; the question is whether it beats HYSA, mortgage paydown, and the index fund — over 25 years.',
      v: 'Compare solar vs HYSA, mortgage paydown, S&P 500 — the do-something-else baselines installer tools never show.' },
    { k: 'tornado sensitivity', kind: 'tornado', title: 'Which assumption actually moves your NPV',
      sub: 'Rank-ordered, dollar-weighted impact on median NPV. Tells you which knob to actually argue about.',
      v: 'Which assumption actually moves your NPV. Rank-ordered, dollar-weighted.' },
    { k: 'battery dispatch · 8760', kind: 'battery', title: 'Hour-by-hour battery dispatch',
      sub: '8,760-hour simulation. Charge off-peak, discharge at peak. NEM 3.0 / NBT and TOU arbitrage modeled.',
      v: 'Hour-by-hour charge/discharge under your tariff. NEM 3.0 + TOU arbitrage modeled.' },
    { k: 'sale-scenario · year X', kind: 'sale', title: 'What happens if you sell in year X',
      sub: 'Probability-weighted across hold duration. Solar home-value uplift, remaining loan, buyer-market conditions.',
      v: 'Probability-weighted across hold duration. Solar home-value uplift, remaining loan, buyer market.' },
    { k: 'proposal audit', kind: 'audit', title: 'Audit a real installer proposal',
      sub: 'Drop a PDF. We extract every field, diff their year-1 kWh / escalator / DC:AC / dealer fee against this baseline, and produce a one-page variance report + an ask-your-installer question list. One credit included.',
      v: 'Drop the installer’s PDF. Variance report + ask-your-installer questions. 1 credit included.' },
    { k: 'methodology PDF + share', kind: 'methodology', title: 'Every assumption, every source — pinned',
      sub: 'Engine version, irradiance source, tariff-table hash. Re-open the audit in 2030 and the numbers don\'t silently drift.',
      v: 'Every assumption, every source. Reproducible — engine + irradiance + tariff hash pinned.' },
  ];
  const t = TIERS.pack;
  const active = items.find(it => it.kind === preview);
  return (
    <Panel style={{
      padding: 0, overflow: 'hidden',
      borderColor: 'var(--rule-strong)',
    }}>
      <div style={{
        display: 'grid', gridTemplateColumns: 'minmax(0, 1.05fr) minmax(0, 1.5fr)',
        gap: 0,
      }}>
        <div style={{
          padding: '32px 32px 28px',
          background: 'var(--ink)', color: 'var(--bg)',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          minHeight: 280,
        }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '4px 10px',
              background: 'rgba(247,245,236,0.1)',
              border: '1px solid rgba(247,245,236,0.2)',
              borderRadius: 'var(--radius)',
              fontFamily: 'var(--mono-font)', fontSize: 10,
              letterSpacing: '0.16em', textTransform: 'uppercase',
              color: 'rgba(247,245,236,0.75)',
            }}>
              <svg width="10" height="10" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="3" y="6" width="8" height="6" rx="1" />
                <path d="M5 6V4.5a2 2 0 014 0V6" />
              </svg>
              Workshop · Decision Pack
            </div>
            <h3 style={{
              fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
              letterSpacing: 'var(--display-tracking)',
              fontSize: 30, lineHeight: 1.1, margin: '16px 0 12px',
            }}>You have the verdict. The work is behind this.</h3>
            <p style={{
              fontSize: 13.5, lineHeight: 1.6, margin: 0,
              color: 'rgba(247,245,236,0.78)', maxWidth: 380,
            }}>Six tools that turn the headline number into a defensible decision — plus one proposal-audit credit.</p>
          </div>
          <div style={{
            display: 'flex', alignItems: 'baseline', gap: 12,
            marginTop: 24, paddingTop: 20,
            borderTop: '1px solid rgba(247,245,236,0.18)',
          }}>
            <button onClick={onUpgrade} style={{
              padding: '12px 18px', fontSize: 14, fontWeight: 600,
              background: 'var(--bg)', color: 'var(--ink)', border: 'none',
              borderRadius: 'var(--radius)', cursor: 'pointer',
              fontFamily: 'var(--body-font)',
              display: 'inline-flex', alignItems: 'center', gap: 8,
            }}>Unlock workshop — {t.price} <Arrow /></button>
            <span style={{
              fontFamily: 'var(--mono-font)', fontSize: 11,
              color: 'rgba(247,245,236,0.55)', letterSpacing: '0.06em',
            }}>one-time · refundable 14 days</span>
          </div>
        </div>
        <div style={{
          padding: '28px 32px', background: 'var(--panel)',
          display: 'flex', flexDirection: 'column',
        }}>
          <MonoLabel>What unlocks · 6 tools + 1 audit credit</MonoLabel>
          <div style={{
            marginTop: 14, display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            columnGap: 24, rowGap: 0,
          }}>
            {items.map((it, i) => (
              <div key={i} style={{
                padding: '12px 0',
                borderBottom: i < items.length - 2 ? '1px dashed var(--rule)' : 'none',
                display: 'flex', flexDirection: 'column', gap: 6,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    fontFamily: 'var(--mono-font)', fontSize: 10,
                    letterSpacing: '0.12em', textTransform: 'uppercase',
                    color: 'var(--accent)', fontWeight: 600,
                  }}>{it.k}</div>
                  <button onClick={() => setPreview(it.kind)} style={{
                    background: 'transparent', border: 'none', padding: '2px 4px',
                    fontFamily: 'var(--mono-font)', fontSize: 10,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: 'var(--accent-2)', cursor: 'pointer',
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    textDecoration: 'underline', textUnderlineOffset: 3,
                  }}>
                    <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="6" cy="6" r="2"/><path d="M1 6c1.5-2.5 3-3.5 5-3.5s3.5 1 5 3.5c-1.5 2.5-3 3.5-5 3.5s-3.5-1-5-3.5z"/></svg>
                    Preview
                  </button>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.45, color: 'var(--ink-2)' }}>{it.v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        kicker={active ? `Preview · ${active.k} · sample data` : ''}
        title={active?.title || ''}
        subtitle={active?.sub}
        maxWidth={820}
      >
        <div style={{ padding: '24px 28px 20px' }}>
          <PreviewBody kind={preview} />
        </div>
        <div style={{
          position: 'sticky', bottom: 0,
          padding: '16px 28px',
          background: 'var(--panel-2)',
          borderTop: '1px solid var(--rule)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16,
        }}>
          <div style={{ fontSize: 12, color: 'var(--ink-dim)', fontStyle: 'italic', maxWidth: 440 }}>
            Sample data shown. Your audit runs against your address, your bill, your tariff — and your numbers replace these.
          </div>
          <button onClick={onUpgrade} style={{
            padding: '11px 18px', fontSize: 13.5, fontWeight: 600,
            background: 'var(--ink)', color: 'var(--bg)', border: 'none',
            borderRadius: 'var(--radius)', cursor: 'pointer',
            fontFamily: 'var(--body-font)',
            display: 'inline-flex', alignItems: 'center', gap: 8, flexShrink: 0,
          }}>Unlock — {t.price} <Arrow /></button>
        </div>
      </Modal>
    </Panel>
  );
}

// Inline lock pill — for individual numeric cells.
function LockedCell({ children, onUpgrade, requires = 'pack' }) {
  const upTier = TIERS[requires];
  return (
    <button onClick={onUpgrade} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 8px',
      background: 'transparent',
      border: '1px dashed var(--rule-strong)',
      borderRadius: 'var(--radius)',
      color: 'var(--ink-dim)',
      fontFamily: 'var(--mono-font)', fontSize: 11,
      letterSpacing: '0.06em', cursor: 'pointer',
    }}>
      <svg width="9" height="9" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3" y="6" width="8" height="6" rx="1" />
        <path d="M5 6V4.5a2 2 0 014 0V6" />
      </svg>
      {children || `${upTier.label} only`}
    </button>
  );
}

// Mock "you are currently on tier X" switcher in the nav.
// In production this would be an account state, not a UI control.
function TierSwitcher({ tier, setTier }) {
  const opts = [
    { k: 'free', label: 'Basic' },
    { k: 'pack', label: 'Decision Pack' },
    { k: 'founders', label: 'Founders' },
  ];
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 0,
      border: '1px dashed var(--accent-2)', borderRadius: 'var(--radius)',
      background: 'var(--panel-2)', padding: 2,
      fontFamily: 'var(--mono-font)', fontSize: 11,
    }} title="Mock: simulate viewing the product on each tier.">
      <span style={{
        padding: '4px 8px', color: 'var(--accent-2)',
        textTransform: 'uppercase', letterSpacing: '0.1em',
        borderRight: '1px dashed var(--rule)', fontWeight: 600,
      }}>Mock tier</span>
      {opts.map(opt => (
        <button key={opt.k} onClick={() => setTier(opt.k)} style={{
          padding: '4px 9px',
          color: tier === opt.k ? 'var(--accent-ink)' : 'var(--ink-2)',
          background: tier === opt.k ? 'var(--accent-2)' : 'transparent',
          borderRadius: 'calc(var(--radius) - 1px)',
          fontWeight: tier === opt.k ? 600 : 500,
          border: 'none', cursor: 'pointer', fontFamily: 'inherit',
        }}>{opt.label}</button>
      ))}
    </div>
  );
}

Object.assign(window, { TIERS, hasFeature, Locked, LockedCell, TierSwitcher, WorkshopTeaser });
