"use client";

// Pydantic-style server error envelope. The backend OpenAPI contract
// returns 422 with a list of `{loc: [...], msg: ..., type: ...}` entries
// for FastAPI validation, plus a flatter `{field: [msg, ...]}` shape
// for our own custom validators (chart-solar-bcy.1 onwards).
//
// `applyServerErrors` flattens both into per-field error arrays and
// pushes them onto the form so they render through `FormTextInput` /
// `FormSegBtn` exactly like client-side Zod errors.
//
// We mutate `meta.errorMap.onServer` (the documented slot for
// async/server validation) — TanStack flattens that into
// `meta.errors[]` for us.

export type FastApiError = {
  detail?: ReadonlyArray<{
    loc: ReadonlyArray<string | number>;
    msg: string;
    type?: string;
  }>;
};

export type FlatErrorMap = Record<string, ReadonlyArray<string>>;

// Loose form shape — the wrapper just needs `setFieldMeta` to exist;
// we don't retype TanStack's deep generics here. Call sites keep the
// full type from `useForm()`.
type FormWithSetFieldMeta = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  setFieldMeta: (field: any, updater: (prev: any) => any) => void;
};

export function flattenServerErrors(
  payload: FastApiError | FlatErrorMap | unknown,
): FlatErrorMap {
  // FastAPI 422
  if (payload && typeof payload === "object" && "detail" in payload) {
    const out: Record<string, string[]> = {};
    for (const e of (payload as FastApiError).detail ?? []) {
      // First loc segment is usually 'body' / 'query' — drop it.
      const path = e.loc.slice(1).map(String).join(".");
      if (!path) continue;
      (out[path] ??= []).push(e.msg);
    }
    return out;
  }
  // Flat envelope
  if (payload && typeof payload === "object") {
    return payload as FlatErrorMap;
  }
  return {};
}

export function applyServerErrors(
  form: FormWithSetFieldMeta,
  errors: FlatErrorMap,
): void {
  for (const [name, msgs] of Object.entries(errors)) {
    form.setFieldMeta(name, (prev) => ({
      ...prev,
      errorMap: { ...prev.errorMap, onServer: msgs.join(" · ") },
      isTouched: true,
      isBlurred: true,
    }));
  }
}
