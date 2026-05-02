// Wizard screen — 5-step Explore flow.

const { useState: useStateW } = React;

const STEPS = [
  { k: 'address', n: '01', label: 'Address' },
  { k: 'usage',   n: '02', label: 'Usage' },
  { k: 'roof',    n: '03', label: 'Roof' },
  { k: 'battery', n: '04', label: 'Battery' },
  { k: 'finance', n: '05', label: 'Financing' },
];

function Stepper({ idx }) {
  return (
    <div style={{ display: 'flex', gap: 0, borderTop: '1px solid var(--rule)', borderBottom: '1px solid var(--rule)' }}>
      {STEPS.map((s, i) => {
        const done = i < idx, active = i === idx;
        return (
          <div key={s.k} style={{
            flex: 1, padding: '14px 20px',
            borderRight: i < STEPS.length - 1 ? '1px solid var(--rule)' : 'none',
            background: active ? 'var(--panel)' : 'transparent',
            display: 'flex', flexDirection: 'column', gap: 4,
            opacity: done || active ? 1 : 0.55,
          }}>
            <div style={{
              fontFamily: 'var(--mono-font)', fontSize: 10,
              letterSpacing: '0.14em', textTransform: 'uppercase',
              color: active ? 'var(--accent-2)' : 'var(--ink-faint)',
            }}>
              {done ? '✓' : s.n} · step
            </div>
            <div style={{
              fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
              fontSize: 15, color: active ? 'var(--ink)' : 'var(--ink-dim)',
            }}>{s.label}</div>
          </div>
        );
      })}
    </div>
  );
}

function StepShell({ idx, title, sub, children, onBack, onNext, nextLabel = 'Continue', onSkip }) {
  return (
    <div style={{ maxWidth: 1080, margin: '0 auto', padding: '40px 40px 80px' }}>
      <Eyebrow>Step {STEPS[idx].n} · {STEPS[idx].label}</Eyebrow>
      <h1 style={{
        fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
        letterSpacing: 'var(--display-tracking)',
        fontSize: 'clamp(32px, 4vw, 52px)', lineHeight: 1.05,
        margin: '0 0 12px', color: 'var(--ink)', textWrap: 'balance',
      }}>{title}</h1>
      {sub && <p style={{
        fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)',
        maxWidth: 680, margin: '0 0 32px',
      }}>{sub}</p>}
      <div style={{ marginTop: 24 }}>{children}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 40, gap: 12, flexWrap: 'wrap' }}>
        <Btn kind="ghost" onClick={onBack}>← Back</Btn>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {onSkip && <button onClick={onSkip} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 13, color: 'var(--ink-dim)', textDecoration: 'underline', textUnderlineOffset: 3,
          }}>Skip — use defaults</button>}
          <Btn kind="primary" onClick={onNext}>{nextLabel} <Arrow /></Btn>
        </div>
      </div>
    </div>
  );
}

function StepAddress({ data, setData, onNext, onBack }) {
  return (
    <StepShell idx={0} onBack={onBack} onNext={onNext}
      title="Where's your roof?"
      sub="Address gives us your latitude, climate zone, utility, and tariff schedule. Nothing is shared with installers — there's no installer to share it with.">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 32, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Field label="Street address" hint="US or UK">
            <TextInput value={data.address} onChange={v => setData({ address: v })} placeholder="1242 Spruce St, Boulder, CO 80302" />
          </Field>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Field label="Utility" hint="auto-detected">
              <TextInput value={data.utility} onChange={v => setData({ utility: v })} placeholder="Xcel Energy" />
            </Field>
            <Field label="Tariff schedule">
              <TextInput value={data.tariff} onChange={v => setData({ tariff: v })} placeholder="RE-TOU residential" />
            </Field>
          </div>
          <Field label="Hold horizon" hint="how long you'll likely own" footnote="ZIP-defaulted from US Census mobility data; you can override.">
            <SegBtn value={data.hold} onChange={v => setData({ hold: v })}
              options={[
                { value: '5', label: '5 yr', sub: 'short' },
                { value: '10', label: '10 yr', sub: 'median' },
                { value: '15', label: '15 yr', sub: 'long' },
                { value: '25', label: 'Lifetime' },
              ]} />
          </Field>
        </div>
        <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
          <MonoLabel>Detected for this address</MonoLabel>
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <DetectRow label="Climate zone" value="Cool, semi-arid (5B)" />
            <DetectRow label="Avg ann. irradiance" value="5.6 kWh/m²/day" sub="NREL NSRDB" />
            <DetectRow label="Utility" value="Xcel Energy" />
            <DetectRow label="Net-metering" value="NEM (1:1)" sub="not NEM 3.0" />
            <DetectRow label="Local incentives" value="$0.50/W rebate" sub="DSIRE · expires 2027" />
          </div>
          <div style={{
            marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--rule)',
            fontSize: 12, color: 'var(--ink-dim)', fontStyle: 'italic', lineHeight: 1.5,
          }}>
            Production model: <span style={{ fontFamily: 'var(--mono-font)', fontStyle: 'normal' }}>pvlib-python · NSRDB hourly TMY</span>. Cached per 1 km bucket; refreshed nightly.
          </div>
        </Panel>
      </div>
    </StepShell>
  );
}

