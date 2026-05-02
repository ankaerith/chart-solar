// Shared UI primitives for Solar Decisions, in Solstice · Ink.

const SDU_BTN_STYLES = {
  primary: {
    padding: '13px 22px', fontSize: 14, fontWeight: 600,
    background: 'var(--ink)', color: 'var(--bg)',
    borderRadius: 'var(--radius)',
    fontFamily: 'var(--body-font)',
    display: 'inline-flex', alignItems: 'center', gap: 8,
    cursor: 'pointer', border: 'none',
    transition: 'transform 0.1s, background 0.15s',
  },
  ghost: {
    padding: '13px 22px', fontSize: 14, fontWeight: 500,
    background: 'transparent', color: 'var(--ink)',
    border: '1px solid var(--rule-strong)',
    borderRadius: 'var(--radius)',
    fontFamily: 'var(--body-font)', cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', gap: 8,
  },
  accent: {
    padding: '13px 22px', fontSize: 14, fontWeight: 600,
    background: 'var(--accent)', color: 'var(--accent-ink)',
    borderRadius: 'var(--radius)',
    fontFamily: 'var(--body-font)',
    display: 'inline-flex', alignItems: 'center', gap: 8,
    cursor: 'pointer', border: 'none',
  },
};

function Btn({ kind = 'primary', children, ...rest }) {
  return <button style={SDU_BTN_STYLES[kind]} {...rest}>{children}</button>;
}

function Arrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M2 7h10M8 3l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Wordmark({ size = 22 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4.2" fill="var(--accent)" />
        <g stroke="var(--accent)" strokeWidth="1.6" strokeLinecap="round">
          <line x1="12" y1="1.5" x2="12" y2="4.5" />
          <line x1="12" y1="19.5" x2="12" y2="22.5" />
          <line x1="1.5" y1="12" x2="4.5" y2="12" />
          <line x1="19.5" y1="12" x2="22.5" y2="12" />
          <line x1="4.4" y1="4.4" x2="6.5" y2="6.5" />
          <line x1="17.5" y1="17.5" x2="19.6" y2="19.6" />
          <line x1="4.4" y1="19.6" x2="6.5" y2="17.5" />
          <line x1="17.5" y1="6.5" x2="19.6" y2="4.4" />
        </g>
      </svg>
      <span style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)', fontSize: 18, color: 'var(--ink)',
      }}>
        Solar Decisions
      </span>
    </div>
  );
}

function Eyebrow({ children, color = 'var(--accent-2)' }) {
  return (
    <div style={{
      fontFamily: 'var(--mono-font)', fontSize: 11,
      letterSpacing: '0.18em', textTransform: 'uppercase',
      color, marginBottom: 16,
      display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <span style={{ width: 24, height: 1, background: color }} />
      {children}
    </div>
  );
}

function MonoLabel({ children, faint = false }) {
  return (
    <div style={{
      fontFamily: 'var(--mono-font)', fontSize: 10.5,
      textTransform: 'uppercase', letterSpacing: '0.14em',
      color: faint ? 'var(--ink-faint)' : 'var(--ink-dim)',
    }}>{children}</div>
  );
}

function Panel({ children, style = {}, ...rest }) {
  return (
    <div style={{
      background: 'var(--panel)', border: '1px solid var(--rule)',
      borderRadius: 'var(--radius-lg)', padding: 24,
      ...style,
    }} {...rest}>{children}</div>
  );
}

function Field({ label, hint, children, footnote }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <MonoLabel>{label}</MonoLabel>
        {hint && <span style={{ fontSize: 11, fontFamily: 'var(--mono-font)', color: 'var(--ink-faint)' }}>{hint}</span>}
      </div>
      {children}
      {footnote && <div style={{ fontSize: 12, color: 'var(--ink-dim)', fontStyle: 'italic', lineHeight: 1.4 }}>{footnote}</div>}
    </label>
  );
}

function TextInput({ value, onChange, placeholder, prefix, suffix, ...rest }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'stretch',
      background: 'var(--bg)',
      border: '1px solid var(--rule-strong)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
      fontFamily: 'var(--body-font)',
    }}>
      {prefix && <div style={{
        padding: '12px 12px 12px 14px', fontSize: 14,
        color: 'var(--ink-dim)', fontFamily: 'var(--mono-font)',
        borderRight: '1px solid var(--rule)',
        background: 'var(--panel-2)',
      }}>{prefix}</div>}
      <input
        type="text"
        value={value || ''}
        onChange={e => onChange?.(e.target.value)}
        placeholder={placeholder}
        style={{
          flex: 1, padding: '12px 14px', fontSize: 14,
          border: 'none', outline: 'none', background: 'transparent',
          color: 'var(--ink)', fontFamily: 'inherit',
          minWidth: 0,
        }}
        {...rest}
      />
      {suffix && <div style={{
        padding: '12px 14px 12px 12px', fontSize: 13,
        color: 'var(--ink-dim)', fontFamily: 'var(--mono-font)',
        borderLeft: '1px solid var(--rule)',
        background: 'var(--panel-2)',
        display: 'flex', alignItems: 'center',
      }}>{suffix}</div>}
    </div>
  );
}

