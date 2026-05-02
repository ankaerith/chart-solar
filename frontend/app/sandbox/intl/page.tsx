"use client";

import { useState } from "react";
import { Eyebrow, Panel, SegBtn } from "@/components/ui";
import {
  Currency,
  DateText,
  Kwh,
  LocaleProvider,
  Num,
  Percent,
  type Locale,
} from "@/lib/intl";

const SAMPLES = [
  { label: "Median NPV", node: <Currency value={31400} /> },
  { label: "P10 NPV", node: <Currency value={8200} /> },
  { label: "P90 NPV", node: <Currency value={58700} /> },
  { label: "Annual usage", node: <Kwh value={8760} /> },
  { label: "Year-1 production", node: <Kwh value={11240} /> },
  { label: "Discount rate", node: <Percent value={0.05} /> },
  { label: "Loan APR", node: <Percent value={0.0625} /> },
  { label: "Generation %", node: <Percent value={0.84} /> },
  { label: "Simulations", node: <Num value={500} /> },
  { label: "PTO date", node: <DateText value={new Date(2026, 4, 2)} /> },
  {
    label: "Estimated finish",
    node: (
      <DateText
        value={new Date(2026, 11, 18)}
        options={{ dateStyle: "long" }}
      />
    ),
  },
] as const;

export default function IntlSandbox() {
  const [locale, setLocale] = useState<Locale>("en-US");
  return (
    <LocaleProvider value={locale}>
      <main className="mx-auto max-w-4xl space-y-10 px-8 py-16">
        <header className="space-y-3">
          <Eyebrow>i18n — sandbox</Eyebrow>
          <h1 className="text-4xl">Locale boundary</h1>
          <p className="max-w-2xl text-[15px] leading-relaxed text-ink-dim">
            Toggle the locale to see every formatter (
            <code className="font-mono text-[13px] text-ink-2">Currency</code>,{" "}
            <code className="font-mono text-[13px] text-ink-2">Num</code>,{" "}
            <code className="font-mono text-[13px] text-ink-2">Percent</code>,{" "}
            <code className="font-mono text-[13px] text-ink-2">DateText</code>,{" "}
            <code className="font-mono text-[13px] text-ink-2">Kwh</code>) flip
            currency, decimal separator, and date order. Source of truth:{" "}
            <code className="font-mono text-[13px] text-ink-2">
              frontend/lib/intl/
            </code>
            .
          </p>
        </header>

        <Panel className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <Eyebrow>Locale</Eyebrow>
            <div className="min-w-[260px]">
              <SegBtn
                value={locale}
                onChange={(v) => setLocale(v)}
                options={[
                  { value: "en-US", label: "en-US", sub: "USD" },
                  { value: "en-GB", label: "en-GB", sub: "GBP" },
                ]}
              />
            </div>
          </div>

          <table className="w-full border-collapse text-[14px]">
            <tbody>
              {SAMPLES.map(({ label, node }) => (
                <tr key={label} className="border-t border-rule">
                  <th
                    scope="row"
                    className="py-2.5 text-left text-[12px] font-medium text-ink-dim"
                  >
                    {label}
                  </th>
                  <td className="py-2.5 text-right text-ink-2">{node}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </main>
    </LocaleProvider>
  );
}
