"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { MonoLabel } from "./mono-label";

export function Modal({
  open,
  onClose,
  kicker,
  title,
  subtitle,
  children,
  maxWidth = 920,
  className,
}: {
  open: boolean;
  onClose?: () => void;
  kicker?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  children?: ReactNode;
  maxWidth?: number;
  className?: string;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    lastFocusedRef.current = document.activeElement;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose?.();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      (lastFocusedRef.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-[1000] flex items-center justify-center overflow-y-auto bg-[rgba(15,20,33,0.55)] px-[4vw] py-[4vh]"
      style={{ animation: "sd-fade-in 0.18s ease-out" }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sd-modal-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "relative max-h-[92vh] w-full overflow-y-auto rounded-lg border border-rule-strong bg-bg shadow-[0_24px_60px_-20px_rgba(15,20,33,0.5)] focus:outline-none",
          className,
        )}
        style={{ maxWidth, animation: "sd-pop-in 0.22s ease-out" }}
      >
        <div className="sticky top-0 z-[2] flex items-start justify-between gap-4 border-b border-rule bg-bg px-7 pt-5 pb-4">
          <div>
            {kicker && <MonoLabel>{kicker}</MonoLabel>}
            <h3
              id="sd-modal-title"
              className={cn(
                "m-0 font-display text-[24px] leading-[1.15] tracking-[var(--display-tracking)] font-[var(--display-weight)]",
                kicker && "mt-[6px]",
              )}
            >
              {title}
            </h3>
            {subtitle && (
              <p className="mt-[6px] max-w-[640px] text-[13.5px] leading-[1.5] text-ink-2">
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-full border border-rule-strong bg-panel text-ink-2 hover:bg-panel-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              aria-hidden="true"
            >
              <path d="M2 2l8 8M10 2l-8 8" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
