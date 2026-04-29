export default function Home() {
  return (
    <main className="mx-auto max-w-3xl space-y-10 px-8 py-16">
      <header className="space-y-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent-2">
          <span className="mr-3 inline-block h-px w-6 align-middle bg-accent-2" />
          Solstice · Ink
        </p>
        <h1 className="text-5xl">Chart Solar</h1>
        <p className="text-lg text-ink-dim">
          Plan it. Check it. Track it. — the honest math for your roof, before, during, and after.
        </p>
      </header>

      <section className="rounded-md border border-rule bg-panel p-6 space-y-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-dim">
          Token preview
        </p>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Swatch name="bg" className="bg-bg" />
          <Swatch name="panel" className="bg-panel" />
          <Swatch name="ink" className="bg-ink text-accent-ink" />
          <Swatch name="accent" className="bg-accent text-accent-ink" />
          <Swatch name="accent-2" className="bg-accent-2 text-accent-ink" />
          <Swatch name="rule" className="bg-rule" />
          <Swatch name="good" className="bg-good text-accent-ink" />
          <Swatch name="warn" className="bg-warn text-accent-ink" />
          <Swatch name="bad" className="bg-bad text-accent-ink" />
        </div>
        <p className="font-mono text-sm text-ink-dim">
          $/W · 8,760h · NPV · IRR — numerics in IBM Plex Mono
        </p>
      </section>

      <p className="text-sm text-ink-faint">
        Phase 0: scaffold. See <code className="font-mono">PRODUCT_PLAN.md</code> for what comes next.
      </p>
    </main>
  );
}

function Swatch({ name, className }: { name: string; className: string }) {
  return (
    <div
      className={`flex h-16 items-end justify-between rounded-md border border-rule px-3 py-2 font-mono text-xs ${className}`}
    >
      <span>{name}</span>
    </div>
  );
}