function SegBtn({ value, options, onChange, columns }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: columns ? `repeat(${columns}, 1fr)` : `repeat(${options.length}, 1fr)`,
      gap: 0,
      border: '1px solid var(--rule-strong)',
      borderRadius: 'var(--radius)',
      overflow: 'hidden',
    }}>
      {options.map((opt, i) => {
        const v = typeof opt === 'string' ? opt : opt.value;
        const label = typeof opt === 'string' ? opt : opt.label;
        const sub = typeof opt === 'object' ? opt.sub : null;
        const selected = value === v;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: '11px 12px',
            background: selected ? 'var(--ink)' : 'var(--bg)',
            color: selected ? 'var(--bg)' : 'var(--ink)',
            border: 'none',
            borderRight: i < options.length - 1 ? '1px solid var(--rule-strong)' : 'none',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: selected ? 600 : 500,
            fontFamily: 'var(--body-font)',
            textAlign: 'center',
            transition: 'background 0.12s',
            display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'center',
          }}>
            <span>{label}</span>
            {sub && <span style={{
              fontSize: 10, fontFamily: 'var(--mono-font)',
              color: selected ? 'rgba(255,255,255,0.7)' : 'var(--ink-faint)',
              letterSpacing: '0.06em',
            }}>{sub}</span>}
          </button>
        );
      })}
    </div>
  );
}

function ValuesChip({ value, onChange }) {
  const opts = [
    { id: 'financial', label: 'Financial' },
    { id: 'independence', label: 'Independence' },
    { id: 'environmental', label: 'Environmental' },
  ];
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 0,
      border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
      background: 'var(--panel)', padding: 2,
      fontFamily: 'var(--mono-font)', fontSize: 11,
    }}>
      <span style={{ padding: '4px 8px', color: 'var(--ink-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', borderRight: '1px solid var(--rule)' }}>
        Lens
      </span>
      {opts.map(opt => (
        <button key={opt.id} onClick={() => onChange(opt.id)} style={{
          padding: '4px 10px',
          color: value === opt.id ? 'var(--accent-ink)' : 'var(--ink-2)',
          background: value === opt.id ? 'var(--accent)' : 'transparent',
          borderRadius: 'calc(var(--radius) - 1px)',
          fontWeight: value === opt.id ? 600 : 500,
          border: 'none', cursor: 'pointer',
          fontFamily: 'inherit',
        }}>{opt.label}</button>
      ))}
    </div>
  );
}

function Footnote({ n, children }) {
  return (
    <div style={{
      fontSize: 12, lineHeight: 1.5, color: 'var(--ink-dim)',
      paddingLeft: 18, position: 'relative', fontFamily: 'var(--body-font)',
    }}>
      <sup style={{ position: 'absolute', left: 0, top: 0, fontFamily: 'var(--mono-font)', color: 'var(--accent-2)' }}>{n}</sup>
      {children}
    </div>
  );
}

// Modal — used for the "preview with sample data" peek from the workshop teaser.
function Modal({ open, onClose, kicker, title, subtitle, children, maxWidth = 920 }) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = e => { if (e.key === 'Escape') onClose?.(); };
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => { document.body.style.overflow = ''; window.removeEventListener('keydown', onKey); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(15,20,33,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '4vh 4vw', overflowY: 'auto',
      animation: 'sd-fade-in 0.18s ease-out',
    }}>
      <style>{`@keyframes sd-fade-in{from{opacity:0}to{opacity:1}}@keyframes sd-pop-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`}</style>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg)', maxWidth, width: '100%', maxHeight: '92vh',
        overflowY: 'auto', position: 'relative',
        border: '1px solid var(--rule-strong)', borderRadius: 'var(--radius-lg)',
        boxShadow: '0 24px 60px -20px rgba(15,20,33,0.5)',
        animation: 'sd-pop-in 0.22s ease-out',
      }}>
        <div style={{
          position: 'sticky', top: 0, zIndex: 2,
          padding: '20px 28px 16px', background: 'var(--bg)',
          borderBottom: '1px solid var(--rule)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16,
        }}>
          <div>
            {kicker && <MonoLabel>{kicker}</MonoLabel>}
            <h3 style={{
              fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
              letterSpacing: 'var(--display-tracking)',
              fontSize: 24, lineHeight: 1.15, margin: kicker ? '6px 0 0' : 0,
            }}>{title}</h3>
            {subtitle && <p style={{ fontSize: 13.5, lineHeight: 1.5, color: 'var(--ink-2)', margin: '6px 0 0', maxWidth: 640 }}>{subtitle}</p>}
          </div>
          <button onClick={onClose} aria-label="Close" style={{
            width: 32, height: 32, borderRadius: '50%',
            border: '1px solid var(--rule-strong)', background: 'var(--panel)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--ink-2)', flexShrink: 0,
          }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 2l8 8M10 2l-8 8" /></svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// Diagonal "DEMO DATA" watermark band — overlays preview content unmissably.
function DemoWatermark() {
  return (
    <div aria-hidden="true" style={{
      position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden',
      borderRadius: 'inherit',
    }}>
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%) rotate(-18deg)',
        fontFamily: 'var(--mono-font)', fontWeight: 700,
        fontSize: 'clamp(48px, 9vw, 110px)',
        letterSpacing: '0.18em',
        color: 'var(--accent)', opacity: 0.07,
        whiteSpace: 'nowrap',
      }}>DEMO · DEMO · DEMO</div>
    </div>
  );
}

Object.assign(window, { Btn, Arrow, Wordmark, Eyebrow, MonoLabel, Panel, Field, TextInput, SegBtn, ValuesChip, Footnote, Modal, DemoWatermark });
