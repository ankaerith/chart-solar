// Library — saved forecasts + saved audits. Two tabs, medium-density rows with sparkline.

const { useState: useStateLb } = React;

// Tiny inline sparkline of cumulative-wealth path (deterministic per id seed).
function Sparkline({ seed = 1, width = 120, height = 32, accent = false }) {
  const n = 26;
  const rand = (s) => { let x = Math.sin(s) * 10000; return x - Math.floor(x); };
  const points = [];
  let v = 0;
  for (let i = 0; i < n; i++) {
    const slope = 0.7 + rand(seed + i) * 1.4;
    v += slope * (i < 5 ? -1.2 : 1);
    points.push(v);
  }
  const min = Math.min(...points), max = Math.max(...points);
  const norm = points.map(p => (p - min) / (max - min || 1));
  const d = norm.map((p, i) => `${i === 0 ? 'M' : 'L'} ${(i / (n - 1)) * width} ${height - p * height * 0.85 - 2}`).join(' ');
  // Crossover marker
  const crossIdx = norm.findIndex((p, i) => i > 4 && p > 0.5);
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <line x1="0" y1={height - 2} x2={width} y2={height - 2} stroke="var(--rule)" strokeWidth="1" />
      <path d={d} fill="none" stroke={accent ? 'var(--accent)' : 'var(--ink)'} strokeWidth="1.4"
        strokeLinejoin="round" strokeLinecap="round" />
      {crossIdx > 0 && (
        <circle cx={(crossIdx / (n - 1)) * width} cy={height - norm[crossIdx] * height * 0.85 - 2}
          r="2" fill={accent ? 'var(--accent)' : 'var(--ink)'} />
      )}
    </svg>
  );
}

// Row: address + date + headline + sparkline + action menu.
function LibraryRow({ item, kind, onOpen, onDelete, onShare }) {
  const [menuOpen, setMenuOpen] = useStateLb(false);
  const [shareCopied, setShareCopied] = useStateLb(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const headline = kind === 'forecast'
    ? { v: item.headlineNpv, k: 'Median NPV', sub: `payback ${item.payback}` }
    : { v: item.varianceLabel, k: 'Variance', sub: `${item.flagsHigh} high-severity flags` };

  const accent = kind === 'forecast';

  const doShare = () => {
    const url = `https://solardecisions.app/s/${item.id}`;
    if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {});
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 1800);
    setMenuOpen(false);
  };

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 180px 200px 140px auto',
      gap: 24, alignItems: 'center',
      padding: '20px 24px',
      borderBottom: '1px solid var(--rule)',
      background: 'var(--bg)',
      position: 'relative',
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--display-font)', fontSize: 16, fontWeight: 500,
          color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>{item.address}</div>
        <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginTop: 4,
          fontFamily: 'var(--mono-font)', letterSpacing: '0.04em' }}>
          {item.systemSize} kW{kind === 'forecast' ? ` · battery ${item.battery}` : ` · ${item.installer}`}
        </div>
      </div>

      <div>
        <MonoLabel>{item.dateLabel}</MonoLabel>
        <div style={{ fontSize: 12.5, color: 'var(--ink-2)', marginTop: 4 }}>
          {item.dateRel}
        </div>
      </div>

      <div>
        <MonoLabel>{headline.k}</MonoLabel>
        <div style={{
          fontFamily: 'var(--display-font)', fontSize: 22, marginTop: 2,
          fontVariantNumeric: 'tabular-nums',
          color: kind === 'forecast' ? 'var(--accent)' : (item.varianceTone || 'var(--bad)'),
        }}>{headline.v}</div>
        <div style={{ fontSize: 11, color: 'var(--ink-faint)',
          fontFamily: 'var(--mono-font)', marginTop: 2 }}>{headline.sub}</div>
      </div>

      <Sparkline seed={item.seed} accent={accent} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }} ref={ref}>
        <button onClick={() => onOpen(item)} style={{
          padding: '8px 14px', fontSize: 12.5,
          background: 'transparent', border: '1px solid var(--rule-strong)',
          borderRadius: 'var(--radius)', cursor: 'pointer', color: 'var(--ink)',
          fontFamily: 'var(--body-font)',
        }}>Open</button>
        <button onClick={() => setMenuOpen(o => !o)} aria-label="More" style={{
          width: 32, height: 32, padding: 0,
          background: 'transparent', border: '1px solid var(--rule)',
          borderRadius: 'var(--radius)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--ink-2)',
        }}>
          <svg width="14" height="3" viewBox="0 0 14 3" fill="currentColor">
            <circle cx="2" cy="1.5" r="1.2"/>
            <circle cx="7" cy="1.5" r="1.2"/>
            <circle cx="12" cy="1.5" r="1.2"/>
          </svg>
        </button>
        {menuOpen && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0,
            minWidth: 200, zIndex: 10,
            background: 'var(--bg)', border: '1px solid var(--rule-strong)',
            borderRadius: 'var(--radius)', boxShadow: '0 12px 30px -10px rgba(15,20,33,0.22)',
            overflow: 'hidden',
          }}>
            <button onClick={doShare} style={menuItemStyle}>
              <span>Copy share link</span>
              <span style={{ fontFamily: 'var(--mono-font)', fontSize: 10, color: 'var(--ink-faint)' }}>public</span>
            </button>
            <button onClick={() => { onOpen(item, true); setMenuOpen(false); }} style={menuItemStyle}>
              <span>Duplicate</span><span></span>
            </button>
            <button onClick={() => { setMenuOpen(false); onDelete(item.id); }} style={{
              ...menuItemStyle, color: 'var(--bad)',
            }}>
              <span>Delete</span><span></span>
            </button>
          </div>
        )}
        {shareCopied && (
          <div style={{
            position: 'absolute', top: 'calc(100% + 6px)', right: 0,
            padding: '8px 12px', background: 'var(--ink)', color: 'var(--bg)',
            borderRadius: 'var(--radius)', fontSize: 11.5, whiteSpace: 'nowrap',
            fontFamily: 'var(--body-font)', zIndex: 11,
          }}>Share link copied</div>
        )}
      </div>
    </div>
  );
}

