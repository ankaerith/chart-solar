"use client";

import { useState } from "react";
import { z } from "zod";
import { Eyebrow, Panel } from "@/components/ui";
import {
  FormSegBtn,
  FormSubmit,
  FormTextInput,
  applyServerErrors,
  flattenServerErrors,
  useForm,
} from "@/lib/forms";

// Demo schema — small composite of inputs the wizard will use later.
// The address half pulls field rules from `lib/api/schemas/address.ts`.
const Schema = z.object({
  email: z.string().email("Enter a valid email"),
  zip: z.string().regex(/^\d{5}$/, "5-digit US ZIP"),
  tier: z.enum(["explore", "audit", "track"]),
});

const TIER_OPTIONS = [
  { value: "explore" as const, label: "Explore", sub: "Free" },
  { value: "audit" as const, label: "Audit", sub: "$79" },
  { value: "track" as const, label: "Track", sub: "$9 / mo" },
];

// Pretend-geocoder: rejects ZIPs we don't know about, with a 600ms delay.
async function fakeGeocode(zip: string): Promise<true> {
  await new Promise((r) => setTimeout(r, 600));
  if (zip === "00000") {
    throw new Error("Address could not be geocoded.");
  }
  return true;
}

export default function FormsSandbox() {
  const [submitted, setSubmitted] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { email: "", zip: "", tier: "explore" } as z.infer<
      typeof Schema
    >,
    validators: { onMount: Schema, onChange: Schema },
    onSubmit: async ({ value }) => {
      try {
        await fakeGeocode(value.zip);
        setSubmitted(JSON.stringify(value, null, 2));
      } catch (err) {
        // Async / geocoder failure surfaces as a field error — same path
        // server validation errors take.
        applyServerErrors(form, {
          zip: [(err as Error).message],
        });
      }
    },
  });

  function injectFastApi422() {
    // Demonstrate the OpenAPI / FastAPI 422 envelope round-trip.
    applyServerErrors(
      form,
      flattenServerErrors({
        detail: [
          { loc: ["body", "email"], msg: "Already on the waitlist", type: "value_error" },
          { loc: ["body", "zip"], msg: "Outside our service area", type: "value_error" },
        ],
      }),
    );
  }

  return (
    <main className="mx-auto max-w-3xl space-y-10 px-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Forms — sandbox</Eyebrow>
        <h1 className="text-4xl">TanStack Form + Zod</h1>
        <p className="max-w-2xl text-[15px] leading-relaxed text-ink-dim">
          Pre-bound wrappers in{" "}
          <code className="font-mono text-[13px] text-ink-2">@/lib/forms</code>{" "}
          drive our Solstice·Ink primitives. Submit gates on schema parse;
          server-side errors flow through the same display path as client
          errors via{" "}
          <code className="font-mono text-[13px] text-ink-2">
            applyServerErrors
          </code>
          .
        </p>
      </header>

      <Panel>
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            void form.handleSubmit();
          }}
        >
          <form.Field name="email">
            {(field) => (
              <FormTextInput
                field={field}
                label="Email"
                placeholder="alice@example.com"
                inputMode="email"
                type="email"
              />
            )}
          </form.Field>

          <form.Field name="zip">
            {(field) => (
              <FormTextInput
                field={field}
                label="ZIP"
                hint="US only"
                placeholder="94110"
                inputMode="numeric"
                prefix="US"
                footnote="Try 00000 to see the simulated geocoder reject."
              />
            )}
          </form.Field>

          <form.Field name="tier">
            {(field) => (
              <FormSegBtn
                field={field}
                label="Tier"
                options={TIER_OPTIONS}
              />
            )}
          </form.Field>

          <div className="flex items-center gap-3 pt-2">
            <FormSubmit form={form}>Submit</FormSubmit>
            <button
              type="button"
              onClick={injectFastApi422}
              className="rounded-md border border-rule-strong px-3 py-2 text-[13px] text-ink-2 hover:bg-panel-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Inject 422
            </button>
          </div>
        </form>
      </Panel>

      {submitted && (
        <Panel className="space-y-2">
          <Eyebrow color="accent">Submitted</Eyebrow>
          <pre className="overflow-x-auto font-mono text-[13px] text-ink-2">
            {submitted}
          </pre>
        </Panel>
      )}
    </main>
  );
}
