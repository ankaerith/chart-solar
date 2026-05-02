// Audit flow — the hero feature.
// 4 stages: upload → extracting → review → report.

const { useState: useAuditState, useEffect: useAuditEffect } = React;

// Mock-extracted fields for the demo PDF.
const MOCK_EXTRACTED = {
  installer: {
    name: 'SunHouse Solar of Colorado, LLC',
    license: 'EC #100431-CO',
    rep: 'Devin Park',
    quoteDate: '2026-03-12',
    expiry: '2026-04-26',
    nabcep: 'claimed (PV Installation Professional)',
  },
  system: {
    panels: 'Hanwha Q.PEAK DUO BLK ML-G10+ 405W',
    panelCount: 18,
    dcKw: 7.29,
    acKw: 5.16,
    dcAcRatio: 1.41,
    inverter: 'Enphase IQ8M-72-2-US (microinverter)',
    battery: 'Tesla Powerwall 3 · 13.5 kWh usable',
    monitoring: 'Enphase Enlighten · 5 yr free, then $14/mo',
    panelWarrantyYears: 12,
    inverterWarrantyYears: 25,
    workmanshipWarrantyYears: 10,
  },
  financial: {
    grossPrice: 38640,
    pricePerWatt: 5.30,
    adders: [
      { label: 'MPU upgrade', value: 1850 },
      { label: 'Trenching (battery)', value: 950 },
      { label: 'Critter guard', value: 480 },
      { label: 'Permitting + interconnect', value: 1200 },
    ],
    incentivesClaimed: [
      { label: 'Federal residential credit', value: 11592, note: 'claimed at 30%' },
      { label: 'Xcel Energy rebate', value: 0, note: 'closed Feb 2026 — installer aware?' },
    ],
    netPriceAfterIncentives: 27048,
    financing: {
      method: 'loan',
      lender: 'Sunlight Financial',
      apr: 0.99,
      term: 25,
      dealerFee: 0.215,
      monthlyPayment: 156,
    },
    escalationAssumed: 4.5,
    degradationAssumed: 0.5,
    year1KwhClaim: 11800,
    twentyFiveYearSavingsClaim: 78400,
    paybackClaim: 7.2,
  },
};

// What our engine produces against the same address+system.
const OUR_FORECAST = {
  year1Kwh: 9940,
  year1KwhRange: [9143, 10737],
  twentyFiveYearWealth: 31400,
  paybackDiscounted: 11.2,
  flagSummary: { high: 2, med: 2, low: 2 },
};

