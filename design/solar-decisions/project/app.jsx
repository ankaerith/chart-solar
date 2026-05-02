// App router — top-level state machine.

const { useState: useStateA, useEffect: useEffectA } = React;

// Mock pre-populated library items so the prototype shows the surface immediately on sign-in.
const MOCK_SAVED_FORECASTS = [
  { id: 'fc_001', address: '1242 Spruce St, Boulder CO',
    systemSize: 7.2, battery: '13.5 kWh',
    headlineNpv: '+$31,400', payback: '11.2 yr',
    dateLabel: 'Saved Apr 28', dateRel: '4 days ago', seed: 7 },
  { id: 'fc_002', address: '88 Mariposa Ave, Lafayette CO',
    systemSize: 9.6, battery: 'none',
    headlineNpv: '+$18,900', payback: '14.1 yr',
    dateLabel: 'Saved Apr 14', dateRel: '18 days ago', seed: 11 },
  { id: 'fc_003', address: '1242 Spruce St (battery v2)',
    systemSize: 7.2, battery: '27 kWh · backup',
    headlineNpv: '+$22,100', payback: '13.6 yr',
    dateLabel: 'Saved Mar 30', dateRel: '5 weeks ago', seed: 19 },
];

const MOCK_SAVED_AUDITS = [
  { id: 'au_001', address: '1242 Spruce St, Boulder CO',
    systemSize: 7.4, installer: 'Pinnacle Solar',
    varianceLabel: '−18%', varianceTone: 'var(--bad)',
    flagsHigh: 2, dateLabel: 'Saved Apr 22', dateRel: '10 days ago', seed: 4 },
];

