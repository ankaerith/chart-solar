import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Panel({
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-lg border border-rule bg-panel p-6",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