function DetectRow({ label, value, sub }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', borderBottom: '1px dashed var(--rule)', paddingBottom: 8, gap: 12 }}>
      <span style={{ fontSize: 12, color: 'var(--ink-dim)' }}>{label}</span>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'var(--mono-font)', fontSize: 12, color: 'var(--ink)', fontWeight: 500 }}>{value}</div>
        {sub && <div style={{ fontSize: 10, color: 'var(--ink-faint)', fontFamily: 'var(--mono-font)' }}>{sub}</div>}
      </div>
    </div>
  );
}

function StepUsage({ data, setData, onNext, onBack }) {
  const monthly = data.kwh / 12;
  return (
    <StepShell idx={1} onBack={onBack} onNext={onNext}
      title="What does your house actually use?"
      sub="The honest math starts here. We can pull a year of hourly data from your utility (Green Button), accept a recent bill, or use a ResStock archetype matched to your home.">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 32, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Field label="Method">
            <SegBtn value={data.method} onChange={v => setData({ method: v })}
              options={[
                { value: 'greenbutton', label: 'Green Button', sub: 'hourly, 1 yr' },
                { value: 'pdf', label: 'Upload bill', sub: 'PDF / image' },
                { value: 'manual', label: 'Type it in', sub: 'monthly avg' },
              ]} />
          </Field>
          {data.method === 'pdf' && (
            <Panel style={{ padding: 24, borderStyle: 'dashed', textAlign: 'center', background: 'var(--panel-2)' }}>
              <div style={{
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                fontSize: 18, marginBottom: 6,
              }}>Drop a recent utility bill</div>
              <div style={{ fontSize: 13, color: 'var(--ink-dim)', marginBottom: 14 }}>
                PDF, PNG, or JPG. We extract usage + rate, delete the file within 24h.
              </div>
              <Btn kind="ghost">Choose file</Btn>
            </Panel>
          )}
          {data.method === 'manual' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Annual usage" footnote="From any 12-month bill summary.">
                <TextInput value={data.kwh} onChange={v => setData({ kwh: v.replace(/[^0-9]/g, '') })} suffix="kWh / yr" />
              </Field>
              <Field label="Avg monthly bill">
                <TextInput value={data.bill} onChange={v => setData({ bill: v.replace(/[^0-9.]/g, '') })} prefix="$" suffix="/ mo" />
              </Field>
            </div>
          )}
          {data.method === 'greenbutton' && (
            <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%', background: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth="2">
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path d="M9 12l2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <div style={{ fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)', fontSize: 17 }}>
                    Sign in to Xcel Energy
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--ink-dim)' }}>OAuth via DataCustodian.org · we read 13 months of hourly intervals · never write</div>
                </div>
              </div>
              <div style={{ marginTop: 14 }}>
                <Btn kind="primary">Connect utility →</Btn>
              </div>
            </Panel>
          )}
          <Field label="Major loads coming" hint="optional, big-impact" footnote="Heat-pump and EV adoption can double your kWh — your future system size should know.">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {['EV', 'Heat pump', 'Pool', 'New addition', 'None planned'].map(t => {
                const active = (data.upcoming || []).includes(t);
                return (
                  <button key={t} onClick={() => {
                    const next = active ? data.upcoming.filter(x => x !== t) : [...(data.upcoming || []), t];
                    setData({ upcoming: next });
                  }} style={{
                    padding: '8px 14px', fontSize: 12.5, borderRadius: 'var(--radius)',
                    border: '1px solid ' + (active ? 'var(--ink)' : 'var(--rule-strong)'),
                    background: active ? 'var(--ink)' : 'transparent',
                    color: active ? 'var(--bg)' : 'var(--ink-2)',
                    cursor: 'pointer', fontFamily: 'var(--body-font)',
                  }}>{t}</button>
                );
              })}
            </div>
          </Field>
        </div>
        <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
          <MonoLabel>Your load profile</MonoLabel>
          <div style={{ marginTop: 14 }}>
            <MonthlyBars data={[
              { m:'J', gen:0, use:980 }, { m:'F', gen:0, use:880 }, { m:'M', gen:0, use:740 },
              { m:'A', gen:0, use:680 }, { m:'M', gen:0, use:710 }, { m:'J', gen:0, use:920 },
              { m:'J', gen:0, use:1180 }, { m:'A', gen:0, use:1120 }, { m:'S', gen:0, use:880 },
              { m:'O', gen:0, use:720 }, { m:'N', gen:0, use:820 }, { m:'D', gen:0, use:990 },
            ]} />
          </div>
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <DetectRow label="Annual" value={`${data.kwh.toLocaleString()} kWh`} />
            <DetectRow label="Peak month" value="July (1,180 kWh)" sub="A/C-driven" />
            <DetectRow label="Archetype" value="ResStock 2400 ft² · gas heat · CZ5B" />
          </div>
        </Panel>
      </div>
    </StepShell>
  );
}

