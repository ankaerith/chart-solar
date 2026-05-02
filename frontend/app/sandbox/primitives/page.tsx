"use client";

import { useState } from "react";
import {
  Arrow,
  Btn,
  DemoWatermark,
  Eyebrow,
  Field,
  Footnote,
  Modal,
  MonoLabel,
  Panel,
  SegBtn,
  TextInput,
  Wordmark,
} from "@/components/ui";

export default function PrimitivesSandbox() {
  const [seg, setSeg] = useState("month");
  const [tilt, setTilt] = useState("south");
  const [usage, setUsage] = useState("8400");
  const [zip, setZip] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <main className="mx-auto max-w-5xl space-y-12 px-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Primitives — sandbox</Eyebrow>
        <h1 className="text-4xl">Solstice·Ink — primitives</h1>
        <p className="max-w-2xl text-[15px] leading-relaxed text-ink-dim">
          Visual catalogue for the bespoke UI primitives ported from
          <code className="mx-1 font-mono text-[13px] text-ink-2">
            design/solar-decisions/project/ui.jsx
          </code>
          . Use this page when adjusting tokens or component styling — it
          covers every primitive in its common states.
        </p>
      </header>

      <Section label="Wordmark" anchor="ui.jsx:43">
        <Wordmark />
      </Section>

      <Section label="Btn" anchor="ui.jsx:31">
        <div className="flex flex-wrap items-center gap-3">
          <Btn kind="primary">
            Run forecast <Arrow />
          </Btn>
          <Btn kind="ghost">Skip</Btn>
          <Btn kind="accent">
            Save <Arrow />
          </Btn>
          <Btn disabled>Disabled</Btn>
        </div>
      </Section>

      <Section label="Eyebrow" anchor="ui.jsx:69">
        <div className="space-y-2">
          <Eyebrow>Methodology</Eyebrow>
          <Eyebrow color="accent">Ask your installer</Eyebrow>
          <Eyebrow color="ink-dim">Field notes</Eyebrow>
        </div>
      </Section>

      <Section label="MonoLabel" anchor="ui.jsx:83">
        <div className="space-y-2">
          <MonoLabel>System size</MonoLabel>
          <MonoLabel faint>Optional</MonoLabel>
        </div>
      </Section>

      <Section label="Panel" anchor="ui.jsx:93">
        <Panel>
          <Eyebrow>Verdict</Eyebrow>
          <p className="text-[15px] leading-relaxed text-ink-2">
            Median NPV +$31,400 (P10 +$8,200 / P90 +$58,700) over 25 years
            against your current utility cost.
          </p>
        </Panel>
      </Section>

      <Section label="Field + TextInput" anchor="ui.jsx:103, 116">
        <div className="grid max-w-md gap-5">
          <Field
            label="Annual usage"
            hint="kWh / yr"
            footnote="From your last 12 months of utility bills."
          >
            <TextInput
              value={usage}
              onChange={setUsage}
              suffix="kWh"
              inputMode="numeric"
            />
          </Field>
          <Field label="ZIP code">
            <TextInput
              value={zip}
              onChange={setZip}
              prefix="US"
              placeholder="94110"
              inputMode="numeric"
            />
          </Field>
        </div>
      </Section>

      <Section label="SegBtn" anchor="ui.jsx:156">
        <div className="grid max-w-2xl gap-5">
          <Field label="Granularity">
            <SegBtn
              value={seg}
              onChange={setSeg}
              options={["month", "season", "year"]}
            />
          </Field>
          <Field label="Roof azimuth">
            <SegBtn
              value={tilt}
              onChange={setTilt}
              columns={4}
              options={[
                { value: "east", label: "East", sub: "90°" },
                { value: "south", label: "South", sub: "180°" },
                { value: "west", label: "West", sub: "270°" },
                { value: "split", label: "Split", sub: "mixed" },
              ]}
            />
          </Field>
        </div>
      </Section>

      <Section label="Footnote" anchor="ui.jsx:230">
        <div className="grid max-w-2xl gap-2">
          <Footnote n={1}>
            NREL PVWatts v8 weather, 1998–2020 climatology; see methodology.
          </Footnote>
          <Footnote n={2}>
            Discount rate: 5% real. Inflation-adjusted to 2026 USD.
          </Footnote>
        </div>
      </Section>

      <Section label="DemoWatermark" anchor="ui.jsx:299">
        <Panel className="relative h-40">
          <p className="font-mono text-[13px] text-ink-dim">
            Anchored inside a <code className="text-ink-2">relative</code>{" "}
            parent.
          </p>
          <DemoWatermark />
        </Panel>
      </Section>

      <Section label="Modal" anchor="ui.jsx:243">
        <Btn kind="ghost" onClick={() => setOpen(true)}>
          Open modal
        </Btn>
        <Modal
          open={open}
          onClose={() => setOpen(false)}
          kicker="Sample data"
          title="Battery hourly dispatch — preview"
          subtitle="Decision Pack unlocks the live version against your roof."
        >
          <div className="relative space-y-4 px-7 pt-6 pb-7">
            <p className="text-[14px] leading-[1.6] text-ink-2">
              Modal body. Locks body scroll, closes on backdrop click or Esc,
              restores focus to the trigger on close.
            </p>
            <Field label="Try a control inside">
              <TextInput value="" onChange={() => {}} placeholder="Type…" />
            </Field>
            <DemoWatermark />
          </div>
        </Modal>
      </Section>
    </main>
  );
}

function Section({
  label,
  anchor,
  children,
}: {
  label: string;
  anchor: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4 border-t border-rule pt-6">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[22px]">{label}</h2>
        <code className="font-mono text-[11px] text-ink-faint">{anchor}</code>
      </div>
      {children}
    </section>
  );
}
