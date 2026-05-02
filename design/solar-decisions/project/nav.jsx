// Unified site navigation: TopNav (used on every screen except wizard), ProfileMenu,
// SaveForecastButton (inline-email gate), Footer, and SaveForecastModal (the lightweight
// "save = create free account" surface). Replaces the per-screen NavBar.

const { useState: useStateN, useEffect: useEffectN, useRef: useRefN } = React;

const NAV_TABS = [
  { k: 'forecast', label: 'Forecast' },
  { k: 'audit',    label: 'Audit' },
  { k: 'pricing',  label: 'Pricing' },
  { k: 'about',    label: 'How it works' },
  { k: 'notes',    label: 'Field Notes' },
];

// Map a route to the active tab (so deep-route screens still light the right tab).
function tabForRoute(route) {
  if (route === 'wizard' || route === 'results') return 'forecast';
  if (route === 'audit') return 'audit';
  if (route === 'pricing') return 'pricing';
  if (route === 'about') return 'about';
  if (route === 'notes' || route === 'note') return 'notes';
  if (route === 'library') return null;
  return null; // landing
}

function TopNav({ route, onNavigate, auth, onSignInRequested, onSignOut, onStart, rightExtras }) {
  const active = tabForRoute(route);
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '18px 40px', borderBottom: '1px solid var(--rule)',
      background: 'var(--bg)', position: 'sticky', top: 0, zIndex: 50,
      flexWrap: 'wrap', gap: 16,
    }}>
      <button onClick={() => onNavigate('landing')} style={{
        background: 'none', border: 'none', padding: 0, cursor: 'pointer',
      }}>
        <Wordmark />
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        {NAV_TABS.map(t => {
          const isActive = active === t.k;
          return (
            <button key={t.k} onClick={() => onNavigate(t.k)} style={{
              background: 'none', border: 'none', padding: '6px 0', cursor: 'pointer',
              fontFamily: 'var(--body-font)', fontSize: 13.5,
              color: isActive ? 'var(--ink)' : 'var(--ink-2)',
              fontWeight: isActive ? 600 : 500,
              borderBottom: isActive ? '1.5px solid var(--ink)' : '1.5px solid transparent',
              letterSpacing: '0.01em',
            }}>{t.label}</button>
          );
        })}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {rightExtras}
        {auth?.state === 'signedIn'
          ? <ProfileMenu auth={auth} onSignOut={onSignOut} onNavigate={onNavigate} />
          : <>
              <SignInButton onClick={onSignInRequested} />
              {onStart && <Btn kind="accent" onClick={onStart}>Run my forecast <Arrow /></Btn>}
            </>
        }
      </div>
    </nav>
  );
}

// Profile pill: avatar + email + dropdown chevron. Dropdown exposes saved counts,
// credits, library link, account, sign out.
function ProfileMenu({ auth, onSignOut, onNavigate }) {
  const [open, setOpen] = useStateN(false);
  const ref = useRefN(null);
  useEffectN(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const initials = (auth.email || '?').slice(0, 2).toUpperCase();
  const emailShort = (auth.email || '').replace(/^(.{14}).+(@.+)$/, '$1…$2');
  const fcCount = (auth.savedForecasts || []).length;
  const auCount = (auth.savedAudits || []).length;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '4px 10px 4px 4px',
        border: '1px solid var(--rule-strong)', borderRadius: 999,
        background: 'var(--panel)', cursor: 'pointer', fontFamily: 'var(--body-font)',
      }}>
        <span style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--ink)', color: 'var(--bg)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--mono-font)', fontWeight: 600, fontSize: 10.5,
          letterSpacing: '0.04em',
        }}>{initials}</span>
        <span style={{ fontSize: 12.5, color: 'var(--ink-2)', maxWidth: 160,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{emailShort || auth.email}</span>
        <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6"
          style={{ color: 'var(--ink-dim)' }}><path d="M3 4.5L6 7.5 9 4.5"/></svg>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 8px)', right: 0,
          minWidth: 280, zIndex: 60,
          background: 'var(--bg)', border: '1px solid var(--rule-strong)',
          borderRadius: 'var(--radius-lg)', boxShadow: '0 16px 40px -12px rgba(15,20,33,0.28)',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--rule)' }}>
            <MonoLabel>Signed in</MonoLabel>
            <div style={{ fontSize: 13.5, color: 'var(--ink)', wordBreak: 'break-all', marginTop: 3 }}>
              {auth.email}
            </div>
          </div>

          <button onClick={() => { setOpen(false); onNavigate('library', { tab: 'forecasts' }); }}
            style={menuRowStyle}>
            <span>Saved forecasts</span>
            <span style={menuCountStyle}>{fcCount}</span>
          </button>
          <button onClick={() => { setOpen(false); onNavigate('library', { tab: 'audits' }); }}
            style={menuRowStyle}>
            <span>Saved audits</span>
            <span style={menuCountStyle}>{auCount}</span>
          </button>

          <div style={{
            display: 'flex', justifyContent: 'space-between', padding: '10px 16px',
            borderTop: '1px dashed var(--rule)', borderBottom: '1px dashed var(--rule)',
            fontSize: 12.5, color: 'var(--ink-2)', background: 'var(--panel-2)',
          }}>
            <span>Audit credits</span>
            <span style={{ fontFamily: 'var(--mono-font)', fontWeight: 600 }}>
              {auth.creditsAudit || 0}
            </span>
          </div>

          <button onClick={() => { setOpen(false); onSignOut(); }} style={{
            ...menuRowStyle, color: 'var(--ink-dim)',
          }}>
            <span>Sign out</span>
            <span></span>
          </button>
        </div>
      )}
    </div>
  );
}

