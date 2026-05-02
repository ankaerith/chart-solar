// Results screen — the payoff. Verdict, distribution, scenarios, sensitivity, action row.

const { useState: useStateR } = React;

function VerdictBanner() {
  // Lens-free verdict: surface a balanced read of the financial median + environmental + resilience.
  const v = {
    head: 'Solar likely wins — modestly.',
    body: 'Median NPV +$31,400 over 25 years at your 5.5% mortgage discount rate. Crossover with grid happens in year 9. The headline payback insulates against the 5.4% utility escalator we modeled — even at 3% you stay net-positive in the 80% band. 247 tCO₂ offset over the system life. Battery sizing trims financial upside but adds 11 hours of typical-load backup.',
    verdict: 'go',
    tone: 'good',
  };
  const tone = 'var(--good)';
  return (
    <div style={{
      borderTop: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)',
      background: 'var(--panel)',
    }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 40px',
        display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 32, alignItems: 'center' }}>
        <div>
          <Eyebrow color={tone}>Verdict · balanced read · {v.verdict}</Eyebrow>
          <h2 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 'clamp(28px, 3.4vw, 44px)', lineHeight: 1.1, margin: '0 0 12px',
          }}>{v.head}</h2>
          <p style={{ fontSize: 15.5, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 720, margin: 0 }}>{v.body}</p>
        </div>
        <div style={{
          width: 90, height: 90, borderRadius: '50%',
          border: `2px solid ${tone}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--display-font)', fontWeight: 700, fontSize: 36, color: tone,
        }}>{v.tone === 'good' ? '✓' : '~'}</div>
      </div>
    </div>
  );
}

function HeadlineGrid() {
  const items = [
    { k: 'Median NPV', v: '+$31,400', sub: 'discount 5.5% · n=500', accent: true },
    { k: 'Disc. payback', v: '11.2 yr', sub: 'vs installer 7 yr' },
    { k: 'Crossover', v: 'yr 9', sub: '$/kWh < utility' },
    { k: 'IRR (median)', v: '6.8%', sub: 'reinvest. caveat' },
    { k: 'Lifetime tCO₂', v: '247', sub: 'WECC marginal' },
    { k: 'P10 → P90', v: '$8.2k–$58.7k', sub: '80% of paths', tight: true },
  ];
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 0,
      borderTop: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)',
    }}>
      {items.map((it, i) => (
        <div key={i} style={{
          padding: '20px 18px',
          borderRight: i < items.length - 1 ? '1px solid var(--rule)' : 'none',
          background: 'var(--bg)',
          minWidth: 0,
        }}>
          <MonoLabel>{it.k}</MonoLabel>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: it.tight ? 22 : 28, marginTop: 6, lineHeight: 1.1,
            color: it.accent ? 'var(--accent)' : 'var(--ink)',
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{it.v}</div>
          <div style={{ fontSize: 11, marginTop: 4, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.sub}</div>
        </div>
      ))}
    </div>
  );
}

function SectionHead({ kicker, title, right }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
      gap: 16, marginBottom: 18, paddingBottom: 12, borderBottom: '1px solid var(--rule-strong)',
    }}>
      <div>
        <MonoLabel>{kicker}</MonoLabel>
        <h3 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 26, margin: '6px 0 0', lineHeight: 1.1,
        }}>{title}</h3>
      </div>
      {right}
    </div>
  );
}

function ScenarioRow({ label, value, delta, bar, max }) {
  const w = Math.abs(value) / max * 100;
  const positive = value >= 0;
  return (
    <div style={{ padding: '12px 0', borderBottom: '1px dashed var(--rule)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--ink)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 13,
          color: positive ? 'var(--good)' : 'var(--bad)', fontWeight: 600,
          flexShrink: 0,
        }}>{positive ? '+' : ''}${(value/1000).toFixed(1)}k</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, alignItems: 'center' }}>
        <div style={{ position: 'relative', height: 16, background: 'var(--panel-2)', borderRadius: 2 }}>
          <div style={{
            position: 'absolute', top: 0, bottom: 0,
            left: positive ? '50%' : `${50 - w/2}%`,
            width: `${w/2}%`,
            background: bar || (positive ? 'var(--accent)' : 'var(--accent-2)'),
          }} />
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'var(--ink)' }} />
        </div>
        <div style={{ fontFamily: 'var(--mono-font)', fontSize: 10.5, color: 'var(--ink-dim)', whiteSpace: 'nowrap', letterSpacing: '0.04em' }}>{delta}</div>
      </div>
    </div>
  );
}

function ScenariosBlock() {
  const max = 60000;
  return (
    <Panel style={{ padding: 28 }}>
      <SectionHead kicker="01 · capital-allocation comparison"
        title="What else could this money do?"
        right={<MonoLabel faint>vs. do-nothing baseline · 25-yr</MonoLabel>} />
      <div style={{ marginTop: 8 }}>
        <ScenarioRow label="Solar — cash" value={42100} delta="best NPV" max={max} />
        <ScenarioRow label="Solar — loan (8.2% eff.)" value={18400} delta="dealer fee drag" max={max} />
        <ScenarioRow label="Solar — lease (2.9% esc.)" value={4200} delta="title with installer" max={max} bar="var(--warn)" />
        <ScenarioRow label="Solar — PPA" value={-1800} delta="net negative" max={max} />
        <ScenarioRow label="HYSA @ 4.5% (cash equiv.)" value={29200} delta="opportunity cost" max={max} bar="var(--ink-dim)" />
        <ScenarioRow label="S&P 500 long-run @ 7%" value={51400} delta="higher risk" max={max} bar="var(--ink-dim)" />
        <ScenarioRow label="Pay down mortgage @ 5.5%" value={31000} delta="zero-risk equivalent" max={max} bar="var(--ink-dim)" />
      </div>
      <div style={{
        marginTop: 16, padding: 14, borderLeft: '2px solid var(--accent-2)',
        background: 'var(--panel-2)', fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink-2)',
      }}>
        <strong style={{ fontFamily: 'var(--mono-font)', fontSize: 11, letterSpacing: '0.1em' }}>READ:</strong>{' '}
        Cash solar narrowly beats S&P 500 over 25 years on the median path — but the loan loses to your mortgage and the PPA loses to the mattress. The financing wrapper matters more than the panels.
      </div>
    </Panel>
  );
}

function SensitivityBlock() {
  const items = [
    { name: 'Utility rate escalation', low: -22000, high: 38000 },
    { name: 'Hold duration (5–25 yr)', low: -8000, high: 18000 },
    { name: 'Federal credit availability', low: -14000, high: 4000 },
    { name: 'Annual degradation rate', low: -6500, high: 4200 },
    { name: 'Discount rate assumption', low: -11000, high: 9500 },
    { name: 'Year-1 production (±15%)', low: -7800, high: 7800 },
    { name: 'Panel-shading assumption', low: -3400, high: 1800 },
  ];
  return (
    <Panel style={{ padding: 28 }}>
      <SectionHead kicker="02 · tornado sensitivity"
        title="Which knobs actually move the answer?"
        right={<MonoLabel faint>impact on median NPV</MonoLabel>} />
      <TornadoChart items={items} />
      <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
        Utility rate escalation dwarfs everything else. We Monte Carlo it across historical CAGR distributions per utility — installer estimates that hard-code 4.5% are doing you a quiet disservice.
      </div>
    </Panel>
  );
}

function CaveatsBlock() {
  const items = [
    { tag: 'KNOWN', body: 'Federal residential credit modeled as $0 for systems placed in service after 2025-12-31. State + utility incentives only.' },
    { tag: 'KNOWN', body: 'Hold duration default of 12 yr is ZIP-defaulted from US Census mobility data. Overrideable; actually-staying-25-yr changes NPV by +$18k.' },
    { tag: 'PARTIAL', body: 'Battery dispatch is rule-based (charge off-peak / discharge at peak) at launch. LP-optimized dispatch lands Phase 2 — typically ±3-5% NPV delta.' },
    { tag: 'PARTIAL', body: 'Hourly load profile is a ResStock archetype until you connect Green Button. Real intervals usually shift sizing recommendation by ±0.5 kW.' },
    { tag: 'UNKNOWN', body: 'Future policy. NEM rules can change. We model rate escalation, not regulatory shocks. The P10 path captures some of this.' },
  ];
  const colorFor = t => t === 'KNOWN' ? 'var(--good)' : t === 'PARTIAL' ? 'var(--warn)' : 'var(--bad)';
  return (
    <Panel style={{ padding: 28 }}>
      <SectionHead kicker="03 · honest limits"
        title="What this forecast does and doesn't know" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 8 }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: 16, alignItems: 'flex-start' }}>
            <div style={{
              fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
              color: colorFor(it.tag), padding: '4px 0',
              borderTop: `2px solid ${colorFor(it.tag)}`, fontWeight: 600,
            }}>{it.tag}</div>
            <div style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--ink-2)', paddingTop: 4 }}>{it.body}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function NextStepRow({ kicker, title, body, cta, primary, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: 24, background: primary ? 'var(--ink)' : 'var(--panel)',
      border: '1px solid ' + (primary ? 'var(--ink)' : 'var(--rule)'),
      borderRadius: 'var(--radius-lg)',
      display: 'flex', flexDirection: 'column', gap: 12,
      color: primary ? 'var(--bg)' : 'var(--ink)',
      cursor: onClick ? 'pointer' : 'default',
      transition: 'transform 0.1s',
    }}>
      <div style={{
        fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
        color: primary ? 'rgba(247,245,236,0.6)' : 'var(--accent-2)',
        textTransform: 'uppercase',
      }}>{kicker}</div>
      <div style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)', fontSize: 22, lineHeight: 1.15,
      }}>{title}</div>
      <div style={{ fontSize: 13, lineHeight: 1.55, color: primary ? 'rgba(247,245,236,0.75)' : 'var(--ink-2)', flex: 1 }}>{body}</div>
      <div style={{
        marginTop: 4, paddingTop: 12,
        borderTop: '1px solid ' + (primary ? 'rgba(247,245,236,0.18)' : 'var(--rule)'),
        fontSize: 13, fontWeight: 600, color: primary ? 'var(--bg)' : 'var(--accent)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>{cta}<span>→</span></div>
    </div>
  );
}

function NextStepsRow({ onAudit, tier, onUpgrade, auth }) {
  const auditCredits = auth?.creditsAudit || 0;
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr)',
      gap: 20, marginTop: 8,
    }}>
      <NextStepRow kicker={auditCredits ? `${auditCredits} audit credit${auditCredits > 1 ? 's' : ''} available` : 'check the proposal'} primary
        title={auditCredits ? 'Audit a quote — credit ready' : 'Audit a quote — $79'}
        body="Drop your installer's PDF. We diff their year-1 kWh, escalator, dealer fee, and DC:AC ratio against this baseline and produce a one-page variance report + an ask-your-installer question list."
        cta={auditCredits ? `Use audit credit (${auditCredits} left)` : 'Run an audit'}
        onClick={onAudit} />
      <NextStepRow kicker="lock these numbers"
        title={tier === 'free' ? 'Save & methodology PDF' : 'Save & methodology PDF'}
        body={tier === 'free'
          ? 'Save this forecast and export the methodology PDF — every assumption, every source. Decision Pack required.'
          : 'Save this forecast (engine + irradiance + tariff hash are pinned). Export the methodology PDF.'}
        cta={tier === 'free' ? '🔒 Decision Pack' : 'Save & export'} />
      <ComingSoonRow
        kicker="coming soon"
        title="Track post-install"
        body="Compare monthly bills and inverter data against this forecast once your system is live. Get notified when we open the waitlist."
        cta="Notify me" />
    </div>
  );
}

function ComingSoonRow({ kicker, title, body, cta }) {
  return (
    <div style={{
      padding: 24, background: 'var(--panel-2)',
      border: '1px dashed var(--rule-strong)',
      borderRadius: 'var(--radius-lg)',
      display: 'flex', flexDirection: 'column', gap: 12,
      color: 'var(--ink-2)', position: 'relative',
    }}>
      <div style={{ position: 'absolute', top: 14, right: 14,
        fontFamily: 'var(--mono-font)', fontSize: 9, letterSpacing: '0.16em',
        textTransform: 'uppercase', color: 'var(--ink-faint)',
        padding: '3px 7px', border: '1px solid var(--rule-strong)', borderRadius: 'var(--radius)',
      }}>Q3</div>
      <div style={{
        fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
        color: 'var(--ink-faint)', textTransform: 'uppercase',
      }}>{kicker}</div>
      <div style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)', fontSize: 22, lineHeight: 1.15,
        color: 'var(--ink-2)',
      }}>{title}</div>
      <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--ink-dim)', flex: 1 }}>{body}</div>
      <div style={{
        marginTop: 4, paddingTop: 12,
        borderTop: '1px dashed var(--rule)',
        fontSize: 13, fontWeight: 500, color: 'var(--ink-dim)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>{cta}<span>→</span></div>
    </div>
  );
}

function UpgradeBanner({ tier, onUpgrade }) {
  const upTier = tier === 'free' ? 'pack' : 'founders';
  const t = TIERS[upTier];
  return (
    <div style={{
      padding: '32px', background: 'var(--ink)', color: 'var(--bg)',
      borderRadius: 'var(--radius-lg)',
      display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 24,
      alignItems: 'center',
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 10,
          letterSpacing: '0.16em', textTransform: 'uppercase',
          color: 'rgba(247,245,236,0.6)', marginBottom: 10,
        }}>{tier === 'free' ? 'You are on Basic — verdict only' : 'You are on Decision Pack'}</div>
        <h3 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 28, lineHeight: 1.1, margin: '0 0 10px',
        }}>{tier === 'free'
          ? 'You are seeing the cover page. The workshop is behind a paywall.'
          : 'Going post-install? Founders bundles 12 months of Track + 2 extra audit credits.'}</h3>
        <p style={{ fontSize: 14, lineHeight: 1.55, color: 'rgba(247,245,236,0.78)', margin: 0, maxWidth: 720 }}>
          {tier === 'free'
            ? 'Hourly battery dispatch, tornado sensitivity, capital-allocation diff, NEM 3.0 modeling, dealer-fee audit, methodology PDF, and one full proposal audit credit — all included in Decision Pack.'
            : 'Three audit credits (most homeowners collect 2–3 quotes), a year of variance-vs-forecast on your real install, and priority support — for $50 more than the Pack alone.'}
        </p>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 48, lineHeight: 1, fontVariantNumeric: 'tabular-nums',
        }}>{t.price}</div>
        <div style={{
          fontFamily: 'var(--mono-font)', fontSize: 11, color: 'rgba(247,245,236,0.6)',
          marginBottom: 14,
        }}>{t.priceSub || 'one-time'}</div>
        <button onClick={onUpgrade} style={{
          padding: '13px 22px', fontSize: 14, fontWeight: 600,
          background: 'var(--bg)', color: 'var(--ink)', border: 'none',
          borderRadius: 'var(--radius)', cursor: 'pointer',
          fontFamily: 'var(--body-font)',
          display: 'inline-flex', alignItems: 'center', gap: 8,
        }}>Unlock {t.label} <Arrow /></button>
      </div>
    </div>
  );
}

function ScreenResults({ tier, setTier, auth, onSignInRequested, onSignOut, onCancel, onAudit, onUpgrade, onSave, onSaveAnonymous, route, onNavigate }) {
  const savedAlready = (auth?.savedForecasts?.length || 0) > 0;
  const rightExtras = (
    <>
      <SaveForecastButton auth={auth} onSave={onSave} onAnonymousGate={onSaveAnonymous} saved={savedAlready} />
      <Btn kind="primary" onClick={tier === 'free' ? onUpgrade : undefined}>
        {tier === 'free' ? 'Unlock workshop' : 'Export PDF'}
      </Btn>
    </>
  );
  return (
    <div>
      <TopNav route={route} onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut}
        rightExtras={rightExtras} />

      <section style={{ padding: '48px 40px 32px', maxWidth: 1280, margin: '0 auto' }}>
        <Eyebrow>Forecast · 1242 Spruce St · Boulder, CO · 7.2 kW</Eyebrow>
        <h1 style={{
          fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
          letterSpacing: 'var(--display-tracking)',
          fontSize: 'clamp(40px, 5.5vw, 72px)', lineHeight: 1.02,
          margin: '0 0 16px', textWrap: 'balance',
        }}>25 years, 500 paths,<br />one distribution.</h1>
        <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', maxWidth: 720, margin: 0 }}>
          Below is the full distribution of cumulative-net-wealth outcomes for your roof, given everything you told us and the things we know about your address, utility, and tariff. The headline number is the median; the band is the 80% confidence interval.
        </p>
      </section>

      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 24px' }}>
        <Panel style={{ padding: 22, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, marginBottom: 14 }}>
            <div>
              <MonoLabel>Cumulative net wealth · solar vs do-nothing baseline</MonoLabel>
              <div style={{
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                fontSize: 22, marginTop: 4,
              }}>Year-by-year, {hasFeature(tier, 'sims_500') ? '500' : '50'} simulated paths</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {['cash', 'loan', 'lease'].map(s => (
                <div key={s} style={{
                  fontFamily: 'var(--mono-font)', fontSize: 10, color: 'var(--ink-dim)',
                  padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
                  textTransform: 'uppercase', letterSpacing: '0.1em',
                }}>{s}</div>
              ))}
            </div>
          </div>
          <div style={{ minHeight: 320 }}><HeroChart /></div>
        </Panel>
      </div>

      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px' }}>
        <HeadlineGrid />
      </div>

      <VerdictBanner />

      {tier === 'free' ? (
        <section style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 40px' }}>
          <WorkshopTeaser tier={tier} onUpgrade={onUpgrade} />
        </section>
      ) : (
        <>
          <section style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 40px',
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: 28 }}>
            <ScenariosBlock />
            <SensitivityBlock />
          </section>
          <section style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 40px' }}>
            <WorkshopKnobs />
          </section>
          <section style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 40px' }}>
            <Panel style={{ padding: 28 }}>
              <SectionHead kicker="bonus · battery dispatch"
                title="What your battery actually does, hour by hour"
                right={<MonoLabel faint>self-consumption strategy · summer weekday</MonoLabel>} />
              <BatteryDispatch />
              <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 14, lineHeight: 1.55, fontStyle: 'italic' }}>
                Off-peak charging fills the bank; the on-peak window discharges into your load. Under NEM 3.0
                this strategy alone is what makes batteries pay back; under your NEM 1:1 it's modest extra.
              </div>
            </Panel>
          </section>
        </>
      )}

      {tier === 'pack' && (
        <section style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 40px' }}>
          <UpgradeBanner tier={tier} onUpgrade={onUpgrade} />
        </section>
      )}

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 80px' }}>
        <SectionHead kicker="04 · what next" title="Next steps" />
        <NextStepsRow onAudit={onAudit} tier={tier} onUpgrade={onUpgrade} auth={auth} />
      </section>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

Object.assign(window, { ScreenResults, ScenarioRow });
