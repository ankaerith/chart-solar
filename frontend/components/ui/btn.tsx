import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Kind = "primary" | "ghost" | "accent";

const KIND_CLASSES: Record<Kind, string> = {
  primary:
    "bg-ink text-bg font-semibold hover:opacity-90 active:translate-y-[1px]",
  ghost:
    "bg-transparent text-ink border border-rule-strong font-medium hover:bg-panel-2",
  accent:
    "bg-accent text-accent-ink font-semibold hover:opacity-90 active:translate-y-[1px]",
};

export interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  kind?: Kind;
}

export const Btn = forwardRef<HTMLButtonElement, BtnProps>(function Btn(
  { kind = "primary", className, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 rounded-md px-[22px] py-[13px] text-[14px] leading-none font-sans transition-[background,opacity,transform] duration-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
        KIND_CLASSES[kind],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
