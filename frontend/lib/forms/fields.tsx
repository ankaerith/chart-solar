"use client";

import type { ReactNode } from "react";
import type { AnyFieldApi } from "@tanstack/react-form";
import { Btn, Field, SegBtn, TextInput } from "@/components/ui";
import type { SegOption } from "@/components/ui";
import { cn } from "@/lib/utils";

// Pre-bound wrappers around the Solstice·Ink primitives that take a
// TanStack `field` API and surface validation errors uniformly. Call
// sites stay small and the editorial styling stays in `components/ui/`.
//
// Pattern:
//   <form.Field name="email" validators={{ onChange: schema.shape.email }}>
//     {(field) => <FormTextInput field={field} label="Email" />}
//   </form.Field>

type FormErrorEntry = string | { message?: string } | null | undefined;

function fieldErrors(field: AnyFieldApi): string[] {
  const meta = field.state.meta as {
    isTouched?: boolean;
    isBlurred?: boolean;
    errors?: ReadonlyArray<FormErrorEntry>;
  };
  if (!meta.isTouched && !meta.isBlurred) return [];
  return (meta.errors ?? [])
    .filter((e): e is NonNullable<FormErrorEntry> => e != null)
    .map((e) => (typeof e === "string" ? e : (e.message ?? String(e))));
}

export function FormTextInput({
  field,
  label,
  hint,
  footnote,
  prefix,
  suffix,
  placeholder,
  inputMode,
  type,
}: {
  field: AnyFieldApi;
  label: string;
  hint?: ReactNode;
  footnote?: ReactNode;
  prefix?: ReactNode;
  suffix?: ReactNode;
  placeholder?: string;
  inputMode?: "text" | "numeric" | "email" | "tel" | "search" | "url";
  type?: string;
}) {
  const errors = fieldErrors(field);
  return (
    <Field
      label={label}
      hint={hint}
      footnote={
        errors.length > 0 ? (
          <span className="text-bad">{errors.join(" · ")}</span>
        ) : (
          footnote
        )
      }
    >
      <TextInput
        value={String(field.state.value ?? "")}
        onChange={(v) => field.handleChange(v)}
        onBlur={() => field.handleBlur()}
        placeholder={placeholder}
        prefix={prefix}
        suffix={suffix}
        inputMode={inputMode}
        type={type}
        aria-invalid={errors.length > 0}
        className={cn(errors.length > 0 && "border-bad")}
      />
    </Field>
  );
}

export function FormSegBtn<T extends string>({
  field,
  label,
  options,
  columns,
  hint,
}: {
  field: AnyFieldApi;
  label: string;
  options: ReadonlyArray<SegOption<T>>;
  columns?: number;
  hint?: ReactNode;
}) {
  const errors = fieldErrors(field);
  return (
    <Field
      label={label}
      hint={hint}
      footnote={
        errors.length > 0 ? (
          <span className="text-bad">{errors.join(" · ")}</span>
        ) : undefined
      }
    >
      <SegBtn
        value={field.state.value as T}
        onChange={(v) => {
          field.handleChange(v);
          field.handleBlur();
        }}
        options={options}
        columns={columns}
      />
    </Field>
  );
}

// Generic over the form so call sites keep their `useForm()` return
// type. The wrapper only consumes `Subscribe`; we don't try to retype
// TanStack's deep generics here. Any form instance with a Subscribe
// slot fits.
type WithSubscribe = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  Subscribe: (props: any) => any;
};

export function FormSubmit<TForm extends WithSubscribe>({
  form,
  children,
}: {
  form: TForm;
  children: ReactNode;
}) {
  return (
    <form.Subscribe
      selector={(s: { canSubmit: boolean; isSubmitting: boolean }) => ({
        canSubmit: s.canSubmit,
        isSubmitting: s.isSubmitting,
      })}
    >
      {({
        canSubmit,
        isSubmitting,
      }: {
        canSubmit: boolean;
        isSubmitting: boolean;
      }) => (
        <Btn type="submit" disabled={!canSubmit || isSubmitting}>
          {isSubmitting ? "Submitting…" : children}
        </Btn>
      )}
    </form.Subscribe>
  );
}
