"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Modal } from "@/components/ui";

// Wraps modal-route bodies so each `@modal/(.)<route>/page.tsx` stays
// terse — opens the shared Modal, routes back on close so the URL
// pops to its previous segment and the parallel slot returns to
// `default.tsx`. Browser back gets the same effect for free.

export function RouteModal({
  kicker,
  title,
  subtitle,
  maxWidth,
  children,
}: {
  kicker?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  maxWidth?: number;
  children: ReactNode;
}) {
  const router = useRouter();
  return (
    <Modal
      open
      onClose={() => router.back()}
      kicker={kicker}
      title={title}
      subtitle={subtitle}
      maxWidth={maxWidth}
    >
      <div className="px-7 pt-6 pb-7">{children}</div>
    </Modal>
  );
}
