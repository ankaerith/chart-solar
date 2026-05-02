// Pricing screen — three tiers side by side, plus add-ons row.

const PRICING_FEATURES = [
  { group: 'Forecast depth', items: [
    { k: 'Independent production model (pvlib + NSRDB)', free: true, pack: true, founders: true },
    { k: 'Median NPV + discounted payback + crossover yr', free: true, pack: true, founders: true },
    { k: 'Lifetime tCO₂ offset (env. lens)', free: true, pack: true, founders: true },
    { k: 'Monte Carlo simulation count', free: 'n=50', pack: 'n=500', founders: 'n=500' },
    { k: 'P10 / P90 confidence band', free: false, pack: true, founders: true },
    { k: 'Hourly 8760-hr simulation (NEM 3.0 / TOU-aware)', free: false, pack: true, founders: true },
  ]},
  { group: 'Battery + dispatch', items: [
    { k: 'Whether to include a battery (yes/no headline)', free: true, pack: true, founders: true },
    { k: 'Hourly battery dispatch simulation', free: false, pack: true, founders: true },
    { k: 'TOU arbitrage modeling (charge off-peak / discharge on-peak)', free: false, pack: true, founders: true },
    { k: 'Self-consumption vs backup-first vs arbitrage strategies', free: false, pack: true, founders: true },
    { k: 'Days-of-backup for critical-load panel', free: false, pack: true, founders: true },
    { k: 'NEM 3.0 / NBT export-credit modeling (CA post-Apr 2023)', free: false, pack: true, founders: true },
  ]},
  { group: 'Capital allocation', items: [
    { k: 'Cash vs loan vs lease vs PPA comparison', free: 'summary', pack: 'full diff', founders: 'full diff' },
    { k: 'Opportunity-cost overlay (HYSA / mortgage / S&P)', free: false, pack: true, founders: true },
    { k: 'Dealer-fee detection on solar loans', free: false, pack: true, founders: true },
    { k: 'Sale-scenario modeling ($/W home-value uplift, assumability)', free: false, pack: true, founders: true },
    { k: 'Tornado sensitivity (which knobs move the answer)', free: false, pack: true, founders: true },
    { k: 'Scenario versioning + side-by-side diff', free: false, pack: true, founders: true },
  ]},
  { group: 'Audit & track', items: [
    { k: 'Proposal audit credits (PDF → variance report)', free: false, pack: '1', founders: '3' },
    { k: 'Multi-bid comparison (audit 2+ quotes side by side)', free: false, pack: true, founders: true },
    { k: 'Ask-your-installer question list', free: false, pack: true, founders: true },
    { k: 'Track post-install (Enphase / SolarEdge / Tesla)', free: false, pack: 'add $9/mo', founders: '12 mo incl.' },
    { k: 'Variance-vs-forecast monthly alerts', free: false, pack: 'with Track', founders: 'incl.' },
  ]},
  { group: 'Outputs & receipts', items: [
    { k: 'Methodology PDF (every assumption + source)', free: false, pack: true, founders: true },
    { k: 'Reproducible snapshot (engine + tariff version pinned)', free: false, pack: true, founders: true },
    { k: 'Share link (read-only, expires)', free: false, pack: true, founders: true },
    { k: 'Priority email support (48h)', free: false, pack: false, founders: true },
  ]},
];

function Tick({ on, value }) {
  if (typeof value === 'string') {
    return <span style={{ fontFamily: 'var(--mono-font)', fontSize: 12, color: 'var(--ink)', fontWeight: 500 }}>{value}</span>;
  }
  if (on) return <span style={{ color: 'var(--good)', fontSize: 16, fontWeight: 600 }}>✓</span>;
  return <span style={{ color: 'var(--ink-faint)', fontSize: 14 }}>—</span>;
}

