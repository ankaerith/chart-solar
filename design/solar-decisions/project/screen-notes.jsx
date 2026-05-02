// Field Notes — long-form pieces. Index page + article view.
// SEO-friendly: long, content-led layout; not a typical "blog" template.

const NOTES = [
  {
    id: 'dealer-fees',
    category: 'Capital',
    title: 'The dealer fee is the most expensive line item in your solar loan.',
    dek: 'Why a "0.99% APR" loan can cost you $9,400 more than the cash equivalent — and how to spot the embedded markup before you sign.',
    author: 'Sarah Aldine',
    role: 'Energy economist',
    date: 'Mar 18, 2026',
    readTime: 11,
    tag: 'Methodology',
  },
  {
    id: 'nem3',
    category: 'Tariffs',
    title: 'NEM 3.0 didn\'t kill solar in California. It killed solar without batteries.',
    dek: 'A year of post-NBT data shows the math is now battery-or-bust. Here\'s what the export-rate decay schedule actually means for your payback.',
    author: 'Marcus Chen',
    role: 'Grid engineer',
    date: 'Feb 28, 2026',
    readTime: 14,
    tag: 'Analysis',
  },
  {
    id: 'overstating',
    category: 'Audit',
    title: 'Why every installer\'s year-1 production number is 8% high.',
    dek: 'We audited 312 proposals across six states. Median overstatement of first-year kWh: 8.4%. The reasons are mostly structural, not malicious.',
    author: 'Sarah Aldine',
    role: 'Energy economist',
    date: 'Feb 11, 2026',
    readTime: 9,
    tag: 'Audit',
  },
  {
    id: 'opportunity-cost',
    category: 'Capital',
    title: 'Solar vs. an S&P 500 index fund: a 25-year shootout.',
    dek: 'If you have $24,000 in cash and a south-facing roof, what should you do? We ran the simulation 5,000 times.',
    author: 'Priya Vance',
    role: 'Quant',
    date: 'Jan 30, 2026',
    readTime: 16,
    tag: 'Methodology',
  },
  {
    id: 'monitoring',
    category: 'Track',
    title: 'Your panels are underperforming and your installer hasn\'t told you.',
    dek: 'Of the 1,247 systems we\'ve been tracking, 22% are running more than 10% below their year-1 forecast. Here\'s why monitoring isn\'t enough.',
    author: 'Marcus Chen',
    role: 'Grid engineer',
    date: 'Jan 14, 2026',
    readTime: 12,
    tag: 'Analysis',
  },
  {
    id: 'lease-vs-loan',
    category: 'Capital',
    title: 'Lease, loan, PPA, cash: the actual decision matrix.',
    dek: 'Forget the marketing brochures. Here are the conditions under which each financing path actually wins, with the receipts.',
    author: 'Sarah Aldine',
    role: 'Energy economist',
    date: 'Dec 22, 2025',
    readTime: 13,
    tag: 'Methodology',
  },
];

const CATEGORIES = ['All', 'Methodology', 'Audit', 'Tariffs', 'Capital', 'Track', 'Analysis'];