// ---- Stage 1: Upload --------------------------------------------------
function AuditUpload({ onUpload, onCancel }) {
  const [hover, setHover] = useAuditState(false);
  const onDrop = (e) => {
    e.preventDefault(); setHover(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) onUpload(f.name);
  };
  return (
    <section style={{ maxWidth: 880, margin: '0 auto', padding: '60px 40px 80px' }}>
      <Eyebrow>Audit · step 1 of 3</Eyebrow>
      <h1 style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)',
        fontSize: 'clamp(36px, 4.5vw, 56px)', lineHeight: 1.05,
        margin: '0 0 16px', textWrap: 'balance',
      }}>Drop the proposal.</h1>
      <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 640, margin: '0 0 32px' }}>
        Any solar PDF — quote, contract, or signed proposal. We extract every field, run our engine on the same system at your address, and produce a one-page variance report.
      </p>

      <div onDragOver={e => { e.preventDefault(); setHover(true); }}
        onDragLeave={() => setHover(false)} onDrop={onDrop}
        style={{
          padding: '64px 24px', borderRadius: 'var(--radius-lg)',
          background: hover ? 'var(--panel)' : 'var(--panel-2)',
          border: `2px dashed ${hover ? 'var(--accent)' : 'var(--rule-strong)'}`,
          textAlign: 'center', transition: 'all 0.15s',
        }}>
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="var(--ink-dim)" strokeWidth="1.4" style={{ margin: '0 auto 18px', display: 'block' }}>
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="12" y1="18" x2="12" y2="12" />
          <polyline points="9 15 12 12 15 15" />
        </svg>
        <div style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          fontSize: 22, color: 'var(--ink)', marginBottom: 8,
        }}>Drop your PDF here</div>
        <div style={{ fontSize: 13.5, color: 'var(--ink-2)', marginBottom: 20 }}>
          or <button onClick={() => onUpload('SunHouse Solar — proposal v3.pdf')} style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            color: 'var(--accent-2)', textDecoration: 'underline', textUnderlineOffset: 2,
            fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 600,
          }}>browse</button>
        </div>
        <button onClick={() => onUpload('SAMPLE — SunHouse Solar proposal v3.pdf')} style={{
          padding: '10px 18px', fontSize: 13, fontWeight: 500,
          background: 'transparent', border: '1px solid var(--rule-strong)',
          borderRadius: 'var(--radius)', color: 'var(--ink-2)', cursor: 'pointer',
          fontFamily: 'var(--body-font)',
        }}>Try a sample proposal →</button>
      </div>

      <div style={{
        marginTop: 24, padding: 18,
        background: 'var(--bg)', border: '1px solid var(--rule)',
        borderRadius: 'var(--radius)',
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 18,
      }}>
        {[
          { k: 'Privacy', v: 'Raw PDF auto-purged within 72 hours. Extracted JSON stays in your account.' },
          { k: 'AI', v: 'Gemini 2.5 Flash on Vertex AI, ZDR enabled. PDFs sent inline, never used for training.' },
          { k: 'Human review', v: 'You confirm/correct extracted fields before we run the audit.' },
        ].map((it, i) => (
          <div key={i}>
            <MonoLabel>{it.k}</MonoLabel>
            <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink-2)', marginTop: 6 }}>{it.v}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 28 }}>
        <button onClick={onCancel} style={{
          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
          color: 'var(--ink-dim)', fontSize: 13, fontFamily: 'var(--body-font)',
        }}>← Back to forecast</button>
      </div>
    </section>
  );
}

// ---- Stage 2: Extracting ----------------------------------------------
function AuditExtracting({ fileName, onDone }) {
  const steps = [
    'Uploading PDF · encrypted at rest',
    'Detecting layout · digital · 14 pages',
    'Extracting installer + system fields',
    'Extracting financial line items',
    'Confidence scoring per field',
    'Running engine on extracted system',
    'Comparing claims vs. independent forecast',
  ];
  const [progress, setProgress] = useAuditState(0);
  useAuditEffect(() => {
    if (progress >= steps.length) { setTimeout(onDone, 400); return; }
    const t = setTimeout(() => setProgress(p => p + 1), 480 + Math.random() * 300);
    return () => clearTimeout(t);
  }, [progress]);
  return (
    <section style={{ maxWidth: 720, margin: '0 auto', padding: '80px 40px' }}>
      <Eyebrow>Audit · extracting</Eyebrow>
      <h2 style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        fontSize: 32, lineHeight: 1.1, margin: '0 0 8px',
      }}>Reading {fileName}</h2>
      <p style={{ fontSize: 14, color: 'var(--ink-dim)', margin: '0 0 32px' }}>
        Typically 8–20 seconds. You can leave this page; we'll email when it's ready.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {steps.map((s, i) => {
          const done = i < progress;
          const active = i === progress;
          return (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '24px 1fr auto', gap: 12,
              alignItems: 'center', padding: '12px 0',
              borderBottom: '1px dashed var(--rule)',
              opacity: done || active ? 1 : 0.4,
              transition: 'opacity 0.3s',
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: '50%',
                border: `1.5px solid ${done ? 'var(--good)' : active ? 'var(--accent)' : 'var(--rule-strong)'}`,
                background: done ? 'var(--good)' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {done && <svg width="10" height="10" viewBox="0 0 12 12" stroke="white" strokeWidth="2" fill="none"><path d="M2 6l3 3 5-6"/></svg>}
                {active && <span style={{
                  width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)',
                  animation: 'sd-pulse 0.8s ease-in-out infinite',
                }}/>}
              </div>
              <div style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>{s}</div>
              <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.08em',
                color: done ? 'var(--good)' : active ? 'var(--accent)' : 'var(--ink-faint)',
                textTransform: 'uppercase',
              }}>{done ? 'done' : active ? 'running' : 'queued'}</div>
            </div>
          );
        })}
      </div>
      <style>{`@keyframes sd-pulse { 0%,100% { transform: scale(0.7); opacity: 0.6 } 50% { transform: scale(1); opacity: 1 } }`}</style>
    </section>
  );
}