function StepRoof({ data, setData, onNext, onBack }) {
  return (
    <StepShell idx={2} onBack={onBack} onNext={onNext}
      title="How big should the system be?"
      sub="We start from your usage and the orientation of your roof. You can override, but most homeowners are well-served by ~120% of annual usage in NEM markets, ~80% in NEM 3.0.">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 32, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Field label="System size" hint="DC kW">
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <input type="range" min="3" max="14" step="0.1" value={data.size}
                onChange={e => setData({ size: parseFloat(e.target.value) })}
                style={{ flex: 1, accentColor: 'var(--accent)' }} />
              <div style={{
                fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                fontSize: 32, fontVariantNumeric: 'tabular-nums',
                minWidth: 110, textAlign: 'right',
              }}>{data.size.toFixed(1)} <span style={{ fontSize: 15, color: 'var(--ink-dim)', fontFamily: 'var(--mono-font)' }}>kW</span></div>
            </div>
          </Field>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Field label="Tilt" hint="degrees">
              <SegBtn value={data.tilt} onChange={v => setData({ tilt: v })}
                options={[{value:'flush',label:'Flush'},{value:'15',label:'15°'},{value:'25',label:'25°'},{value:'35',label:'35°'}]} />
            </Field>
            <Field label="Azimuth" hint="primary roof face">
              <SegBtn value={data.azimuth} onChange={v => setData({ azimuth: v })}
                options={[{value:'E',label:'E'},{value:'SE',label:'SE'},{value:'S',label:'S'},{value:'SW',label:'SW'},{value:'W',label:'W'}]} />
            </Field>
          </div>
          <Field label="Shading" hint="annual access" footnote="From your address, we estimated 92% solar access. You can override if you've had a tree-trim study.">
            <SegBtn value={data.shading} onChange={v => setData({ shading: v })}
              options={[
                { value: 'open', label: 'Open', sub: '95-100%' },
                { value: 'light', label: 'Light', sub: '85-95%' },
                { value: 'mod', label: 'Moderate', sub: '70-85%' },
                { value: 'heavy', label: 'Heavy', sub: '<70%' },
              ]} />
          </Field>
        </div>
        <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
          <MonoLabel>Modeled output</MonoLabel>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            fontSize: 48, lineHeight: 1, marginTop: 10, fontVariantNumeric: 'tabular-nums',
            letterSpacing: 'var(--display-tracking)',
          }}>{Math.round(data.size * 1450).toLocaleString()}<span style={{ fontSize: 16, color: 'var(--ink-dim)', fontFamily: 'var(--mono-font)', marginLeft: 6 }}>kWh / yr</span></div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-dim)' }}>
            ≈ {Math.round((data.size * 1450 / data.kwh) * 100)}% of your annual usage
          </div>
          <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <DetectRow label="DC capacity" value={`${data.size.toFixed(1)} kW`} sub={`~${Math.round(data.size * 2.5)} panels @ 400 W`} />
            <DetectRow label="DC:AC ratio" value="1.18" sub="modest clipping" />
            <DetectRow label="Solar access" value="92%" sub="Sunroof + LIDAR" />
            <DetectRow label="Usable roof" value="~620 ft²" sub="south + southwest faces" />
          </div>
        </Panel>
      </div>
    </StepShell>
  );
}