function App() {
  useEffectA(() => { window.applyTheme(); }, []);

  const [route, setRoute] = useStateA('landing');
  const [wizardIdx, setWizardIdx] = useStateA(0);
  const [tier, setTier] = useStateA('free');
  const [libraryTab, setLibraryTab] = useStateA('forecasts');
  const [activeNoteId, setActiveNoteId] = useStateA('dealer-fees');

  // Auth — extended with savedForecasts / savedAudits.
  const [auth, setAuth] = useStateA({
    state: 'anonymous',                                // anonymous | signedIn
    email: null,
    creditsAudit: 0,
    savedForecasts: [],
    savedAudits: [],
  });

  const [modal, setModal] = useStateA(null);          // null | 'checkout' | 'signin' | 'magic-sent' | 'save-forecast'
  const [pendingTier, setPendingTier] = useStateA(null);

  const [wizard, setWizard] = useStateA({
    address: { address: '1242 Spruce St, Boulder CO 80302', utility: 'Xcel Energy', tariff: 'RE-TOU residential', hold: '10' },
    usage:   { method: 'manual', kwh: 11200, bill: 168, upcoming: ['EV'] },
    roof:    { size: 7.2, tilt: '25', azimuth: 'S', shading: 'light' },
    battery: { include: true, capacity: 13.5, dispatch: 'self', critical: ['Fridge', 'Furnace fan', 'Internet'] },
    finance: { method: 'cash', term: '15', apr: '6.99', dealerFee: 'no', escalator: '2.9', discount: '5.5' },
  });

  const [audit, setAudit] = useStateA({
    stage: 'upload', fileName: null, extracted: null,
  });

  // Unified navigation. Mapping tab keys → routes.
  const onNavigate = (target, opts = {}) => {
    if (target === 'landing')   { setRoute('landing'); }
    else if (target === 'forecast') { setRoute('wizard'); setWizardIdx(0); }
    else if (target === 'audit')    { onAuditRequested(); return; }
    else if (target === 'pricing')  { setRoute('pricing'); }
    else if (target === 'about')    { setRoute('about'); }
    else if (target === 'notes')    { setRoute('notes'); }
    else if (target === 'note')     { if (opts.noteId) setActiveNoteId(opts.noteId); setRoute('note'); }
    else if (target === 'library')  { if (opts.tab) setLibraryTab(opts.tab); setRoute('library'); }
    else { setRoute(target); }
    window.scrollTo(0, 0);
  };

  const goLanding = () => onNavigate('landing');
  const goWizard  = () => onNavigate('forecast');
  const goResults = () => { setRoute('results'); window.scrollTo(0, 0); };
  const goPricing = () => onNavigate('pricing');
  const goAudit   = () => { setAudit(a => ({ ...a, stage: 'upload' })); setRoute('audit'); window.scrollTo(0, 0); };

  const onUpgradeRequested = (which = 'pack') => { setPendingTier(which); setModal('checkout'); };

  const onCheckoutSuccess = (email) => {
    const nextTier = pendingTier || 'pack';
    const credits = nextTier === 'founders' ? 3 : 1;
    setAuth({
      state: 'signedIn', email, creditsAudit: credits,
      savedForecasts: MOCK_SAVED_FORECASTS,
      savedAudits: MOCK_SAVED_AUDITS,
    });
    setTier(nextTier);
    setPendingTier(null);
    setModal(null);
  };

  const onSignInRequested = () => setModal('signin');
  const onMagicLinkSent = () => setModal('magic-sent');
  const onMagicLinkClicked = (email) => {
    setAuth({
      state: 'signedIn', email, creditsAudit: 1,
      savedForecasts: MOCK_SAVED_FORECASTS,
      savedAudits: MOCK_SAVED_AUDITS,
    });
    setTier('pack');
    setModal(null);
  };

  const onSignOut = () => {
    setAuth({ state: 'anonymous', email: null, creditsAudit: 0,
      savedForecasts: [], savedAudits: [] });
    setTier('free');
    setRoute('landing');
  };

  const onAuditRequested = () => {
    if (auth.state !== 'signedIn') { onUpgradeRequested('pack'); return; }
    if (auth.creditsAudit < 1) { onUpgradeRequested('pack'); return; }
    goAudit();
  };

  const onAuditComplete = () => {
    setAuth(a => ({
      ...a,
      creditsAudit: Math.max(0, a.creditsAudit - 1),
      savedAudits: [
        { id: `au_${Date.now()}`, address: '1242 Spruce St, Boulder CO',
          systemSize: 7.4, installer: 'Pinnacle Solar',
          varianceLabel: '−18%', varianceTone: 'var(--bad)',
          flagsHigh: 2, dateLabel: 'Saved today', dateRel: 'just now', seed: Math.floor(Math.random()*30) },
        ...(a.savedAudits || []),
      ],
    }));
    setAudit(a => ({ ...a, stage: 'report' }));
  };

  // Save-forecast (Results screen). If anon, opens save modal; if signed in, prepends item.
  const onSaveForecast = () => {
    setAuth(a => ({
      ...a,
      savedForecasts: [
        { id: `fc_${Date.now()}`, address: wizard.address.address,
          systemSize: wizard.roof.size, battery: wizard.battery.include ? `${wizard.battery.capacity} kWh` : 'none',
          headlineNpv: '+$31,400', payback: '11.2 yr',
          dateLabel: 'Saved today', dateRel: 'just now', seed: Math.floor(Math.random()*30) },
        ...(a.savedForecasts || []),
      ],
    }));
  };
  const onSaveForecastAnonymous = () => setModal('save-forecast');
  const onSaveForecastEmailSubmitted = (email) => {
    // Lightweight free-tier account creation + save the current forecast.
    setAuth({
      state: 'signedIn', email, creditsAudit: 0,
      savedForecasts: [
        { id: `fc_${Date.now()}`, address: wizard.address.address,
          systemSize: wizard.roof.size, battery: wizard.battery.include ? `${wizard.battery.capacity} kWh` : 'none',
          headlineNpv: '+$31,400', payback: '11.2 yr',
          dateLabel: 'Saved today', dateRel: 'just now', seed: Math.floor(Math.random()*30) },
      ],
      savedAudits: [],
    });
    setModal(null);
    onNavigate('library', { tab: 'forecasts' });
  };

  const onLibraryDelete = (kind, id) => {
    setAuth(a => ({
      ...a,
      [kind === 'forecasts' ? 'savedForecasts' : 'savedAudits']:
        (a[kind === 'forecasts' ? 'savedForecasts' : 'savedAudits'] || []).filter(x => x.id !== id),
    }));
  };

  const navProps = {
    auth, onSignInRequested, onSignOut,
    tier, setTier,
    onNavigate, route,
    onStart: goWizard,
  };

  let screen;
  if (route === 'landing') {
    screen = <ScreenLanding {...navProps} onAudit={onAuditRequested} onPricing={goPricing} setRoute={setRoute} />;
  } else if (route === 'wizard') {
    screen = <ScreenWizard wizard={wizard} setWizard={setWizard} idx={wizardIdx} setIdx={setWizardIdx} onFinish={goResults} onCancel={goLanding} />;
  } else if (route === 'pricing') {
    screen = <ScreenPricing {...navProps} onCancel={() => setRoute('landing')} onAfterChoose={(t) => onUpgradeRequested(t || 'pack')} />;
  } else if (route === 'audit') {
    screen = <ScreenAudit audit={audit} setAudit={setAudit} {...navProps}
      onCancel={goResults} onComplete={onAuditComplete} />;
  } else if (route === 'library') {
    screen = <ScreenLibrary {...navProps} initialTab={libraryTab}
      onOpenForecast={() => goResults()}
      onOpenAudit={() => { setAudit(a => ({ ...a, stage: 'report', extracted: a.extracted || window.MOCK_EXTRACTED })); setRoute('audit'); window.scrollTo(0, 0); }}
      onDelete={onLibraryDelete} />;
  } else if (route === 'notes') {
    screen = <NotesIndex {...navProps} onOpen={(noteId) => onNavigate('note', { noteId })} />;
  } else if (route === 'note') {
    screen = <NoteArticle id={activeNoteId} {...navProps} onBack={() => onNavigate('notes')} />;
  } else { // results
    screen = <ScreenResults {...navProps}
      onCancel={goLanding} onAudit={onAuditRequested}
      onUpgrade={() => onUpgradeRequested('pack')}
      onSave={onSaveForecast} onSaveAnonymous={onSaveForecastAnonymous} />;
  }

  return (
    <>
      {screen}
      <CheckoutModal
        open={modal === 'checkout'}
        tier={pendingTier || 'pack'}
        onClose={() => { setModal(null); setPendingTier(null); }}
        onSuccess={onCheckoutSuccess}
        onSwitchToSignIn={() => setModal('signin')}
      />
      <SignInModal
        open={modal === 'signin'}
        onClose={() => setModal(null)}
        onSent={onMagicLinkSent}
      />
      <MagicLinkSentModal
        open={modal === 'magic-sent'}
        onClose={() => setModal(null)}
        onClicked={onMagicLinkClicked}
      />
      <SaveForecastModal
        open={modal === 'save-forecast'}
        onClose={() => setModal(null)}
        onCreated={onSaveForecastEmailSubmitted}
      />
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
