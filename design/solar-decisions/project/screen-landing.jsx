// Landing screen — entry point. Hero with chart, modes strip, math row, footer.

const { useState: useStateL } = React;

// NavBar removed; replaced by global TopNav in nav.jsx.

function HeroPanel() {
  return (
    <Panel style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <MonoLabel>Sample household · Boulder CO · 7.2 kW</MonoLabel>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            fontSize: 22, marginTop: 4, letterSpacing: 'var(--display-tracking)',
          }}>25-year cumulative net wealth</div>
        </div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 10, color: 'var(--ink-faint)',
          padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
          textTransform: 'uppercase', letterSpacing: '0.1em', whiteSpace: 'nowrap',
        }}>n = 28 sims</div>
      </div>
      <div style={{ flex: '1 1 auto', minHeight: 280 }}><HeroChart /></div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid var(--rule)' }}>
        <div style={{ padding: '10px 14px 0 0', borderRight: '1px solid var(--rule)' }}>
          <MetricRow label="Median NPV" value="+$31,400" sub="discount 5.0%" accent />
          <MetricRow label="Crossover yr" value="yr 9" sub="solar > grid $/kWh" />
          <MetricRow label="P10 outcome" value="+$8,200" sub="rate path stagnant" />
        </div>
        <div style={{ padding: '10px 0 0 14px' }}>
          <MetricRow label="Discounted payback" value="11.2 yr" sub="vs installer claim 7" />
          <MetricRow label="vs HYSA 4.5%" value="+$12,900" sub="opportunity cost" />
          <MetricRow label="P90 outcome" value="+$58,700" sub="rate path historical" />
        </div>
      </div>
    </Panel>
  );
}

function MetricRow({ label, value, sub, accent }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
      padding: '10px 0', borderBottom: '1px solid var(--rule)', gap: 16,
    }}>
      <MonoLabel>{label}</MonoLabel>
      <div style={{ textAlign: 'right' }}>
        <div style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          fontSize: 18, color: accent ? 'var(--accent)' : 'var(--ink)',
          fontVariantNumeric: 'tabular-nums',
        }}>{value}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)' }}>{sub}</div>}
      </div>
    </div>
  );
}

// Was: ValueLensNote — removed (no values lens in design anymore).

function SunBackdrop() {
  // Pinned sun backdrop — fixed to the viewport like the header.
  // Rendered via portal to <body> so it sits BENEATH the #root content
  // stacking context. The page scrolls over it.
  const cx = 1100, cy = 140, R = 70;
  const rings = [140, 220, 320, 440, 580, 740, 920];
  const svg = (
    <svg viewBox="0 0 1280 900" preserveAspectRatio="xMaxYMin slice"
      aria-hidden="true"
      style={{
        position: 'fixed', top: 0, right: 0,
        width: '100vw', height: '100vh',
        pointerEvents: 'none', zIndex: 0,
      }}>
      <g fill="none" stroke="var(--accent)" strokeWidth="1">
        {rings.map((r, i) => (
          <circle key={i} cx={cx} cy={cy} r={r}
            opacity={0.18 - i * 0.018} />
        ))}
      </g>
      <circle cx={cx} cy={cy} r={R} fill="var(--accent)" opacity="0.85" />
    </svg>
  );
  return ReactDOM.createPortal(svg, document.body);
}

function Hero({ onStart, onAudit }) {
  return (
    <section className="hero" style={{
      display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.05fr)',
      gap: 64, alignItems: 'center', padding: '64px 40px 56px',
      maxWidth: 1360, margin: '0 auto',
      position: 'relative',
    }}>
      <div>
        <Eyebrow>Plan it · Check it · Track it</Eyebrow>
        <h1 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 'clamp(40px, 6.2vw, 84px)', lineHeight: 1.02,
          margin: '0 0 24px', color: 'var(--ink)', textWrap: 'balance',
        }}>The honest math<br />for your roof.</h1>
        <p style={{
          fontFamily: 'var(--body-font)', fontSize: 'clamp(16px, 1.3vw, 19px)',
          lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 540, margin: '0 0 32px',
        }}>
          Residential solar is sold on 25-year promises built from optimistic assumptions.
          We run the numbers independently — hourly physics, Monte Carlo on rate paths,
          every alternative your capital could be doing instead. <em style={{ color: 'var(--ink)' }}>No installer affiliations. No lead-gen.</em>
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <Btn kind="primary" onClick={onStart}>Start free forecast <Arrow /></Btn>
          <Btn kind="ghost" onClick={onAudit}>Audit my proposal · $79</Btn>
          <span style={{ fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-faint)', marginLeft: 4 }}>
            no signup to start · address + utility bill
          </span>
        </div>
      </div>
      <div>
        <HeroPanel />
      </div>
    </section>
  );
}