function PricingHeaderCard({ tierKey, recommended, onSelect, onChoose }) {
  const t = TIERS[tierKey];
  return (
    <div style={{
      padding: '28px 24px 24px',
      border: '1px solid ' + (recommended ? 'var(--ink)' : 'var(--rule)'),
      borderRadius: 'var(--radius-lg)',
      background: recommended ? 'var(--ink)' : 'var(--panel)',
      color: recommended ? 'var(--bg)' : 'var(--ink)',
      position: 'relative',
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      {recommended && <div style={{
        position: 'absolute', top: -10, left: 24,
        background: 'var(--accent-2)', color: 'var(--accent-ink)',
        padding: '3px 10px', borderRadius: 'var(--radius)',
        fontFamily: 'var(--mono-font)', fontSize: 10,
        letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 600,
      }}>Most chosen</div>}
      <div>
        <MonoLabel faint={!recommended}>
          <span style={{ color: recommended ? 'rgba(247,245,236,0.7)' : 'var(--ink-faint)' }}>{tierKey === 'free' ? '01' : tierKey === 'pack' ? '02' : '03'} · tier</span>
        </MonoLabel>
        <h3 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 28, margin: '6px 0 0', lineHeight: 1.05,
        }}>{t.label}</h3>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <div style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 44, lineHeight: 1, fontVariantNumeric: 'tabular-nums',
        }}>{t.price}</div>
        {t.priceSub && <span style={{
          fontFamily: 'var(--mono-font)', fontSize: 11,
          color: recommended ? 'rgba(247,245,236,0.65)' : 'var(--ink-faint)',
          letterSpacing: '0.06em',
        }}>{t.priceSub}</span>}
      </div>
      <div style={{
        fontSize: 13.5, lineHeight: 1.5,
        color: recommended ? 'rgba(247,245,236,0.82)' : 'var(--ink-2)',
        fontStyle: 'italic',
      }}>{t.blurb}</div>
      <button onClick={() => onChoose(tierKey)} style={{
        marginTop: 4, padding: '12px 20px', fontSize: 14, fontWeight: 600,
        background: recommended ? 'var(--bg)' : 'transparent',
        color: recommended ? 'var(--ink)' : 'var(--ink)',
        border: recommended ? 'none' : '1px solid var(--rule-strong)',
        borderRadius: 'var(--radius)', cursor: 'pointer',
        fontFamily: 'var(--body-font)',
      }}>
        {tierKey === 'free' ? 'Start basic forecast' : tierKey === 'pack' ? 'Buy Decision Pack' : 'Become a Founder'}
      </button>
    </div>
  );
}

