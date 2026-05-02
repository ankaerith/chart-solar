// Workshop Knobs — the "every assumption editable" panel that justifies the
// Decision Pack price. Four groups (Battery, Loans, Financial, Production) of
// knobs that set the inputs to the simulation. Editing any knob triggers a
// recompute pulse on the headline number; values are mock-only — this is a
// design surface, not a real engine.
//
// Visual language: dense + numerical. Each row is label · control · current
// value · plain-language hint. Section heads borrow from the rest of the
// screen (kicker + serif title + right-aligned mono meta). One pulsing
// "recomputing…" indicator at top-right when any knob has changed.

const { useState: useStateW, useRef: useRefW, useEffect: useEffectW } = React;

// ---- atomic knob primitives -------------------------------------------

// Slider — for continuous numerical values
function KnobSlider({ label, value, min, max, step = 1, unit = '', hint, fmt, onChange }) {
  const display = fmt ? fmt(value) : `${value}${unit}`;
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '180px 1fr 96px',
      alignItems: 'center', gap: 18,
      padding: '10px 0', borderBottom: '1px solid var(--rule)',
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', fontFamily: 'var(--body-font)' }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: 'var(--ink-dim)', marginTop: 2, lineHeight: 1.4, fontFamily: 'var(--body-font)' }}>{hint}</div>}
      </div>
      <input type="range" value={value} min={min} max={max} step={step}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ accentColor: 'var(--accent)', width: '100%' }} />
      <div style={{
        fontFamily: 'var(--mono-font)', fontSize: 12.5, color: 'var(--ink)',
        textAlign: 'right', fontVariantNumeric: 'tabular-nums',
      }}>{display}</div>
    </div>
  );
}

// Segment — for enumerated short-list choices (NEM mode, dispatch strategy)
function KnobSeg({ label, value, options, hint, onChange }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '180px 1fr',
      alignItems: 'center', gap: 18,
      padding: '10px 0', borderBottom: '1px solid var(--rule)',
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', fontFamily: 'var(--body-font)' }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: 'var(--ink-dim)', marginTop: 2, lineHeight: 1.4, fontFamily: 'var(--body-font)' }}>{hint}</div>}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {options.map(o => {
          const active = value === o.k;
          return (
            <button key={o.k} onClick={() => onChange(o.k)} style={{
              padding: '6px 12px', borderRadius: 'var(--radius)',
              border: '1px solid ' + (active ? 'var(--ink)' : 'var(--rule-strong)'),
              background: active ? 'var(--ink)' : 'transparent',
              color: active ? 'var(--bg)' : 'var(--ink-2)',
              fontFamily: 'var(--mono-font)', fontSize: 11,
              letterSpacing: '0.06em', textTransform: 'uppercase',
              cursor: 'pointer',
            }}>{o.label}</button>
          );
        })}
      </div>
    </div>
  );
}

// Toggle — booleans (tax-deductible, multi-loan stack)
function KnobToggle({ label, value, hint, onChange }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '180px 1fr auto',
      alignItems: 'center', gap: 18,
      padding: '10px 0', borderBottom: '1px solid var(--rule)',
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', fontFamily: 'var(--body-font)' }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: 'var(--ink-dim)', marginTop: 2, lineHeight: 1.4, fontFamily: 'var(--body-font)' }}>{hint}</div>}
      </div>
      <div />
      <button onClick={() => onChange(!value)} style={{
        width: 38, height: 22, borderRadius: 999, position: 'relative',
        border: '1px solid var(--rule-strong)',
        background: value ? 'var(--accent)' : 'var(--panel-2)',
        cursor: 'pointer', padding: 0,
      }}>
        <span style={{
          position: 'absolute', top: 2, left: value ? 18 : 2,
          width: 16, height: 16, borderRadius: '50%',
          background: 'var(--bg)', transition: 'left 0.16s ease',
        }} />
      </button>
    </div>
  );
}

// ---- group container ---------------------------------------------------

