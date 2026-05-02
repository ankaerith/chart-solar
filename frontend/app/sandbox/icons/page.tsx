import { Eyebrow, Panel } from "@/components/ui";
import { Arrow, Icon, Wordmark } from "@/components/icons";

const ICONS = [
  ["Check", Icon.Check],
  ["ChevronDown", Icon.ChevronDown],
  ["ChevronUp", Icon.ChevronUp],
  ["ChevronLeft", Icon.ChevronLeft],
  ["ChevronRight", Icon.ChevronRight],
  ["Close", Icon.Close],
  ["ExternalLink", Icon.ExternalLink],
  ["Info", Icon.Info],
  ["Lock", Icon.Lock],
  ["Menu", Icon.Menu],
  ["Search", Icon.Search],
  ["Warn", Icon.Warn],
  ["Alert", Icon.Alert],
  ["Upload", Icon.Upload],
] as const;

export default function IconsSandbox() {
  return (
    <main className="mx-auto max-w-5xl space-y-12 px-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Icons — sandbox</Eyebrow>
        <h1 className="text-4xl">Icon vocabulary</h1>
        <p className="max-w-2xl text-[15px] leading-relaxed text-ink-dim">
          Curated set. Bespoke <code className="font-mono text-[13px] text-ink-2">Wordmark</code>{" "}
          and <code className="font-mono text-[13px] text-ink-2">Arrow</code> live under{" "}
          <code className="font-mono text-[13px] text-ink-2">components/ui/</code>; everything else
          comes from <code className="font-mono text-[13px] text-ink-2">lucide-react</code> via the{" "}
          <code className="font-mono text-[13px] text-ink-2">Icon.*</code> namespace with editorial
          defaults (1.5 px stroke, 16 px size).
        </p>
      </header>

      <section className="space-y-4 border-t border-rule pt-6">
        <h2 className="text-[22px]">Bespoke marks</h2>
        <Panel>
          <div className="flex items-center gap-12 text-ink-dim">
            <div className="flex flex-col items-center gap-2">
              <Wordmark />
              <code className="font-mono text-[11px] text-ink-faint">Wordmark</code>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Arrow className="h-5 w-5 text-ink" />
              <code className="font-mono text-[11px] text-ink-faint">Arrow</code>
            </div>
          </div>
        </Panel>
      </section>

      <section className="space-y-4 border-t border-rule pt-6">
        <h2 className="text-[22px]">lucide-react vocabulary</h2>
        <Panel>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {ICONS.map(([name, IconComp]) => (
              <div
                key={name}
                className="flex items-center gap-3 rounded border border-rule bg-bg p-3"
              >
                <IconComp className="text-ink" size={20} />
                <code className="font-mono text-[12px] text-ink-2">
                  Icon.{name}
                </code>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="space-y-4 border-t border-rule pt-6">
        <h2 className="text-[22px]">Sizing scale</h2>
        <Panel>
          <div className="flex items-center gap-8">
            {[12, 14, 16, 20, 24, 32].map((s) => (
              <div key={s} className="flex flex-col items-center gap-2">
                <Icon.ChevronRight className="text-ink" size={s} />
                <code className="font-mono text-[11px] text-ink-faint">{s}px</code>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </main>
  );
}