// ---- Stage 3: Review extraction (HITL) --------------------------------
function AuditReview({ extracted, onConfirm, onCancel }) {
  const [data, setData] = useAuditState(extracted);
  const update = (path, value) => {
    setData(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const keys = path.split('.');
      let obj = next;
      for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]];
      obj[keys[keys.length - 1]] = value;
      return next;
    });
  };

  const sectionStyle = {
    padding: '20px 24px', background: 'var(--panel)',
    border: '1px solid var(--rule)', borderRadius: 'var(--radius-lg)',
    marginBottom: 18,
  };

  // Field-level: confidence indicator
  const FieldRow = ({ label, value, confidence = 'high', onChange, suffix }) => {
    const tone = confidence === 'high' ? 'var(--good)' : confidence === 'med' ? 'var(--warn)' : 'var(--bad)';
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 80px', gap: 14, alignItems: 'center', padding: '8px 0', borderBottom: '1px dashed var(--rule)' }}>
        <div style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>{label}</div>
        <div>
          <input value={value} onChange={(e) => onChange?.(e.target.value)}
            style={{
              width: '100%', padding: '6px 10px', fontSize: 13,
              background: 'var(--bg)', border: '1px solid var(--rule)',
              borderRadius: 'var(--radius)', fontFamily: 'var(--body-font)',
              color: 'var(--ink)', outline: 'none',
            }}/>
        </div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 9.5, letterSpacing: '0.12em',
          color: tone, textTransform: 'uppercase', textAlign: 'right',
          borderTop: `2px solid ${tone}`, paddingTop: 3, fontWeight: 600,
        }}>{confidence} · {confidence === 'high' ? '0.97' : confidence === 'med' ? '0.78' : '0.52'}</div>
      </div>
    );
  };

  return (
    <section style={{ maxWidth: 880, margin: '0 auto', padding: '40px 40px 80px' }}>
      <Eyebrow>Audit · step 2 of 3 · review extraction</Eyebrow>
      <h1 style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)',
        fontSize: 'clamp(32px, 4vw, 48px)', lineHeight: 1.05, margin: '0 0 12px',
      }}>Did we read this right?</h1>
      <p style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--ink-2)', margin: '0 0 24px', maxWidth: 640 }}>
        We extracted these fields from your proposal. Confidence per field at right — anything below "high" is worth checking. Edit inline; the audit re-runs against your corrections.
      </p>

      <div style={sectionStyle}>
        <MonoLabel>Installer</MonoLabel>
        <div style={{ marginTop: 10 }}>
          <FieldRow label="Company" value={data.installer.name} confidence="high"
            onChange={v => update('installer.name', v)} />
          <FieldRow label="License #" value={data.installer.license} confidence="high"
            onChange={v => update('installer.license', v)} />
          <FieldRow label="Sales rep" value={data.installer.rep} confidence="high"
            onChange={v => update('installer.rep', v)} />
          <FieldRow label="Quote date" value={data.installer.quoteDate} confidence="high" />
          <FieldRow label="NABCEP" value={data.installer.nabcep} confidence="med"
            onChange={v => update('installer.nabcep', v)} />
        </div>
      </div>

      <div style={sectionStyle}>
        <MonoLabel>System</MonoLabel>
        <div style={{ marginTop: 10 }}>
          <FieldRow label="Panel model" value={data.system.panels} confidence="high" />
          <FieldRow label="Panel count" value={data.system.panelCount} confidence="high" />
          <FieldRow label="DC kW" value={data.system.dcKw} confidence="high" />
          <FieldRow label="AC kW" value={data.system.acKw} confidence="high" />
          <FieldRow label="DC:AC ratio" value={data.system.dcAcRatio} confidence="high" />
          <FieldRow label="Inverter" value={data.system.inverter} confidence="high" />
          <FieldRow label="Battery" value={data.system.battery} confidence="med"
            onChange={v => update('system.battery', v)} />
          <FieldRow label="Panel warranty (yr)" value={data.system.panelWarrantyYears} confidence="med" />
        </div>
      </div>

      <div style={sectionStyle}>
        <MonoLabel>Financial</MonoLabel>
        <div style={{ marginTop: 10 }}>
          <FieldRow label="Gross price" value={`$${data.financial.grossPrice.toLocaleString()}`} confidence="high" />
          <FieldRow label="$/W" value={data.financial.pricePerWatt} confidence="high" />
          <FieldRow label="Net after incentives" value={`$${data.financial.netPriceAfterIncentives.toLocaleString()}`} confidence="med" />
          <FieldRow label="Loan APR (stated)" value={`${data.financial.financing.apr}%`} confidence="high" />
          <FieldRow label="Loan term" value={`${data.financial.financing.term} yr`} confidence="high" />
          <FieldRow label="Dealer fee" value={`${(data.financial.financing.dealerFee*100).toFixed(1)}%`} confidence="low" />
          <FieldRow label="Escalation assumed" value={`${data.financial.escalationAssumed}%`} confidence="high" />
          <FieldRow label="Year-1 kWh claim" value={data.financial.year1KwhClaim.toLocaleString()} confidence="high" />
          <FieldRow label="25-yr savings claim" value={`$${data.financial.twentyFiveYearSavingsClaim.toLocaleString()}`} confidence="med" />
        </div>
      </div>

      <div style={{
        padding: 16, background: 'var(--panel-2)', borderLeft: '2px solid var(--warn)',
        fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.55, marginBottom: 24,
      }}>
        <strong style={{ fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.1em' }}>NOTE:</strong>{' '}
        The dealer fee was extracted from the financing addendum, not the headline price. We'll flag it in the report.
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
        <button onClick={onCancel} style={{
          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
          color: 'var(--ink-dim)', fontSize: 13, fontFamily: 'var(--body-font)',
        }}>← Cancel</button>
        <Btn kind="primary" onClick={() => onConfirm(data)}>
          Looks right — run the audit <Arrow />
        </Btn>
      </div>
    </section>
  );
}