const menuRowStyle = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  width: '100%', padding: '12px 16px',
  background: 'transparent', border: 'none', cursor: 'pointer',
  fontFamily: 'var(--body-font)', fontSize: 13, color: 'var(--ink)',
  textAlign: 'left',
};
const menuCountStyle = {
  fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-faint)',
  letterSpacing: '0.04em',
};

// SaveForecastButton — used on Results. If signed in, saves immediately + toasts.
// If anonymous, opens the save-modal (email gate that creates a free-tier account).
function SaveForecastButton({ auth, onSave, onAnonymousGate, saved, label = 'Save forecast' }) {
  const [toast, setToast] = useStateN(false);
  const click = () => {
    if (auth?.state === 'signedIn') {
      onSave?.();
      setToast(true);
      setTimeout(() => setToast(false), 1800);
    } else {
      onAnonymousGate?.();
    }
  };
  return (
    <div style={{ position: 'relative', display: 'inline-flex' }}>
      <Btn kind="ghost" onClick={click}>
        <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d={saved ? "M3 2h8v10l-4-3-4 3z" : "M3 2h8v10l-4-3-4 3z"} fill={saved ? 'currentColor' : 'none'}/>
        </svg>
        {saved ? 'Saved' : label}
      </Btn>
      {toast && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 8px)', right: 0,
          padding: '8px 12px', background: 'var(--ink)', color: 'var(--bg)',
          borderRadius: 'var(--radius)', fontSize: 12, whiteSpace: 'nowrap',
          fontFamily: 'var(--body-font)', zIndex: 5,
        }}>Saved to your account</div>
      )}
    </div>
  );
}