function NotesIndex({ onOpen, onNavigate, auth, onSignInRequested, onSignOut, onStart }) {
  const [filter, setFilter] = React.useState('All');
  const filtered = filter === 'All' ? NOTES : NOTES.filter(n => n.tag === filter || n.category === filter);
  const [feature, ...rest] = filtered;

  return (
    <div>
      <TopNav route="notes" onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} onStart={onStart} />

      <section style={{
        maxWidth: 1280, margin: '0 auto', padding: '64px 40px 32px',
        borderBottom: '1px solid var(--rule)',
      }}>
        <Eyebrow>Field Notes · Vol. III · Spring 2026</Eyebrow>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 64,
          alignItems: 'flex-end' }}>
          <h1 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 'clamp(40px, 5.5vw, 76px)', lineHeight: 1.02,
            margin: 0, textWrap: 'balance',
          }}>Notes from the field, the spreadsheet, and the pole.</h1>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: 'var(--ink-2)', margin: 0,
            maxWidth: 380 }}>
            Working papers from our analysts. Methodology pieces, audit case studies,
            tariff explainers, and the occasional grumpy essay about installer-marketing math.
            New entries every two weeks.
          </p>
        </div>
      </section>

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '24px 40px 0' }}>
        <div style={{
          display: 'flex', gap: 0, borderBottom: '1px solid var(--rule)',
          flexWrap: 'wrap',
        }}>
          {CATEGORIES.map(c => {
            const active = filter === c;
            return (
              <button key={c} onClick={() => setFilter(c)} style={{
                padding: '14px 18px', background: 'transparent', border: 'none', cursor: 'pointer',
                fontFamily: 'var(--body-font)', fontSize: 13.5,
                color: active ? 'var(--ink)' : 'var(--ink-2)',
                fontWeight: active ? 600 : 500,
                borderBottom: active ? '2px solid var(--ink)' : '2px solid transparent',
                marginBottom: -1,
              }}>{c}</button>
            );
          })}
        </div>
      </section>

      {feature && (
        <section style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 40px 32px' }}>
          <button onClick={() => onOpen(feature.id)} style={{
            display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 56,
            width: '100%', textAlign: 'left', cursor: 'pointer',
            background: 'transparent', border: 'none', padding: 0,
            alignItems: 'center',
          }}>
            <FeatureArt id={feature.id} />
            <div>
              <MonoLabel>Featured · {feature.category}</MonoLabel>
              <h2 style={{
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                letterSpacing: 'var(--display-tracking)',
                fontSize: 'clamp(28px, 3.4vw, 44px)', lineHeight: 1.08,
                margin: '12px 0 16px', textWrap: 'balance', color: 'var(--ink)',
              }}>{feature.title}</h2>
              <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', margin: '0 0 24px', maxWidth: 540 }}>
                {feature.dek}
              </p>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 14,
                fontFamily: 'var(--mono-font)', fontSize: 11.5, color: 'var(--ink-faint)',
                letterSpacing: '0.06em', textTransform: 'uppercase',
              }}>
                <span>{feature.author}</span>
                <span style={{ color: 'var(--rule-strong)' }}>·</span>
                <span>{feature.date}</span>
                <span style={{ color: 'var(--rule-strong)' }}>·</span>
                <span>{feature.readTime} min read</span>
              </div>
            </div>
          </button>
        </section>
      )}

      <section style={{ maxWidth: 1280, margin: '0 auto', padding: '20px 40px 60px' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 0,
          borderTop: '1px solid var(--rule)',
        }}>
          {rest.map((n, i) => (
            <NoteCard key={n.id} note={n} onOpen={() => onOpen(n.id)} idx={i} />
          ))}
        </div>
      </section>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

function NoteCard({ note, onOpen }) {
  return (
    <button onClick={onOpen} style={{
      display: 'flex', flexDirection: 'column', textAlign: 'left',
      padding: '28px 28px 28px 0', cursor: 'pointer',
      background: 'transparent', border: 'none', borderRight: '1px solid var(--rule)',
      borderBottom: '1px solid var(--rule)',
      gap: 14, minHeight: 280,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <MonoLabel>{note.category}</MonoLabel>
        <span style={{
          fontFamily: 'var(--mono-font)', fontSize: 10.5, color: 'var(--ink-faint)',
          letterSpacing: '0.06em',
        }}>{note.readTime} min</span>
      </div>
      <h3 style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)',
        fontSize: 22, lineHeight: 1.15, margin: 0, color: 'var(--ink)',
        textWrap: 'balance',
      }}>{note.title}</h3>
      <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--ink-2)', margin: 0, flex: 1 }}>
        {note.dek}
      </p>
      <div style={{
        paddingTop: 12, borderTop: '1px dashed var(--rule)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-dim)',
        letterSpacing: '0.04em',
      }}>
        <span>{note.author} · {note.date}</span>
        <span style={{ color: 'var(--accent)' }}>→</span>
      </div>
    </button>
  );
}