function StepBattery({ data, setData, onNext, onBack, onSkip }) {
  return (
    <StepShell idx={3} onBack={onBack} onNext={onNext} onSkip={onSkip}
      title="A battery — yes or no?"
      sub="In a NEM 1:1 market like yours, a battery rarely pays back on financial terms alone. Worth it for outage resilience, or under TOU arbitrage. We'll show both lenses.">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 32, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Field label="Include battery">
            <SegBtn value={data.include ? 'yes' : 'no'} onChange={v => setData({ include: v === 'yes' })}
              options={[
                { value: 'no', label: 'No battery', sub: 'cheaper, simpler' },
                { value: 'yes', label: 'Add battery', sub: 'backup + arbitrage' },
              ]} />
          </Field>
          {data.include && (
            <>
              <Field label="Capacity" hint="kWh usable">
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <input type="range" min="5" max="40" step="2.5" value={data.capacity}
                    onChange={e => setData({ capacity: parseFloat(e.target.value) })}
                    style={{ flex: 1, accentColor: 'var(--accent)' }} />
                  <div style={{
                    fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
                    fontSize: 28, minWidth: 110, textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                  }}>{data.capacity} <span style={{ fontSize: 13, color: 'var(--ink-dim)', fontFamily: 'var(--mono-font)' }}>kWh</span></div>
                </div>
              </Field>
              <Field label="Dispatch strategy">
                <SegBtn value={data.dispatch} onChange={v => setData({ dispatch: v })}
                  options={[
                    { value: 'self', label: 'Self-consumption', sub: 'eat your solar' },
                    { value: 'tou', label: 'TOU arbitrage', sub: 'shave on-peak' },
                    { value: 'backup', label: 'Backup-first', sub: 'reserve 80%' },
                  ]} />
              </Field>
              <Field label="Critical loads" hint="for backup-first">
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {['Fridge', 'Furnace fan', 'Well pump', 'Internet', 'Medical', 'Lights only'].map(t => {
                    const active = (data.critical || []).includes(t);
                    return (
                      <button key={t} onClick={() => {
                        const next = active ? data.critical.filter(x => x !== t) : [...(data.critical || []), t];
                        setData({ critical: next });
                      }} style={{
                        padding: '8px 14px', fontSize: 12.5, borderRadius: 'var(--radius)',
                        border: '1px solid ' + (active ? 'var(--ink)' : 'var(--rule-strong)'),
                        background: active ? 'var(--ink)' : 'transparent',
                        color: active ? 'var(--bg)' : 'var(--ink-2)', cursor: 'pointer',
                      }}>{t}</button>
                    );
                  })}
                </div>
              </Field>
            </>
          )}
        </div>
        <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
          <MonoLabel>Sample 24-hour dispatch</MonoLabel>
          <div style={{ marginTop: 14 }}>
            {data.include ? <BatteryDispatch /> : (
              <div style={{
                padding: 28, textAlign: 'center', border: '1px dashed var(--rule)',
                borderRadius: 'var(--radius)', color: 'var(--ink-dim)', fontStyle: 'italic',
              }}>No battery selected — solar exports directly to the grid at full retail credit (your NEM 1:1 makes this fine).</div>
            )}
          </div>
          {data.include && (
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <DetectRow label="Days of backup" value="0.9 day" sub="critical loads only" />
              <DetectRow label="Self-consumption" value="74%" sub="vs 38% solo solar" />
              <DetectRow label="Annual savings" value="$280 / yr" sub="modest in NEM 1:1" />
            </div>
          )}
        </Panel>
      </div>
    </StepShell>
  );
}