function KnobGroup({ kicker, title, meta, children, defaultOpen = true }) {
  const [open, setOpen] = useStateW(defaultOpen);
  return (
    <div style={{
      borderTop: '1px solid var(--rule-strong)',
      padding: '20px 0',
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', background: 'none', border: 'none', padding: 0,
        cursor: 'pointer', textAlign: 'left',
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        gap: 14, marginBottom: open ? 14 : 0,
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 4,
          }}>{kicker}</div>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            fontSize: 22, color: 'var(--ink)',
          }}>{title}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {meta && <div style={{ fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-dim)' }}>{meta}</div>}
          <span style={{
            fontFamily: 'var(--mono-font)', fontSize: 14, color: 'var(--ink-dim)',
            transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s',
          }}>▾</span>
        </div>
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}

// ---- main panel --------------------------------------------------------

const DEFAULT_KNOBS = {
  // Battery dispatch
  dispatchStrategy: 'self',         // self | peak | backup | optimal
  reservePct: 20,                   // 0-100 backup reserve
  rtePct: 90,                       // round-trip efficiency
  cRate: 0.5,                       // C-rate
  // Loans
  multiLoan: false,
  dealerFeePct: 18,
  taxDeductible: false,
  apr: 6.99,
  termYr: 25,
  // Financial
  discountPct: 5.5,
  escalatorPct: 5.4,
  holdYr: 12,
  degradationPct: 0.5,
  // Production
  nemMode: 'nem2',                  // nem1 | nem2 | nem3
  soilingPct: 2,
  clipping: true,
  shadingPct: 4,
};

function WorkshopKnobs() {
  const [knobs, setKnobs] = useStateW(DEFAULT_KNOBS);
  const [pulse, setPulse] = useStateW(false);
  const set = (k, v) => {
    setKnobs(prev => ({ ...prev, [k]: v }));
    setPulse(true);
    clearTimeout(set._t);
    set._t = setTimeout(() => setPulse(false), 700);
  };
  const reset = () => setKnobs(DEFAULT_KNOBS);
  const dirty = JSON.stringify(knobs) !== JSON.stringify(DEFAULT_KNOBS);

  // Mock recomputed median NPV — moves with the knobs in a believable direction.
  const baseMedian = 31400;
  const delta =
    (knobs.discountPct - 5.5) * -3200 +
    (knobs.escalatorPct - 5.4) * 4100 +
    (knobs.holdYr - 12) * 1600 +
    (knobs.degradationPct - 0.5) * -2200 +
    (knobs.dealerFeePct - 18) * -380 +
    (knobs.apr - 6.99) * -1900 +
    (knobs.taxDeductible ? 2400 : 0) +
    (knobs.nemMode === 'nem3' ? -8200 : knobs.nemMode === 'nem1' ? 3100 : 0) +
    (knobs.soilingPct - 2) * -480 +
    (knobs.shadingPct - 4) * -520 +
    (knobs.dispatchStrategy === 'optimal' ? 2800 : knobs.dispatchStrategy === 'peak' ? 1200 : knobs.dispatchStrategy === 'backup' ? -1400 : 0) +
    (knobs.rtePct - 90) * 220;
  const median = Math.round(baseMedian + delta);

  return (
    <Panel style={{ padding: 28 }}>
      {/* Top header — matches SectionHead pattern but swaps in a live-recompute meter */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center',
        gap: 24, marginBottom: 18, paddingBottom: 18,
        borderBottom: '1px solid var(--rule)',
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 6,
          }}>03 · workshop · advanced knobs</div>
          <h2 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 'clamp(28px, 3vw, 38px)', lineHeight: 1.1, margin: '0 0 8px',
          }}>Every assumption is yours to argue with.</h2>
          <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--ink-2)', margin: 0, maxWidth: 720 }}>
            These are the priors driving the simulation. Most homeowners change two
            or three. Power users rebuild the whole financial picture from these
            controls — and the headline updates live.
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 4,
          }}>median NPV · {pulse ? 'recomputing…' : 'recomputed'}</div>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            fontSize: 'clamp(28px, 2.6vw, 36px)', lineHeight: 1, color: median >= 0 ? 'var(--good)' : 'var(--bad)',
            fontVariantNumeric: 'tabular-nums',
            opacity: pulse ? 0.6 : 1, transition: 'opacity 0.2s',
          }}>{median >= 0 ? '+' : ''}${median.toLocaleString()}</div>
          {dirty && (
            <button onClick={reset} style={{
              marginTop: 8, background: 'none', border: 'none', padding: 0,
              fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-dim)',
              textDecoration: 'underline', cursor: 'pointer',
              letterSpacing: '0.04em',
            }}>↻ reset to ZIP/utility defaults</button>
          )}
        </div>
      </div>

      {/* --- Battery dispatch ------------------------------------------- */}
      <KnobGroup kicker="3.1 · battery dispatch" title="Battery"
        meta="Powerwall 3 · 13.5 kWh">
        <KnobSeg label="Strategy" value={knobs.dispatchStrategy}
          hint="Self-consumption is the default under NEM 1:1. Peak shaving wins under NEM 3.0. Backup-priority sacrifices NPV for reserve."
          options={[
            { k: 'self', label: 'Self-cons.' },
            { k: 'peak', label: 'Peak shave' },
            { k: 'backup', label: 'Backup-pri.' },
            { k: 'optimal', label: 'LP-optimal' },
          ]}
          onChange={v => set('dispatchStrategy', v)} />
        <KnobSlider label="Backup reserve" value={knobs.reservePct}
          min={0} max={100} step={5} unit="%"
          hint="Capacity always held in reserve for outages. Bigger reserve = less dispatchable kWh = lower NPV but more resilience."
          onChange={v => set('reservePct', v)} />
        <KnobSlider label="Round-trip efficiency" value={knobs.rtePct}
          min={80} max={95} step={1} unit="%"
          hint="Powerwall 3 spec is 90%. Older LFP packs run 86-88%. RTE compounds on every cycle — small numbers, big lifetime impact."
          onChange={v => set('rtePct', v)} />
        <KnobSlider label="C-rate (cont.)" value={knobs.cRate}
          min={0.2} max={1.0} step={0.1}
          fmt={v => `${v.toFixed(1)}C`}
          hint="Continuous discharge rate. 0.5C means a 13.5 kWh pack delivers 6.75 kW continuous. Caps backup utility for big-load homes."
          onChange={v => set('cRate', v)} />
      </KnobGroup>

      {/* --- Loans ------------------------------------------------------ */}
      <KnobGroup kicker="3.2 · advanced loans" title="Loan stack"
        meta="primary loan · 6.99% · 25 yr">
        <KnobSlider label="APR" value={knobs.apr}
          min={3} max={12} step={0.1} unit="%"
          fmt={v => `${v.toFixed(2)}%`}
          hint="Headline rate. Solar loans publicly quote ~4-7% but most include a 'dealer fee' that hides the true cost — set below."
          onChange={v => set('apr', v)} />
        <KnobSlider label="Term" value={knobs.termYr}
          min={5} max={30} step={1} unit=" yr"
          hint="Longer term shrinks payment, raises lifetime interest, and shifts cumulative-wealth crossover later."
          onChange={v => set('termYr', v)} />
        <KnobSlider label="Dealer fee" value={knobs.dealerFeePct}
          min={0} max={35} step={1} unit="%"
          hint="The hidden adder installer-financiers bake into the system price. 18% is typical 2025. 0% is a credit-union HELOC."
          onChange={v => set('dealerFeePct', v)} />
        <KnobToggle label="Tax-deductible interest"
          value={knobs.taxDeductible}
          hint="HELOC / mortgage-secured loans can deduct interest. Unsecured solar loans cannot. Adds ~$2.4k median NPV at 24% bracket."
          onChange={v => set('taxDeductible', v)} />
        <KnobToggle label="Stack multiple loans"
          value={knobs.multiLoan}
          hint="Models a primary loan + a re-amortization at year 5 (e.g. ITC paydown clause common in solar loans)."
          onChange={v => set('multiLoan', v)} />
      </KnobGroup>

      {/* --- Financial assumptions ------------------------------------ */}
      <KnobGroup kicker="3.3 · financial priors" title="Financial assumptions"
        meta="median NPV is most sensitive to escalator">
        <KnobSlider label="Discount rate" value={knobs.discountPct}
          min={2} max={12} step={0.1} unit="%"
          fmt={v => `${v.toFixed(1)}%`}
          hint="Your opportunity cost. Default = your mortgage rate. Higher = future savings worth less today = NPV drops."
          onChange={v => set('discountPct', v)} />
        <KnobSlider label="Utility escalator" value={knobs.escalatorPct}
          min={0} max={10} step={0.1} unit="%/yr"
          fmt={v => `${v.toFixed(1)}%/yr`}
          hint="ZIP-defaulted from your utility's 10-yr filings. Xcel CO is 5.4%. Higher = solar wins by more."
          onChange={v => set('escalatorPct', v)} />
        <KnobSlider label="Hold duration" value={knobs.holdYr}
          min={3} max={25} step={1} unit=" yr"
          hint="ZIP-defaulted from US Census mobility data. Selling early kills cash-NPV; financed systems often transfer better."
          onChange={v => set('holdYr', v)} />
        <KnobSlider label="Panel degradation" value={knobs.degradationPct}
          min={0.2} max={1.2} step={0.05} unit="%/yr"
          fmt={v => `${v.toFixed(2)}%/yr`}
          hint="Datasheet warranties 0.5%/yr. Real-world long-tail bifacial mono is 0.3-0.4%. Cheap polycrystalline runs 0.7%+."
          onChange={v => set('degradationPct', v)} />
      </KnobGroup>

      {/* --- Production ------------------------------------------------ */}
      <KnobGroup kicker="3.4 · production" title="Production model"
        meta="hourly · NREL PVWatts v8 + ResStock load">
        <KnobSeg label="NEM mode" value={knobs.nemMode}
          hint="NEM 1:1 (CO/UT) credits exports at retail. NEM 2.0 (older CA) at retail w/ NBCs. NEM 3.0 (CA) at avoided-cost — kills export economics, requires battery."
          options={[
            { k: 'nem1', label: 'NEM 1:1' },
            { k: 'nem2', label: 'NEM 2.0' },
            { k: 'nem3', label: 'NEM 3.0' },
          ]}
          onChange={v => set('nemMode', v)} />
        <KnobSlider label="Soiling" value={knobs.soilingPct}
          min={0} max={8} step={0.5} unit="%"
          hint="Annual production loss from dust, pollen, snow. 2% mid-CO. ~5% in dry agricultural zones. <1% in PNW (rain self-cleans)."
          onChange={v => set('soilingPct', v)} />
        <KnobSlider label="Shading loss" value={knobs.shadingPct}
          min={0} max={25} step={1} unit="%"
          hint="From your roof model. 4% is the satellite-derived estimate for your address. Tree-pruning could drop this to ~1%."
          onChange={v => set('shadingPct', v)} />
        <KnobToggle label="Inverter clipping"
          value={knobs.clipping}
          hint="Models DC:AC ratio > 1.2. At your sizing the loss is ~1.5%/yr summer noons. Off = assume oversized inverter."
          onChange={v => set('clipping', v)} />
      </KnobGroup>

      {/* Footer note */}
      <div style={{
        marginTop: 22, padding: '14px 16px',
        background: 'var(--panel-2)', borderLeft: '2px solid var(--accent-2)',
        fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink-2)',
        fontFamily: 'var(--body-font)',
      }}>
        <strong style={{ fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.12em', textTransform: 'uppercase' }}>note · </strong>
        Every knob writes back into the 8760-hour engine. The headline number is
        the new median across {500} simulations; the full distribution rebuild
        completes in ~600 ms client-side. The tornado plot above re-ranks every
        time you settle on a new value.
      </div>
    </Panel>
  );
}

Object.assign(window, { WorkshopKnobs });
