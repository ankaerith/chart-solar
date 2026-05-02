// Auth UI: CheckoutModal, SignInModal, MagicLinkSentModal, AccountChip.
// Conversion-critical surface — minimum friction, no nags, no upsell theater.

const { useState: useAuthState } = React;

// ---- Checkout: the "purchase = sign-in" moment --------------------------
function CheckoutModal({ open, tier, onClose, onSuccess, onSwitchToSignIn }) {
  const [email, setEmail] = useAuthState('');
  const [card, setCard] = useAuthState('');
  const [submitting, setSubmitting] = useAuthState(false);
  const t = TIERS[tier] || TIERS.pack;

  React.useEffect(() => { if (!open) { setEmail(''); setCard(''); setSubmitting(false); } }, [open]);

  const canSubmit = /\S+@\S+\.\S+/.test(email) && card.replace(/\s/g, '').length >= 12;

  const submit = (e) => {
    e?.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setTimeout(() => onSuccess(email), 700);
  };

  const formatCard = (raw) => raw.replace(/\D/g, '').slice(0, 16).replace(/(.{4})/g, '$1 ').trim();

  return (
    <Modal open={open} onClose={onClose} maxWidth={560}
      kicker={`Checkout · ${t.label}`}
      title={`${t.price} — unlock the workshop`}
      subtitle="Email + card. Your account is created on payment — we'll email you a magic-link receipt to come back later.">
      <form onSubmit={submit} style={{ padding: '8px 28px 24px' }}>
        <div style={{
          padding: 16, background: 'var(--panel-2)',
          border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
          marginBottom: 22,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
            <div>
              <MonoLabel>What you get</MonoLabel>
              <div style={{ fontFamily: 'var(--display-font)', fontSize: 18, marginTop: 4 }}>{t.label}</div>
            </div>
            <div style={{
              fontFamily: 'var(--display-font)', fontSize: 28,
              fontVariantNumeric: 'tabular-nums', color: 'var(--ink)',
            }}>{t.price}</div>
          </div>
          <ul style={{ margin: '12px 0 0', paddingLeft: 18, fontSize: 13, lineHeight: 1.6, color: 'var(--ink-2)' }}>
            <li>Full workshop — every assumption editable</li>
            <li>{tier === 'founders' ? '3 proposal-audit credits' : '1 proposal-audit credit'}</li>
            <li>Methodology PDF + saveable forecasts</li>
            {tier === 'founders' && <li>12 months of Track when post-install ships</li>}
          </ul>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Email" hint="for receipt + magic-link sign-in">
            <TextInput value={email} onChange={setEmail} placeholder="you@example.com"
              type="email" autoFocus />
          </Field>
          <Field label="Card · mock" hint="any 16 digits work">
            <TextInput value={card} onChange={(v) => setCard(formatCard(v))}
              placeholder="4242 4242 4242 4242" />
          </Field>
        </div>

        <div style={{ marginTop: 22, display: 'flex', alignItems: 'center', gap: 12 }}>
          <button type="submit" disabled={!canSubmit || submitting} style={{
            flex: 1, padding: '13px 20px', fontSize: 14.5, fontWeight: 600,
            background: 'var(--ink)', color: 'var(--bg)', border: 'none',
            borderRadius: 'var(--radius)', cursor: canSubmit && !submitting ? 'pointer' : 'not-allowed',
            fontFamily: 'var(--body-font)', opacity: canSubmit && !submitting ? 1 : 0.55,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            {submitting ? 'Processing…' : `Pay ${t.price} · unlock`}
            {!submitting && <Arrow />}
          </button>
        </div>

        <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between',
          fontSize: 11.5, fontFamily: 'var(--mono-font)', color: 'var(--ink-faint)',
          letterSpacing: '0.04em' }}>
          <span>Refundable 14 days · no subscription</span>
          <button type="button" onClick={onSwitchToSignIn} style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            color: 'var(--accent-2)', fontFamily: 'inherit', fontSize: 'inherit',
            textDecoration: 'underline', textUnderlineOffset: 2,
          }}>Already paid? Sign in</button>
        </div>
      </form>
    </Modal>
  );
}

// ---- Returning sign-in: magic link only --------------------------------
function SignInModal({ open, onClose, onSent }) {
  const [email, setEmail] = useAuthState('');
  React.useEffect(() => { if (!open) setEmail(''); }, [open]);
  const canSubmit = /\S+@\S+\.\S+/.test(email);
  const submit = (e) => { e?.preventDefault(); if (canSubmit) onSent(email); };
  return (
    <Modal open={open} onClose={onClose} maxWidth={460}
      kicker="Sign in"
      title="Magic link, no password"
      subtitle="We'll email a link that signs you in. No password to remember.">
      <form onSubmit={submit} style={{ padding: '8px 28px 24px' }}>
        <Field label="Email">
          <TextInput value={email} onChange={setEmail} placeholder="you@example.com"
            type="email" autoFocus />
        </Field>
        <button type="submit" disabled={!canSubmit} style={{
          marginTop: 18, width: '100%',
          padding: '13px 20px', fontSize: 14, fontWeight: 600,
          background: 'var(--ink)', color: 'var(--bg)', border: 'none',
          borderRadius: 'var(--radius)', cursor: canSubmit ? 'pointer' : 'not-allowed',
          fontFamily: 'var(--body-font)', opacity: canSubmit ? 1 : 0.55,
        }}>Send magic link</button>
      </form>
    </Modal>
  );
}