const menuItemStyle = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  width: '100%', padding: '11px 14px',
  background: 'transparent', border: 'none', cursor: 'pointer',
  fontFamily: 'var(--body-font)', fontSize: 13, color: 'var(--ink)',
  textAlign: 'left',
};

function EmptyState({ kind, onCta }) {
  const copy = kind === 'forecasts'
    ? { head: 'No forecasts yet.', body: 'Run one in about 4 minutes — address, utility bill, system size. We auto-save it here when you finish.', cta: 'Start a forecast' }
    : { head: 'No audits yet.', body: 'Drop an installer proposal PDF and we\'ll read it, flag the risky math, and write the questions you should ask back.', cta: 'Audit a proposal' };
  return (
    <div style={{
      padding: '64px 32px', textAlign: 'center',
      border: '1px dashed var(--rule-strong)', borderRadius: 'var(--radius-lg)',
      background: 'var(--panel)',
    }}>
      <div style={{
        fontFamily: 'var(--display-font)', fontSize: 24, marginBottom: 10,
      }}>{copy.head}</div>
      <p style={{ fontSize: 14, color: 'var(--ink-2)', maxWidth: 460, margin: '0 auto 20px', lineHeight: 1.55 }}>
        {copy.body}
      </p>
      <Btn kind="accent" onClick={onCta}>{copy.cta} <Arrow /></Btn>
    </div>
  );
}