function StepFinance({ data, setData, onNext, onBack }) {
  return (
    <StepShell idx={4} onBack={onBack} onNext={onNext} nextLabel="See my forecast"
      title="Cash, loan, or lease?"
      sub="The financing wrapper changes the math more than panel brand ever will. We model dealer fees, escalators, and assumability — the things installers don't volunteer.">
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 32, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Field label="Method">
            <SegBtn value={data.method} onChange={v => setData({ method: v })} columns={4}
              options={[
                { value: 'cash', label: 'Cash', sub: 'best NPV' },
                { value: 'loan', label: 'Loan', sub: 'most common' },
                { value: 'lease', label: 'Lease', sub: 'no upfront' },
                { value: 'ppa', label: 'PPA', sub: '$/kWh deal' },
              ]} />
          </Field>
          {data.method === 'loan' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Field label="Loan term">
                  <SegBtn value={data.term} onChange={v => setData({ term: v })}
                    options={[{value:'10',label:'10 yr'},{value:'15',label:'15 yr'},{value:'20',label:'20 yr'},{value:'25',label:'25 yr'}]} />
                </Field>
                <Field label="Stated APR">
                  <TextInput value={data.apr} onChange={v => setData({ apr: v })} suffix="% APR" />
                </Field>
              </div>
              <Field label="Dealer fee disclosed?" hint="critical input"
                footnote="Solar loans typically embed 20–30% fees in the system price. A '3.99% APR' loan with a 25% dealer fee has an effective real cost of capital of 8–10%. We surface the actual cost.">
                <SegBtn value={data.dealerFee} onChange={v => setData({ dealerFee: v })}
                  options={[
                    { value: 'no', label: 'Not disclosed', sub: 'we estimate ~22%' },
                    { value: 'yes', label: 'Disclosed', sub: 'enter %' },
                    { value: 'zero', label: 'No fee', sub: 'rare' },
                  ]} />
              </Field>
            </>
          )}
          {data.method === 'lease' && (
            <Field label="Escalator" footnote="Industry standard is 2.9%. Anything above 3.5% is aggressive — flagged as a potential audit issue.">
              <SegBtn value={data.escalator} onChange={v => setData({ escalator: v })}
                options={[{value:'0',label:'0%'},{value:'1.9',label:'1.9%'},{value:'2.9',label:'2.9%'},{value:'3.9',label:'3.9%'}]} />
            </Field>
          )}
          <Field label="Discount rate" hint="opportunity cost"
            footnote="What could your capital have done instead? Pick a benchmark — your mortgage APR, a HYSA, or long-run equity returns.">
            <SegBtn value={data.discount} onChange={v => setData({ discount: v })}
              options={[
                { value: '4.5', label: '4.5%', sub: 'HYSA' },
                { value: '5.5', label: '5.5%', sub: 'mortgage' },
                { value: '7', label: '7.0%', sub: 'S&P long-run' },
                { value: 'custom', label: 'Custom' },
              ]} />
          </Field>
        </div>
        <Panel style={{ padding: 22, background: 'var(--panel-2)' }}>
          <MonoLabel>Estimated upfront</MonoLabel>
          <div style={{
            fontFamily: 'var(--display-font)', fontWeight: 'var(--display-weight)',
            fontSize: 44, lineHeight: 1, marginTop: 10, fontVariantNumeric: 'tabular-nums',
            letterSpacing: 'var(--display-tracking)',
          }}>${(data.method === 'cash' ? 28400 : data.method === 'loan' ? 0 : 0).toLocaleString()}</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-dim)' }}>
            {data.method === 'cash' && 'Net of $0 federal credit (post-2025) + $4,250 state rebate.'}
            {data.method === 'loan' && '$0 down. Loan principal ~$28,400. Effective APR after dealer fee: 8.2%.'}
            {data.method === 'lease' && '$0 down. Year-1 lease payment ~$118/mo. Title stays with installer.'}
            {data.method === 'ppa' && '$0 down. $/kWh purchase, $0.078/kWh year 1, escalator applies.'}
          </div>
          <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <DetectRow label="Gross system" value="$32,650" sub="$3.20/W · regional median" />
            <DetectRow label="State + utility" value="−$4,250" sub="rebates · DSIRE-verified" />
            <DetectRow label="Net cost" value="$28,400" />
            {data.method === 'loan' && <DetectRow label="Effective COC" value="8.2%" sub="incl. ~22% dealer fee est" />}
          </div>
        </Panel>
      </div>
    </StepShell>
  );
}

function ScreenWizard({ wizard, setWizard, idx, setIdx, onFinish, onCancel }) {
  const setData = (key) => (patch) => setWizard(prev => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  const next = () => idx < 4 ? setIdx(idx + 1) : onFinish();
  const back = () => idx > 0 ? setIdx(idx - 1) : onCancel();
  return (
    <div style={{ minHeight: '100vh' }}>
      <nav style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 40px', borderBottom: '1px solid var(--rule)', background: 'var(--bg)',
      }}>
        <button onClick={onCancel} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
          <Wordmark />
        </button>
        <div style={{ fontFamily: 'var(--mono-font)', fontSize: 11, color: 'var(--ink-dim)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          Explore · free · no signup
        </div>
        <button onClick={onCancel} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--ink-dim)' }}>Save & exit ✕</button>
      </nav>
      <Stepper idx={idx} />
      {idx === 0 && <StepAddress data={wizard.address} setData={setData('address')} onNext={next} onBack={back} />}
      {idx === 1 && <StepUsage data={wizard.usage} setData={setData('usage')} onNext={next} onBack={back} />}
      {idx === 2 && <StepRoof data={{ ...wizard.roof, kwh: wizard.usage.kwh }} setData={setData('roof')} onNext={next} onBack={back} />}
      {idx === 3 && <StepBattery data={wizard.battery} setData={setData('battery')} onNext={next} onBack={back} onSkip={next} />}
      {idx === 4 && <StepFinance data={wizard.finance} setData={setData('finance')} onNext={next} onBack={back} />}
    </div>
  );
}

Object.assign(window, { ScreenWizard });