// ---- Magic link sent: simulate the click ------------------------------
function MagicLinkSentModal({ open, onClose, onClicked }) {
  // The mock — show what they'd see in their inbox, plus a "Click the link" button
  // so the prototype actually proceeds.
  return (
    <Modal open={open} onClose={onClose} maxWidth={500}
      kicker="Check your inbox"
      title="We sent you a magic link"
      subtitle="In production you'd click the link in the email. Here, click the mock email below to continue.">
      <div style={{ padding: '8px 28px 24px' }}>
        <button onClick={() => onClicked('returning@example.com')} style={{
          width: '100%', textAlign: 'left',
          background: 'var(--panel-2)', border: '1px solid var(--rule-strong)',
          borderRadius: 'var(--radius)', padding: 16, cursor: 'pointer',
          display: 'flex', flexDirection: 'column', gap: 8,
          fontFamily: 'var(--body-font)',
        }}>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 10.5, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: 'var(--ink-faint)',
            display: 'flex', justifyContent: 'space-between',
          }}>
            <span>From: hello@solardecisions.app</span>
            <span>now</span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>
            Sign in to Solar Decisions
          </div>
          <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.5 }}>
            Click here to sign in — link expires in 15 minutes.
          </div>
          <div style={{
            marginTop: 4, fontSize: 12.5, color: 'var(--accent-2)',
            textDecoration: 'underline', textUnderlineOffset: 2,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>Sign me in <Arrow /></div>
        </button>
        <div style={{
          marginTop: 14, fontSize: 11.5, fontFamily: 'var(--mono-font)',
          color: 'var(--ink-faint)', letterSpacing: '0.04em',
          textAlign: 'center',
        }}>↑ mock email · click to simulate magic-link click</div>
      </div>
    </Modal>
  );
}

// ---- Account chip in nav (signed-in) -----------------------------------
function AccountChip({ auth, onSignOut }) {
  const [open, setOpen] = useAuthState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);
  if (auth.state !== 'signedIn') return null;
  const initials = (auth.email || '?').slice(0, 1).toUpperCase();
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '6px 10px 6px 6px',
        border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
        background: 'var(--panel)', cursor: 'pointer',
        fontFamily: 'var(--body-font)',
      }}>
        <span style={{
          width: 24, height: 24, borderRadius: '50%',
          background: 'var(--accent)', color: 'var(--accent-ink)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--display-font)', fontWeight: 600, fontSize: 12,
        }}>{initials}</span>
        <span style={{
          fontFamily: 'var(--mono-font)', fontSize: 11,
          color: 'var(--ink-2)', letterSpacing: '0.04em',
        }}>{auth.creditsAudit} credit{auth.creditsAudit === 1 ? '' : 's'}</span>
        <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6"
          style={{ color: 'var(--ink-dim)' }}><path d="M3 4.5L6 7.5 9 4.5"/></svg>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', right: 0,
          minWidth: 240, zIndex: 50,
          background: 'var(--bg)', border: '1px solid var(--rule-strong)',
          borderRadius: 'var(--radius)', boxShadow: '0 12px 32px -10px rgba(15,20,33,0.25)',
          padding: 14,
        }}>
          <div style={{
            fontFamily: 'var(--mono-font)', fontSize: 10, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: 4,
          }}>Signed in</div>
          <div style={{ fontSize: 13.5, color: 'var(--ink)', wordBreak: 'break-all', marginBottom: 12 }}>
            {auth.email}
          </div>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr auto',
            padding: '10px 0', borderTop: '1px dashed var(--rule)',
            borderBottom: '1px dashed var(--rule)',
            fontSize: 12.5, color: 'var(--ink-2)',
          }}>
            <span>Audit credits</span>
            <span style={{ fontFamily: 'var(--mono-font)', fontWeight: 600 }}>{auth.creditsAudit}</span>
          </div>
          <button onClick={() => { setOpen(false); onSignOut(); }} style={{
            marginTop: 10, width: '100%',
            padding: '8px 10px', fontSize: 12.5,
            background: 'transparent', border: '1px solid var(--rule)',
            borderRadius: 'var(--radius)', color: 'var(--ink-2)', cursor: 'pointer',
            fontFamily: 'var(--body-font)',
          }}>Sign out</button>
        </div>
      )}
    </div>
  );
}

// ---- Sign-in inline button (anonymous) ---------------------------------
function SignInButton({ onClick }) {
  return (
    <button onClick={onClick} style={{
      background: 'transparent', border: 'none', padding: '8px 4px',
      fontFamily: 'var(--body-font)', fontSize: 13.5, color: 'var(--ink-2)',
      cursor: 'pointer',
    }}>Sign in</button>
  );
}

Object.assign(window, { CheckoutModal, SignInModal, MagicLinkSentModal, AccountChip, SignInButton });
