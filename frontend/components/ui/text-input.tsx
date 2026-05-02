"use client";

import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TextInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix" | "onChange"> {
  prefix?: ReactNode;
  suffix?: ReactNode;
  onChange?: (value: string) => void;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  function TextInput(
    { prefix, suffix, value, onChange, placeholder, className, type = "text", ...rest },
    ref,
  ) {
    return (
      <div
        className={cn(
          "flex items-stretch overflow-hidden rounded-md border border-rule-strong bg-bg font-sans focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-bg",
          className,
        )}
      >
        {prefix && (
          <div className="flex items-center border-r border-rule bg-panel-2 px-3 py-3 font-mono text-[14px] text-ink-dim">
            {prefix}
          </div>
        )}
        <input
          ref={ref}
          type={type}
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent px-[14px] py-3 text-[14px] text-ink outline-none placeholder:text-ink-faint"
          {...rest}
        />
        {suffix && (
          <div className="flex items-center border-l border-rule bg-panel-2 px-3 py-3 font-mono text-[13px] text-ink-dim">
            {suffix}
          </div>
        )}
      </div>
    );
  },
);
