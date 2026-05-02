# Shared form / API schemas

Zod schemas that the frontend uses for form validation and that mirror the backend Pydantic models 1-to-1, so client and server validate the same shape.

Until the OpenAPI → typed-client generator lands (see `bd show chart-solar-ajgz`), schemas in this directory are hand-written. Keep field names + types in lockstep with `backend/api/schemas/` — diff before merging.

## Naming

One file per logical resource. Match the backend module name where reasonable: `address.ts` ↔ `backend/api/schemas/address.py`.

## Pattern

```ts
import { z } from "zod";

export const AddressInput = z.object({
  street: z.string().min(1, "Required"),
  zip: z.string().regex(/^\d{5}(-\d{4})?$/, "5-digit US ZIP"),
});

export type AddressInput = z.infer<typeof AddressInput>;
```