function ScreenPricing({ tier, setTier, onCancel, onAfterChoose, route, onNavigate, auth, onSignInRequested, onSignOut, onStart }) {
  const choose = (k) => { setTier(k); onAfterChoose(); };
  return (
    <div>
      <TopNav route={route} onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} onStart={onStart} />

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '64px 40px 32px' }}>
        <Eyebrow>Pricing · honest by design</Eyebrow>
        <h1 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 'clamp(40px, 5.2vw, 68px)', lineHeight: 1.05,
          margin: '0 0 16px', textWrap: 'balance', maxWidth: 880,
        }}>The basic answer is free.<br />The workshop costs $79.</h1>
        <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 720, margin: 0 }}>
          We charge once. We don't sell leads, we don't take installer affiliate fees, and we don't
          paywall the verdict. We do paywall the workshop — the tornado plot, the hourly battery
          dispatch, the audit of the loan paperwork — because that's where the real engineering hours go.
        </p>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 40px 0' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          <PricingHeaderCard tierKey="free" onChoose={choose} />
          <PricingHeaderCard tierKey="pack" recommended onChoose={choose} />
          <PricingHeaderCard tierKey="founders" onChoose={choose} />
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '48px 40px 0' }}>
        <SectionHead kicker="feature matrix" title="What's actually in each tier" />
        <div style={{
          border: '1px solid var(--rule-strong)', borderRadius: 'var(--radius-lg)',
          overflow: 'hidden', background: 'var(--panel)',
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: 'minmax(0, 2.4fr) repeat(3, minmax(120px, 1fr))',
            background: 'var(--bg-2)',
            borderBottom: '1px solid var(--rule-strong)',
          }}>
            <div style={{ padding: '14px 20px' }}><MonoLabel>capability</MonoLabel></div>
            {['Basic', 'Decision Pack', 'Founders'].map((h, i) => (
              <div key={h} style={{
                padding: '14px 16px', textAlign: 'center',
                borderLeft: '1px solid var(--rule)',
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                fontSize: 14, color: i === 1 ? 'var(--accent)' : 'var(--ink)',
              }}>{h}</div>
            ))}
          </div>
          {PRICING_FEATURES.map((g, gi) => (
            <div key={gi}>
              <div style={{
                padding: '12px 20px',
                background: 'var(--panel-2)',
                borderBottom: '1px solid var(--rule)',
                borderTop: gi === 0 ? 'none' : '1px solid var(--rule-strong)',
                fontFamily: 'var(--mono-font)', fontSize: 11,
                textTransform: 'uppercase', letterSpacing: '0.14em',
                color: 'var(--ink-2)', fontWeight: 600,
              }}>{g.group}</div>
              {g.items.map((row, ri) => (
                <div key={ri} style={{
                  display: 'grid', gridTemplateColumns: 'minmax(0, 2.4fr) repeat(3, minmax(120px, 1fr))',
                  borderBottom: ri < g.items.length - 1 ? '1px solid var(--rule)' : 'none',
                  alignItems: 'center', minHeight: 44,
                }}>
                  <div style={{ padding: '11px 20px', fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.4 }}>{row.k}</div>
                  {['free','pack','founders'].map((tk, ti) => (
                    <div key={tk} style={{
                      padding: '11px 16px', textAlign: 'center',
                      borderLeft: '1px solid var(--rule)',
                      background: ti === 1 ? 'rgba(29,52,97,0.04)' : 'transparent',
                    }}>
                      <Tick on={row[tk] === true} value={typeof row[tk] === 'string' ? row[tk] : null} />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 40px 0' }}>
        <SectionHead kicker="add-ons" title="Things you can buy à la carte" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 20 }}>
          <AddOn label="Extra audit credit" price="$49" body="One additional proposal audit. Usable any time after Decision Pack." />
          <AddOn label="Track subscription" price="$9 / mo" body="Post-install variance vs forecast. Bill ingestion + Enphase / SolarEdge / Tesla. Cancel anytime." />
          <AddOn label="Methodology consult" price="$249" body="60-min Zoom with our modeling lead to walk through your forecast and proposal in detail." />
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 40px 0' }}>
        <SectionHead kicker="receipts" title="What we promise — in writing" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 0,
          border: '1px solid var(--rule)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          {[
            { h: 'No installer affiliations.', b: 'We do not accept lead-gen revenue, referral fees, or marketing partnerships from any installer, lender, or panel manufacturer. Ever.' },
            { h: 'No data resale.', b: 'Your audit data is yours. Aggregated regional pricing is opt-in (default off). Raw PDFs are deleted within 24-72 hours.' },
            { h: '14-day refund.', b: 'If you bought Decision Pack and the math feels wrong, email us. Refund issued, audit credit revoked, your call.' },
            { h: 'Methodology published.', b: 'Engine version, irradiance source, tariff hash — pinned to every saved forecast. Reproducible later, by us or anyone else.' },
          ].map((it, i, arr) => (
            <div key={i} style={{
              padding: 22, background: 'var(--panel)',
              borderRight: i < arr.length - 1 && (i + 1) % 2 !== 0 ? '1px solid var(--rule)' : 'none',
              borderBottom: i < arr.length - 2 ? '1px solid var(--rule)' : 'none',
            }}>
              <div style={{
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                fontSize: 17, marginBottom: 8, letterSpacing: 'var(--display-tracking)',
              }}>{it.h}</div>
              <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink-2)' }}>{it.b}</div>
            </div>
          ))}
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '64px 40px 80px', textAlign: 'center' }}>
        <h2 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 'clamp(28px, 3.5vw, 44px)', lineHeight: 1.1, margin: '0 0 16px',
          textWrap: 'balance', maxWidth: 720, marginLeft: 'auto', marginRight: 'auto',
        }}>Run the basic forecast first. Decide later.</h2>
        <Btn kind="primary" onClick={onCancel}>Start free forecast <Arrow /></Btn>
      </section>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

function AddOn({ label, price, body }) {
  return (
    <div style={{
      padding: 22, background: 'var(--panel)', border: '1px solid var(--rule)',
      borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)', fontSize: 18,
        }}>{label}</div>
        <div style={{ fontFamily: 'var(--mono-font)', fontSize: 14, color: 'var(--accent)', fontWeight: 600 }}>{price}</div>
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink-2)' }}>{body}</div>
    </div>
  );
}

Object.assign(window, { ScreenPricing });