// Decorative editorial panel for the featured note. Variant per id.
function FeatureArt({ id }) {
  const variants = {
    'dealer-fees': (
      <div style={{
        position: 'relative', height: 420, borderRadius: 'var(--radius-lg)',
        background: 'var(--panel)', border: '1px solid var(--rule)',
        padding: 28, overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <MonoLabel>Loan structure · stylized</MonoLabel>
          <span style={{ fontFamily: 'var(--mono-font)', fontSize: 10.5, color: 'var(--ink-faint)' }}>$28,400 system</span>
        </div>
        <div style={{ marginTop: 28, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Bar label="Cash price" w="68%" v="$24,200" tone="var(--ink)" />
          <Bar label="Dealer fee (markup)" w="22%" v="$6,800" tone="var(--bad)" />
          <Bar label="Misc. fees" w="3%" v="$880" tone="var(--ink-dim)" />
          <Bar label="Total financed" w="93%" v="$31,880" tone="var(--accent-2)" />
        </div>
        <div style={{
          marginTop: 32, padding: 14, borderTop: '1px solid var(--rule)',
          fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.55,
        }}>
          The "0.99% APR" advertised on the loan only makes sense if you ignore the
          22% premium baked into the principal. <strong style={{ color: 'var(--ink)' }}>Effective rate: ~8.4%.</strong>
        </div>
      </div>
    ),
    'nem3': (
      <div style={{
        position: 'relative', height: 420, borderRadius: 'var(--radius-lg)',
        background: 'var(--panel)', border: '1px solid var(--rule)',
        padding: 28, overflow: 'hidden',
      }}>
        <MonoLabel>NBT export-rate decay · CA · 2023→2030</MonoLabel>
        <svg viewBox="0 0 360 280" style={{ width: '100%', marginTop: 18 }}>
          <line x1="20" y1="20" x2="20" y2="240" stroke="var(--rule)" strokeWidth="1" />
          <line x1="20" y1="240" x2="340" y2="240" stroke="var(--rule)" strokeWidth="1" />
          {[0.30, 0.20, 0.10, 0.04].map((v, i) => (
            <g key={i}>
              <rect x={40 + i * 80} y={240 - v * 700} width="48" height={v * 700}
                fill={i < 2 ? 'var(--ink)' : 'var(--bad)'} />
              <text x={64 + i * 80} y={250} textAnchor="middle"
                fontFamily="var(--mono-font)" fontSize="9" fill="var(--ink-faint)">
                {2023 + i * 2}
              </text>
              <text x={64 + i * 80} y={240 - v * 700 - 6} textAnchor="middle"
                fontFamily="var(--mono-font)" fontSize="9" fill="var(--ink-2)">
                ${v.toFixed(2)}
              </text>
            </g>
          ))}
        </svg>
        <div style={{ marginTop: 14, fontSize: 12, color: 'var(--ink-dim)',
          fontFamily: 'var(--mono-font)', letterSpacing: '0.04em',
          paddingTop: 10, borderTop: '1px solid var(--rule)',
        }}>↓ 87% in seven years · battery becomes essential</div>
      </div>
    ),
  };
  return variants[id] || (
    <div style={{
      height: 420, borderRadius: 'var(--radius-lg)',
      background: 'var(--panel)', border: '1px solid var(--rule)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)', fontSize: 12,
    }}>editorial illustration</div>
  );
}

function Bar({ label, w, v, tone }) {
  return (
    <div>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 12, fontFamily: 'var(--mono-font)', color: 'var(--ink-2)',
        marginBottom: 4, letterSpacing: '0.04em',
      }}>
        <span>{label}</span><span>{v}</span>
      </div>
      <div style={{ height: 14, background: 'var(--bg)', border: '1px solid var(--rule)' }}>
        <div style={{ height: '100%', width: w, background: tone }} />
      </div>
    </div>
  );
}

// ---- Article view -----------------------------------------------------
function NoteArticle({ id, onBack, onNavigate, auth, onSignInRequested, onSignOut, onStart }) {
  const note = NOTES.find(n => n.id === id) || NOTES[0];
  return (
    <div>
      <TopNav route="notes" onNavigate={onNavigate} auth={auth}
        onSignInRequested={onSignInRequested} onSignOut={onSignOut} onStart={onStart} />

      <article>
        <header style={{
          maxWidth: 760, margin: '0 auto', padding: '64px 40px 40px',
          textAlign: 'left',
        }}>
          <button onClick={onBack} style={{
            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
            color: 'var(--ink-dim)', fontSize: 12.5, fontFamily: 'var(--body-font)',
            marginBottom: 24, letterSpacing: '0.02em',
          }}>← All notes</button>
          <Eyebrow>{note.category} · {note.tag}</Eyebrow>
          <h1 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 'clamp(36px, 5vw, 60px)', lineHeight: 1.05,
            margin: '0 0 20px', textWrap: 'balance',
          }}>{note.title}</h1>
          <p style={{ fontSize: 19, lineHeight: 1.55, color: 'var(--ink-2)',
            fontFamily: 'var(--display-font)', fontStyle: 'italic',
            margin: '0 0 32px', textWrap: 'balance',
          }}>{note.dek}</p>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            paddingTop: 20, borderTop: '1px solid var(--rule)',
            fontFamily: 'var(--mono-font)', fontSize: 11.5, color: 'var(--ink-dim)',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{note.author}</span>
            <span style={{ color: 'var(--rule-strong)' }}>·</span>
            <span>{note.role}</span>
            <span style={{ color: 'var(--rule-strong)' }}>·</span>
            <span>{note.date}</span>
            <span style={{ color: 'var(--rule-strong)' }}>·</span>
            <span>{note.readTime} min read</span>
          </div>
        </header>

        <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 40px 24px' }}>
          <FeatureArt id={note.id} />
        </div>

        <div style={{
          maxWidth: 680, margin: '0 auto', padding: '32px 40px 80px',
          fontFamily: 'var(--display-font)', fontSize: 19, lineHeight: 1.65,
          color: 'var(--ink)',
        }}>
          <p style={{ marginTop: 0 }}>
            <span style={{
              fontFamily: 'var(--display-font)', fontWeight: 700, fontSize: 56,
              float: 'left', lineHeight: 0.9, marginRight: 8, marginTop: 6,
              color: 'var(--accent)',
            }}>S</span>
            ix months ago a homeowner in Lakewood forwarded us a proposal that quoted
            "0.99% APR for 25 years." It looked like the deal of a lifetime. It wasn't.
            The cash price of the same system, paid up front, was $6,800 lower.
          </p>
          <p>
            That gap has a name. The industry calls it a <em>dealer fee</em> —
            an upfront markup the lender pays the installer in exchange for offering
            a below-market rate. The homeowner doesn't see it as a line item.
            They see it baked into the principal of the loan.
          </p>
          <h2 style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            letterSpacing: 'var(--display-tracking)',
            fontSize: 32, lineHeight: 1.1, margin: '40px 0 14px',
          }}>How the math actually works.</h2>
          <p>
            Suppose you're quoted a $24,200 system, financed at 0.99% APR over 25
            years. The lender knows that rate doesn't cover their cost of capital,
            so they charge the installer a fee — typically 22–28% of the financed
            amount — and the installer rolls that fee into your loan principal.
          </p>
          <p>
            On a $24,200 system with a 25% dealer fee, the loan principal becomes
            $32,267. You'll make 300 monthly payments of about $122. Total paid:
            $36,500. Compare that to paying $24,200 in cash today, even at a 5%
            opportunity-cost discount rate: present-value cost is $24,200.
          </p>
          <blockquote style={{
            margin: '32px 0', padding: '20px 28px',
            borderLeft: '2px solid var(--accent-2)',
            background: 'var(--panel-2)',
            fontFamily: 'var(--display-font)', fontSize: 22, lineHeight: 1.4,
            fontStyle: 'italic', color: 'var(--ink)',
          }}>
            "The loan is structured to feel cheap and audit expensive. That's a
            design choice, not an accident."
          </blockquote>
          <p>
            We've reviewed 312 proposals where a dealer fee was disclosed in the
            fine print. The median fee was 24.7%. In none of them was the cash-price
            equivalent shown next to the financed price. That's not regulatory failure
            — it's a marketing convention the industry has settled into.
          </p>
          <p style={{ color: 'var(--ink-dim)', fontStyle: 'italic', fontSize: 16 }}>
            (Article continues. The full version runs about 11 minutes — methodology
            appendix, three case studies, and a one-page checklist for spotting the
            fee in your own quote. This preview shows the editorial design.)
          </p>
        </div>

        <div style={{
          maxWidth: 760, margin: '0 auto', padding: '32px 40px 80px',
          borderTop: '1px solid var(--rule)',
        }}>
          <MonoLabel>Cited in this piece</MonoLabel>
          <ol style={{
            margin: '14px 0 0', padding: 0, listStyle: 'none',
            fontSize: 13.5, lineHeight: 1.55, color: 'var(--ink-2)',
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            {[
              '312-proposal audit dataset, Solar Decisions internal corpus, 2024–2026 (CO, CA, TX, AZ, MA, NJ).',
              'Sunlight Financial 10-K, FY2023 — disclosed dealer fee economics.',
              'NREL Best Practices Guide for Solar Loan Disclosure (2022).',
              'CFPB consumer complaint database, "solar loan dealer fee" search, n=2,140 (2020–2025).',
            ].map((s, i) => (
              <li key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr', gap: 8 }}>
                <span style={{ fontFamily: 'var(--mono-font)', color: 'var(--accent-2)' }}>{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </div>
      </article>

      <section style={{
        background: 'var(--panel)', borderTop: '1px solid var(--rule)',
        padding: '56px 40px',
      }}>
        <div style={{ maxWidth: 1080, margin: '0 auto' }}>
          <Eyebrow>Keep reading</Eyebrow>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 28,
            marginTop: 14,
          }}>
            {NOTES.filter(n => n.id !== id).slice(0, 3).map(n => (
              <button key={n.id} onClick={() => onNavigate('note', { noteId: n.id })} style={{
                background: 'var(--bg)', border: '1px solid var(--rule)',
                borderRadius: 'var(--radius-lg)', padding: 24, cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 10, textAlign: 'left',
                fontFamily: 'var(--body-font)',
              }}>
                <MonoLabel>{n.category}</MonoLabel>
                <div style={{
                  fontFamily: 'var(--display-font)', fontSize: 18, lineHeight: 1.2,
                  color: 'var(--ink)', textWrap: 'balance',
                }}>{n.title}</div>
                <div style={{
                  marginTop: 4, fontFamily: 'var(--mono-font)', fontSize: 11,
                  color: 'var(--ink-faint)', letterSpacing: '0.04em',
                }}>{n.readTime} min · {n.date}</div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <Footer onNavigate={onNavigate} />
    </div>
  );
}

Object.assign(window, { NotesIndex, NoteArticle, NOTES });