function ModeCard({ idx, name, tag, head, body, footer, primary, onClick }) {
  return (
    <article onClick={onClick} style={{
      padding: 28, background: 'var(--panel)', border: '1px solid var(--rule)',
      borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column',
      gap: 16, cursor: onClick ? 'pointer' : 'default',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <MonoLabel>{idx} · {name}</MonoLabel>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 10, color: 'var(--ink-faint)',
          padding: '2px 6px', border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
        }}>{tag}</div>
      </div>
      <h3 style={{
        margin: 0, fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)', fontSize: 26, lineHeight: 1.1,
        color: primary ? 'var(--accent)' : 'var(--ink)',
      }}>{head}</h3>
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--ink-2)', flex: '1 1 auto' }}>{body}</p>
      <div style={{
        paddingTop: 14, borderTop: '1px solid var(--rule)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-dim)',
      }}>
        <span>{footer}</span><span style={{ color: 'var(--accent)' }}>→</span>
      </div>
    </article>
  );
}

function ModesStrip({ onStart }) {
  return (
    <section style={{ padding: '40px 40px 64px', maxWidth: 1360, margin: '0 auto' }}>
      <MonoLabel>── one engine, three questions ──</MonoLabel>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: 20, marginTop: 16,
      }}>
        <ModeCard idx="01" name="Explore" tag="free" head="Should I go solar?"
          body="Address + a utility bill. We run an independent production model and a Monte Carlo across rate-escalation paths. Output is a distribution of 25-year outcomes, not a single headline number."
          footer="PVWatts v8 · Sunroof shading · NSRDB" primary onClick={onStart} />
        <ModeCard idx="02" name="Audit" tag="$79" head="Check this proposal."
          body="Drop your installer's PDF. We diff their math against independent benchmarks — where the year-1 kWh, escalator, dealer fee, or DC:AC ratio drift, by how much, and which levers drive the gap."
          footer="Vertex AI extraction · NREL baseline" />
        <ModeCard idx="03" name="Track" tag="$9 / mo" head="Did it actually work?"
          body="Post-install. Bill ingestion + Enphase / SolarEdge / Tesla monitoring. Monthly variance vs. the forecast you were sold — bill-level and production-level."
          footer="green button · monitoring api · TTL 25y" />
      </div>
    </section>
  );
}

function MathRow() {
  const items = [
    { k: '8760', l: 'hours simulated per year, every year, for 25 years' },
    { k: 'n=500', l: 'Monte Carlo paths across weather, rates, degradation, hold' },
    { k: '0%', l: 'affiliate revenue · lead-gen handoffs · referral fees' },
    { k: 'NEM 3', l: 'net-billing tariff modeled hourly, post-Apr 2023 CA' },
  ];
  return (
    <section style={{ borderTop: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)', background: 'var(--panel-2)' }}>
      <div style={{
        maxWidth: 1360, margin: '0 auto', padding: '32px 40px',
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 32,
      }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6, borderLeft: '1px solid var(--rule)', paddingLeft: 16 }}>
            <div style={{
              fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
              letterSpacing: 'var(--display-tracking)', fontSize: 36,
              color: 'var(--ink)', lineHeight: 1,
            }}>{it.k}</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.4, color: 'var(--ink-dim)' }}>{it.l}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// Footer + ValueLensNote both removed — Footer is global (nav.jsx).

function ScreenLanding({ tier, setTier, onStart, onAudit, onPricing, route, onNavigate, auth, onSignInRequested, onSignOut }) {
  return (
    <div>
      <SunBackdrop />
      <TopNav route={route} onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} onStart={onStart} />
      <Hero onStart={onStart} onAudit={onAudit} />
      <ModesStrip onStart={onStart} />
      <MathRow />
      <Footer onNavigate={onNavigate} />
    </div>
  );
}

Object.assign(window, { ScreenLanding });