// SaveForecastModal — the inline email gate. Used when an anonymous user clicks Save.
function SaveForecastModal({ open, onClose, onCreated }) {
  const [email, setEmail] = useStateN('');
  const [stage, setStage] = useStateN('email');     // 'email' | 'sent'
  useEffectN(() => { if (!open) { setEmail(''); setStage('email'); } }, [open]);
  const canSubmit = /\S+@\S+\.\S+/.test(email);
  const submit = (e) => {
    e?.preventDefault();
    if (!canSubmit) return;
    setStage('sent');
  };
  return (
    <Modal open={open} onClose={onClose} maxWidth={500}
      kicker="Save your forecast"
      title={stage === 'email' ? 'Where should we keep this?' : 'Saved · check your inbox'}
      subtitle={stage === 'email'
        ? "Enter your email and we'll save this forecast to a free account. No password — just a magic link to come back."
        : "Your forecast is saved. We sent a magic link to confirm your email so you can pick up from any device."}>
      <div style={{ padding: '8px 28px 26px' }}>
        {stage === 'email' && (
          <form onSubmit={submit}>
            <Field label="Email">
              <TextInput value={email} onChange={setEmail} placeholder="you@example.com"
                type="email" autoFocus />
            </Field>
            <button type="submit" disabled={!canSubmit} style={{
              marginTop: 16, width: '100%',
              padding: '13px 20px', fontSize: 14, fontWeight: 600,
              background: 'var(--ink)', color: 'var(--bg)', border: 'none',
              borderRadius: 'var(--radius)', cursor: canSubmit ? 'pointer' : 'not-allowed',
              fontFamily: 'var(--body-font)', opacity: canSubmit ? 1 : 0.5,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>Save forecast <Arrow /></button>
            <div style={{
              marginTop: 12, fontSize: 11.5, fontFamily: 'var(--mono-font)',
              color: 'var(--ink-faint)', letterSpacing: '0.04em', textAlign: 'center',
            }}>Free account · no card · unsubscribe anytime</div>
          </form>
        )}
        {stage === 'sent' && (
          <div>
            <div style={{
              padding: 16, background: 'var(--panel-2)',
              border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
              marginBottom: 18,
            }}>
              <MonoLabel>Forecast saved</MonoLabel>
              <div style={{ fontSize: 14, marginTop: 4, color: 'var(--ink)' }}>
                {email}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-dim)', marginTop: 8, lineHeight: 1.55 }}>
                Library now has 1 forecast. Magic-link email sent — click it from any device to pick up where you left off.
              </div>
            </div>
            <button onClick={() => { onCreated(email); }} style={{
              width: '100%', padding: '13px 20px', fontSize: 14, fontWeight: 600,
              background: 'var(--ink)', color: 'var(--bg)', border: 'none',
              borderRadius: 'var(--radius)', cursor: 'pointer',
              fontFamily: 'var(--body-font)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>Open my Library <Arrow /></button>
          </div>
        )}
      </div>
    </Modal>
  );
}

// Footer — shared across all main screens.
function Footer({ onNavigate }) {
  const cols = [
    { head: 'Product', items: [
      ['Forecast',        () => onNavigate?.('forecast')],
      ['Audit a proposal', () => onNavigate?.('audit')],
      ['Pricing',         () => onNavigate?.('pricing')],
      ['How it works',    () => onNavigate?.('about')],
    ]},
    { head: 'Resources', items: [
      ['Field Notes',     () => onNavigate?.('notes')],
      ['Methodology',     () => {}],
      ['Sources & data',  () => {}],
      ['Changelog',       () => {}],
    ]},
    { head: 'Company', items: [
      ['About',           () => {}],
      ['Independence pledge', () => {}],
      ['Press',           () => {}],
      ['Contact',         () => {}],
    ]},
    { head: 'Legal', items: [
      ['Privacy',         () => {}],
      ['Terms',           () => {}],
      ['Security',        () => {}],
      ['Disclosures',     () => {}],
    ]},
  ];
  return (
    <footer style={{
      borderTop: '1px solid var(--rule)', background: 'var(--panel-2)',
      padding: '56px 40px 32px', marginTop: 40,
    }}>
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) repeat(4, minmax(0, 1fr))',
          gap: 40, marginBottom: 48,
        }}>
          <div>
            <Wordmark />
            <p style={{
              marginTop: 14, fontSize: 13, lineHeight: 1.55, color: 'var(--ink-2)',
              maxWidth: 280,
            }}>
              Independent solar math. No installer affiliations, no lead-gen,
              no kickbacks. We work for the homeowner.
            </p>
            <div style={{
              marginTop: 16,
              fontFamily: 'var(--mono-font)', fontSize: 10.5,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: 'var(--ink-faint)',
            }}>Boulder · Denver · remote</div>
          </div>
          {cols.map((col) => (
            <div key={col.head}>
              <div style={{
                fontFamily: 'var(--mono-font)', fontSize: 10.5,
                letterSpacing: '0.14em', textTransform: 'uppercase',
                color: 'var(--ink-faint)', marginBottom: 14,
              }}>{col.head}</div>
              <ul style={{
                margin: 0, padding: 0, listStyle: 'none',
                display: 'flex', flexDirection: 'column', gap: 10,
              }}>
                {col.items.map(([label, click]) => (
                  <li key={label}>
                    <button onClick={click} style={{
                      background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                      fontFamily: 'var(--body-font)', fontSize: 13, color: 'var(--ink-2)',
                      textAlign: 'left',
                    }}>{label}</button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div style={{
          paddingTop: 20, borderTop: '1px solid var(--rule)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexWrap: 'wrap', gap: 12,
          fontFamily: 'var(--mono-font)', fontSize: 11,
          color: 'var(--ink-faint)', letterSpacing: '0.04em',
        }}>
          <div>© 2026 Solar Decisions, PBC · est. Boulder CO</div>
          <div style={{ display: 'flex', gap: 18 }}>
            <span>v0.7.2 · engine pinned 2026.04</span>
            <span>status: <span style={{ color: 'var(--good)' }}>● operational</span></span>
          </div>
        </div>
      </div>
    </footer>
  );
}

Object.assign(window, { TopNav, ProfileMenu, SaveForecastButton, SaveForecastModal, Footer, tabForRoute });
