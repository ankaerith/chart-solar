import { Btn, Field, TextInput } from "@/components/ui";

// Routing-scaffold placeholder. Real anonymous-→-account migration is
// chart-solar-4tz; the inline-email gate UI here is the design contract
// from solar-decisions/project/nav.jsx:204 (SaveForecastModal).

export function SaveForecastContent() {
  return (
    <div className="space-y-5">
      <p className="text-[14px] leading-[1.55] text-ink-2">
        We&apos;ll save this forecast to a free account. No password — just a
        magic link to come back.
      </p>
      <Field
        label="Email"
        footnote="The forecast in your browser tab will be migrated to the new account."
      >
        <TextInput placeholder="alice@example.com" type="email" />
      </Field>
      <div className="flex items-center gap-3">
        <Btn kind="primary" type="submit">
          Save forecast
        </Btn>
        <span className="font-mono text-[11px] text-ink-faint">
          Wired up in chart-solar-4tz
        </span>
      </div>
    </div>
  );
}