// ---- Stage 4: Variance Report -----------------------------------------
function AuditReport({ extracted, onCancel, onAuditAnother }) {
  const ours = OUR_FORECAST;
  const theirs = extracted;
  const variance = ((ours.year1Kwh - theirs.financial.year1KwhClaim) / theirs.financial.year1KwhClaim * 100).toFixed(0);

  const flags = [
    { sev: 'high', tag: 'dealer fee', body: `${(theirs.financial.financing.dealerFee*100).toFixed(1)}% fee embedded in "${theirs.financial.financing.apr}% APR" loan. Effective real cost of capital ~8.4%, not ${theirs.financial.financing.apr}%. Cash price excluding the fee should be ~$${Math.round(theirs.financial.grossPrice * (1 - theirs.financial.financing.dealerFee)).toLocaleString()}.` },
    { sev: 'high', tag: 'year-1 kWh', body: `Installer projects ${theirs.financial.year1KwhClaim.toLocaleString()} kWh; our PVWatts run for this roof returns ${ours.year1Kwh.toLocaleString()} kWh (range ${ours.year1KwhRange[0].toLocaleString()}–${ours.year1KwhRange[1].toLocaleString()}). Overstated by ~${Math.abs(variance)}%.` },
    { sev: 'med', tag: 'escalation', body: `Proposal hard-codes ${theirs.financial.escalationAssumed}% utility escalation. Historical CAGR for Xcel CO is 3.1%; over 25 yr that's a ~$9,400 swing in claimed savings.` },
    { sev: 'med', tag: 'DC:AC ratio', body: `${theirs.system.dcAcRatio} — aggressive. Expect ~3% clipping loss on summer afternoons not reflected in the year-1 number.` },
    { sev: 'low', tag: 'panel warranty', body: `${theirs.system.panelWarrantyYears}-yr product warranty on a Tier-1 module that ships with 25-yr industry baseline. Worth asking why.` },
    { sev: 'low', tag: 'monitoring', body: 'Free monitoring is 5 years; renewal is $14/mo not disclosed in the headline price. ~$1,250 over 25 yr.' },
  ];

  const questions = [
    `What is the system price excluding the ${(theirs.financial.financing.dealerFee*100).toFixed(0)}% dealer fee, paid in cash?`,
    `Which production model (PVWatts / Aurora / proprietary) generated the ${theirs.financial.year1KwhClaim.toLocaleString()} kWh year-1 figure, and what shading factor was used?`,
    `Will you commit to the ${theirs.financial.escalationAssumed}% escalation assumption in writing, with a refund clause if utility rates underperform?`,
    `Why a ${theirs.system.dcAcRatio} DC:AC ratio for this roof orientation, and what clipping loss is modeled into the year-1 number?`,
    `Why is the panel warranty ${theirs.system.panelWarrantyYears} years when industry baseline is 25?`,
    `Is the federal credit firmly available for systems placed in service after 2025-12-31, or is that contingent?`,
  ];

  const sevColor = s => s === 'high' ? 'var(--bad)' : s === 'med' ? 'var(--warn)' : 'var(--ink-dim)';
  const [forecastOpen, setForecastOpen] = useAuditState(false);

  return (
    <div>
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '40px 40px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 24, alignItems: 'flex-start' }}>
          <div>
            <Eyebrow color="var(--bad)">Audit · variance report · {extracted.installer.name}</Eyebrow>
            <h1 style={{
              fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
              letterSpacing: 'var(--display-tracking)',
              fontSize: 'clamp(36px, 5vw, 64px)', lineHeight: 1.02,
              margin: '0 0 16px', textWrap: 'balance',
            }}>The proposal overstates by {Math.abs(variance)}%.</h1>
            <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 760, margin: 0 }}>
              Six flags found, two high-severity. The headline 25-year savings claim of ${theirs.financial.twentyFiveYearSavingsClaim.toLocaleString()} relies on a year-1 production figure that exceeds an independent PVWatts run on the same roof, and a utility escalation assumption that exceeds the historical CAGR for your tariff.
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end',
            paddingTop: 6 }}>
            <div style={{
              fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: 'var(--ink-faint)',
            }}>Audit complete · saved to your account</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Btn kind="ghost" onClick={onAuditAnother}>Audit another</Btn>
              <Btn kind="primary">Export PDF <Arrow /></Btn>
            </div>
          </div>
        </div>
      </section>

      {/* Headline numbers — first thing under the headline */}
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '12px 40px 0' }}>
        <Panel style={{ padding: 28 }}>
          <SectionHead kicker="01 · headline — recomputed"
            title="Their 25-year savings claim vs. ours"
            right={
              <button onClick={() => setForecastOpen(true)} style={{
                padding: '8px 14px', fontSize: 12.5, fontWeight: 500,
                background: 'transparent', border: '1px solid var(--rule-strong)',
                borderRadius: 'var(--radius)', color: 'var(--ink-2)', cursor: 'pointer',
                fontFamily: 'var(--body-font)',
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>Open full forecast <Arrow /></button>
            } />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0,
            border: '1px solid var(--rule)', borderRadius: 'var(--radius)', overflow: 'hidden', marginTop: 8 }}>
            <div style={{ padding: 22, borderRight: '1px solid var(--rule)' }}>
              <MonoLabel>Installer's claim</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 36, marginTop: 6,
                color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                ${theirs.financial.twentyFiveYearSavingsClaim.toLocaleString()}
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)', marginTop: 4 }}>
                payback {theirs.financial.paybackClaim} yr · escalation {theirs.financial.escalationAssumed}%
              </div>
            </div>
            <div style={{ padding: 22 }}>
              <MonoLabel>Our independent run</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 36, marginTop: 6,
                color: 'var(--accent)', fontVariantNumeric: 'tabular-nums' }}>
                ${ours.twentyFiveYearWealth.toLocaleString()}
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)', marginTop: 4 }}>
                payback {ours.paybackDiscounted} yr · escalation 3.1% (historical CAGR)
              </div>
            </div>
          </div>
          <div style={{ fontSize: 13, color: 'var(--ink-dim)', marginTop: 16, lineHeight: 1.55, fontStyle: 'italic' }}>
            Our number isn't "the right answer" — it's a defensible counterfactual built on independent inputs. The gap is the conversation.
          </div>
        </Panel>
      </section>

      {/* Detail strip */}
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '24px 40px 0' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0,
          border: '1px solid var(--rule)', borderRadius: 'var(--radius-lg)', overflow: 'hidden',
          background: 'var(--bg)',
        }}>
          {[
            { k: 'Quoted year-1', v: `${theirs.financial.year1KwhClaim.toLocaleString()} kWh` },
            { k: 'Our model', v: `${ours.year1Kwh.toLocaleString()} kWh` },
            { k: 'Variance', v: `${variance}%`, tone: 'var(--bad)' },
            { k: 'Effective APR', v: '~8.4%', tone: 'var(--bad)', sub: `vs ${theirs.financial.financing.apr}% stated` },
          ].map((c, i) => (
            <div key={i} style={{ padding: '20px 22px', borderRight: i < 3 ? '1px solid var(--rule)' : 'none' }}>
              <MonoLabel>{c.k}</MonoLabel>
              <div style={{
                fontFamily: 'var(--display-font)', fontSize: 28, marginTop: 6,
                fontVariantNumeric: 'tabular-nums', color: c.tone || 'var(--ink)',
              }}>{c.v}</div>
              {c.sub && <div style={{ fontSize: 11, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)', marginTop: 2 }}>{c.sub}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Flags + Questions */}
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '32px 40px 80px',
        display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 28 }}>
        <Panel style={{ padding: 28 }}>
          <SectionHead kicker="02 · flags" title={`${flags.length} found · ${flags.filter(f=>f.sev==='high').length} high-severity`} />
          <div style={{ marginTop: 6 }}>
            {flags.map((f, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '60px 130px 1fr', gap: 14, alignItems: 'flex-start',
                padding: '14px 0', borderBottom: i < flags.length - 1 ? '1px dashed var(--rule)' : 'none' }}>
                <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
                  color: sevColor(f.sev), textTransform: 'uppercase',
                  borderTop: `2px solid ${sevColor(f.sev)}`, paddingTop: 5, fontWeight: 600 }}>{f.sev}</div>
                <div style={{ fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.06em',
                  color: 'var(--ink-2)', paddingTop: 3 }}>{f.tag}</div>
                <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink-2)' }}>{f.body}</div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel style={{ padding: 28 }}>
          <SectionHead kicker="03 · ask your installer" title="Six questions, sourced" />
          <ol style={{ margin: '8px 0 0', paddingLeft: 22, fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink-2)' }}>
            {questions.map((q, i) => <li key={i} style={{ marginBottom: 12 }}>{q}</li>)}
          </ol>
          <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px dashed var(--rule)' }}>
            <Btn kind="ghost">Copy as email</Btn>
          </div>
        </Panel>
      </section>

      <ForecastModal open={forecastOpen} onClose={() => setForecastOpen(false)} />
    </div>
  );
}

