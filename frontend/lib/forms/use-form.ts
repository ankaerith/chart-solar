"use client";

// Re-export TanStack Form's useForm so call sites have a single import
// surface; future helpers (form options factory, devtools wrapper, …)
// land here without churning every consumer.
//
// Why a re-export rather than a direct import: keeps the option to swap
// the underlying form library or layer Zod-default-value sugar without
// touching every form. The wrapper also pins the boundary that says
// "all forms must come through @/lib/forms".

export { useForm } from "@tanstack/react-form";
