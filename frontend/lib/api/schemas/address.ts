import { z } from "zod";

// Reference shape for the wizard "Address" step + a placeholder until
// the OpenAPI generator (chart-solar-ajgz) starts emitting these from
// the backend Pydantic model.
//
// The validation rules here MUST mirror backend/api/schemas/address.py
// (when it lands). Diff before merging — the whole point of sharing
// the schema is that client and server agree on the same shape.

export const AddressInput = z.object({
  street: z.string().min(1, "Required").max(120, "Too long"),
  city: z.string().min(1, "Required").max(80, "Too long"),
  state: z
    .string()
    .length(2, "Two-letter state code")
    .regex(/^[A-Z]{2}$/, "Use uppercase, e.g. CA"),
  zip: z
    .string()
    .regex(/^\d{5}(-\d{4})?$/, "5-digit US ZIP, optionally ZIP+4"),
});

export type AddressInput = z.infer<typeof AddressInput>;