// Modal showing our full independent forecast — what we'd produce on the same address+system,
// rendered with the same components used in the Results screen.
function ForecastModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} maxWidth={1080}
      kicker="Our independent forecast"
      title="$31,400 median NPV · 11.2 yr discounted payback"
      subtitle="Run on the same address + system the proposal specifies, using PVWatts production, historical Xcel CO escalation, and your hold-duration default. This is what we'd tell you if you'd asked us first.">
      <div style={{ padding: '8px 28px 28px' }}>
        <Panel style={{ padding: 18, marginBottom: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
            <div>
              <MonoLabel>Cumulative net wealth · solar vs do-nothing</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 18, marginTop: 4 }}>500 simulated paths · 25 years</div>
            </div>
          </div>
          <div style={{ minHeight: 280 }}><HeroChart /></div>
        </Panel>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 0,
          border: '1px solid var(--rule)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 18 }}>
          {[
            { k: 'Median NPV', v: '+$31,400' },
            { k: 'Discounted payback', v: '11.2 yr' },
            { k: 'Crossover year', v: 'yr 9' },
            { k: 'IRR (median)', v: '6.8%' },
            { k: 'P10 — P90', v: '$8.2k → $58.7k' },
          ].map((it, i, arr) => (
            <div key={i} style={{ padding: '16px 18px',
              borderRight: i < arr.length - 1 ? '1px solid var(--rule)' : 'none' }}>
              <MonoLabel>{it.k}</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 22, marginTop: 4,
                fontVariantNumeric: 'tabular-nums' }}>{it.v}</div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 13, color: 'var(--ink-dim)', lineHeight: 1.55, fontStyle: 'italic' }}>
          The headline number is the median; the band is the 80% confidence interval. If you upload your real
          utility intervals via Green Button, sizing typically shifts by ±0.5 kW.
        </div>
      </div>
    </Modal>
  );
}