function ScreenLibrary({ auth, route, onNavigate, onSignInRequested, onSignOut, onStart,
  initialTab, onOpenForecast, onOpenAudit, onDelete }) {
  const [tab, setTab] = useStateLb(initialTab || 'forecasts');
  const isAnonymous = auth.state !== 'signedIn';
  const forecasts = auth.savedForecasts || [];
  const audits = auth.savedAudits || [];
  const items = tab === 'forecasts' ? forecasts : audits;

  return (
    <div>
      <TopNav route="library" onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} onStart={onStart} />

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '48px 40px 24px' }}>
        <Eyebrow>Library</Eyebrow>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap' }}>
          <h1 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 'clamp(32px, 4vw, 52px)', lineHeight: 1.05, margin: 0,
          }}>Your saved work.</h1>
          <div style={{
            fontSize: 13, color: 'var(--ink-2)', maxWidth: 520, lineHeight: 1.55,
          }}>
            Forecasts auto-save when you finish. Audits save when the variance report opens.
            Each item gets a versioned snapshot — engine, tariff, and inputs are pinned.
          </div>
        </div>
      </section>

      {isAnonymous && (
        <section style={{ maxWidth: 1280, margin: '0 auto', padding: '0 40px 16px' }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            gap: 16, flexWrap: 'wrap',
            padding: '14px 18px', background: 'var(--panel-2)',
            border: '1px solid var(--rule)', borderRadius: 'var(--radius-lg)',
            borderLeft: '3px solid var(--accent-2)',
          }}>
            <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.5, maxWidth: 720 }}>
              <strong style={{ color: 'var(--ink)' }}>Local-only mode.</strong>{' '}
              These items live in this browser. Sign in to keep them across devices and unlock share links.
            </div>
            <Btn kind="primary" onClick={onSignInRequested}>Sign in to keep these <Arrow /></Btn>
          </div>
        </section>
      )}

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '8px 40px 0' }}>
        <div style={{
          display: 'flex', borderBottom: '1px solid var(--rule)', gap: 0,
        }}>
          {[
            { k: 'forecasts', label: 'Forecasts', count: forecasts.length },
            { k: 'audits',    label: 'Audits',    count: audits.length },
          ].map(t => {
            const active = tab === t.k;
            return (
              <button key={t.k} onClick={() => setTab(t.k)} style={{
                padding: '14px 22px',
                background: 'transparent', border: 'none', cursor: 'pointer',
                fontFamily: 'var(--body-font)', fontSize: 14,
                color: active ? 'var(--ink)' : 'var(--ink-2)',
                fontWeight: active ? 600 : 500,
                borderBottom: active ? '2px solid var(--ink)' : '2px solid transparent',
                marginBottom: -1,
                display: 'inline-flex', alignItems: 'center', gap: 8,
              }}>
                {t.label}
                <span style={{
                  fontFamily: 'var(--mono-font)', fontSize: 11,
                  color: 'var(--ink-faint)', letterSpacing: '0.04em',
                }}>({t.count})</span>
              </button>
            );
          })}
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '24px 40px 80px' }}>
        {items.length === 0 ? (
          <EmptyState kind={tab} onCta={tab === 'forecasts' ? onStart : () => onNavigate('audit')} />
        ) : (
          <div style={{
            border: '1px solid var(--rule)', borderRadius: 'var(--radius-lg)',
            overflow: 'hidden', background: 'var(--bg)',
          }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 180px 200px 140px auto',
              gap: 24, padding: '12px 24px',
              background: 'var(--panel-2)', borderBottom: '1px solid var(--rule)',
              fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
              textTransform: 'uppercase', color: 'var(--ink-faint)',
            }}>
              <div>Address · system</div>
              <div>Saved</div>
              <div>{tab === 'forecasts' ? 'Headline' : 'Variance'}</div>
              <div>25-yr path</div>
              <div></div>
            </div>
            {items.map(item => (
              <LibraryRow key={item.id} item={item}
                kind={tab === 'forecasts' ? 'forecast' : 'audit'}
                onOpen={tab === 'forecasts' ? onOpenForecast : onOpenAudit}
                onDelete={(id) => onDelete(tab, id)} />
            ))}
          </div>
        )}
      </section>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

Object.assign(window, { ScreenLibrary });