// ---- Screen wrapper ----------------------------------------------------
function ScreenAudit({ audit, setAudit, auth, onSignInRequested, onSignOut, tier, setTier, onCancel, onComplete, route, onNavigate }) {
  const setStage = (stage) => setAudit(a => ({ ...a, stage }));
  const onUpload = (fileName) => { setAudit(a => ({ ...a, fileName })); setStage('extracting'); };
  const onExtractDone = () => { setAudit(a => ({ ...a, extracted: MOCK_EXTRACTED })); setStage('review'); };
  const onConfirm = (corrected) => { setAudit(a => ({ ...a, extracted: corrected })); onComplete(); };
  const onAuditAnother = () => { setAudit({ stage: 'upload', fileName: null, extracted: null }); window.scrollTo(0, 0); };

  return (
    <div>
      <TopNav route={route} onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} />

      {audit.stage === 'upload' && <AuditUpload onUpload={onUpload} onCancel={onCancel} />}
      {audit.stage === 'extracting' && <AuditExtracting fileName={audit.fileName} onDone={onExtractDone} />}
      {audit.stage === 'review' && audit.extracted && <AuditReview extracted={audit.extracted} onConfirm={onConfirm} onCancel={onCancel} />}
      {audit.stage === 'report' && audit.extracted && <AuditReport extracted={audit.extracted} onCancel={onCancel} onAuditAnother={onAuditAnother} />}

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

Object.assign(window, { ScreenAudit });
